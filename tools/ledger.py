"""Ledger tool for writing approved invoice transactions into the accounting database."""

import config
from typing import Dict, Any, Optional
from tools.database import get_db_connection


def insert_ledger_entry(
    invoice_number: str,
    vendor_id: int,
    amount: float,
    currency: str = "USD",
    due_date: Optional[str] = None,
    po_number: Optional[str] = None,
    notes: Optional[str] = None,
    file_path: Optional[str] = None,
    user_approved: bool = False
) -> Dict[str, Any]:
    """Insert a new transaction record into the accounting ledger.
    
    Safety Rules:
      - If amount > config.APPROVAL_THRESHOLD and user_approved is False,
        the transaction is rejected and requires explicit human approval.
        
    Args:
        invoice_number: Identifier from the invoice.
        vendor_id: ID of the registered vendor in the database.
        amount: Total payable amount.
        currency: Currency code (default 'USD').
        due_date: Due date string.
        po_number: Associated purchase order number if available.
        notes: Audit notes or line item summary.
        file_path: Path of the processed invoice file.
        user_approved: Boolean flag confirming human approval was obtained.
        
    Returns:
        Dict with status, ledger_entry_id, or approval error.
    """
    # 1. Safety Threshold Check
    if amount > config.APPROVAL_THRESHOLD and not user_approved:
        return {
            "success": False,
            "requires_approval": True,
            "error": (
                f"Policy Violation: Invoice amount ${amount:,.2f} exceeds the "
                f"auto-approval limit (${config.APPROVAL_THRESHOLD:,.2f}). "
                f"You MUST call request_user_approval before writing this entry."
            ),
            "amount": amount,
            "threshold": config.APPROVAL_THRESHOLD
        }

    # 2. Database Write
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Verify vendor exists
        cursor.execute("SELECT id, name, status FROM vendors WHERE id = ?", (vendor_id,))
        vendor = cursor.fetchone()
        if not vendor:
            conn.close()
            return {
                "success": False,
                "error": f"Vendor ID {vendor_id} not found in database. Cannot insert ledger entry."
            }

        if vendor["status"] == "suspended":
            conn.close()
            return {
                "success": False,
                "error": f"Vendor '{vendor['name']}' is suspended. Invoices cannot be processed."
            }

        # Insert into ledger
        cursor.execute(
            """INSERT INTO ledger (invoice_number, vendor_id, po_number, amount, currency, due_date, status, entered_by, notes)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', 'ai-clerk', ?)""",
            (invoice_number, vendor_id, po_number, amount, currency, due_date, notes)
        )
        ledger_entry_id = cursor.lastrowid

        # Record in processed_invoices for duplicate tracking
        cursor.execute(
            """INSERT INTO processed_invoices (invoice_number, vendor_id, file_path, ledger_entry_id)
               VALUES (?, ?, ?, ?)""",
            (invoice_number, vendor_id, file_path, ledger_entry_id)
        )

        conn.commit()
        conn.close()

        return {
            "success": True,
            "ledger_entry_id": ledger_entry_id,
            "invoice_number": invoice_number,
            "vendor_name": vendor["name"],
            "amount": amount,
            "currency": currency,
            "status": "pending",
            "message": f"Successfully created ledger entry #{ledger_entry_id}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Database insertion failed: {str(e)}"
        }
