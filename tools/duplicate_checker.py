"""Duplicate checker tool to prevent double-processing or double-payments."""

from typing import Dict, Any
from tools.database import get_db_connection


def check_duplicate(invoice_number: str) -> Dict[str, Any]:
    """Check if an invoice has already been entered into the ledger or processed.
    
    Args:
        invoice_number: The invoice identifier string (e.g. 'INV-2024-0042').
        
    Returns:
        Dict indicating whether the invoice is a duplicate, with prior record details if found.
    """
    clean_num = invoice_number.strip()
    if not clean_num:
        return {"success": False, "error": "Empty invoice number provided"}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check ledger
        cursor.execute(
            """SELECT l.id, l.invoice_number, l.amount, l.status, l.entered_at, v.name as vendor_name
               FROM ledger l
               LEFT JOIN vendors v ON l.vendor_id = v.id
               WHERE UPPER(l.invoice_number) = UPPER(?)""",
            (clean_num,)
        )
        ledger_row = cursor.fetchone()

        # Check processed_invoices tracking table
        cursor.execute(
            """SELECT id, invoice_number, processed_at, file_path 
               FROM processed_invoices 
               WHERE UPPER(invoice_number) = UPPER(?)""",
            (clean_num,)
        )
        proc_row = cursor.fetchone()
        conn.close()

        if ledger_row:
            return {
                "success": True,
                "is_duplicate": True,
                "reason": f"Invoice {clean_num} already exists in accounting ledger.",
                "existing_record": dict(ledger_row)
            }

        if proc_row:
            return {
                "success": True,
                "is_duplicate": True,
                "reason": f"Invoice {clean_num} was previously processed.",
                "existing_record": dict(proc_row)
            }

        return {
            "success": True,
            "is_duplicate": False,
            "invoice_number": clean_num
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error checking for duplicate invoice: {str(e)}"
        }
