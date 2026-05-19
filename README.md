# xau-agent

**AI trading agent bán tự động** cho **XAUUSD** scalp khung **M15** trên MT5 Exness.

- Reasoning: **6 AI vai diễn tranh luận** (DeepSeek) — Macro · Bull · Bear · 3 Risk Debator · Judge · Execution Trader
- Filter xu hướng: **H1 + H4** (EMA50/200)
- Cross-check: **TradingView 26-indicator consensus** (free, không cần TradingView paid)
- News: **Tavily** (Fed, CPI, NFP, DXY)
- Giá thật từ **MT5** (không yfinance, không Alpha Vantage)
- Mọi lệnh **phải bạn duyệt Y/N** trước khi gửi MT5

> ⚠️ Tool **NGHIÊN CỨU + HỖ TRỢ RA QUYẾT ĐỊNH**, không phải khuyến nghị đầu tư. Paper trade tối thiểu 2 tuần trước khi bật `--live`.

---

## Yêu cầu

- **Python 3.12+** (pandas-ta mới yêu cầu)
- **uv** (https://docs.astral.sh/uv/) — Python package manager
- **MT5 terminal** đang chạy với account Exness (demo hoặc real)
- **DeepSeek API key** — https://platform.deepseek.com (nạp tối thiểu $1)
- **Tavily API key** — https://tavily.com (free 1000 req/tháng)
- **Windows / macOS / Linux** (MT5 chính thức chỉ Windows; Linux/macOS dùng Wine)

---

## Cài đặt (5 phút)

### 1. Clone

```bash
git clone https://github.com/andyluu98/xau-agent.git
cd xau-agent
```

### 2. Tạo venv + install deps

```bash
uv venv --python 3.12
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

uv pip install -e ".[dev]"
```

### 3. Tạo `.env`

```bash
cp .env.example .env
```

Mở `.env` bằng editor, điền 5 thứ:

| Biến | Lấy ở đâu |
|---|---|
| `MT5_LOGIN` | MT5 terminal → File → Login (số tài khoản) |
| `MT5_PASSWORD` | mật khẩu trade (không phải email password) |
| `MT5_SERVER` | server name (vd: `Exness-MT5Trial7`, `Exness-MT5Real25`) |
| `DEEPSEEK_API_KEY` | https://platform.deepseek.com → API Keys |
| `TAVILY_API_KEY` | https://tavily.com → Dashboard |

**Để trống `MT5_LOGIN=0`** nếu muốn bot attach vào MT5 đã login sẵn (không re-login).

### 4. Bật AutoTrading trong MT5

Nếu muốn bot **gửi/sửa lệnh** thật (không chỉ dry-run):
- MT5 → Tools → Options → tab Expert Advisors → check **"Allow algorithmic trading"**
- Hoặc click nút **"Algo Trading"** trên toolbar → 🟢 xanh

### 5. Verify

```bash
pytest -v                    # phải pass 7/7
xau-agent plan               # in chiến lược (không cần MT5)
xau-agent tv                 # in TradingView consensus (không cần MT5)
```

Nếu cả 3 OK → setup xong, đi tiếp.

---

## 6 lệnh CLI

| Lệnh | Bot làm gì | Cần MT5? | Cần LLM? |
|---|---|---|---|
| `xau-agent plan` | In chiến lược + 6 vai + hướng dẫn | ❌ | ❌ |
| `xau-agent tv` | In TV 26-indicator consensus (M15/H1/H4) | ❌ | ❌ |
| `xau-agent zones` | In vùng MUA/BÁN (S/R + EMA + swing + round) | ✅ | ❌ |
| `xau-agent hunt` | **Săn 1 lần** — 6 vai tranh luận + đề xuất Y/N | ✅ | ✅ |
| `xau-agent scan-once` | Quét 1 lần với gate strict (chỉ trade setup đẹp) | ✅ | ✅ |
| `xau-agent run` | Loop liên tục mỗi M15 close | ✅ | ✅ |

**Mặc định mọi lệnh trade ở chế độ `DRY_RUN=true`** — bot chỉ in lệnh, không gửi MT5.
Để gửi thật: thêm `--live`. Ví dụ: `xau-agent hunt --live`.

---

## Luồng 1 phiên `hunt`

```
MT5 connect (1s)
  └─ Fetch OHLCV M15+H1+H4 (2s)
       └─ Trend filter EMA50/200 H1+H4 — khác chiều → SKIP
            └─ Tavily news brief (cache 1h)
            └─ TradingView 26-indicator vote (cache 5min)
            └─ Build setup M15 (Entry/SL/TP từ ATR)
            └─ 6-vai LLM debate (~15s):
                 1. Macro/Tech Analyst → context BIAS+STRENGTH
                 2. Bull (advocate FOR)
                 3. Bear (advocate AGAINST)
                 4. Risk Aggressive
                 5. Risk Neutral
                 6. Risk Conservative
                ─── Judge → GO/SKIP+confidence+summary
            └─ Nếu Judge GO → Execution Trader (vai #7):
                 Thiết kế chi tiết: entry timing, lot multiplier, hold rule
            └─ Prompt Y/N/S
                 y → executor.place() (hoặc log nếu dry-run)
```

**Cost mỗi phiên:** ~7 LLM calls = **~$0.007** (DeepSeek `deepseek-chat`).

---

## Kiến trúc

```
src/xau_agent/
├── config.py                      # pydantic Settings, load .env
├── main.py                        # CLI entry với 6 subcommand
├── mt5/
│   ├── connector.py               # init/shutdown MT5, attach session
│   ├── fetcher.py                 # OHLCV M15/H1/H4 + tick price
│   └── executor.py                # place market order, count positions
├── analysis/
│   ├── indicators.py              # pandas-ta wrappers (EMA/RSI/MACD/BB/ATR)
│   ├── trend.py                   # H1+H4 EMA alignment
│   ├── setup.py                   # M15 entry detect (strict + forced)
│   └── zones.py                   # S/R + EMA + swing + round levels
├── llm/
│   ├── prompts.py                 # 8 role prompts (system_base + 7 vai)
│   ├── agents.py                  # 6-vai debate orchestration
│   ├── execution.py               # Execution Trader (vai #7)
│   └── deepseek.py                # HTTP client (OpenAI-compat, json_mode)
├── external/
│   └── tradingview_ta.py          # TV 26-indicator (tradingview-ta lib)
├── news/
│   └── tavily.py                  # Gold/Fed/USD news brief, cache 1h
└── cli/
    ├── display.py                 # rich panels (banner, trend, debate, result)
    ├── prompt.py                  # Y/N/S input
    ├── plan.py                    # in-CLI strategy summary
    └── zones_display.py           # rich table cho buy/sell zones
```

**Mọi file < 200 LOC** (compliant với CLAUDE.md). Tổng ~2200 LOC.

---

## Cảnh báo quan trọng

1. **DRY_RUN mặc định ON.** Đừng tắt cho đến khi paper-trade ≥ 2 tuần.
2. **AI có thể sai.** 6 vai chống AI gật bừa, nhưng vẫn có thể sai. Bạn là người chịu trách nhiệm cuối.
3. **Đặt SL/TP NGAY khi vào lệnh.** Bot tự đặt SL/TP khi gửi qua executor, nhưng nếu bạn vào tay trên MT5 thì phải đặt ngay.
4. **Tài khoản demo trước.** Bot đã test trên Exness Real Cent — vẫn khuyên bạn dùng demo cho học viên.
5. **Symbol cent variant.** Exness Cent account dùng `XAUUSDc` (không phải `XAUUSD`). Check `xau-agent zones` xem bot có connect đúng symbol không.

---

## Tài liệu

- **Spec đầy đủ:** [`plans/260516-0107-system-spec/spec.md`](plans/260516-0107-system-spec/spec.md) — kiến trúc, decisions, gaps, constitution
- **Plan săn vàng:** [`plans/260516-0009-m15-scalp-strategy/plan.md`](plans/260516-0009-m15-scalp-strategy/plan.md) — 9 mục giải thích plain Vietnamese
- **Backlog TODO:** [`plans/backlog.md`](plans/backlog.md) — danh sách tính năng chưa triển khai

---

## License

MIT — xem [LICENSE](LICENSE).
