"""Database tool for querying company database."""

import sqlite3
import re
from typing import Dict, Any, List
import config


def get_db_connection():
    """Get a connection to the SQLite database with row factory."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_database(query: str, params: List[Any] = None) -> Dict[str, Any]:
    """Execute a safe read query against the company database.
    
    Args:
        query: SQL SELECT query to execute.
        params: Optional query parameters for parameterized queries.
    
    Returns:
        Dict with rows (list of dicts), count, and execution status.
    """
    clean_query = query.strip()
    
    # Safety guard: only allow SELECT queries
    if not re.match(r"^SELECT\b", clean_query, re.IGNORECASE):
        return {
            "success": False,
            "error": "Security restriction: Only SELECT queries are permitted through this tool.",
            "rows": [],
            "count": 0
        }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(clean_query, params)
        else:
            cursor.execute(clean_query)
            
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "count": len(rows),
            "rows": rows
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Database query error: {str(e)}",
            "rows": [],
            "count": 0
        }
