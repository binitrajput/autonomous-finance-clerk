"""Comprehensive test suite for the Autonomous AI Task Worker.
Covers:
  1. Happy Path: End-to-end autonomous invoice processing with human approval
  2. Auto-Approval: Invoices under $1,000 proceed without pausing
  3. Duplicate Detection: Prevents double-processing of existing invoice
  4. Error Handling: Rejects malformed invoice without polluting database
  5. Human Rejection: Safe halt when user denies approval
  6. Fuzzy Matching / Self-Healing: Resolves vendor name variation autonomously
  7. Verification: Outcome verifier confirms physical database state
  8. Generalization: Analytical SQL queries handled seamlessly
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
import pytest

import config
import agent.core as agent_core
from agent.core import AutonomousAgent
from agent.memory import WorkingMemory
from agent.verifier import OutcomeVerifier
from tools.approval import set_approval_callback
from tools.database import get_db_connection
from tools.invoice_reader import read_invoice
from tools.ledger import insert_ledger_entry


def test_1_happy_path_with_approval():
    """Scenario 1: Process Acme invoice ($4,250 > $1,000) with approval callback."""
    # Register approval callback that approves the transaction
    set_approval_callback(lambda q, ctx: True)

    agent = AutonomousAgent()
    result = agent.run("Process the latest invoice from Acme Corp and enter it into our system.", verbose=False)

    assert result["success"] is True
    assert result["verification"]["passed"] is True
    assert result["facts"]["invoice_number"] == "INV-2024-0042"
    assert result["facts"]["total_amount"] == 4250.00

    # Verify physical DB state
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ledger WHERE invoice_number = 'INV-2024-0042'")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["amount"] == 4250.00
    assert row["status"] == "pending"


def test_2_auto_approval_under_threshold():
    """Scenario 2: Process Globex invoice ($802.50 <= $1,000) - auto-approves."""
    approval_called = False

    def mock_approval(q, ctx):
        nonlocal approval_called
        approval_called = True
        return True

    set_approval_callback(mock_approval)

    agent = AutonomousAgent()
    result = agent.run("Process the latest invoice from Globex International.", verbose=False)

    assert result["success"] is True
    assert result["facts"]["total_amount"] == 802.50
    # Approval callback should NOT be triggered because amount <= 1000
    assert approval_called is False

    # Verify ledger row
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ledger WHERE invoice_number = 'INV-2024-0078'")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["amount"] == 802.50


def test_3_duplicate_detection_blocked():
    """Scenario 3: Attempt to process invoice INV-2024-0035 (already in ledger)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM ledger")
    initial_count = cursor.fetchone()["cnt"]
    conn.close()

    agent = AutonomousAgent()
    result = agent.run("Process duplicate_invoice.json", verbose=False)

    assert result["status"] == "DUPLICATE_BLOCKED"
    assert result["verification"]["passed"] is False
    assert result["verification"]["safe_halt"] is True

    # Confirm ledger count has NOT changed
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM ledger")
    after_count = cursor.fetchone()["cnt"]
    conn.close()

    assert initial_count == after_count


