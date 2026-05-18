# xau-agent — System Specification (Spec Kit v1)

**Date:** 2026-05-16 · **Author:** session audit · **Repo:** https://github.com/andyluu98/xau-agent

> Tài liệu duy nhất mô tả: hệ thống hoạt động thế nào, vì sao khác upstream, cái gì có sẵn, cái gì còn thiếu, ưu tiên xây tiếp ra sao.

---

## 1. Hệ thống là gì (1 câu)

xau-agent là CLI Python chạy trên Windows, kết nối MT5 đang mở để fetch giá XAUUSDc, tham vấn 3 AI tranh luận (DeepSeek) cộng tin tức (Tavily), rồi hỏi người dùng duyệt y/n trước khi đặt lệnh.

## 2. Boundary — cái gì IN scope, cái gì OUT

### IN scope
- Một (1) symbol: XAUUSDc trên Exness MT5 (cent variant)
- Một (1) chiến lược: scalp khung M15, lọc xu hướng H1+H4
- Bán tự động — bot phân tích, người gõ Y/N
- Source data: MT5 OHLCV (giá) + Tavily (tin)
- Reasoning: DeepSeek 3-agent debate (Bull / Bear / Judge)
- CLI thuần, không web UI

### OUT scope (không làm trong v1)
- Trade nhiều symbol song song (chỉ 1 XAUUSDc)
- Trade nhiều khung (chỉ M15 entry)
- Full-auto không có gate người duyệt
- Backtest framework (chạy lịch sử dài) — sẽ xem xét v2
- Web dashboard / mobile app
- Multi-user / multi-account
- HFT (high-frequency trading) — M15 không cần
- Convert sang Go (đã thảo luận, hoãn)

## 3. Hiện trạng code (1387 LOC, 22 files)

```
src/xau_agent/                           [Python 3.12, snake_case PEP 8]
├── config.py            73 LOC  pydantic Settings, load .env
├── main.py             235 LOC  CLI entry: 5 subcommands (run/scan-once/hunt/plan/zones)
├── mt5/
│   ├── connector.py     53 LOC  init/shutdown, attach to running MT5
│   ├── fetcher.py       60 LOC  OHLCV M15/H1/H4 + current bid/ask
│   └── executor.py      84 LOC  place market order with dry-run flag
├── analysis/
│   ├── indicators.py    51 LOC  pandas-ta wrappers (EMA/RSI/MACD/BB/ATR)
│   ├── trend.py         64 LOC  H1+H4 alignment via EMA50/200
│   ├── setup.py        116 LOC  M15 strict gate + build_forced (hunt mode)
│   └── zones.py        110 LOC  swing high/low + EMA + round numbers across 3 TFs
├── llm/
│   ├── deepseek.py      58 LOC  HTTP client (OpenAI-compat), json_mode flag
│   └── agents.py       133 LOC  Bull / Bear / Judge prompts + verdict parser
├── news/
│   └── tavily.py        82 LOC  XAUUSD/Fed/CPI news brief, 1h in-process cache
└── cli/
    ├── display.py       67 LOC  rich panels (banner, trend, proposal, result)
    ├── prompt.py        19 LOC  Y/N/S input
    ├── plan.py         104 LOC  in-CLI strategy summary
    └── zones_display.py 78 LOC  rich table for buy/sell zones
```

**Compliance với CLAUDE.md:** ✅ mọi file <200 LOC, snake_case PEP 8, no markdown ngoài plans/docs.

## 4. So sánh xau-agent vs upstream vs MCP

### TradingAgents (TauricResearch) — repo bố

| Khía cạnh | TradingAgents | xau-agent | Ghi chú |
|-----------|---------------|-----------|---------|
| Mục tiêu | Multi-stock equity (US) | XAUUSDc forex/commodity | Khác hẳn |
| Số agent | 4 analyst + 2 researcher + 3 risk + 3 manager = 12 | 3 (Bull/Bear/Judge) | Ta cắt còn 25% |
| Orchestration | LangGraph (StateGraph + checkpointer SQLite) | Plain Python flow | Ta đơn giản 10x |
| Data | yfinance / alpha_vantage / reddit / stocktwits / finnhub | MT5 (giá) + Tavily (tin) | Ta bỏ yfinance/AV hoàn toàn |
| Memory | TradingMemoryLog (append-only markdown + reflection) | **THIẾU** | Cần xây trong v1.1 |
| Risk manager | 3-debater pattern (aggressive/neutral/conservative) | **THIẾU** | Đơn giản hơn: chỉ Judge |
| CLI | Typer, multi-flag, checkpoint resume | argparse, 5 subcommand | Ta gọn hơn |
| Output | Markdown report saved to disk | Console rich panels + console log | Ta thiếu log file |
| Reflection | Post-trade alpha vs benchmark | **THIẾU** | Cần khi vào Phase 2 |

