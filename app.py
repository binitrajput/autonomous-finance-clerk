"""Streamlit Web Application for the Autonomous AI Finance Clerk."""

import streamlit as st
import pandas as pd
import sqlite3
import os
import json

import config
from agent.core import AutonomousAgent
from tools.approval import set_approval_callback
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
    st.session_state.auto_approve = True

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
    model_choice = st.selectbox(
        "Active Model Brain",
        ["gemini/gemini-2.0-flash", "openai/gpt-4o-mini", "anthropic/claude-3-5-sonnet", "Deterministic Engine"],
        index=0
    )
    st.caption("Supports LiteLLM & pure Python autonomous fallback.")

    threshold_val = st.number_input("Approval Threshold ($)", min_value=100.0, max_value=10000.0, value=config.APPROVAL_THRESHOLD, step=100.0)
    config.APPROVAL_THRESHOLD = threshold_val

    st.markdown("---")
    st.subheader("🛡️ Human-in-the-Loop Gate")
    st.session_state.auto_approve = st.toggle("Simulate User Approval (Yes)", value=True, help="When off, simulates user rejecting high-value payments > $1,000.")

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

    if prompt_to_run:
        st.session_state.chat_history.append({"role": "user", "content": prompt_to_run})

        with st.chat_message("user"):
            st.write(prompt_to_run)

        with st.chat_message("assistant"):
            status_container = st.status(f"🤖 Autonomous Worker executing: '{prompt_to_run}'...", expanded=True)
            
            # Configure approval hook
            set_approval_callback(lambda q, ctx: st.session_state.auto_approve)

            # Initialize agent
            agent_model = None if model_choice == "Deterministic Engine" else model_choice
            agent = AutonomousAgent(model_name=agent_model)

            result = agent.run(prompt_to_run, verbose=False)

            # Display Step-by-Step execution trace
            for step in result["steps"]:
                status_icon = "✅" if step["status"] == "success" else "⚠️"
                status_container.write(f"**Step {step['step']}:** `{step['tool']}` — {status_icon} *{step['status'].upper()}*")
                with status_container.expander(f"Inspect Tool Payload ({step['tool']})"):
                    st.json({"arguments": step["arguments"], "result": step["result"]})

            if result["verification"].get("passed"):
                status_container.update(label="✅ Task Finished & Verified in Database!", state="complete", expanded=False)
            else:
                status_container.update(label=f"⚠️ Task Finished ({result['status']})", state="complete", expanded=False)

            # Outcome Verification Badge
            if result["verification"].get("passed"):
                st.success(f"**Outcome Verification Passed:** Record confirmed in SQLite database.")
            else:
                st.warning(f"**Outcome Verification Note:** {result['verification'].get('reason')}")

            # Final Report
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
