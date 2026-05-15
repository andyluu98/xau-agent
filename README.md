# xau-agent

Semi-auto AI trading agent cho **XAUUSD** scalp khung **M15** trên MT5 Exness.
Trend filter ở **H1 + H4**, reasoning bằng **DeepSeek**, news brief bằng **Tavily**.
Mọi lệnh phải bạn duyệt qua CLI trước khi đặt.

## Triết lý

- **Bạn là người chịu trách nhiệm cuối.** Bot chỉ đề xuất + giải thích, bạn gõ `y` mới đặt lệnh.
- **`--dry-run` mặc định.** Bot in lệnh ra console, không gửi MT5. Bật live khi đã quen.
- **Không yfinance, không Alpha Vantage.** Giá lấy thẳng từ MT5, tin từ Tavily.

## Cài đặt

```bash
uv venv && source .venv/Scripts/activate    # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
cp .env.example .env                         # rồi điền API key + MT5 creds
```

## Chạy

```bash
xau-agent run                 # dry-run mặc định
xau-agent run --live          # tắt dry-run, gửi lệnh thật vào MT5
xau-agent scan-once           # quét 1 lần rồi thoát (dùng để test)
```

## Luồng 1 chu kỳ

```
M15 đóng nến
  └─ MT5 fetcher kéo OHLCV: M15 (200 nến), H1 (200), H4 (200)
       └─ trend.py: H4 EMA50 vs EMA200 + H1 EMA50 vs EMA200
            └─ Nếu H1 ≠ H4 chiều → SKIP (in lý do, không gọi LLM)
       └─ setup.py: M15 RSI + MACD + BB + ATR → entry hint
            └─ Nếu không có setup → SKIP
       └─ tavily.py: lấy 5 tin gold/Fed/USD gần nhất (cache 1h)
       └─ agents.py: 3 lượt DeepSeek (bull / bear / judge)
       └─ cli/display.py: in panel: setup + reasoning + Entry/SL/TP/Lot
       └─ cli/prompt.py: [y]es / [n]o / [s]kip ?
            └─ y → executor.py đặt lệnh MT5 (hoặc in nếu --dry-run)
            └─ n / s → log lý do, không trade
```

## Cảnh báo

- Tool **nghiên cứu + hỗ trợ ra quyết định**, không phải khuyến nghị đầu tư.
- Paper trade tối thiểu 2 tuần trước khi bật `--live`.
- AI có thể sai. Thị trường có thể black swan.

## Cấu trúc

Xem `src/xau_agent/` — mỗi module dưới 200 LOC, tách rõ theo concern (MT5 / analysis / llm / news / cli).