**Quyết định kế thừa:**
- Lấy: pattern Bull/Bear/Judge debate (đã có)
- Lấy thêm: TradingMemoryLog (cần build)
- Lấy thêm: 3-risk-debator (optional, có thể v2)
- Bỏ: LangGraph (overkill cho 1 symbol/1 strat) — vẫn giữ flow Python phẳng

### tradingview-mcp — repo MCP server

| Khía cạnh | tradingview-mcp | xau-agent (option integrate) |
|-----------|-----------------|------------------------------|
| Tech | Node.js TypeScript, 78 MCP tools | Python client gọi MCP qua subprocess |
| Auth | Cần TradingView Desktop chạy + paid subscription | Phụ thuộc user có TV paid không |
| Data | All indicators visible trên TV chart | Bổ sung cho MT5 (cross-check) |
| Latency | CDP localhost — nhanh | OK cho M15 |
| Symbol | OANDA:XAUUSD | Cần map XAUUSDc↔OANDA:XAUUSD |
| Use case khả thi | `data_get_study_values` để lấy 26-indicator consensus (Strong Buy/Sell vote) | Thêm 1 input cho Judge |
| Use case khác | Pine Script eval, replay backtest, capture screenshot | Ít giá trị cho mục tiêu hiện tại |

**Quyết định:** ❌ KHÔNG integrate v1. Lý do:
1. Bắt user phải có TV paid + Desktop chạy → ma sát cao
2. 78 tools nhưng ta chỉ cần 1-2 (study_values + quote_get)
3. MT5 data đã đủ cho M15 scalp; TV chỉ "nice to have"
4. Có thể v2 thêm như 1 input optional cho Judge

## 5. Kiến trúc (cập nhật, đơn giản hóa)

```
┌─────────────────────────────────────────────────────────────────────┐
│  CLI Entry (argparse) — main.py                                     │
│    run / scan-once / hunt / plan / zones                            │
└──────────────────────┬──────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────┐
│  Session (mt5.connector)         │  init MT5 → fetch / execute → shutdown
└──────┬───────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Data Layer                                                       │
│    mt5.fetcher  →  OHLCV M15+H1+H4 (200 nến mỗi khung)          │
│    news.tavily  →  brief 5 link + TL;DR, cache 1h                │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Analysis Layer (offline, không gọi LLM)                          │
│    analysis.trend     →  H1+H4 EMA50/200 alignment               │
│    analysis.setup     →  M15 entry (strict) hoặc forced (hunt)   │
│    analysis.zones     →  swing + EMA + round numbers             │
│    analysis.indicators →  pandas-ta helpers                       │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Reasoning Layer (LLM debate)                                     │
│    llm.agents.bull_case   →  DeepSeek (advocate FOR)             │
│    llm.agents.bear_case   →  DeepSeek (advocate AGAINST)         │
│    llm.agents.judge       →  DeepSeek (JSON: GO/SKIP+conf+why)   │
│    llm.deepseek           →  HTTP client, json_mode, retry       │
└──────┬───────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────────┐
│  Decision + Execution                                             │
│    cli.display       →  rich panels (setup, debate, result)      │
│    cli.prompt        →  Y/N/S                                     │
│    mt5.executor      →  place order (or log if dry-run)          │
└──────────────────────────────────────────────────────────────────┘
```

## 6. Data flow chi tiết (lệnh `hunt`)

```mermaid
sequenceDiagram
  participant U as User
  participant CLI as main.py
  participant MT5
  participant Tav as Tavily
  participant DS as DeepSeek
  U->>CLI: xau-agent hunt
  CLI->>MT5: initialize() (attach)
  MT5-->>CLI: account info
  CLI->>MT5: copy_rates_from_pos × 3 (M15, H1, H4)
  MT5-->>CLI: OHLCV × 3
  CLI->>CLI: trend.evaluate(H1, H4)
  alt trend FLAT
    CLI-->>U: SKIP banner
  else trend aligned
    CLI->>CLI: setup.build_forced(M15, side)
    CLI->>Tav: search(gold + Fed + CPI)
    Tav-->>CLI: 5 results + TL;DR
    CLI->>DS: bull_case(setup, trend, news)
    DS-->>CLI: 4-6 câu ủng hộ
    CLI->>DS: bear_case(setup, trend, news)
    DS-->>CLI: 4-6 câu phản đối
    CLI->>DS: judge(json_mode=true)
    DS-->>CLI: {decision, confidence, summary}
    CLI-->>U: rich panel (setup + bull + bear + judge)
    alt judge.decision == GO
      CLI-->>U: prompt Y/N/S
      alt user = Y
        CLI->>MT5: order_send (or log if dry-run)
        MT5-->>CLI: ticket / error
        CLI-->>U: result panel
      end
    end
  end
  CLI->>MT5: shutdown()
```

