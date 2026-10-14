import os
import json
import math
import re
import time
from typing import Dict, Any, List, Optional

try:
    import litellm
    litellm.suppress_debug_info = True
    LITELLM_AVAILABLE = True
except ImportError:
    litellm = None
    LITELLM_AVAILABLE = False

import config
from agent.memory import WorkingMemory
from agent.prompts import SYSTEM_PROMPT
from agent.verifier import OutcomeVerifier
from tools.registry import execute_tool, get_tool_schemas
from tools.report import generate_report


class AutonomousAgent:
    """Autonomous AI Task Worker for Finance & Accounting workflows."""

    def __init__(self, model_name: str = None, max_steps: int = None):
        self.model_name = model_name or config.MODEL_NAME
        # Auto-prefix for Groq if GROQ_API_KEY is present and model doesn't already have groq/
        if os.getenv("GROQ_API_KEY") and not self.model_name.startswith("groq/") and ("gpt-oss" in self.model_name or "llama" in self.model_name or "qwen" in self.model_name):
            self.model_name = f"groq/{self.model_name}"
        self.max_steps = max_steps or config.MAX_STEPS
        self.tool_schemas = get_tool_schemas()

    def run(self, task: str, verbose: bool = True) -> Dict[str, Any]:
        """Run the autonomous agent loop to achieve the natural language goal."""
        memory = WorkingMemory(goal=task)

        # Check if an API key is configured for the active model
        has_api_key = self._check_api_credentials()

        if verbose:
            mode_desc = f"LLM Mode ({self.model_name})" if has_api_key else "Deterministic Heuristic Engine (Offline)"
            print("\n" + "="*70)
            print(f"🤖 [AUTONOMOUS TASK WORKER INITIALIZED]")
            print(f"🎯 Objective: {task}")
            print(f"🧠 Brain: {mode_desc}")
            print("="*70)

        # Messages trace for the conversation
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}\nExecute the required sequence of actions autonomously."}
        ]

        status = "COMPLETED"
        final_text = ""
        finished = False

        for step_idx in range(1, self.max_steps + 1):
            if verbose:
                print(f"\n🔄 --- Step {step_idx}/{self.max_steps} ---")

            # 1. Decide next action: either via LLM or via autonomous heuristic engine
            if has_api_key:
                decision = self._llm_step(messages, task=task, memory=memory)
                if decision.pop("_fallback_to_heuristic", False):
                    has_api_key = False
            else:
                decision = self._heuristic_step(task, memory)

            # 2. Check if agent finished without tool calls
            if not decision.get("tool_calls"):
                final_text = decision.get("content", "Task execution finished.")
                finished = True
                if verbose:
                    print(f"🏁 Agent concluded: {final_text}")
                break

            # 3. Execute tool calls
            for tool_call in decision["tool_calls"]:
                tool_name = tool_call["name"]
                tool_args = tool_call["arguments"]

                if verbose:
                    print(f"⚙️ Tool Selected: `{tool_name}`")
                    print(f"📥 Arguments: {json.dumps(tool_args, indent=2)}")

                # ACT: Execute tool
                tool_result = execute_tool(tool_name, tool_args)
                tool_succeeded = tool_result.get("success", False)
                if tool_name == "request_user_approval":
                    tool_succeeded = tool_succeeded and tool_result.get("approved", False)
                elif tool_name == "verify_ledger_entry":
                    tool_succeeded = tool_succeeded and tool_result.get("verified", False)
                tool_status = "success" if tool_succeeded else "error"

                if verbose:
                    print(f"📤 Status: {tool_status.upper()}")
                    if not tool_succeeded:
                        print(f"⚠️ Error/Warning: {tool_result.get('error', tool_result.get('reason', tool_result.get('message')))}")
                    else:
                        print(f"✅ Result Summary: {self._summarize_result(tool_name, tool_result)}")

                # OBSERVE & REMEMBER: Record into working memory
                memory.add_step(tool_name, tool_args, tool_result, status=tool_status)

                # Feed tool result back into conversation for next reasoning loop
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call.get("id", f"call_{step_idx}"),
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "arguments": json.dumps(tool_args)
                        }
                    }]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", f"call_{step_idx}"),
                    "name": tool_name,
                    "content": json.dumps(tool_result)
                })

                # If duplicate or malformed invoice or approval denied, handle early completion
                if tool_name == "check_duplicate" and tool_result.get("is_duplicate"):
                    final_text = f"Halted: {tool_result.get('reason')} No action taken."
                    status = "DUPLICATE_BLOCKED"
                    break

                if tool_name == "read_invoice" and tool_result.get("is_malformed"):
                    final_text = f"Halted: Invoice is malformed ({tool_result.get('error')}). No ledger entry created."
                    status = "MALFORMED_BLOCKED"
                    break

                if tool_name == "request_user_approval" and not tool_result.get("approved"):
                    final_text = f"Halted: User denied approval for invoice processing."
                    status = "APPROVAL_REJECTED"
                    break

            if status in ["DUPLICATE_BLOCKED", "MALFORMED_BLOCKED", "APPROVAL_REJECTED"]:
                break

        if not finished and status == "COMPLETED":
            status = "FAILED"
            final_text = f"Stopped after reaching the maximum of {self.max_steps} steps before completing the task."

        # 4. INDEPENDENT VERIFICATION STEP
        verification = OutcomeVerifier.verify_execution(memory)
        if status == "COMPLETED" and not verification.get("passed"):
            status = "FAILED"
            final_text = (
                f"{final_text}\n\nOutcome not verified: "
                f"{verification.get('reason', 'No verifiable result was recorded.')}"
            ).strip()

        # 5. EVIDENCE & REPORT GENERATION
        evidence = {
            "task_objective": task,
            "status": status,
            "discovered_facts": memory.facts,
            "verification_audit": verification,
            "errors_resolved": len(memory.errors_encountered)
        }

        report_md = generate_report(
            task=task,
            status=status,
            summary=final_text or "Autonomous processing completed.",
            steps_executed=memory.get_all_steps_dict(),
            evidence=evidence
        )

        return {
            "success": verification.get("passed", False) and status == "COMPLETED",
            "status": status,
            "final_response": final_text,
            "steps": memory.get_all_steps_dict(),
            "facts": memory.facts,
            "verification": verification,
            "evidence": evidence,
            "report": report_md
        }

    def _llm_step(self, messages: List[Dict[str, Any]], task: str = "", memory: Optional[WorkingMemory] = None) -> Dict[str, Any]:
        """Make an LLM call via LiteLLM with native tool calling."""
        request_options = {
            "model": self.model_name,
            "messages": messages,
            "tools": self.tool_schemas,
            "tool_choice": "auto",
            "api_key": self._api_key_for_model(),
            "timeout": config.LLM_TIMEOUT_SECONDS
        }
        if "gemini-3" not in self.model_name.lower():
            request_options["temperature"] = 0.0

        max_attempts = max(1, config.MAX_RETRIES)
        for attempt in range(max_attempts):
            try:
                response = litellm.completion(**request_options)
                break
            except Exception as e:
                error_text = str(e).lower()
                exception_name = type(e).__name__.lower()
                is_rate_limited = "429" in error_text or "ratelimit" in exception_name or "rate limit reached" in error_text
                is_transient = is_rate_limited or "503" in error_text or "serviceunavailable" in exception_name
                if is_transient and attempt + 1 < max_attempts:
                    retry_delay = re.search(r"try again in\s+([\d.]+)\s*s", error_text)
                    if is_rate_limited and retry_delay:
                        wait_seconds = min(max(1, math.ceil(float(retry_delay.group(1)))), 60)
                    else:
                        wait_seconds = min(2 ** attempt, 4)
                    provider = self.model_name.split("/", 1)[0]
                    issue = "rate limited" if is_rate_limited else "temporarily unavailable"
                    print(f"⚠️ {provider} is {issue}; retrying in {wait_seconds}s ({attempt + 1}/{max_attempts - 1}).")
                    time.sleep(wait_seconds)
                    continue
                print(f"⚠️ LLM call error: {str(e)}. Falling back to autonomous heuristic engine.")
                decision = self._heuristic_step(task, memory)
                decision["_fallback_to_heuristic"] = True
                return decision

        msg = response.choices[0].message
        tool_calls = []

        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                fn = tc.function
                args = json.loads(fn.arguments) if isinstance(fn.arguments, str) else fn.arguments
                tool_calls.append({
                    "id": getattr(tc, "id", "call_1"),
                    "name": fn.name,
                    "arguments": args
                })

        return {
            "content": getattr(msg, "content", ""),
            "tool_calls": tool_calls
        }

    def _heuristic_step(self, task: str, memory: Optional[WorkingMemory]) -> Dict[str, Any]:
        """Autonomous heuristic decision engine for offline/deterministic execution."""
        task_lower = task.lower()
        steps = memory.steps if memory else []
        tools_called = [s.tool for s in steps]

        # A request to list invoice files is a read-only discovery task, not a
        # request to inspect pending ledger entries or process an invoice.
        if "invoice" in task_lower and any(w in task_lower for w in ["list", "show", "available"]):
            if "search_invoices" not in tools_called:
                return {
                    "tool_calls": [{
                        "name": "search_invoices",
                        "arguments": {"query": ""}
                    }]
                }
            search_step = next(s for s in reversed(steps) if s.tool == "search_invoices")
            files = search_step.result.get("files", [])
            if not files:
                return {"content": "No invoice files are currently available."}
            lines = ["Available invoice files:"]
            for invoice in files:
                lines.append(
                    f"- {invoice.get('invoice_number', invoice.get('file_name', 'Unknown'))}: "
                    f"{invoice.get('vendor_name', 'Unknown vendor')}, "
                    f"{invoice.get('invoice_date') or 'date unavailable'}, "
                    f"{invoice.get('total_amount') if invoice.get('total_amount') is not None else 'amount unavailable'}"
                )
            return {"content": "\n".join(lines)}

        # Scenario A: Analytical Query (e.g. "How many unpaid invoices...")
        if any(w in task_lower for w in ["how many", "count", "show all", "list", "total unpaid"]):
            if "query_database" not in tools_called:
                return {
                    "tool_calls": [{
                        "name": "query_database",
                        "arguments": {"query": "SELECT * FROM ledger WHERE status = 'pending'"}
                    }]
                }
            last_query = next((s.result for s in reversed(steps) if s.tool == "query_database"), {})
            count = last_query.get("count", 0)
            rows = last_query.get("rows", [])
            total = sum(r.get("amount", 0) for r in rows)
            return {"content": f"Found {count} pending invoices in the ledger totaling ${total:,.2f} USD."}

        # Scenario B: Invoice Processing Flow
        # Step 1: Search invoices
        if "search_invoices" not in tools_called:
            vendor_hint = ""
            for v in ["acme", "globex", "initech", "umbrella", "wayne"]:
                if v in task_lower:
                    vendor_hint = v
                    break
            return {
                "tool_calls": [{
                    "name": "search_invoices",
                    "arguments": {"vendor_name": vendor_hint, "query": task}
                }]
            }

        # Step 2: Read invoice file
        if "read_invoice" not in tools_called:
            search_step = next(s for s in steps if s.tool == "search_invoices")
            files = search_step.result.get("files", [])
            if not files:
                return {"content": "No matching invoice files were found in the directory."}
            target_file = files[0]["file_path"]
            return {
                "tool_calls": [{
                    "name": "read_invoice",
                    "arguments": {"file_path": target_file}
                }]
            }

        read_step = next(s for s in steps if s.tool == "read_invoice")
        inv_data = read_step.result
        if inv_data.get("is_malformed"):
            return {"content": f"Invoice is malformed: {inv_data.get('error')}"}

        inv_num = inv_data.get("invoice_number")
        amount = inv_data.get("total_amount", 0.0)
        vendor_name = inv_data.get("vendor_name", "")

        # Step 3: Check duplicate
        if "check_duplicate" not in tools_called:
            return {
                "tool_calls": [{
                    "name": "check_duplicate",
                    "arguments": {"invoice_number": inv_num}
                }]
            }

        dup_step = next(s for s in steps if s.tool == "check_duplicate")
        if dup_step.result.get("is_duplicate"):
            return {"content": f"Invoice {inv_num} is a duplicate. Halted."}

        # Step 4: Query vendor in DB (with fuzzy fallback)
        if "query_database" not in tools_called:
            return {
                "tool_calls": [{
                    "name": "query_database",
                    "arguments": {"query": "SELECT * FROM vendors"}
                }]
            }

        db_step = next(s for s in reversed(steps) if s.tool == "query_database")
        if not db_step.result.get("success"):
            return {
                "tool_calls": [{
                    "name": "query_database",
                    "arguments": {"query": "SELECT * FROM vendors"}
                }]
            }
        vendors = db_step.result.get("rows", [])
        vendor_key = vendor_name.strip().casefold()
        matched_vendors = [
            vendor for vendor in vendors
            if vendor_key and (
                vendor_key == str(vendor.get("name", "")).casefold()
                or vendor_key.startswith(str(vendor.get("name", "")).casefold())
                or str(vendor.get("name", "")).casefold().startswith(vendor_key)
                or vendor_key.split()[:1] == str(vendor.get("name", "")).casefold().split()[:1]
            )
        ]
        if not matched_vendors:
            return {"content": f"Vendor '{vendor_name}' could not be identified in company database."}
        vendor_id = matched_vendors[0]["id"]

        # Step 5: Approval if > $1000
        if amount > config.APPROVAL_THRESHOLD and "request_user_approval" not in tools_called:
            return {
                "tool_calls": [{
                    "name": "request_user_approval",
                    "arguments": {
                        "question": f"Invoice {inv_num} for ${amount:,.2f} exceeds ${config.APPROVAL_THRESHOLD:,.2f}. Approve ledger entry?",
                        "context": {"vendor": vendor_name, "amount": amount, "invoice": inv_num}
                    }
                }]
            }

        # Step 6: Insert into ledger
        if "insert_ledger_entry" not in tools_called:
            approved = True if amount <= config.APPROVAL_THRESHOLD else any(s.result.get("approved") for s in steps if s.tool == "request_user_approval")
            if not approved:
                return {"content": "User denied approval for ledger entry."}
            return {
                "tool_calls": [{
                    "name": "insert_ledger_entry",
                    "arguments": {
                        "invoice_number": inv_num,
                        "vendor_id": vendor_id,
                        "amount": amount,
                        "currency": inv_data.get("currency", "USD"),
                        "due_date": inv_data.get("due_date"),
                        "po_number": inv_data.get("po_number"),
                        "notes": inv_data.get("notes"),
                        "file_path": inv_data.get("file_path"),
                        "user_approved": approved
                    }
                }]
            }

        # Step 7: Verify ledger entry
        if "verify_ledger_entry" not in tools_called:
            ledger_step = next(s for s in steps if s.tool == "insert_ledger_entry")
            entry_id = ledger_step.result.get("ledger_entry_id")
            return {
                "tool_calls": [{
                    "name": "verify_ledger_entry",
                    "arguments": {
                        "ledger_entry_id": entry_id,
                        "expected_invoice_number": inv_num,
                        "expected_amount": amount
                    }
                }]
            }

        # Step 8: Done!
        return {
            "content": f"Invoice {inv_num} for {vendor_name} (${amount:,.2f}) successfully processed, entered into accounting ledger, and verified."
        }

    def _check_api_credentials(self) -> bool:
        """Check if environment variables contain valid keys for the configured model."""
        if not LITELLM_AVAILABLE:
            return False
        return bool(self._api_key_for_model())

    def _api_key_for_model(self) -> Optional[str]:
        """Return the credential matching this model's provider."""
        model = self.model_name.lower()
        if model.startswith("groq/"):
            return os.getenv("GROQ_API_KEY")
        if model.startswith("gemini/") or "gemini" in model:
            return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if model.startswith("anthropic/") or "claude" in model:
            return os.getenv("ANTHROPIC_API_KEY")
        if model.startswith("openai/") or "gpt" in model:
            return os.getenv("OPENAI_API_KEY")
        return None

    def _summarize_result(self, tool_name: str, result: Dict[str, Any]) -> str:
        """Produce a one-line human-readable summary of tool execution."""
        if tool_name == "search_invoices":
            return f"Found {result.get('count', 0)} matching file(s)."
        if tool_name == "read_invoice":
            return f"Parsed invoice {result.get('invoice_number')} | Vendor: {result.get('vendor_name')} | Amount: ${result.get('total_amount', 0):,.2f}"
        if tool_name == "query_database":
            return f"Returned {result.get('count', 0)} database row(s)."
        if tool_name == "check_duplicate":
            return f"Duplicate: {result.get('is_duplicate', False)}"
        if tool_name == "request_user_approval":
            return f"Approved: {result.get('approved', False)}"
        if tool_name == "insert_ledger_entry":
            return f"Created Ledger Entry #{result.get('ledger_entry_id')} for ${result.get('amount', 0):,.2f}"
        if tool_name == "verify_ledger_entry":
            return f"Outcome Verified: {result.get('verified', False)}"
        return "Executed."
