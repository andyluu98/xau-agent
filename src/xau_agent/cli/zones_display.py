"""Render zones list as rich table: vùng MUA (dưới giá) + vùng BÁN (trên giá)."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from xau_agent.analysis.zones import Zone

console = Console()

_KIND_LABEL = {
    "swing_high": "Đỉnh swing",
    "swing_low": "Đáy swing",
    "ema": "EMA",
    "round": "Mốc tròn",
    "recent_high": "Đỉnh 7d",
    "recent_low": "Đáy 7d",
}


def render_zones(symbol: str, current_price: float, zones: list[Zone], top_n: int = 6) -> None:
    above = sorted([z for z in zones if z.distance > 0], key=lambda z: z.distance)[:top_n]
    below = sorted([z for z in zones if z.distance < 0], key=lambda z: -z.distance)[:top_n]

    console.print(Panel.fit(
        f"[bold]{symbol}[/bold]  giá hiện tại: [yellow]{current_price:.2f}[/yellow]",
        border_style="cyan",
    ))

    # === Vùng BÁN (kháng cự — phía trên giá) ===
    t_sell = Table(
        title="[bold red]VÙNG BÁN[/bold red] — kháng cự (giá có thể bật xuống khi chạm)",
        show_header=True, header_style="bold red",
    )
    t_sell.add_column("Giá", style="red", justify="right")
    t_sell.add_column("Cách giá", justify="right")
    t_sell.add_column("Loại")
    t_sell.add_column("Khung", style="dim", width=6)
    t_sell.add_column("Ghi chú", style="dim")
    for z in above:
        t_sell.add_row(
            f"{z.price:.2f}",
            f"+{z.distance:.2f}",
            _KIND_LABEL.get(z.kind, z.kind),
            z.tf,
            z.note,
        )
    console.print(t_sell)

    # === Vùng MUA (hỗ trợ — phía dưới giá) ===
    t_buy = Table(
        title="[bold green]VÙNG MUA[/bold green] — hỗ trợ (giá có thể bật lên khi chạm)",
        show_header=True, header_style="bold green",
    )
    t_buy.add_column("Giá", style="green", justify="right")
    t_buy.add_column("Cách giá", justify="right")
    t_buy.add_column("Loại")
    t_buy.add_column("Khung", style="dim", width=6)
    t_buy.add_column("Ghi chú", style="dim")
    for z in below:
        t_buy.add_row(
            f"{z.price:.2f}",
            f"{z.distance:.2f}",
            _KIND_LABEL.get(z.kind, z.kind),
            z.tf,
            z.note,
        )
    console.print(t_buy)

    console.print(Panel(
        "[bold]Cách dùng:[/bold]\n"
        "• [red]Vùng BÁN[/red]: nếu giá lên đến → cân nhắc SELL (đặt SL trên vùng đó vài pip)\n"
        "• [green]Vùng MUA[/green]: nếu giá xuống đến → cân nhắc BUY (đặt SL dưới vùng đó vài pip)\n"
        "• Vùng có [bold]nhiều khung[/bold] hội tụ (EMA + swing + round) → mạnh hơn\n"
        "• Đây là [bold]gợi ý vùng[/bold], không phải tín hiệu vào lệnh — vẫn cần xác nhận từ [yellow]xau-agent hunt[/yellow]",
        title="Hướng dẫn", border_style="dim",
    ))
