"""Initialize the company SQLite database from schema and seed data."""

import sqlite3
import os
try:
    from company_system.seed_data import seed_database
except ImportError:
    from seed_data import seed_database


def initialize_database(db_path: str = None) -> str:
    """Create database tables and seed with test data.
    
    Args:
        db_path: Path to the SQLite database file. Defaults to company_system/company.db.
    
    Returns:
        The path to the initialized database.
    """
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "company.db")

    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")

    # Create tables
    conn = sqlite3.connect(db_path)
    with open(schema_path, 'r') as f:
        conn.executescript(f.read())
    conn.close()

    # Seed data
    seed_database(db_path)

    return db_path


def reset_database(db_path: str = None) -> str:
    """Drop and recreate the database (for testing)."""
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), "company.db")
    
    if os.path.exists(db_path):
        os.remove(db_path)
    
    return initialize_database(db_path)


if __name__ == "__main__":
    path = reset_database()
    print(f"Database initialized at: {path}")
