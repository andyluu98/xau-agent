"""Render Day Plan output dưới dạng rich panel + table."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xau_agent.llm.dayplan import DayPlan

console = Console()


def _bias_color(bias: str) -> str:
    return {"BULL": "green", "BEAR": "red", "RANGE": "yellow"}.get(bias.upper(), "white")


def render_dayplan(plan: DayPlan, current_price: float, symbol: str) -> None:
    """In day plan đầy đủ: bias, levels, scenarios, news, risk note."""
    color = _bias_color(plan.day_bias)

    # 1) Header — bias
    header = (
        f"[bold {color}]{plan.day_bias}[/bold {color}]  "
        f"strength={plan.bias_strength}/10  "
        f"symbol={symbol}  current={current_price:.2f}"
    )
    console.print(Panel(header, title="[bold]📅 KẾ HOẠCH NGÀY[/bold]", border_style=color))

    # 2) Macro context (raw text từ Macro Analyst)
    if plan.macro_text:
        console.print(Panel(plan.macro_text.strip(),
                            title="[cyan]Macro / Tech Analyst[/cyan]", border_style="cyan"))

    # 3) Key levels — table
    if plan.key_levels:
        t = Table(title="Mức giá quan trọng", show_header=True, header_style="bold")
        t.add_column("Price", justify="right")
        t.add_column("Cách giá hiện tại", justify="right")
        t.add_column("Ghi chú")
        for lvl in sorted(plan.key_levels, key=lambda l: l.price, reverse=True):
            dist = lvl.price - current_price
            arrow = "↑" if dist > 0 else ("↓" if dist < 0 else "·")
            t.add_row(f"{lvl.price:.2f}", f"{arrow} {abs(dist):.2f}", lvl.note)
        console.print(t)

    # 4) Scenarios — table
    if plan.scenarios:
        t = Table(title="Kịch bản đa nhánh", show_header=True, header_style="bold magenta")
        t.add_column("#", width=3)
        t.add_column("Điều kiện (trigger)")
        t.add_column("Hành động (action)")
        t.add_column("Rủi ro chính", style="dim")
        for i, sc in enumerate(plan.scenarios, 1):
            t.add_row(str(i), sc.trigger, sc.action, sc.risk)
        console.print(t)

    # 5) News risk + daily risk note
    if plan.news_risks:
        console.print(Panel(plan.news_risks.strip(),
                            title="[yellow]⚠ News risks trong ngày[/yellow]",
                            border_style="yellow"))
    if plan.daily_risk_note:
        console.print(Panel(plan.daily_risk_note.strip(),
                            title="[bold]🛡 Risk note cho ngày[/bold]",
                            border_style="blue"))

    # 6) Footer hint
    console.print(Panel(
        "[dim]Plan này KHÔNG phải lệnh để vào — chỉ là bản đồ. "
        "Khi sẵn sàng vào, dùng [yellow]xau-agent hunt[/yellow] hoặc "
        "[yellow]xau-agent plan-now[/yellow] (có nhìn quá khứ).[/dim]",
        border_style="dim",
    ))
