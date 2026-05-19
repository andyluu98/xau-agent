# Backlog — TODO chưa triển khai

> Cập nhật: 2026-05-19 · Spec gốc: [`260516-0107-system-spec/spec.md`](260516-0107-system-spec/spec.md)

Danh sách tính năng đã thiết kế trong spec nhưng **chưa code**. Đánh số P0 (chặn) → P3 (nice-to-have). Học viên/dev mới đọc file này biết next step là gì.

---

## ✅ Đã hoàn thành (cho biết phạm vi hiện tại)

| ID | Mô tả | Module |
|----|-------|--------|
| Core | MT5 fetch + execute + DRY_RUN mặc định | `mt5/` |
| Core | Trend filter H1+H4 (EMA50/200) | `analysis/trend.py` |
| Core | Setup M15 strict (RSI/MACD gate) + forced (hunt mode) | `analysis/setup.py` |
| Core | Zones (S/R + EMA + swing + round) | `analysis/zones.py` |
| Core | Tavily news brief (cache 1h) | `news/tavily.py` |
| Core | DeepSeek client (HTTP, json_mode, tenacity retry) | `llm/deepseek.py` |
| Core | **6-vai debate**: Macro + Bull + Bear + 3 Risk + Judge | `llm/agents.py` |
| Core | **Execution Trader** (vai #7, chỉ chạy khi GO) | `llm/execution.py` |
| Core | TradingView 26-indicator consensus | `external/tradingview_ta.py` |
| Core | CLI 6 lệnh: `plan / tv / zones / hunt / scan-once / run` | `main.py` |
| Core | Rich panel display | `cli/display.py` |
| Core | Y/N/S approval prompt | `cli/prompt.py` |
| Core | order_modify để sửa SL/TP lệnh đang mở (đã test live) | `mt5/executor.py` (1-off script) |
| Tests | 7 unit test pass (config/trend/setup) | `tests/` |
| Docs | README, spec v1, plan plain-Vietnamese | `README.md`, `plans/` |

---

## 🔥 P0 — CẦN cho Phase 1 Paper Trade

### G1. Sổ tay CSV (Trade Journal) — ✅ DONE 2026-05-19

**Đã làm:**
- `src/xau_agent/journal.py` (~110 LOC) — TradeRecord 32 cột + log_trade + read_trades + parse helpers
- Tự động log mỗi phiên có Judge verdict (cả SKIP và GO) vào `state/trades.csv`
- Subcommand `xau-agent journal [--limit N]` in N lệnh gần nhất
- 6 unit tests bổ sung trong `tests/test_journal.py`

**Còn thiếu (để G6 trade_monitor xử lý):**
- Update `exit_time`, `exit_price`, `pnl_usc`, `hold_minutes` khi lệnh đóng
- Hiện các cột này = giá trị default (0/empty) khi log entry

### G2. Daily DD Kill Switch — ✅ DONE 2026-05-19

**Đã làm:**
- `src/xau_agent/risk_manager.py` (~115 LOC) — compute_daily_pnl + is_killed + arm_kill + check_risk
- Đọc MT5 `history_deals_get` từ 00:00 UTC hôm nay → tính tổng P&L
- Nếu P&L ≤ -KILL_DD_PCT% balance → tạo `state/kill_switch.flag` với timestamp + reason
- Auto-reset khi sang ngày mới UTC (compare flag timestamp)
- Hook đầu `_scan_once` và `_hunt_once` qua `_kill_gate()` — render SKIP panel nếu bị block
- CLI `xau-agent reset-kill` reset thủ công
- 3 unit test (lifecycle, auto-reset, today-active)
- Mặc định `KILL_DD_PCT=3.0` (config qua .env)
- KHÔNG cần G1 journal (đọc trực tiếp MT5 history)

### G3. Risk-based Lot Sizing — ✅ DONE 2026-05-19

**Đã làm:**
- `mt5/executor.calc_lot_by_risk(symbol, balance, sl_distance_price, risk_pct)`
- Dùng `symbol_info.trade_tick_size + trade_tick_value` → tính loss per lot chính xác
- Round xuống bội số `volume_step`, clamp `volume_min`/`volume_max`
- Combine với `lot_multiplier` từ Execution Trader (vai #7)
- Activate qua `RISK_PCT_PER_TRADE > 0` trong .env (default 0 = giữ DEFAULT_LOT)
- Helper `_resolve_lot()` trong main.py tính final_lot
- Live verified trên Exness Cent: balance 11485 USC, 1% risk, SL=2.0 price → lot 0.57 (= 1% loss đúng)

---

## 🟡 P1 — CẦN cho Phase 2 Demo Live

### G4. Trading Session Filter

**Vấn đề:** Phiên Á (6-13h VN) vàng đi lình xình. Gọi AI lúc đó tốn quota DeepSeek vô ích.

**Spec:**
- Trong `main.py` `_scan_once` và `_hunt_once`: kiểm giờ UTC+7
- Cho phép trade nếu: London 14-16h **hoặc** LDN-NY overlap 19-23h **hoặc** NY 23-03h
- Skip với `display.render_skip("ngoài giờ trade (chỉ trade London + NY)")`
- Config flag `STRICT_SESSION=true` (mặc định) — tắt được nếu user muốn force

**Effort:** ~30 LOC, 1 commit
**Phụ thuộc:** không

### G5. News Blackout — ✅ DONE 2026-05-19 (branch feat/g5-news-blackout)

**Đã làm:**
- `news/tavily.py.detect_blackout()` (~60 LOC): query Tavily với từ khóa imminent + high-impact, check intersection 2 set
- HIGH_IMPACT_KEYWORDS: FOMC, CPI, NFP, PCE, Powell, Fed rate decision, non-farm payroll, core inflation
- IMMINENCE_PATTERNS (strict, không bao gồm "today" trần): "in 1 hour", "in 30 minutes", "imminent", "release at", "minutes away"...
- Phải có CẢ keyword + imminence indicator mới block
- Cache 30 phút trong _blackout_cache
- Fail-safe: lỗi Tavily → return False (không block do lỗi mạng)
- `_news_blackout_gate()` trong main.py sau kill_gate
- Config NEWS_BLACKOUT_ENABLED=true (mặc định)
- 6 unit test cover: imminent FOMC, imminent CPI, generic "today" mention (false), no event, event-no-time, tavily error
- Live verified: Tavily real call detect "FOMC imminent" → block đúng

---

## 🟢 P2 — CẦN cho Phase 3 Cent Real Micro

### G6. Trailing SL / Breakeven

**Vấn đề:** Lệnh có lãi rồi mất hết khi giá quay lại.

**Spec:**
- Tạo `src/xau_agent/trade_monitor.py` chạy background loop mỗi 1 phút
- Mỗi position: nếu giá đạt +1 × ATR → move SL về breakeven
- Nếu giá đạt +2 × ATR → trail SL theo distance 1 × ATR
- Dùng `mt5.order_send` với `TRADE_ACTION_SLTP` (đã có pattern)
- Subcommand `xau-agent monitor` để chạy standalone

**Effort:** ~120 LOC, 1 commit
**Phụ thuộc:** không

### G7. Auto-close Stale Position

**Vấn đề:** Scalp không nên hold > 4 tiếng. Hold lâu = vào phiên xấu (Asia open, etc.).

**Spec:**
- Cộng vào `trade_monitor.py`: nếu position.time > 4h → close
- Hoặc nếu chuyển sang phiên bị blackout (G4) → close
- Log lý do close vào journal (G1) với `exit_reason="stale_4h"`

**Effort:** ~30 LOC, gộp với G6
**Phụ thuộc:** G6

### G8. Memory Agent (Reflection)

**Vấn đề:** Mỗi phiên độc lập, AI không học từ phiên trước.

**Spec:**
- Tạo `src/xau_agent/llm/memory.py`
- Đọc journal CSV → lấy 20 phiên gần nhất có outcome
- Mỗi lần `hunt`: chèn vào prompt Judge **3 phiên tương tự nhất** (setup giống) với outcome
- Format: "Lần trước trong tình huống RSI=X, MACD=Y, trend=Z → quyết GO/SKIP → kết quả +X pip/-Y pip"
- Cuối tuần Sunday: chạy `xau-agent reflect` — Judge đọc 30 phiên → đề xuất tinh chỉnh prompt

**Effort:** ~150 LOC, 2 commit
**Phụ thuộc:** G1

### G9. KPI Stats Dashboard

**Vấn đề:** Không có cách nhanh xem bot có hiệu quả không.

**Spec:**
- Tạo `src/xau_agent/cli/stats.py`
- Subcommand `xau-agent stats [--days 7]`
- Đọc journal → in:
  - Win rate, PF, avg RR thực tế
  - Phân tích theo phiên (Tokyo / London / NY)
  - Phân tích theo trend strength (H4+H1 strongly aligned vs weakly)
  - Correlation: judge_confidence ↔ actual_pnl
- Rich table + bar chart đơn giản

**Effort:** ~100 LOC, 1 commit
**Phụ thuộc:** G1

---

## ⚪ P3 — Nice to have

### G10. Spread Check Pre-trade

**Spec:** Trong `executor.place()`: lấy `symbol_info_tick`, nếu spread > 2 × normal_spread → return error "spread too wide". Tránh gửi lệnh lúc news.

**Effort:** ~20 LOC

### G11. Pullback Entry Detection

**Spec:** Trong `analysis/setup.py`: hàm `is_pullback(m15, side)` — chỉ trả True nếu nến vừa pullback chạm EMA20 hoặc BB mid rồi quay lại. Tránh đu đỉnh/đáy. Tích hợp như 1 gate trong `setup.detect()` strict mode.

**Effort:** ~40 LOC

### G12. Telegram Alert

**Spec:** Tạo `src/xau_agent/notify/telegram.py`. Khi `hunt` có proposal GO → gửi message qua Telegram bot (BotFather). User duyệt y/n qua inline button.

**Effort:** ~100 LOC + setup BotFather token

### G13b. TradingView MCP Server

**Spec:** Wrap `external/tradingview_ta.py` thành MCP server riêng để Claude Desktop / Cursor dùng được. Hiện đã dùng lib trực tiếp (G13 done). MCP chỉ làm khi cần expose.

**Effort:** ~150 LOC + MCP SDK

### G14. End-of-Day Reflection LLM

**Spec:** Cuối ngày (sau giờ NY close): Judge đọc tất cả lệnh hôm đó từ journal → viết 1 paragraph tổng kết "hôm nay thắng vì sao, thua vì sao, mai cần cẩn thận chỗ nào". Lưu vào `state/reflections/YYYY-MM-DD.md`.

**Effort:** ~80 LOC
**Phụ thuộc:** G1 + G8

---

## 📋 Phase Rollout

| Phase | Status | Cần | Mục tiêu |
|-------|--------|-----|----------|
| **0. Smoke** | ✅ DONE | - | Pipeline chạy không lỗi |
| **1. Paper** | ⏳ NEXT | G1 | 30 phiên dry-run, win-rate ≥ 50% |
| **2. Demo** | 🟡 | + G2 + G3 + G4 + G5 | 100 lệnh demo Exness, 0 MT5 error |
| **3. Cent micro** | 🟡 | + G6 + G7 + G9 | 4 tuần real cent, DD ≤ 5%, PF ≥ 1.4 |
| **4. Production** | 🟡 | + G8 + G14 (option G10 G11) | Vận hành thường xuyên |

---

## 🎯 Đề xuất triển khai theo thứ tự

1. **G1 (Journal CSV)** — chặn Phase 1, 30 phút code
2. **G2 (Kill switch)** — depends G1, 20 phút
3. **G3 (Risk lot)** — independent, 20 phút
4. **G4 (Session filter)** — independent, 10 phút
5. **G5 (News blackout)** — independent, 30 phút
6. **G9 (Stats)** — depends G1, 30 phút
7. **G6+G7 (Monitor)** — independent, 60 phút
8. **G8 (Memory)** — depends G1, 90 phút
9. **G11 (Pullback)** — independent polish, 20 phút
10. **G14 (Reflection)** — depends G8, 30 phút
11. **G10/G12/G13b** — optional

Mỗi item **1 commit riêng**, **branch riêng** nếu lo conflict.

---

## ⚠️ Cảnh báo cho học viên

- **Đừng làm hết 1 lần.** Mỗi G làm xong → paper trade 1 tuần xem có hiệu quả không → mới qua G tiếp.
- **Đừng bỏ G1.** Không có journal = không biết bot có thật giỏi không, mọi tinh chỉnh sau đó là đoán mò.
- **DRY_RUN luôn ON khi đang dev.** Chỉ bật `--live` khi feature đã test pytest pass + dry-run 50 phiên không lỗi.
- **Test pytest sau mỗi commit:** `pytest -v` phải pass 7/7 (hoặc nhiều hơn nếu bạn thêm test).
- **Commit message:** conventional commits — `feat(g1):`, `fix(g2):`, `docs(spec):`...

---

## 📞 Hỏi gì?

- Spec tổng: [`plans/260516-0107-system-spec/spec.md`](260516-0107-system-spec/spec.md)
- Strategy plan: [`plans/260516-0009-m15-scalp-strategy/plan.md`](260516-0009-m15-scalp-strategy/plan.md)
- Issues: https://github.com/andyluu98/xau-agent/issues
