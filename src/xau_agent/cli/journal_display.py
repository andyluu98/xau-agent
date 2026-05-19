"""Render trade journal CSV thành rich table."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xau_agent.journal import TRADES_CSV, read_trades

console = Console()


def _color_side(side: str) -> str:
    return "green" if side == "BUY" else "red" if side == "SELL" else "yellow"


def _color_judge(decision: str) -> str:
    return "green" if decision == "GO" else "yellow"


def _color_mode(dry_run_str: str) -> str:
    return "[yellow]DRY[/yellow]" if dry_run_str.lower() == "true" else "[bold red]LIVE[/bold red]"


def render_recent(limit: int = 10) -> None:
    rows = read_trades(limit)
    if not rows:
        console.print(Panel(
            f"[dim]Chưa có lệnh nào trong sổ tay.[/dim]\n"
            f"File: [yellow]{TRADES_CSV}[/yellow]\n"
            f"Sẽ tự tạo khi bot gửi lệnh đầu tiên (gồm cả dry-run).",
            title="[bold]Trade Journal[/bold]", border_style="dim",
        ))
        return

    t = Table(
        title=f"Trade Journal — {len(rows)} lệnh gần nhất",
        show_header=True, header_style="bold cyan", expand=False,
    )
    t.add_column("Time", style="dim")
    t.add_column("Side", justify="center")
    t.add_column("Entry/SL/TP", justify="right")
    t.add_column("Lot", justify="right")
    t.add_column("Judge", justify="center")
    t.add_column("Macro", justify="center", style="cyan")
    t.add_column("User", justify="center")
    t.add_column("Mode")

    for r in rows:
        side = r.get("side", "")
        decision = r.get("judge_decision", "")
        bias = r.get("macro_bias", "")
        strength = r.get("macro_strength", "")
        macro_str = f"{bias} {strength}" if bias else "—"
        entry = float(r.get("entry") or 0)
        sl = float(r.get("sl") or 0)
        tp = float(r.get("tp") or 0)
        prices = f"{entry:.2f} / {sl:.2f} / {tp:.2f}"
        judge_str = (
            f"[{_color_judge(decision)}]{decision}[/{_color_judge(decision)}] "
            f"({r.get('judge_confidence', '0')})"
        )
        t.add_row(
            r.get("timestamp", "")[:16].replace("T", " "),
            f"[{_color_side(side)}]{side}[/{_color_side(side)}]",
            prices,
            r.get("lot", ""),
            judge_str,
            macro_str,
            r.get("user_decision") or "—",
            _color_mode(r.get("dry_run", "True")),
        )
    console.print(t)

    # Summary footer
    total = len(read_trades(0))
    gos = sum(1 for r in rows if r.get("judge_decision") == "GO")
    skips = sum(1 for r in rows if r.get("judge_decision") == "SKIP")
    placed = sum(1 for r in rows if r.get("user_decision") == "YES")
    console.print(Panel(
        f"Tổng trong sổ: [bold]{total}[/bold]  •  GO: [green]{gos}[/green]  •  "
        f"SKIP: [yellow]{skips}[/yellow]  •  User APPROVED: [bold]{placed}[/bold]",
        border_style="dim",
    ))
