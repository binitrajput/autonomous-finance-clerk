"""Outcome verifier that independently audits whether the requested state change was achieved."""

from typing import Dict, Any, List, Optional
from tools.database import get_db_connection


class OutcomeVerifier:
    """Verifies that the agent's stated outcome was actually achieved in reality."""

    @staticmethod
    def audit_ledger_entry(ledger_entry_id: int, expected: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Directly query the database to confirm ledger record persistence."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ledger WHERE id = ?", (ledger_entry_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {
                "verified": False,
                "error": f"Audit failure: Record #{ledger_entry_id} not found in database."
            }

        record = dict(row)
        discrepancies = []
        expected = expected or {}
        if expected.get("invoice_number") and record["invoice_number"].strip().upper() != str(expected["invoice_number"]).strip().upper():
            discrepancies.append("invoice_number does not match the inserted value")
        if expected.get("vendor_id") is not None and record["vendor_id"] != expected["vendor_id"]:
            discrepancies.append("vendor_id does not match the inserted value")
        if expected.get("amount") is not None and abs(float(record["amount"]) - float(expected["amount"])) > 0.01:
            discrepancies.append("amount does not match the inserted value")
        if expected.get("currency") and record["currency"].upper() != str(expected["currency"]).upper():
            discrepancies.append("currency does not match the inserted value")
        if expected.get("due_date") is not None and record["due_date"] != expected["due_date"]:
            discrepancies.append("due_date does not match the inserted value")

        return {
            "verified": not discrepancies,
            "record": record,
            "discrepancies": discrepancies
        }

    @staticmethod
    def verify_execution(memory) -> Dict[str, Any]:
        """Perform end-to-end check on memory history and physical database state."""
        ledger_id = memory.facts.get("ledger_entry_id")
        
        # If the task required writing to the ledger
        if ledger_id:
            insert_step = next((s for s in memory.steps if s.tool == "insert_ledger_entry" and s.result.get("ledger_entry_id") == ledger_id), None)
            expected = insert_step.arguments if insert_step else {}
            audit = OutcomeVerifier.audit_ledger_entry(ledger_id, expected)
            if not audit["verified"]:
                return {
                    "passed": False,
                    "reason": audit.get("error", "; ".join(audit.get("discrepancies", []))),
                    "record": audit.get("record")
                }
            tool_verification = next((s.result for s in reversed(memory.steps) if s.tool == "verify_ledger_entry" and s.arguments.get("ledger_entry_id") == ledger_id), None)
            if tool_verification is not None and not tool_verification.get("verified"):
                return {"passed": False, "reason": tool_verification.get("message", "Ledger verification tool reported a mismatch.")}
            return {
                "passed": True,
                "ledger_entry_id": ledger_id,
                "db_record": audit["record"]
            }

        # A safe halt takes precedence over earlier discovery steps. A workflow
        # may search invoices successfully and then stop on a duplicate,
        # malformed invoice, or denied approval; that is not task completion.
        aborted = next((s for s in reversed(memory.steps) if (
            (s.tool == "check_duplicate" and s.result.get("is_duplicate"))
            or (s.tool == "read_invoice" and s.result.get("is_malformed"))
            or (s.tool == "request_user_approval" and not s.result.get("approved"))
        )), None)
        if aborted:
            return {
                "passed": False,
                "safe_halt": True,
                "reason": "Execution safely stopped; the requested ledger entry was not created."
            }

        # A successful read-only query is verifiable evidence of completion.
        query_step = next((s for s in reversed(memory.steps) if s.tool == "query_database"), None)
        if query_step and query_step.result.get("success"):
            return {
                "passed": True,
                "query_verified": True,
                "row_count": query_step.result.get("count", len(query_step.result.get("rows", []))),
                "reason": "Read-only database query executed successfully."
            }

        # Listing or searching invoice files is also a read-only task with
        # independently checkable tool evidence; it does not require a ledger write.
        invoice_search = next((s for s in reversed(memory.steps) if s.tool == "search_invoices"), None)
        if invoice_search and invoice_search.result.get("success"):
            return {
                "passed": True,
                "invoice_search_verified": True,
                "invoice_count": invoice_search.result.get("count", len(invoice_search.result.get("files", []))),
                "reason": "Invoice search completed successfully."
            }

        return {
            "passed": False,
            "reason": "No verifiable outcome was recorded."
        }
