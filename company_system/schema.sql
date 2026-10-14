-- Autonomous Finance Clerk: Company Database Schema
-- Simulates an internal ERP / Accounting system

CREATE TABLE IF NOT EXISTS vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    tax_id TEXT UNIQUE,
    email TEXT,
    payment_terms TEXT DEFAULT 'NET30',
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'suspended', 'blacklisted')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number TEXT UNIQUE NOT NULL,
    vendor_id INTEGER REFERENCES vendors(id),
    description TEXT,
    approved_amount REAL NOT NULL,
    status TEXT DEFAULT 'open' CHECK(status IN ('open', 'fulfilled', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL,
    vendor_id INTEGER REFERENCES vendors(id),
    po_number TEXT,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'USD',
    due_date TEXT,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'paid', 'rejected')),
    entered_by TEXT DEFAULT 'ai-clerk',
    entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- The same vendor invoice must not be posted twice, even if requests race.
CREATE UNIQUE INDEX IF NOT EXISTS idx_ledger_vendor_invoice_unique
    ON ledger(vendor_id, UPPER(invoice_number));

CREATE TABLE IF NOT EXISTS processed_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT UNIQUE NOT NULL,
    vendor_id INTEGER REFERENCES vendors(id),
    file_path TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ledger_entry_id INTEGER REFERENCES ledger(id)
);