## 7. State / contracts giữa modules

### `OrderRequest` (mt5/executor.py)
```python
symbol: str        # "XAUUSDc"
side: "BUY"|"SELL"
lot: float         # ≥ symbol_info.volume_min
sl: float          # price level
tp: float          # price level
comment: str       # "xau-agent" để filter sau
```

### `Setup` (analysis/setup.py)
```python
side: "BUY"|"SELL"
entry: float       # M15 last close
sl: float          # entry ± 1.5×ATR
tp: float          # entry ± 2.5×ATR
atr: float         # M15 ATR(14)
rsi: float         # M15 RSI(14)
macd_hist: float   # M15 MACD histogram
reason: str        # diagnostic text
```

### `TrendVerdict` (analysis/trend.py)
```python
aligned: bool                              # True iff H1==H4 (UP or DOWN)
direction: "UP"|"DOWN"|"FLAT"
per_tf: list[TFTrend]                      # each with tf, direction, close, ema50, ema200
reason: str
```

### `Verdict` (llm/agents.py)
```python
decision: "GO"|"SKIP"
confidence: int  # 0-100
summary: str    # 1-3 câu lý do tiếng Việt
```

## 8. Gaps — cái cần xây để đến Phase 4 (live cent thật)

Đánh số ưu tiên P0 (chặn) → P3 (nice-to-have).

| ID | Item | Why | Module | Priority |
|----|------|-----|--------|----------|
| G1 | Trade journal (CSV/SQLite log mỗi lệnh) | Không có data → không review được → không cải tiến được | new `journal.py` | **P0** |
| G2 | Daily DD kill switch (-3%/ngày → stop) | Chống tilt, bảo vệ vốn | new `risk_manager.py` | **P0** |
| G3 | Risk-based lot sizing (1% per trade thay vì fix 0.01) | Lot cố định ignore ATR → không scale được | `mt5/executor.py` | **P0** |
| G4 | Session filter (chỉ trade London+NY) | 50% setup phiên Á là noise | `main.py` (gate trước fetch) | **P1** |
| G5 | News blackout (skip ±1h quanh FOMC/CPI/NFP) | Black swan candle quét SL | `news/tavily.py` + main | **P1** |
| G6 | Trailing SL / breakeven (+1×ATR → BE, +2×ATR → trail) | Khóa lợi nhuận | new `trade_monitor.py` | **P2** |
| G7 | Auto-close stale position (>4h chưa chạm SL/TP) | Tránh hold qua phiên xấu | `trade_monitor.py` | **P2** |
| G8 | Memory log (lưu setup + verdict + outcome → tra cứu sau) | Reflection mechanism như upstream | new `memory.py` | **P2** |
| G9 | KPI dashboard (`xau-agent stats` đọc journal in win-rate/PF) | Cần để biết bot có hiệu quả | new `cli/stats.py` | **P2** |
| G10 | Spread check (skip nếu spread > 2× normal) | Tránh lệnh giá xấu lúc news | `mt5/executor.py` | **P3** |
| G11 | Pullback entry detection (chỉ vào lúc giá pullback EMA20/BB mid) | Tránh đu đỉnh/đáy | `analysis/setup.py` | **P3** |
| G12 | Telegram alert (tùy chọn) | Bạn không ngồi máy vẫn nhận signal | new `notify/telegram.py` | **P3** |
| G13 | TradingView MCP integrate (chỉ `data_get_study_values`) | Cross-check 26-indicator vote | new `external/tv_mcp.py` | **P3** |
| G14 | Reflection LLM (cuối ngày tổng kết trades) | Học từ thắng/thua | `memory.py` + LLM | **P3** |

## 9. Phase rollout (cập nhật theo Gap list)

| Phase | Pre-requisites | Mục tiêu | Exit criteria |
|-------|----------------|----------|---------------|
| **0. Smoke** ✅ DONE | nothing | Verify pipeline | Tests pass + hunt chạy không lỗi |
| **1. Paper** | G1 (journal) | Thu thập 30+ setup giả lập | Win-rate ≥ 50% trên 30 ghi |
| **2. Demo live** | G1+G2+G3+G4+G5 | Test execution latency, slippage | 0 lỗi MT5 trong 100 lệnh demo |
| **3. Cent real micro** | + G6+G7+G9 | Test tâm lý + edge thật | DD ≤ 5%, PF ≥ 1.4 trên 4 tuần |
| **4. Cent real full** | + G8+G14 (optional G10+G11) | Production | Maintain PF ≥ 1.4, DD ≤ 10% |

