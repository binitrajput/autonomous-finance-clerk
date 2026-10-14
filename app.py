"""Streamlit Web Application for the Autonomous AI Finance Clerk."""

import streamlit as st
import pandas as pd
import sqlite3
import os
import json

# Streamlit Community Cloud stores credentials in st.secrets. Expose supported
# values to the existing environment-based configuration before importing it.
try:
    for secret_key in ("MODEL_NAME", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        if not os.getenv(secret_key) and st.secrets.get(secret_key):
            os.environ[secret_key] = str(st.secrets[secret_key])
except Exception:
    # Local runs may not have a Streamlit secrets file configured.
    pass

import config
from agent.core import AutonomousAgent
from tools.approval import set_approval_callback
from tools.duplicate_checker import check_duplicate
from tools.invoice_reader import read_invoice
from tools.invoice_search import search_invoices
from company_system.setup_db import initialize_database, reset_database

# Page Configuration
st.set_page_config(
    page_title="Autonomous AI Task Worker — Finance Clerk",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database on first run
initialize_database()

# Session State
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "auto_approve" not in st.session_state:
    st.session_state.auto_approve = False
if "pending_invoice_approval" not in st.session_state:
    st.session_state.pending_invoice_approval = None
if "pending_agent_task" not in st.session_state:
    st.session_state.pending_agent_task = None
if "approved_invoice" not in st.session_state:
    st.session_state.approved_invoice = None

# Helper to load DB tables
def load_db_table(table_name: str) -> pd.DataFrame:
    conn = sqlite3.connect(config.DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    conn.close()
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.title("🤖 Autonomous Worker")
    st.markdown("**Role:** Autonomous Finance & Ops Clerk")
    st.markdown("---")

    st.subheader("⚙️ Agent Controls")
    model_options = list(dict.fromkeys([
        config.MODEL_NAME,
        "gemini/gemini-3.8-flash",
        "openai/gpt-4o-mini",
        "anthropic/claude-3-5-sonnet",
        "Deterministic Engine"
    ]))
    model_choice = st.selectbox(
        "Active Model Brain",
        model_options,
        index=0
    )
    st.caption("Supports LiteLLM & pure Python autonomous fallback.")

    threshold_val = st.number_input("Approval Threshold ($)", min_value=100.0, max_value=10000.0, value=config.APPROVAL_THRESHOLD, step=100.0)
    config.APPROVAL_THRESHOLD = threshold_val

    st.markdown("---")
    st.subheader("🛡️ Human-in-the-Loop Gate")
    st.caption("High-value invoices pause for approval of the specific invoice before processing.")

    st.markdown("---")
    if st.button("🔄 Reset Company Database", use_container_width=True):
        reset_database()
        st.success("Database reset to clean seed state!")
        st.rerun()

    st.markdown("---")
    st.caption("Built for Autonomous AI Task Worker Submission")

# --- MAIN CONTENT ---
st.title("🏦 Autonomous AI Task Worker")
st.markdown("### Accounts Payable & Finance Operations Agent")
st.markdown(
    """
    An autonomous agent that plans, uses tools across local files and an internal ERP database, 
    detects anomalies, handles errors, verifies database state changes, and produces audit evidence.
    """
)

# Tabs: Agent Chat / System Database
tab_chat, tab_db, tab_invoices, tab_arch = st.tabs(["💬 Agent Interface", "🗄️ ERP Database Explorer", "📂 Invoice Directory", "📐 Architecture & State Machine"])

with tab_chat:
    # 1-Click Prompt Templates
    st.markdown("##### ⚡ Quick Scenarios:")
    col1, col2, col3, col4 = st.columns(4)
    quick_prompt = None

    if col1.button("📋 Happy Path (Acme $4.2K)", use_container_width=True):
        quick_prompt = "Process the latest invoice from Acme Corp and enter it into our system."
    if col2.button("⚡ Auto-Approve (Globex $802)", use_container_width=True):
        quick_prompt = "Process the latest invoice from Globex International."
    if col3.button("🛑 Test Duplicate Blocker", use_container_width=True):
        quick_prompt = "Process duplicate_invoice.json"
    if col4.button("📊 Analytical DB Query", use_container_width=True):
        quick_prompt = "How many pending invoices do we have in our ledger?"

    # Input Box
    user_task = st.chat_input("Enter natural language task for the AI worker...")
    prompt_to_run = user_task or quick_prompt

    def request_specific_approval(question, context):
        """Accept only the invoice and amount the user reviewed in the form."""
        approved_invoice = st.session_state.get("approved_invoice")
        invoice_number = context.get("invoice_number", context.get("invoice"))
        try:
            matches = (
                approved_invoice is not None
                and str(invoice_number).strip().upper() == approved_invoice["invoice_number"].strip().upper()
                and round(float(context.get("amount")), 2) == round(float(approved_invoice["amount"]), 2)
            )
        except (TypeError, ValueError, AttributeError):
            matches = False
        if matches:
            st.session_state.approved_invoice = None
        return matches

    task_to_run = st.session_state.pending_agent_task
    if task_to_run:
        st.session_state.pending_agent_task = None
    elif prompt_to_run:
        st.session_state.chat_history.append({"role": "user", "content": prompt_to_run})
        # Preview the same newest matching invoice so approval is tied to visible details.
        search_result = search_invoices(query=prompt_to_run)
        files = search_result.get("files", []) if search_result.get("success") else []
        preview = read_invoice(files[0]["file_path"]) if files else {}
        task_lower = prompt_to_run.lower()
        intends_write = any(word in task_lower for word in ("process", "enter", "record", "add", "submit"))
        if (intends_write and preview.get("success")
                and preview.get("total_amount", 0) > config.APPROVAL_THRESHOLD):
            duplicate = check_duplicate(preview["invoice_number"])
            if not duplicate.get("is_duplicate"):
                st.session_state.pending_invoice_approval = {
                    "task": prompt_to_run,
                    "invoice": preview,
                }
            else:
                task_to_run = prompt_to_run
        else:
            task_to_run = prompt_to_run

    pending_approval = st.session_state.pending_invoice_approval
    if pending_approval:
        invoice = pending_approval["invoice"]
        st.warning("This invoice exceeds the approval threshold. Review the details before the agent starts processing it.")
        st.write(
            f"**Vendor:** {invoice.get('vendor_name')}  \n"
            f"**Invoice:** {invoice.get('invoice_number')}  \n"
            f"**Amount:** {invoice.get('currency', 'USD')} {invoice.get('total_amount'):,.2f}  \n"
            f"**Due date:** {invoice.get('due_date') or 'Not provided'}  \n"
            f"**Purchase order:** {invoice.get('po_number') or 'Not provided'}"
        )
        with st.form("invoice_approval_form"):
            decision = st.radio("Do you approve processing this invoice?", ["Reject", "Approve"], horizontal=True)
            submitted = st.form_submit_button("Confirm decision")
        if submitted:
            st.session_state.pending_invoice_approval = None
            if decision == "Approve":
                st.session_state.approved_invoice = {
                    "invoice_number": invoice["invoice_number"],
                    "amount": invoice["total_amount"],
                }
                st.session_state.pending_agent_task = pending_approval["task"]
            else:
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": f"Safely stopped: approval was declined for {invoice['invoice_number']}; no ledger entry was created."
                })
                st.info(f"Approval declined for **{invoice['invoice_number']}**. The task was not processed.")
            if decision == "Approve":
                st.rerun()

    if task_to_run:
        with st.chat_message("user"):
            st.write(task_to_run)

        with st.chat_message("assistant"):
            status_container = st.status(f"🤖 Autonomous Worker executing: '{task_to_run}'...", expanded=True)
            status_container.write(
                f"Waiting for the selected model when reasoning is needed "
                f"(request timeout: {config.LLM_TIMEOUT_SECONDS:g}s). If it times out, the agent will switch to its deterministic fallback."
            )
            set_approval_callback(request_specific_approval)

            agent_model = None if model_choice == "Deterministic Engine" else model_choice
            agent = AutonomousAgent(model_name=agent_model)
            try:
                result = agent.run(task_to_run, verbose=False)
            finally:
                set_approval_callback(None)

            for step in result["steps"]:
                status_icon = "✅" if step["status"] == "success" else "⚠️"
                status_container.write(f"**Step {step['step']}:** `{step['tool']}` — {status_icon} *{step['status'].upper()}*")
                status_container.json({"arguments": step["arguments"], "result": step["result"]})

            if result["success"]:
                status_container.update(label="✅ Task completed and verified", state="complete", expanded=False)
            elif result["verification"].get("safe_halt"):
                status_container.update(label=f"🛑 Safely stopped ({result['status']})", state="complete", expanded=False)
            else:
                status_container.update(label=f"⚠️ Outcome not verified ({result['status']})", state="error", expanded=False)

            if result["success"]:
                st.success("**Outcome verified:** the requested database result was confirmed.")
            elif result["verification"].get("safe_halt"):
                st.info(f"**Safely stopped:** {result['verification'].get('reason')}")
            else:
                st.warning(f"**Not verified:** {result['verification'].get('reason')}")

            st.markdown("### 📄 Completion & Audit Report")
            st.markdown(result["report"])

with tab_db:
    st.subheader("🏢 Internal ERP Accounting Database")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### `ledger` Table (Transactions)")
        st.dataframe(load_db_table("ledger"), use_container_width=True)
    with col_b:
        st.markdown("#### `processed_invoices` (Tracking)")
        st.dataframe(load_db_table("processed_invoices"), use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        st.markdown("#### `vendors` Table")
        st.dataframe(load_db_table("vendors"), use_container_width=True)
    with col_d:
        st.markdown("#### `purchase_orders` Table")
        st.dataframe(load_db_table("purchase_orders"), use_container_width=True)

with tab_invoices:
    st.subheader("📂 Invoice Directory (`invoices/`)")
    for f in sorted(os.listdir(config.INVOICE_DIR)):
        if f.endswith(".json"):
            with st.expander(f"📄 {f}"):
                with open(os.path.join(config.INVOICE_DIR, f)) as fp:
                    st.json(json.load(fp))

with tab_arch:
    st.subheader("📐 Agent State Machine & ReAct Architecture")
    svg_path = os.path.join(os.path.dirname(__file__), "agent_state_machine.svg")
    if os.path.exists(svg_path):
        with open(svg_path, "r") as fp:
            st.components.v1.html(fp.read(), height=750, scrolling=True)
    else:
        st.info("State machine SVG available in project root.")
