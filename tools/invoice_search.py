"""Invoice search tool to discover invoice files in the invoices directory."""

import os
import json
import re
from typing import Dict, Any, List
import config


def search_invoices(vendor_name: str = "", query: str = "") -> Dict[str, Any]:
    """Search the invoices directory for files matching a vendor name, filename, or query.
    
    Args:
        vendor_name: Optional vendor name to filter by (e.g. 'Acme', 'Globex').
        query: Optional free-form search query or filename.
        
    Returns:
        Dict with list of matching file paths, their metadata, and count.
    """
    invoice_dir = config.INVOICE_DIR
    if not os.path.exists(invoice_dir):
        return {"success": False, "error": f"Invoice directory not found: {invoice_dir}", "files": []}

    matches: List[Dict[str, Any]] = []
    
    # Check if a specific .json file is referenced in query or vendor_name
    file_ref_match = re.search(r"([\w\-]+\.json)", f"{vendor_name} {query}", re.IGNORECASE)
    target_file_ref = file_ref_match.group(1).lower() if file_ref_match else None

    # If an exact filename was referenced, find and return that exact file
    if target_file_ref:
        for filename in sorted(os.listdir(invoice_dir)):
            if filename.lower() == target_file_ref:
                file_path = os.path.join(invoice_dir, filename)
                meta = {"file_name": filename, "file_path": file_path}
                try:
                    with open(file_path, "r") as f:
                        content = json.load(f)
                        meta["invoice_number"] = content.get("invoice_number", "UNKNOWN")
                        meta["vendor_name"] = content.get("vendor_name", "UNKNOWN")
                        meta["invoice_date"] = content.get("invoice_date", "")
                        meta["total_amount"] = content.get("total_amount")
                except Exception:
                    meta["read_error"] = "Corrupted or unreadable file"
                return {
                    "success": True,
                    "count": 1,
                    "query": target_file_ref,
                    "files": [meta]
                }

    # Keyword terms for search
    search_text = (vendor_name or query).strip().lower()
    keywords = [w for w in re.split(r"\W+", search_text) if len(w) > 2 and w not in ["process", "invoice", "the", "from", "and", "our", "system", "into", "enter"]]

    for filename in sorted(os.listdir(invoice_dir)):
        if not filename.endswith(".json"):
            continue

        file_path = os.path.join(invoice_dir, filename)
        file_matched = False
        meta = {"file_name": filename, "file_path": file_path}

        # Check keyword in filename
        if any(k in filename.lower() for k in keywords):
            file_matched = True

        # Peek inside file for content match
        try:
            with open(file_path, "r") as f:
                content = json.load(f)
                meta["invoice_number"] = content.get("invoice_number", "UNKNOWN")
                meta["vendor_name"] = content.get("vendor_name", "UNKNOWN")
                meta["invoice_date"] = content.get("invoice_date", "")
                meta["total_amount"] = content.get("total_amount")

                # 3. Check vendor name inside content
                v_inside = str(content.get("vendor_name", "")).lower()
                if any(k in v_inside for k in keywords):
                    file_matched = True
        except Exception:
            meta["read_error"] = "Corrupted or unreadable file"

        # If no search terms given, match all
        if not keywords and not target_file_ref:
            file_matched = True

        if file_matched:
            matches.append(meta)

    # Sort matches by invoice_date descending (latest first)
    matches.sort(key=lambda x: str(x.get("invoice_date", "")), reverse=True)

    return {
        "success": True,
        "count": len(matches),
        "query": search_text,
        "files": matches
    }
