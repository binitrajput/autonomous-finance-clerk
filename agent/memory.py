"""Working memory module for tracking state, facts, and execution history."""

from typing import Dict, Any, List, Optional
from datetime import datetime


class StepRecord:
    """Record of a single action taken by the agent."""
    def __init__(self, step_number: int, tool: str, arguments: Dict[str, Any], result: Any, status: str = "success"):
        self.step_number = step_number
        self.tool = tool
        self.arguments = arguments
        self.result = result
        self.status = status
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step_number,
            "tool": self.tool,
            "arguments": self.arguments,
            "result": self.result,
            "status": self.status,
            "timestamp": self.timestamp
        }


class WorkingMemory:
    """Working memory that remembers discovered facts, previous actions, and errors."""

    def __init__(self, goal: str = ""):
        self.goal: str = goal
        self.steps: List[StepRecord] = []
        self.facts: Dict[str, Any] = {}
        self.errors_encountered: List[Dict[str, Any]] = []
        self.user_approvals: Dict[str, bool] = {}
        self.verification_results: List[Dict[str, Any]] = []

    def set_goal(self, goal: str):
        self.goal = goal

    def add_step(self, tool: str, arguments: Dict[str, Any], result: Any, status: str = "success") -> StepRecord:
        step_num = len(self.steps) + 1
        record = StepRecord(step_num, tool, arguments, result, status)
        self.steps.append(record)

        # Automatically extract and store key facts if present in tool result
        if isinstance(result, dict) and result.get("success"):
            for key in ["invoice_number", "vendor_id", "vendor_name", "total_amount", "amount", "po_number", "ledger_entry_id"]:
                if key in result and result[key] is not None:
                    self.facts[key] = result[key]

        if status == "error" or (isinstance(result, dict) and not result.get("success")):
            self.errors_encountered.append({
                "step": step_num,
                "tool": tool,
                "error": result.get("error") if isinstance(result, dict) else str(result)
            })

        return record

    def record_approval(self, key: str, approved: bool):
        self.user_approvals[key] = approved

    def is_approved(self, key: str) -> bool:
        return self.user_approvals.get(key, False)

    def record_verification(self, verification_result: Dict[str, Any]):
        self.verification_results.append(verification_result)

    def get_summary_context(self) -> str:
        """Format current working memory as context for the LLM prompt."""
        lines = [f"Goal: {self.goal}"]
        if self.facts:
            lines.append("Discovered Facts:")
            for k, v in self.facts.items():
                lines.append(f"  - {k}: {v}")
        if self.errors_encountered:
            lines.append("Errors Encountered:")
            for err in self.errors_encountered[-3:]:  # last 3 errors
                lines.append(f"  - In step {err['step']} ({err['tool']}): {err['error']}")
        return "\n".join(lines)

    def get_all_steps_dict(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self.steps]
