# 🤖 Autonomous AI Task Worker — Finance & Operations Clerk

[![Tests](https://img.shields.io/badge/Tests-8%2F8%20Passing-brightgreen.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-ReAct%20Loop-blue.svg)]()
[![Model-Agnostic](https://img.shields.io/badge/LLM-Gemini%20%7C%20OpenAI%20%7C%20Claude-purple.svg)]()
[![Verification](https://img.shields.io/badge/Audit-Independent%20DB%20Verification-emerald.svg)]()

> An autonomous AI worker prototype that accepts natural language enterprise tasks, decomposes them into tool-driven action plans across simulated file systems and an internal ERP database, recovers from anomalous states, enforces human-in-the-loop safety gates, and independently verifies outcome completion.

---

## 📌 Problem Statement & Solution

**The Enterprise Problem:**  
Accounts payable and finance teams spend countless hours manually reading incoming invoices, checking supplier records, cross-referencing purchase orders, logging entries into accounting software, and auditing duplicate submissions.

**The Solution:**  
This project implements an **Autonomous AI Task Worker** capable of taking end-goal natural language directives such as:
> *"Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and tell me once it is done."*

The system plans and executes the entire workflow without hand-held micro-prompts, verifies the database state, and produces verifiable audit evidence.

---

## 📐 Architecture & State Machine

The agent operates on an augmented **ReAct (Reason + Act + Observe)** execution loop with dedicated **Safety**, **Self-Healing**, and **Outcome Verification** checkpoints:

![Agent State Machine](agent_state_machine.png)

```
[User Task] ➡️ [1. Reason & Plan] ➡️ [2. Select Tool]
                       ⬆️                      ⬇️
            [6. Working Memory]     [3. Approval Gate?] (> $1,000 threshold)
                       ⬆️                /            \
            [5. Observe Result]    (Approved)      (Denied) ➡️ [Safe Halt]
                       ⬆️             ⬇️
             [Self-Healing] ⬅️ [4. Execute Tool (Files/DB)]
                       |
               [All Steps Done]
                       ⬇️
            [7. Independent Verification (DB Audit)]
                       ⬇️
            [8. Task Complete & Evidence Report]
```

---

## 🌟 Rubric & Key Capabilities

| Evaluation Criterion | Implementation in System |
|:---|:---|
| **Autonomy** | Decomposes high-level prompts into 5–8 atomic actions without step-by-step instructions. |
| **Execution** | Performs real file I/O, queries and inserts into a real SQLite database, rather than mocking outputs. |
| **Reliability & Self-Healing** | Recovers from fuzzy vendor names (e.g. *"Acme Corporation"* vs *"Acme Corp"*), catches malformed payloads, and aborts duplicates. |
| **Verification** | Executes an independent SQL assertion (`verify_ledger_entry`) confirming the physical database record exists and amounts match before completing. |
| **Safety & HITL** | Hard-coded approval gate: any transaction exceeding **$1,000.00** pauses execution to require human sign-off. |
| **Generalization** | The core ReAct loop seamlessly answers analytical database questions (e.g. *"How many pending invoices do we have?"*) using the same tools. |
| **Engineering Quality** | Clean separation of concerns (`agent/`, `tools/`, `company_system/`, `tests/`), typed interfaces, and zero hallucination errors. |

---

## 📁 Repository Structure

```
autonomous-finance-clerk/
├── agent/
│   ├── core.py              # Central ReAct agent loop (LiteLLM + deterministic engine)
│   ├── memory.py            # Working memory tracking discovered facts & step history
│   ├── planner.py           # Planning & prompt decomposition
│   ├── verifier.py          # Independent outcome audit verifier
│   └── prompts.py           # System prompts enforcing safety and verification
├── tools/
│   ├── registry.py          # Central registry with JSON function schemas
│   ├── invoice_search.py    # Discovers invoices matching vendor/keywords
│   ├── invoice_reader.py    # Parses JSON/PDF invoices and validates schemas
│   ├── database.py          # Safe read-only SQL queries on company database
│   ├── duplicate_checker.py # Prevents double-processing against ledger
│   ├── ledger.py            # Writes transactions into ledger with threshold guard
│   ├── approval.py          # Human-in-the-loop approval module
│   ├── verification.py      # Audits database state persistence
│   └── report.py            # Formats Markdown audit reports
├── company_system/
│   ├── schema.sql           # SQLite schema (vendors, purchase_orders, ledger)
│   ├── seed_data.py         # Realistic seed data
│   ├── setup_db.py          # DB initialization and test reset utility
│   └── company.db           # SQLite database file
├── invoices/                # Sample test invoices
│   ├── acme_corp_INV-2024-0042.json  # Valid high-value ($4,250 - requires approval)
│   ├── globex_INV-2024-0078.json     # Valid low-value ($802.50 - auto-approves)
│   ├── initech_INV-2024-0091.json    # Valid software license renewal
│   ├── duplicate_invoice.json        # Duplicate invoice test case
│   ├── malformed_invoice.json        # Malformed missing amounts test case
│   └── fuzzy_vendor_invoice.json     # Fuzzy vendor variation test case
├── tests/
│   ├── conftest.py          # Automated DB reset before every test
│   └── test_all_scenarios.py# 8 comprehensive automated test suites
├── app.py                   # Streamlit web dashboard
├── main.py                  # Rich CLI application
├── config.py                # Environment configuration
├── requirements.txt         # Project dependencies
└── README.md                # System documentation
```

---

## 🚀 Quick Start (2 Minutes)

### 1. Clone & Install
```bash
git clone https://github.com/binitrajput/autonomous-finance-clerk.git
cd autonomous-finance-clerk

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
```bash
cp .env.example .env
# Add your GEMINI_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY
# If no key is provided, the agent runs in offline autonomous mode!
```

---

## 💻 Running the Applications

### Option A: Interactive CLI
```bash
python main.py
```
Or pass a prompt directly:
```bash
python main.py --task "Process the latest invoice from Acme Corp and enter it into our system."
```

### Option B: Streamlit Web Dashboard
```bash
streamlit run app.py
```
Features:
- Real-time step-by-step agent thought process
- Interactive Human-in-the-Loop approval modal
- Live ERP Database explorer (`ledger`, `vendors`, `purchase_orders`)
- 1-Click test scenario launcher

---

## 🧪 Automated Test Suite (8/8 Passing)

Run the test suite:
```bash
pytest tests/ -v
```

### Test Coverage Breakdown:
1. `test_1_happy_path_with_approval`: Full autonomous cycle with human approval on $4,250 invoice.
2. `test_2_auto_approval_under_threshold`: Auto-approves $802.50 invoice without interrupting user.
3. `test_3_duplicate_detection_blocked`: Successfully catches and halts duplicate invoice submission.
4. `test_4_malformed_invoice_handled_safely`: Rejects corrupted/malformed files without polluting the database.
5. `test_5_user_denies_approval`: Halts execution safely when user denies approval.
6. `test_6_fuzzy_vendor_matching`: Fuzzy matches *"Acme Corporation"* to registered *"Acme Corp"*.
7. `test_7_outcome_verification_catches_discrepancy`: Verifier catches and reports nonexistent or corrupted records.
8. `test_8_generalization_analytical_query`: Solves analytical SQL query without altering code.

---

## 🌐 Live Cloud Deployment

Deploy in 1-click on [Streamlit Community Cloud](https://share.streamlit.io):
1. Connect your GitHub repository: `binitrajput/autonomous-finance-clerk`
2. Set Main file path: `app.py`
3. Click **Deploy**!
