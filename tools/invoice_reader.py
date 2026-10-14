"""Invoice reader tool to extract and validate invoice details from files."""

import json
from pathlib import Path
from typing import Dict, Any
import config


def read_invoice(file_path: str) -> Dict[str, Any]:
    """Read and validate an invoice file.
    
    Args:
        file_path: Absolute or relative path to the invoice JSON file.
        
    Returns:
        Dict containing parsed invoice fields or error details if malformed.
    """
    invoice_root = Path(config.INVOICE_DIR).resolve()
    requested_path = Path(file_path)
    try:
        candidate = requested_path if requested_path.is_absolute() else invoice_root / requested_path
        try:
            resolved_path = candidate.resolve(strict=True)
        except FileNotFoundError:
            # Also accept project-root-relative paths such as invoices/example.json.
            if requested_path.is_absolute():
                raise
            resolved_path = (Path.cwd() / requested_path).resolve(strict=True)
        resolved_path.relative_to(invoice_root)
    except ValueError:
        return {
            "success": False,
            "blocked": True,
            "error": "Invoice path must point to a file inside the configured invoice directory.",
            "is_malformed": False
        }
    except FileNotFoundError:
        return {
            "success": False,
            "error": "Invoice file not found in the configured invoice directory.",
            "is_malformed": False
        }
    except OSError:
        return {
            "success": False,
            "blocked": True,
            "error": "Invoice path could not be safely resolved.",
            "is_malformed": False
        }

    if not resolved_path.is_file() or resolved_path.suffix.lower() != ".json":
        return {
            "success": False,
            "blocked": True,
            "error": "Only JSON invoice files inside the configured invoice directory can be read.",
            "is_malformed": False
        }
    file_path = str(resolved_path)

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

    if not isinstance(data, dict):
        return {
            "success": False,
            "error": "Malformed invoice: expected a JSON object.",
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
