"""Rich-based console rendering for proposals + debate."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def banner(symbol: str, entry_tf: str, trend_tfs: list[str], dry_run: bool) -> None:
    mode = "[bold yellow]DRY-RUN[/bold yellow]" if dry_run else "[bold red]LIVE[/bold red]"
    console.print(
        Panel.fit(
            f"[bold]xau-agent[/bold]  symbol={symbol}  entry={entry_tf}  trend={'+'.join(trend_tfs)}  mode={mode}",
            border_style="cyan",
        )
    )


def render_skip(reason: str, trend_note: str = "") -> None:
    body = Text(reason, style="dim")
    if trend_note:
        body.append(f"\n{trend_note}", style="dim italic")
    console.print(Panel(body, title="[grey]SKIP[/grey]", border_style="grey50"))


def render_trend(per_tf: list) -> None:
    """per_tf: list of TFTrend dataclasses (with .tf, .direction, .note)."""
    t = Table(title="Multi-TF trend", show_header=True, header_style="bold")
    t.add_column("TF"); t.add_column("Direction"); t.add_column("Detail")
    for row in per_tf:
        color = {"UP": "green", "DOWN": "red", "FLAT": "yellow"}[row.direction]
        t.add_row(row.tf, f"[{color}]{row.direction}[/{color}]", row.note)
    console.print(t)


def render_tv_consensus(tv_map: dict) -> None:
    """Render bảng consensus 26-indicator từ TradingView (free public widget).
    tv_map: {"M15": TVConsensus, "H1": TVConsensus, "H4": TVConsensus}."""
    if not tv_map:
        return
    t = Table(title="TradingView 26-indicator consensus", show_header=True, header_style="bold magenta")
    t.add_column("TF"); t.add_column("Recommendation"); t.add_column("Buy", justify="right")
    t.add_column("Sell", justify="right"); t.add_column("Neutral", justify="right")
    t.add_column("Oscillators", style="dim"); t.add_column("Moving Avg", style="dim")
    for tf, c in tv_map.items():
        if "STRONG_BUY" in c.recommendation:
            col = "bright_green"
        elif "BUY" in c.recommendation:
            col = "green"
        elif "STRONG_SELL" in c.recommendation:
            col = "bright_red"
        elif "SELL" in c.recommendation:
            col = "red"
        else:
            col = "yellow"
        t.add_row(
            tf, f"[{col}]{c.recommendation}[/{col}]",
            str(c.buy), str(c.sell), str(c.neutral),
            c.oscillators_reco, c.moving_averages_reco,
        )
    console.print(t)


def render_proposal(setup, result, news: str, lot: float) -> None:
    """Render full 6-vai debate result. `result` là DebateResult."""
    color = "green" if setup.side == "BUY" else "red"
    head = (
        f"[bold {color}]{setup.side}[/bold {color}]  "
        f"Entry={setup.entry:.2f}  SL={setup.sl:.2f}  TP={setup.tp:.2f}  "
        f"Lot={lot}  ATR={setup.atr:.2f}  RSI={setup.rsi:.1f}  MACDh={setup.macd_hist:+.4f}"
    )
    console.print(Panel(head, title="[bold]Setup[/bold]", border_style=color))

    console.print(Panel(result.macro.strip(), title="[cyan]1. Macro / Tech Analyst[/cyan]", border_style="cyan"))
    console.print(Panel(result.bull.strip(), title="[green]2. Bull[/green]", border_style="green"))
    console.print(Panel(result.bear.strip(), title="[red]3. Bear[/red]", border_style="red"))
    console.print(Panel(result.risk_aggressive.strip(),
                        title="[orange3]4. Risk Aggressive[/orange3]", border_style="orange3"))
    console.print(Panel(result.risk_neutral.strip(),
                        title="[yellow]5. Risk Neutral[/yellow]", border_style="yellow"))
    console.print(Panel(result.risk_conservative.strip(),
                        title="[blue]6. Risk Conservative[/blue]", border_style="blue"))

    if news:
        console.print(Panel(news.strip(), title="News brief", border_style="dim"))

    v = result.verdict
    vcolor = "green" if v.decision == "GO" else "yellow"
    console.print(Panel(
        f"[bold {vcolor}]{v.decision}[/bold {vcolor}]  confidence={v.confidence}  {v.summary}",
        title="[bold]Judge (final)[/bold]", border_style=vcolor,
    ))


def render_execution_plan(plan, default_lot: float) -> None:
    """Render Execution Trader output (vai #7, chỉ chạy khi Judge GO)."""
    final_lot = round(default_lot * plan.lot_multiplier, 2)
    body = (
        f"[bold]Entry strategy:[/bold] {plan.entry_strategy}\n"
        f"[bold]Entry price hint:[/bold] {plan.entry_price_hint:.2f}\n"
        f"[bold]Lot multiplier:[/bold] {plan.lot_multiplier}×  → final lot = {final_lot}\n"
        f"[bold]Hold rule:[/bold] {plan.hold_rule}\n"
        f"[bold]Notes:[/bold] {plan.notes}"
    )
    console.print(Panel(body, title="[bold magenta]7. Execution Trader[/bold magenta]", border_style="magenta"))


def render_result(ok: bool, message: str, ticket=None, price=None) -> None:
    style = "green" if ok else "red"
    body = f"ok={ok}  ticket={ticket}  price={price}  msg={message}"
    console.print(Panel(body, title="[bold]Order result[/bold]", border_style=style))
