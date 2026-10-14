"""Ledger tool for writing approved invoice transactions into the accounting database."""

import config
import sqlite3
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional
from tools.database import get_db_connection
from tools.approval import consume_approval


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
    # Validate values again at the write boundary; callers may bypass the
    # invoice parser, and LLM tool arguments must never be trusted by themselves.
    invoice_number = str(invoice_number).strip()
    if not invoice_number:
        return {"success": False, "error": "Invoice number cannot be empty."}
    try:
        amount_value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return {"success": False, "error": "Invoice amount must be a valid positive number."}
    if not amount_value.is_finite() or amount_value <= 0:
        return {"success": False, "error": "Invoice amount must be a valid positive number."}
    if not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency.strip()):
        return {"success": False, "error": "Currency must be a three-letter code."}
    currency = currency.strip().upper()
    amount = float(amount_value)

    # 1. Safety Threshold Check
    if amount_value > Decimal(str(config.APPROVAL_THRESHOLD)) and (
        not user_approved or not consume_approval(invoice_number, amount)
    ):
        return {
            "success": False,
            "requires_approval": True,
            "error": (
                f"Policy Violation: Invoice amount ${amount:,.2f} exceeds the "
                f"auto-approval limit (${config.APPROVAL_THRESHOLD:,.2f}). "
                "A matching, explicit approval is required before writing this entry."
            ),
            "amount": amount,
            "threshold": config.APPROVAL_THRESHOLD
        }

    # 2. Database Write
    conn = None
    try:
        conn = get_db_connection()
        # Acquire the SQLite write reservation before checking/inserting so
        # simultaneous requests serialize; the unique index is the final guard.
        conn.execute("BEGIN IMMEDIATE")
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

        if vendor["status"] != "active":
            conn.close()
            return {
                "success": False,
                "error": f"Vendor '{vendor['name']}' is {vendor['status']}. Invoices require an active vendor."
            }

        # When the invoice names a PO, enforce ownership, state, and remaining
        # approved value while holding the same write transaction.
        po_number = po_number.strip() if isinstance(po_number, str) else po_number
        if po_number:
            cursor.execute(
                "SELECT vendor_id, approved_amount, status FROM purchase_orders WHERE po_number = ?",
                (po_number,)
            )
            purchase_order = cursor.fetchone()
            if not purchase_order:
                conn.close()
                return {"success": False, "error": f"Purchase order {po_number} was not found."}
            if purchase_order["vendor_id"] != vendor_id:
                conn.close()
                return {"success": False, "error": f"Purchase order {po_number} belongs to a different vendor."}
            if purchase_order["status"] != "open":
                conn.close()
                return {"success": False, "error": f"Purchase order {po_number} is {purchase_order['status']}, not open."}

            cursor.execute(
                """SELECT COALESCE(SUM(amount), 0) AS committed
                   FROM ledger WHERE po_number = ? AND status != 'rejected'""",
                (po_number,)
            )
            committed = Decimal(str(cursor.fetchone()["committed"]))
            available = Decimal(str(purchase_order["approved_amount"])) - committed
            if amount_value > available:
                conn.close()
                return {
                    "success": False,
                    "error": (
                        f"Invoice amount ${amount_value:,.2f} exceeds the remaining "
                        f"approved PO amount of ${max(available, Decimal('0')):,.2f}."
                    )
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
        conn = None

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
    except sqlite3.IntegrityError as e:
        duplicate = None
        if conn is not None:
            conn.rollback()
            duplicate = conn.execute(
                """SELECT 1 FROM ledger
                   WHERE vendor_id = ? AND UPPER(invoice_number) = UPPER(?)
                   UNION ALL
                   SELECT 1 FROM processed_invoices
                   WHERE UPPER(invoice_number) = UPPER(?)
                   LIMIT 1""",
                (vendor_id, invoice_number, invoice_number)
            ).fetchone()
            conn.close()
        if duplicate:
            return {
                "success": False,
                "is_duplicate": True,
                "error": f"Invoice {invoice_number} has already been recorded."
            }
        return {"success": False, "error": f"Database constraint rejected the entry: {e}"}
    except Exception as e:
        if conn is not None:
            conn.rollback()
            conn.close()
        return {
            "success": False,
            "error": f"Database insertion failed: {str(e)}"
        }
