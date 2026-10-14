"""Audit report generator tool formatting completion evidence."""

from datetime import datetime
from typing import Dict, Any, List


def generate_report(
    task: str,
    status: str,
    summary: str,
    steps_executed: List[Dict[str, Any]] = None,
    evidence: Dict[str, Any] = None
) -> str:
    """Generate a structured Markdown completion and audit report.
    
    Args:
        task: Original natural language user prompt.
        status: Overall outcome ('SUCCESS', 'APPROVAL_REJECTED', 'FAILED', 'PARTIAL').
        summary: High-level concise explanation.
        steps_executed: Sequence of actions taken by the agent.
        evidence: Concrete proof of work (ledger row, file path, verification details).
        
    Returns:
        Formatted Markdown string.
    """
    steps = steps_executed or []
    ev = evidence or {}
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    verification = ev.get("verification_audit", {})
    if status == "COMPLETED" and verification.get("passed"):
        status_badge = "✅ COMPLETED & VERIFIED"
    elif verification.get("safe_halt"):
        status_badge = f"🛑 SAFELY HALTED — {status}"
    else:
        status_badge = f"⚠️ INCOMPLETE — {status}"

    lines = [
        "# 📋 Autonomous Finance Clerk — Execution Audit Report",
        f"**Generated At:** `{timestamp}` | **Status:** {status_badge}",
        "",
        "## 1. Objective",
        f"> {task}",
        "",
        "## 2. Summary",
        summary,
        "",
        "## 3. Evidence of Completion",
    ]

    if ev:
        for k, v in ev.items():
            if isinstance(v, dict):
                lines.append(f"- **{k}:**")
                for sub_k, sub_v in v.items():
                    lines.append(f"  - `{sub_k}`: {sub_v}")
            else:
                lines.append(f"- **{k}:** `{v}`")
    else:
        lines.append("_No evidence artifacts recorded._")

    lines.extend([
        "",
        f"## 4. Execution Trace ({len(steps)} Steps)",
        "| Step | Action | Outcome | Details |",
        "|:---:|:---|:---:|:---|"
    ])

    for i, s in enumerate(steps, 1):
        action = s.get("tool", "Decision")
        outcome = "✅ OK" if s.get("status") == "success" else "⚠️ " + s.get("status", "info")
        detail = s.get("summary", str(s.get("output", ""))[:60])
        lines.append(f"| {i} | `{action}` | {outcome} | {detail} |")

    lines.append("")
    lines.append("---")
    lines.append("_Autonomous Finance Worker — Audit Log automatically generated._")

    return "\n".join(lines)
