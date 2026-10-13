"""Invoice reader tool to extract and validate invoice details from files."""

import os
import json
from typing import Dict, Any


def read_invoice(file_path: str) -> Dict[str, Any]:
    """Read and validate an invoice file.
    
    Args:
        file_path: Absolute or relative path to the invoice JSON file.
        
    Returns:
        Dict containing parsed invoice fields or error details if malformed.
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"Invoice file not found: {file_path}",
            "is_malformed": False
        }

    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Invalid JSON syntax in invoice: {str(e)}",
            "is_malformed": True,
            "file_path": file_path
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error opening invoice file: {str(e)}",
            "is_malformed": True,
            "file_path": file_path
        }

    # Validation rules
    missing_fields = []
    for required in ["invoice_number", "vendor_name", "total_amount"]:
        if required not in data or data[required] is None:
            missing_fields.append(required)

    if missing_fields:
        return {
            "success": False,
            "error": f"Malformed invoice: Missing required field(s): {', '.join(missing_fields)}",
            "is_malformed": True,
            "file_path": file_path,
            "partial_data": data
        }

    # Validate amount is numeric
    try:
        amount = float(data["total_amount"])
        if amount <= 0:
            return {
                "success": False,
                "error": f"Invalid invoice total_amount: {amount} (must be positive)",
                "is_malformed": True,
                "file_path": file_path
            }
    except (ValueError, TypeError):
        return {
            "success": False,
            "error": f"Invalid non-numeric total_amount: {data.get('total_amount')}",
            "is_malformed": True,
            "file_path": file_path
        }

    return {
        "success": True,
        "is_malformed": False,
        "file_path": file_path,
        "invoice_number": data.get("invoice_number"),
        "vendor_name": data.get("vendor_name"),
        "vendor_tax_id": data.get("vendor_tax_id"),
        "invoice_date": data.get("invoice_date"),
        "due_date": data.get("due_date"),
        "currency": data.get("currency", "USD"),
        "total_amount": float(data.get("total_amount")),
        "subtotal": data.get("subtotal"),
        "tax": data.get("tax"),
        "po_number": data.get("po_number"),
        "line_items": data.get("line_items", []),
        "notes": data.get("notes", "")
    }
