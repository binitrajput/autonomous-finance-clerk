"""Command-line interface for the Autonomous Finance Clerk."""

import sys
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

import config
from agent.core import AutonomousAgent
from company_system.setup_db import initialize_database

console = Console()


def print_banner():
    banner_text = """[bold cyan]🤖 Autonomous AI Task Worker — Finance & Operations Clerk[/bold cyan]
[dim]ReAct Planning Loop • Human-in-the-Loop Safety • Verification • Self-Healing[/dim]"""
    console.print(Panel(banner_text, border_style="cyan"))


def main():
    parser = argparse.ArgumentParser(description="Autonomous AI Task Worker for Finance")
    parser.add_argument("--task", type=str, help="Natural language task prompt", default=None)
    parser.add_argument("--reset-db", action="store_true", help="Reset and seed company database")
    parser.add_argument("--model", type=str, default=None, help="LLM model override")
    args = parser.parse_args()

    # Ensure database exists
    initialize_database()

    print_banner()

    agent = AutonomousAgent(model_name=args.model)

    task = args.task
    if not task:
        console.print("\n[bold yellow]Enter your natural language task below:[/bold yellow]")
        console.print("[dim]Example: 'Process the latest invoice from Acme Corp and enter it into our system.'[/dim]")
        try:
            task = console.input("\n[bold green]Task ❯ [/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Exiting.[/dim]")
            sys.exit(0)

    if not task:
        console.print("[red]No task provided. Exiting.[/red]")
        sys.exit(1)

    result = agent.run(task, verbose=True)

    # Display Execution Summary Table
    table = Table(title="📊 Execution Summary & Trace", border_style="bright_blue")
    table.add_column("Step", justify="center", style="cyan")
    table.add_column("Tool", style="magenta")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="dim")

    for s in result["steps"]:
        status_icon = "[green]✅ SUCCESS[/green]" if s["status"] == "success" else f"[yellow]⚠️ {s['status']}[/yellow]"
        summary_txt = str(s.get("result", {}).get("message", s.get("result", {}).get("error", "")))
        if not summary_txt:
            summary_txt = f"Ran {s['tool']}"
        table.add_row(str(s["step"]), s["tool"], status_icon, summary_txt[:70])

    console.print("\n")
    console.print(table)

    # Verification Badge
    if result["verification"].get("passed"):
        console.print(Panel("[bold green]✅ OUTCOME VERIFICATION PASSED — Database state matches expected goal![/bold green]", border_style="green"))
    else:
        console.print(Panel(f"[bold yellow]⚠️ Verification Note: {result['verification'].get('reason')}[/bold yellow]", border_style="yellow"))

    # Print Final Markdown Report
    console.print("\n[bold cyan]📄 Audit Report Generated:[/bold cyan]\n")
    console.print(Markdown(result["report"]))


if __name__ == "__main__":
    main()
