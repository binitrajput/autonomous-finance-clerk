"""Human-in-the-loop approval tool for high-value actions and anomalous states."""

from typing import Dict, Any, Optional, Callable

# Global hook for testing or UI override
_APPROVAL_CALLBACK: Optional[Callable[[str, Dict[str, Any]], bool]] = None


def set_approval_callback(callback: Optional[Callable[[str, Dict[str, Any]], bool]]):
    """Set a custom callback for handling user approval in tests or UI."""
    global _APPROVAL_CALLBACK
    _APPROVAL_CALLBACK = callback


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
        approved = _APPROVAL_CALLBACK(question, ctx)
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

    return {
        "success": True,
        "approved": approved,
        "question": question,
        "response": "User approved" if approved else "User rejected or aborted",
        "context": ctx
    }
