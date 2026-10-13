"""Tool Registry providing schemas and execution dispatcher for the AI agent."""

from typing import Dict, Any, List, Callable
from tools.invoice_search import search_invoices
from tools.invoice_reader import read_invoice
from tools.database import query_database
from tools.duplicate_checker import check_duplicate
from tools.ledger import insert_ledger_entry
from tools.approval import request_user_approval
from tools.verification import verify_ledger_entry
from tools.report import generate_report

# Tool function mapping
TOOL_FUNCTIONS: Dict[str, Callable] = {
    "search_invoices": search_invoices,
    "read_invoice": read_invoice,
    "query_database": query_database,
    "check_duplicate": check_duplicate,
    "insert_ledger_entry": insert_ledger_entry,
    "request_user_approval": request_user_approval,
    "verify_ledger_entry": verify_ledger_entry,
}

# OpenAI/LiteLLM/Gemini-compatible Function Calling Schemas
TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_invoices",
            "description": "Search the invoices directory for available files matching a vendor name or query. Returns a list of files sorted latest first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vendor_name": {
                        "type": "string",
                        "description": "Name or keyword of the vendor (e.g. 'Acme', 'Globex', 'Initech')."
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional search term for general query."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_invoice",
            "description": "Read and validate an invoice file. Returns parsed vendor, amount, due date, line items, or error if malformed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the invoice JSON file (e.g. 'invoices/acme_corp_INV-2024-0042.json')."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Execute a safe read-only SQL query against the company database to check vendors, purchase orders, or ledger entries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL SELECT query (e.g. \"SELECT * FROM vendors WHERE name LIKE '%Acme%'\")."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_duplicate",
            "description": "Check if an invoice number has already been entered into the accounting ledger or previously processed to prevent double payments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_number": {
                        "type": "string",
                        "description": "Invoice number to check (e.g. 'INV-2024-0042')."
                    }
                },
                "required": ["invoice_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "insert_ledger_entry",
            "description": "Insert an approved invoice into the company accounting ledger. NOTE: Invoices exceeding $1,000 REQUIRE calling request_user_approval first and passing user_approved=True.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_number": {
                        "type": "string",
                        "description": "Invoice identifier string."
                    },
                    "vendor_id": {
                        "type": "integer",
                        "description": "Database ID of the verified vendor from the vendors table."
                    },
                    "amount": {
                        "type": "number",
                        "description": "Total payment amount."
                    },
                    "currency": {
                        "type": "string",
                        "description": "Currency code (e.g. 'USD')."
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date (YYYY-MM-DD)."
                    },
                    "po_number": {
                        "type": "string",
                        "description": "Purchase order number if applicable."
                    },
                    "notes": {
                        "type": "string",
                        "description": "Brief description of the purchase or line items."
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Path to the invoice file."
                    },
                    "user_approved": {
                        "type": "boolean",
                        "description": "Set to true only if human approval was explicitly granted or amount is <= $1,000."
                    }
                },
                "required": ["invoice_number", "vendor_id", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_user_approval",
            "description": "Pause execution to ask the human user for explicit approval on high-value actions (> $1,000) or ambiguous states.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Specific question for the user explaining amount and vendor."
                    },
                    "context": {
                        "type": "object",
                        "description": "Supporting details like vendor name, invoice amount, PO number."
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_ledger_entry",
            "description": "Independently query the database to verify that a ledger record was created with the expected values.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ledger_entry_id": {
                        "type": "integer",
                        "description": "ID of the newly created ledger record."
                    },
                    "expected_invoice_number": {
                        "type": "string",
                        "description": "Expected invoice number."
                    },
                    "expected_amount": {
                        "type": "number",
                        "description": "Expected numerical amount."
                    }
                },
                "required": ["ledger_entry_id"]
            }
        }
    }
]


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a registered tool safely and return the result."""
    if tool_name not in TOOL_FUNCTIONS:
        return {
            "success": False,
            "error": f"Unknown tool: '{tool_name}'. Available: {list(TOOL_FUNCTIONS.keys())}"
        }

    func = TOOL_FUNCTIONS[tool_name]
    try:
        return func(**arguments)
    except TypeError as e:
        return {
            "success": False,
            "error": f"Invalid arguments passed to '{tool_name}': {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool execution failed for '{tool_name}': {str(e)}"
        }


def get_tool_schemas() -> List[Dict[str, Any]]:
    """Return all tool schemas for LLM tool calling."""
    return TOOL_SCHEMAS
