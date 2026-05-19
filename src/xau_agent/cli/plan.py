"""In-CLI plan summary. Hiển thị toàn bộ chiến lược săn vàng gọn trong 1 màn hình terminal."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def show_plan() -> None:
    console.print(Panel.fit(
        "[bold yellow]xau-agent[/bold yellow] — săn vàng XAUUSD khung M15 trên MT5\n"
        "[dim]Bot phân tích → bạn duyệt y/n → bot đặt lệnh (hoặc dry-run)[/dim]",
        border_style="cyan",
    ))

    # === 3 lệnh chính ===
    t = Table(title="3 lệnh chính", show_header=True, header_style="bold cyan")
    t.add_column("Lệnh", style="yellow")
    t.add_column("Bot làm gì")
    t.add_column("Khi nào dùng", style="dim")
    t.add_row("hunt", "Săn 1 lần ngay (gọi AI + TV consensus, hỏi y/n)", "Muốn biết 'bây giờ có nên trade?'")
    t.add_row("scan-once", "Quét 1 lần (chỉ vào lệnh khi setup đẹp)", "Tiết kiệm quota AI")
    t.add_row("run", "Loop liên tục mỗi 15 phút", "Để bot canh đêm/giờ làm việc")
    t.add_row("tv", "In TV 26-indicator consensus (free, no MT5)", "Xem 26 indicator vote nhanh")
    t.add_row("zones", "In vùng MUA/BÁN (S/R, EMA, swing, round)", "Tìm vùng entry/exit")
    t.add_row("plan", "In chiến lược này", "Đọc lại cách bot hoạt động")
    t.add_row("journal", "In sổ tay CSV — lệnh gần nhất + Judge/User decision", "Review bot performance")
    console.print(t)

    # === 6 bước trong hunt ===
    s = Table(title="Lệnh 'hunt' đi qua 6 bước", show_header=True, header_style="bold cyan")
    s.add_column("#", style="yellow", width=3)
    s.add_column("Bước", style="bold")
    s.add_column("Thời gian", style="dim", width=8)
    s.add_column("Mục đích")
    s.add_row("1", "MT5 connect", "~1s", "Lấy info account đang mở")
    s.add_row("2", "Fetch giá M15+H1+H4", "~2s", "200 nến mỗi khung")
    s.add_row("3", "Kiểm xu hướng H1+H4", "~1s", "Khác chiều → SKIP, không gọi AI")
    s.add_row("4", "Lấy news Tavily", "~2s", "Vàng + Fed + CPI + NFP (cache 1h)")
    s.add_row("5", "3 AI tranh luận", "~8s", "Bull cãi ủng hộ + Bear cãi phản đối + Judge quyết")
    s.add_row("6", "Hỏi bạn y/n/s", "tùy", "Chỉ hỏi khi Judge nói GO")
    console.print(s)

    # === Cách bot vào lệnh ===
    e = Table(title="Cách bot tính Entry / SL / TP", show_header=True, header_style="bold cyan")
    e.add_column("Giá trị", style="yellow")
    e.add_column("Công thức")
    e.add_column("Ví dụ (ATR=13)", style="dim")
    e.add_row("Entry", "Giá đóng cửa nến M15 vừa đóng", "4556.70")
    e.add_row("Stop Loss", "Entry ± 1.5 × ATR", "4577.10 (SELL) / 4536.30 (BUY)")
    e.add_row("Take Profit", "Entry ± 2.5 × ATR", "4522.20 (SELL) / 4591.20 (BUY)")
    e.add_row("Risk:Reward", "2.5 / 1.5 = 1.67", "Thắng 4/10 lệnh hòa vốn, 5/10 có lời")
    console.print(e)

    # === Khi nào bot BỎ QUA ===
    k = Table(title="Bot BỎ QUA (không gọi AI, tiết kiệm quota)", show_header=True, header_style="bold red")
    k.add_column("Lý do", style="red")
    k.add_column("Vì sao")
    k.add_row("H1 và H4 khác chiều", "Xu hướng không rõ, scalp dễ chết")
    k.add_row("Đã có 1 lệnh đang mở", "Tránh chồng lệnh (max_open_trades=1)")
    k.add_row("Judge nói SKIP", "AI không đủ tự tin → không quấy rầy bạn")
    k.add_row("[dim](tương lai)[/dim] Đã 4 lệnh/ngày", "[dim]Tránh overtrade[/dim]")
    k.add_row("[dim](tương lai)[/dim] Lỗ 3%/ngày", "[dim]Bảo vệ tài khoản[/dim]")
    k.add_row("[dim](tương lai)[/dim] Sắp có FOMC/CPI/NFP", "[dim]Tránh biến động sốc[/dim]")
    console.print(k)

    # === 4 giai đoạn rollout ===
    g = Table(title="4 giai đoạn từ tập đến tiền thật", show_header=True, header_style="bold green")
    g.add_column("Phase", style="yellow", width=8)
    g.add_column("Thời gian", width=10)
    g.add_column("Làm gì")
    g.add_column("Tiền thật?", style="bold")
    g.add_row("1. Tập", "Tuần 1", "Gõ 'hunt' nhiều lần, đọc AI nói gì, không đặt lệnh", "[green]Không[/green]")
    g.add_row("2. Canh", "Tuần 2-3", "'run' loop dry-run, ngó proposal y/n, ghi sổ", "[green]Không[/green]")
    g.add_row("3. Demo", "Tuần 4-5", "'run --live' trên Exness DEMO (tiền giả)", "[yellow]Giả[/yellow]")
    g.add_row("4. Cent", "Tuần 6+", "'run --live' trên cent thật, lot 0.01, max DD 10%", "[red]Thật[/red]")
    console.print(g)

    # === Hiện trạng + Khuyến nghị ===
    console.print(Panel(
        "[bold]Đang ở:[/bold] Phase 1 (Tập)  •  DRY_RUN=true  •  Symbol=XAUUSDc  •  Lot=0.01\n"
        "[bold]Bước tiếp:[/bold] gõ [yellow]xau-agent hunt[/yellow] vài lần, đọc panel, hiểu cách bot suy nghĩ.\n"
        "Khi đã quen → 'run' để bot tự canh, vẫn dry-run.\n"
        "Khi tự tin (≥30 lệnh giả lập thắng ≥50%) → demo Exness real với --live.",
        title="[bold]Trạng thái hôm nay[/bold]",
        border_style="cyan",
    ))

    # === Tính năng còn thiếu ===
    f = Table(title="Còn thiếu — sẽ thêm khi bạn yêu cầu", show_header=True, header_style="bold magenta")
    f.add_column("#", style="yellow", width=3)
    f.add_column("Tính năng")
    f.add_column("Lợi ích")
    f.add_row("1", "Lọc giờ trade (chỉ London+NY: 14h-3h VN)", "Né phiên Á lình xình, tiết kiệm quota")
    f.add_row("2", "Né tin sốc (FOMC/CPI/NFP trong 1h)", "Tránh biến động hoang dại")
    f.add_row("3", "Tự tính lot theo % rủi ro (thay vì cố định 0.01)", "Lệnh nhỏ khi ATR rộng, an toàn hơn")
    f.add_row("4", "Sổ tay CSV (log mỗi lệnh để cuối tuần review)", "Biết bot có thực sự hiệu quả")
    f.add_row("5", "Kill switch lỗ 3%/ngày → tự tắt", "Tránh tilt, bảo vệ vốn")
    f.add_row("6", "Trailing SL (lệnh có lãi → dời SL về hòa)", "Khóa lợi nhuận, giảm rủi ro")
    console.print(f)

    console.print(Panel(
        "Đọc full plan: [yellow]plans/260516-0009-m15-scalp-strategy/plan.md[/yellow]\n"
        "Repo: [yellow]https://github.com/andyluu98/xau-agent[/yellow]",
        border_style="dim",
    ))