**P0 cần làm trước Phase 1.** P1 cần trước Phase 2. P2 trước Phase 3.

## 10. Constitution — quy tắc không được vi phạm

1. **DRY_RUN mặc định true.** Phải explicit `--live` mới gửi lệnh thật.
2. **Mọi lệnh phải qua human gate `prompt.ask_approval()`.** Không bao giờ auto-place không hỏi.
3. **`.env` không bao giờ commit.** Có hook privacy-block bảo vệ.
4. **Không yfinance, không Alpha Vantage.** XAUUSD spot không cần stock data.
5. **File <200 LOC.** Lớn hơn → split (đã có precedent).
6. **Python file snake_case PEP 8** (kebab-case không import được).
7. **Mọi quyết định trade phải log lại** (G1 P0).
8. **Daily DD ≥ 3% → kill switch tự động** (G2 P0). Không trade tiếp đến hôm sau.
9. **Mỗi commit thuộc 1 concern.** Không gộp 5 feature vào 1 commit.
10. **Test phải pass trước push.** Pytest tests/ minimum.

## 11. Risk register

| Risk | Khả năng | Hậu quả | Mitigation |
|------|----------|---------|------------|
| MT5 disconnect giữa lệnh | Trung bình | Cao | try/except + reconnect + alert (G2 partial) |
| DeepSeek timeout/down | Thấp | Trung bình | tenacity retry × 3 + graceful skip |
| Tavily rate limit | Thấp | Thấp | Cache 1h + free tier 1000/tháng dư |
| AI hallucinate setup tốt khi thực tế xấu | Trung bình | Cao | 3-agent debate (Bear chống) + RR ≥ 1.5 hard gate |
| User tilt sau loss streak | Cao | Cao | G2 kill switch + cooldown |
| Black swan news (chiến tranh, Fed shock) | Thấp | Rất cao | G5 news blackout + G2 daily DD |
| Real account thay vì demo | Đã xảy ra | Cao | DRY_RUN default + cảnh báo loud trong README |

## 12. Decisions log

| Decision | Ngày | Rationale | Còn hiệu lực? |
|----------|------|-----------|---------------|
| Bỏ yfinance + Alpha Vantage | 2026-05-15 | XAUUSD spot không dùng được | ✅ |
| Bỏ LangGraph | 2026-05-15 | Overkill cho 1 strat đơn | ✅ |
| Python thay vì Go | 2026-05-15 | M15 không cần latency cao + lib stack chín | ✅ |
| 3-agent debate (cắt từ 12 upstream) | 2026-05-15 | YAGNI — đủ để chống AI gật bừa | ✅ |
| DeepSeek thay vì OpenAI/Claude | 2026-05-15 | Rẻ ($0.001/scan), Vietnamese OK | ✅ |
| Tavily thay vì scrape | 2026-05-15 | Free tier 1000/tháng đủ, JSON sẵn | ✅ |
| CLI thay vì Telegram/Web | 2026-05-15 | MVP nhanh, ít phụ thuộc | ✅ (re-evaluate Phase 3) |
| Hoãn TradingView MCP | 2026-05-16 | Bắt user paid TV + Desktop chạy → ma sát | ✅ (re-evaluate v2) |
| Hoãn convert sang Go | 2026-05-15 | M15 không cần, mất LangGraph stack | ✅ |
| symbol = XAUUSDc (Exness Cent) | 2026-05-15 | Account đang dùng | Cần check khi switch demo |

## 13. Open questions (cần user quyết)

1. **G1 (Journal):** SQLite hay CSV? SQLite query được nhưng setup phức tạp hơn. CSV mở Excel xem trực tiếp.
2. **G3 (Risk-based lot):** Cố định 1% balance/lệnh, hay điều chỉnh theo win-rate gần đây (Kelly fraction)?
3. **G4 (Session filter):** Strict cấm phiên Á, hay chỉ "warning" cho user override?
4. **G8 (Memory):** Lưu tối đa N entries (rotate) hay unbounded?
5. **G13 (TV MCP):** Có muốn integrate cuối cùng không, sau Phase 2 chẳng hạn?
6. **Phase 1 duration:** Mặc định 2 tuần. Bạn muốn dài hơn (4 tuần để có nhiều data) không?

## 14. Next concrete step

Đề xuất tôi triển khai **G1 (journal) ngay** vì:
- P0
- Cần thiết cho Phase 1 (không có log thì không review được)
- Self-contained, không phá module hiện có
- ~80 LOC, 1 commit

Bạn confirm `G1 → tiến hành` hay chọn item khác trong gap list?
