"""Human-in-the-loop approval tool for high-value actions and anomalous states."""

from typing import Dict, Any, Optional, Callable
import json
import logging
import time

from tools.database import get_db_connection

# Global hook for testing or UI override
_APPROVAL_CALLBACK: Optional[Callable[[str, Dict[str, Any]], bool]] = None
_APPROVED_ACTIONS: Dict[tuple, float] = {}
_APPROVAL_TTL_SECONDS = 600
logger = logging.getLogger(__name__)


def set_approval_callback(callback: Optional[Callable[[str, Dict[str, Any]], bool]]):
    """Set a custom callback for handling user approval in tests or UI."""
    global _APPROVAL_CALLBACK
    _APPROVAL_CALLBACK = callback


def consume_approval(invoice_number: str, amount: float) -> bool:
    """Consume a matching, recent approval grant exactly once."""
    key = (str(invoice_number).strip().upper(), round(float(amount), 2))
    expires_at = _APPROVED_ACTIONS.pop(key, None)
    return expires_at is not None and expires_at >= time.time()


def _record_approval(context: Dict[str, Any], decision: bool, decision_source: str) -> bool:
    invoice_number = context.get("invoice_number", context.get("invoice"))
    amount = context.get("amount", context.get("total_amount"))
    if invoice_number is None or amount is None:
        return False
    try:
        key = (str(invoice_number).strip().upper(), round(float(amount), 2))
        if not key[0] or key[1] <= 0:
            return False
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO approval_events
                   (invoice_number, amount, decision, decision_source, context_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(invoice_number).strip(), key[1], "approved" if decision else "rejected",
                 decision_source, json.dumps(context, default=str, sort_keys=True))
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("Could not persist approval decision; failing closed")
        return False
    if decision:
        _APPROVED_ACTIONS[key] = time.time() + _APPROVAL_TTL_SECONDS
    return True


def record_approval_decision(context: Dict[str, Any], approved: bool, decision_source: str) -> bool:
    """Persist a decision made by a UI before agent execution starts."""
    return _record_approval(context, approved, decision_source)


def request_user_approval(question: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Request human authorization before proceeding with sensitive or high-risk actions.
    
    Args:
        question: The clear question asked to the user (e.g. 'Approve payment of $4,250 for Acme?').
        context: Additional data explaining why approval is requested (amount, vendor, PO).
        
    Returns:
        Dict containing approved status (bool), reason, and user feedback.
    """
    ctx = context or {}
    global _APPROVAL_CALLBACK

    # If an automated callback is registered (e.g. in test suite or Streamlit session)
    if _APPROVAL_CALLBACK is not None:
        approved = bool(_APPROVAL_CALLBACK(question, ctx))
        recorded = _record_approval(ctx, approved, "configured_callback")
        if not recorded:
            return {
                "success": False,
                "approved": False,
                "question": question,
                "response": "Approval decision could not be written to the audit log; action blocked.",
                "context": ctx
            }
        return {
            "success": True,
            "approved": approved,
            "question": question,
            "response": "Approved via callback" if approved else "Rejected via callback",
            "context": ctx
        }

    # Default: Interactive console prompt
    print("\n" + "="*60)
    print("🛑 [HUMAN APPROVAL REQUIRED]")
    print(f"Question: {question}")
    if ctx:
        print(f"Context: {ctx}")
    print("="*60)

    try:
        user_input = input("Proceed? [y/N]: ").strip().lower()
        approved = user_input in ["y", "yes"]
    except EOFError:
        # Non-interactive fallback
        approved = False

    recorded = _record_approval(ctx, approved, "interactive_console")
    if not recorded:
        return {
            "success": False,
            "approved": False,
            "question": question,
            "response": "Approval decision could not be written to the audit log; action blocked.",
            "context": ctx
        }

    return {
        "success": True,
        "approved": approved,
        "question": question,
        "response": "User approved" if approved else "User rejected or aborted",
        "context": ctx
    }
