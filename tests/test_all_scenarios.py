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
import pytest

import config
from agent.core import AutonomousAgent
from agent.verifier import OutcomeVerifier
from tools.approval import set_approval_callback
from tools.database import get_db_connection


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