def test_4_malformed_invoice_handled_safely():
    """Scenario 4: Attempt to process malformed invoice missing required amount."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM ledger")
    initial_count = cursor.fetchone()["cnt"]
    conn.close()

    agent = AutonomousAgent()
    result = agent.run("Process the invoice from malformed_invoice.json", verbose=False)

    assert result["status"] == "MALFORMED_BLOCKED"
    assert result["verification"]["passed"] is False
    assert result["verification"]["safe_halt"] is True

    # Database must remain untouched
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM ledger")
    after_count = cursor.fetchone()["cnt"]
    conn.close()

    assert initial_count == after_count


def test_5_user_denies_approval():
    """Scenario 5: User rejects payment approval - safe halt without DB write."""
    # Register approval callback that rejects the transaction
    set_approval_callback(lambda q, ctx: False)

    agent = AutonomousAgent()
    result = agent.run("Process the latest invoice from Acme Corp", verbose=False)

    assert result["status"] == "APPROVAL_REJECTED"

    # Verify no entry for INV-2024-0042 in database
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ledger WHERE invoice_number = 'INV-2024-0042'")
    row = cursor.fetchone()
    conn.close()

    assert row is None


def test_6_fuzzy_vendor_matching():
    """Scenario 6: Invoice says 'Acme Corporation', database has 'Acme Corp'."""
    set_approval_callback(lambda q, ctx: True)

    agent = AutonomousAgent()
    result = agent.run("Process fuzzy_vendor_invoice.json", verbose=False)

    assert result["success"] is True
    assert result["facts"]["invoice_number"] == "INV-2024-0099"

    # Confirms record linked correctly to Acme Corp (vendor_id = 1)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ledger WHERE invoice_number = 'INV-2024-0099'")
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["vendor_id"] == 1


def test_7_outcome_verification_catches_discrepancy():
    """Scenario 7: Outcome verifier catches a nonexistent ledger entry ID."""
    verification = OutcomeVerifier.audit_ledger_entry(ledger_entry_id=999999)
    assert verification["verified"] is False
    assert "not found" in verification["error"].lower()


def test_8_generalization_analytical_query():
    """Scenario 8: Agent handles analytical question instead of invoice workflow."""
    agent = AutonomousAgent()
    result = agent.run("How many pending invoices do we have in our ledger?", verbose=False)

    assert result["success"] is True
    assert "pending invoices" in result["final_response"].lower()


def test_9_invoice_listing_is_a_verified_read_only_task():
    """Scenario 9: Listing sample invoices completes without ledger writes."""
    agent = AutonomousAgent()
    result = agent.run("List the available invoices", verbose=False)

    assert result["success"] is True
    assert result["verification"]["invoice_search_verified"] is True
    assert result["verification"]["invoice_count"] > 0
    assert "INV-2024-0042" in result["final_response"]
    assert result["reasoning"]["source"] == "deterministic fallback"
    assert result["reasoning"]["llm_decisions"] == 0


def test_10_processing_task_is_not_verified_by_invoice_search_alone():
    """A discovery step cannot prove a requested ledger write succeeded."""
    memory = WorkingMemory(goal="Process the latest Globex invoice and enter it into the system")
    memory.add_step("search_invoices", {}, {"success": True, "count": 1, "files": [{}]})
    memory.add_step("read_invoice", {}, {"success": True, "invoice_number": "INV-2024-0078"})
    memory.add_step("query_database", {}, {"success": False, "error": "no such column: vendor_id"}, status="error")

    verification = OutcomeVerifier.verify_execution(memory)

    assert verification["passed"] is False
    assert "no verified ledger entry" in verification["reason"].lower()


def test_11_rate_limit_retry_honors_provider_wait_time(monkeypatch):
    """A Groq rate limit response is retried after its suggested delay."""
    class RateLimitError(Exception):
        pass

    attempts = []
    sleeps = []

    def completion(**_kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise RateLimitError("Rate limit reached. Please try again in 7.5975s.")
        message = SimpleNamespace(content="Done", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    monkeypatch.setattr(agent_core.litellm, "completion", completion)
    monkeypatch.setattr(agent_core.time, "sleep", sleeps.append)
    monkeypatch.setattr(config, "MAX_RETRIES", 2)

    agent = AutonomousAgent(model_name="groq/openai/gpt-oss-120b")
    decision = agent._llm_step([{"role": "user", "content": "hello"}], task="hello", memory=WorkingMemory())

    assert len(attempts) == 2
    assert sleeps == [8]
    assert decision["content"] == "Done"


def test_12_run_reports_when_llm_made_the_decisions(monkeypatch):
    """The run result identifies actual LLM decisions separately from fallback."""
    agent = AutonomousAgent()
    monkeypatch.setattr(agent, "_check_api_credentials", lambda: True)
    decisions = [
        {"tool_calls": [{"name": "search_invoices", "arguments": {"query": ""}}]},
        {"content": "Invoice list complete.", "tool_calls": []}
    ]
    monkeypatch.setattr(agent, "_llm_step", lambda *_args, **_kwargs: decisions.pop(0))

    result = agent.run("List the available invoices", verbose=False)

    assert result["success"] is True
    assert result["reasoning"] == {
        "source": "LLM",
        "model": agent.model_name,
        "llm_decisions": 2,
        "fallback_decisions": 0
    }


def test_13_invoice_reader_blocks_paths_outside_invoice_directory():
    """The invoice tool cannot read a file by traversing outside its data folder."""
    result = read_invoice("../.env")

    assert result["success"] is False
    assert result["blocked"] is True
    assert "GROQ_API_KEY" not in str(result)


def test_14_simultaneous_duplicate_inserts_create_one_ledger_row():
    """The database uniqueness guard makes duplicate writes race-safe."""
    invoice_number = "INV-RACE-0001"
    start_together = Barrier(2)

    def attempt_insert(number):
        start_together.wait()
        return insert_ledger_entry(
            invoice_number=number,
            vendor_id=2,
            amount=100.00,
            currency="USD"
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt_insert, [invoice_number, invoice_number.lower()]))

    assert sum(result["success"] for result in results) == 1
    assert sum(result.get("is_duplicate", False) for result in results) == 1

    conn = get_db_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM ledger WHERE UPPER(invoice_number) = UPPER(?)",
        (invoice_number,)
    ).fetchone()[0]
    conn.close()
    assert count == 1
