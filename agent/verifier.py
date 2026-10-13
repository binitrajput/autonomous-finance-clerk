"""Outcome verifier that independently audits whether the requested state change was achieved."""

from typing import Dict, Any, List
from tools.database import get_db_connection


class OutcomeVerifier:
    """Verifies that the agent's stated outcome was actually achieved in reality."""

    @staticmethod
    def audit_ledger_entry(ledger_entry_id: int) -> Dict[str, Any]:
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

        return {
            "verified": True,
            "record": dict(row)
        }

    @staticmethod
    def verify_execution(memory) -> Dict[str, Any]:
        """Perform end-to-end check on memory history and physical database state."""
        ledger_id = memory.facts.get("ledger_entry_id")
        
        # If the task required writing to the ledger
        if ledger_id:
            audit = OutcomeVerifier.audit_ledger_entry(ledger_id)
            if not audit["verified"]:
                return {
                    "passed": False,
                    "reason": audit["error"]
                }
            return {
                "passed": True,
                "ledger_entry_id": ledger_id,
                "db_record": audit["record"]
            }

        # If it was a query-only task or an intentionally aborted duplicate/error
        has_aborted = any("duplicate" in str(s.result).lower() or "malformed" in str(s.result).lower() or "rejected" in str(s.result).lower() for s in memory.steps)
        if has_aborted:
            return {
                "passed": True,
                "reason": "Agent safely aborted or caught invalid condition without polluting database."
            }

        return {
            "passed": True,
            "reason": "Execution completed."
        }
