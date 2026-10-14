"""Seed the company database with realistic test data."""

import sqlite3
import os


def seed_database(db_path: str) -> None:
    """Populate the database with sample vendors, purchase orders, and one existing ledger entry."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # --- Vendors ---
    vendors = [
        ('Acme Corp', 'TAX-AC-2024-001', 'billing@acmecorp.com', 'NET30', 'active'),
        ('Globex International', 'TAX-GX-2024-002', 'invoices@globex.com', 'NET45', 'active'),
        ('Initech Solutions', 'TAX-IN-2024-003', 'accounts@initech.io', 'NET30', 'active'),
        ('Umbrella Industries', 'TAX-UI-2024-004', 'finance@umbrella.com', 'NET60', 'suspended'),
        ('Wayne Enterprises', 'TAX-WE-2024-005', 'ap@wayne.com', 'NET30', 'active'),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO vendors (name, tax_id, email, payment_terms, status) VALUES (?, ?, ?, ?, ?)",
        vendors
    )

    # --- Purchase Orders ---
    purchase_orders = [
        ('PO-2024-001', 1, 'Monthly widget supply - Q4', 5000.00, 'open'),
        ('PO-2024-002', 2, 'Cloud infrastructure services', 12000.00, 'open'),
        ('PO-2024-003', 3, 'Software license renewal', 3500.00, 'open'),
        ('PO-2024-004', 1, 'Emergency parts order', 800.00, 'open'),
        ('PO-2024-005', 5, 'Security consulting engagement', 15000.00, 'open'),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO purchase_orders (po_number, vendor_id, description, approved_amount, status) VALUES (?, ?, ?, ?, ?)",
        purchase_orders
    )

    # --- One existing ledger entry (for duplicate detection testing) ---
    seed_invoice_number = 'INV-2024-0035'
    cursor.execute(
        """INSERT INTO ledger (invoice_number, vendor_id, po_number, amount, currency, due_date, status, notes)
           SELECT ?, 2, 'PO-2024-002', 3200.00, 'USD', '2024-11-15', 'paid', 'Cloud services - September'
           WHERE NOT EXISTS (
               SELECT 1 FROM ledger WHERE UPPER(invoice_number) = UPPER(?)
           )""",
        (seed_invoice_number, seed_invoice_number)
    )
    cursor.execute(
        "SELECT id FROM ledger WHERE UPPER(invoice_number) = UPPER(?) ORDER BY id LIMIT 1",
        (seed_invoice_number,)
    )
    seed_ledger_entry_id = cursor.fetchone()[0]
    cursor.execute(
        """INSERT OR IGNORE INTO processed_invoices (invoice_number, vendor_id, file_path, ledger_entry_id)
           VALUES (?, 2, 'invoices/globex_INV-2024-0035.json', ?)""",
        (seed_invoice_number, seed_ledger_entry_id)
    )

    conn.commit()
    conn.close()
    print(f"Database seeded successfully at {db_path}")


if __name__ == "__main__":
    db_path = os.path.join(os.path.dirname(__file__), "company.db")
    seed_database(db_path)
