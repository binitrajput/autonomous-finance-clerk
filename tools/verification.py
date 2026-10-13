"""Verification tool to independently verify that accounting changes actually persisted."""

from typing import Dict, Any, Optional
from tools.database import get_db_connection


def verify_ledger_entry(
    ledger_entry_id: int,
    expected_invoice_number: Optional[str] = None,
    expected_amount: Optional[float] = None
) -> Dict[str, Any]:
    """Independently audit and verify that a ledger entry was created and persisted correctly.
    
    Args:
        ledger_entry_id: The ID returned by insert_ledger_entry.
        expected_invoice_number: Expected invoice number to compare against.
        expected_amount: Expected numerical amount to compare against.
        
    Returns:
        Dict detailing verification result, matched fields, or discrepancies found.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT l.id, l.invoice_number, l.amount, l.currency, l.status, l.entered_at,
                      v.name as vendor_name, l.po_number, l.due_date
               FROM ledger l
               LEFT JOIN vendors v ON l.vendor_id = v.id
               WHERE l.id = ?""",
            (ledger_entry_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {
                "success": False,
                "verified": False,
                "error": f"Verification failed: Ledger entry #{ledger_entry_id} not found in database."
            }

        record = dict(row)
        discrepancies = []

        if expected_invoice_number:
            if record["invoice_number"].strip().upper() != expected_invoice_number.strip().upper():
                discrepancies.append(
                    f"Invoice number mismatch: expected '{expected_invoice_number}', got '{record['invoice_number']}'"
                )

        if expected_amount is not None:
            if abs(float(record["amount"]) - float(expected_amount)) > 0.01:
                discrepancies.append(
                    f"Amount mismatch: expected ${expected_amount:,.2f}, got ${record['amount']:,.2f}"
                )

        if discrepancies:
            return {
                "success": True,
                "verified": False,
                "discrepancies": discrepancies,
                "record": record,
                "message": "Record exists but values do not match expected outcome."
            }

        return {
            "success": True,
            "verified": True,
            "ledger_entry_id": ledger_entry_id,
            "record": record,
            "message": f"Successfully verified ledger entry #{ledger_entry_id} in database."
        }
    except Exception as e:
        return {
            "success": False,
            "verified": False,
            "error": f"Verification error during database check: {str(e)}"
        }
