# Plan săn vàng — cách bot hoạt động

> Đọc 5 phút là hiểu bot làm gì, lúc nào vào lệnh, lúc nào bỏ qua.

---

## 1. Bot này là cái gì

Bot là 1 chương trình chạy trên máy bạn, làm 4 việc:

1. **Nhìn giá vàng** trên MT5 (lấy giá thật từ Exness)
2. **Đọc tin tức** vàng + Fed + USD (qua Tavily, 1 dịch vụ tổng hợp tin)
3. **Hỏi 3 AI** xem có nên vào lệnh không (3 lần gọi DeepSeek)
4. **Hỏi bạn** "Y/N" — bạn gõ Y thì bot đặt lệnh trên MT5, gõ N thì bỏ qua

Bot **KHÔNG TỰ ĐẶT LỆNH**. Mọi lệnh đều phải bạn duyệt. Đang ở chế độ "tập" (`DRY_RUN=true`), nghĩa là kể cả bạn gõ Y, bot cũng chỉ in lệnh ra màn hình chứ không gửi MT5.

---

## 2. Có mấy lệnh để gọi bot

| Gõ lệnh này | Bot làm gì | Khi nào dùng |
|-------------|------------|--------------|
| `xau-agent hunt` | **Săn 1 lần ngay** — phân tích đầy đủ, gọi 3 AI, hỏi bạn duyệt | Bạn muốn biết "bây giờ có nên trade không?" |
| `xau-agent scan-once` | Quét 1 lần — chỉ vào lệnh khi giá đẹp đủ tiêu chuẩn, nếu không thì bỏ qua không gọi AI | Tiết kiệm tiền AI, chỉ dùng khi setup chắc |
| `xau-agent run` | Chạy liên tục — cứ 15 phút bot tự quét 1 lần, có gì hỏi bạn | Để bot canh giùm cả đêm |

Bắt đầu thì cứ `xau-agent hunt`. Quen rồi dùng `run`.

---

## 3. Khi bạn gõ `xau-agent hunt`, bot đi qua 6 bước

### Bước 1 — Kết nối MT5 (1 giây)

Bot nhìn vào MT5 đang chạy trên máy, lấy thông tin tài khoản (số tiền, server). In ra:
```
MT5 connected: login=183473322 server=Exness-MT5Real25 balance=11431.46 USC
```

### Bước 2 — Lấy giá vàng (1-2 giây)

Bot lấy giá 200 nến gần nhất ở 3 khung:
- **M15** — nến 15 phút, để bot **vào lệnh**
- **H1** — nến 1 giờ, để bot **xác định xu hướng ngắn**
- **H4** — nến 4 giờ, để bot **xác định xu hướng dài**

### Bước 3 — Kiểm tra xu hướng (1 giây)

Bot vẽ 2 đường trung bình:
- **EMA50** — trung bình giá 50 nến gần nhất
- **EMA200** — trung bình giá 200 nến gần nhất

Cách bot đọc:
- Giá nằm trên CẢ 2 đường VÀ EMA50 > EMA200 → **xu hướng TĂNG**
- Giá nằm dưới CẢ 2 đường VÀ EMA50 < EMA200 → **xu hướng GIẢM**
- Còn lại → **đi ngang**

Bot kiểm tra cả H1 và H4. **Nếu 2 khung khác chiều → bot BỎ QUA** (không lãng phí gọi AI). Vì:
- H4 tăng + H1 giảm → đang là pha hồi trong xu hướng tăng dài → khó scalp
- Ngược lại tương tự

In ra bảng kiểu:
```
┌────┬───────────┬────────────────────────────────────────────┐
│ TF │ Direction │ Detail                                     │
├────┼───────────┼────────────────────────────────────────────┤
│ H1 │ DOWN      │ close=4556.70 EMA50=4625.13 EMA200=4673.11 │
│ H4 │ DOWN      │ close=4556.70 EMA50=4660.67 EMA200=4699.10 │
└────┴───────────┴────────────────────────────────────────────┘
```

### Bước 4 — Lấy tin tức (2-3 giây)

Bot hỏi Tavily: "có tin gì mới về vàng / Fed / CPI / NFP / DXY không?". Tavily trả về 5 link + tóm tắt 1 dòng. Bot dùng cái này để cho AI đọc.

Nếu trong 1 giờ vừa rồi bot đã hỏi rồi, **dùng lại cache** (đỡ tốn quota).

### Bước 5 — Hỏi 3 AI tranh luận (8-10 giây)

Bot gọi DeepSeek **3 lần**:

**Lần 1 — Bull (kẻ ủng hộ).** Bot bảo nó: "Đóng vai luật sư biện hộ. Phải đưa 3 lý do ủng hộ lệnh này, dù lệnh xấu cũng phải bào chữa". AI viết 4-6 câu tiếng Việt.

**Lần 2 — Bear (kẻ phản đối).** Bot bảo: "Đóng vai công tố. Phải tìm 3 lý do phản đối lệnh này". AI viết 4-6 câu.

**Lần 3 — Judge (quan tòa).** Bot đưa kết quả 2 phía cho AI và bảo: "Đọc xong 2 bên, quyết định GO hay SKIP. Trả về JSON". AI trả về:
```json
{"decision":"SKIP","confidence":70,"summary":"RSI trung tính, MACD dương trên M15..."}
```

**Tại sao 3 AI mà không 1?** Vì 1 AI dễ "gật bừa". 3 AI buộc phải có lý do 2 bên, quan tòa cân nhắc rồi quyết. Giống như tòa án có công tố + luật sư + thẩm phán.

### Bước 6 — Hỏi bạn duyệt

Nếu Judge nói **SKIP** → bot bỏ qua, kết thúc. **Không hỏi bạn.**

Nếu Judge nói **GO** → bot in panel đẹp:
- Setup: BUY/SELL, giá vào, giá cắt lỗ (SL), giá chốt lời (TP), khối lượng
- Lý do Bull
- Lý do Bear
- Tin tức tóm tắt
- Phán quyết Judge

Rồi hỏi:
```
Approve order? y/n/s
```

- `y` → bot gửi lệnh MT5 (hoặc in nếu đang dry-run)
- `n` → bot ghi nhận từ chối, kết thúc
- `s` → giống `n` (skip)

---

## 4. Bot xác định Entry / SL / TP thế nào

Khi đã quyết vào lệnh:

- **Entry** = giá đóng cửa của nến M15 vừa đóng
- **Stop Loss** (cắt lỗ) = Entry ± 1.5 × ATR
- **Take Profit** (chốt lời) = Entry ± 2.5 × ATR

**ATR là gì?** Trung bình biên độ 1 nến trong 14 nến gần nhất. Ví dụ ATR=13 nghĩa là vàng đang dao động mỗi nến khoảng 13 điểm. Bot dùng ATR để SL không bị quét vô lý:
- ATR rộng (vàng đang biến mạnh) → SL rộng theo, tránh bị "đá vé" rồi giá quay lại
- ATR hẹp (vàng đang đi nhẹ) → SL hẹp theo, không cần đặt xa

**Risk:Reward** = 2.5 / 1.5 = **1.67**. Tức là kỳ vọng được nhiều hơn mất ~67%. Thắng 4/10 lệnh đã hòa vốn, thắng 5/10 có lời.

---

## 5. Khi nào bot vào lệnh, khi nào bỏ qua

Bot **BỎ QUA** trong các trường hợp sau (không tốn quota AI):

| Lý do bỏ qua | Tại sao |
|--------------|---------|
| H1 và H4 khác chiều | Xu hướng không rõ, scalp dễ chết |
| Tài khoản đã có 1 lệnh đang mở (XAUUSDc) | Tránh chồng lệnh |
| (Sau này thêm) Đã trade đủ 4 lệnh/ngày | Tránh overtrade |
| (Sau này thêm) Đã thua 3% trong ngày | Bảo vệ tài khoản |
| (Sau này thêm) Sắp có tin FOMC/CPI/NFP | Tránh biến động hoang dại |

Bot **gọi AI và có thể vào lệnh** khi:

- H1 + H4 cùng chiều (đều TĂNG hoặc đều GIẢM)
- (Với `hunt`) — đến đây là gọi AI luôn, AI quyết SKIP hay GO
- (Với `scan-once`) — cần thêm: M15 có nến tín hiệu khớp xu hướng + RSI/MACD đẹp

---

## 6. Hôm nay (16/05/2026) bot đang thấy gì

Lần test cuối cùng (00:11 sáng nay):

- **Giá vàng:** 4556.70 (cent account, đơn vị 1 phần 100 USD)
- **Xu hướng H4:** GIẢM (giá 4556 < EMA50 là 4660)
- **Xu hướng H1:** GIẢM (giá 4556 < EMA50 là 4625)
- **2 khung đồng thuận GIẢM** → bot không bỏ qua, gọi AI
- **Bull:** ủng hộ SELL, đưa 3 lý do (xu hướng mạnh, tin Fed hawkish, ATR đủ chạm TP)
- **Bear:** phản đối SELL, đưa 3 lý do (RSI 53.2 trung tính, MACD hist DƯƠNG +1.78 nghĩa là momentum ngắn hạn đang TĂNG, giá đã giảm sâu dễ hồi)
- **Judge:** SKIP, confidence 70. Lý do: "RSI trung tính, MACD dương trên M15, giá cách EMA50 H1 quá xa dễ hồi, SL hẹp so với ATR. Dù xu hướng lớn giảm nhưng setup scalping chưa đủ chất lượng."

**Hiểu nôm na:** Xu hướng lớn đang xuống, nhưng vàng vừa giảm mạnh nên có khả năng nó "thở" 1 chút (hồi lên) trước khi giảm tiếp. Vào SELL ngay bây giờ dễ bị "đá vé SL" rồi giá mới chịu xuống tiếp. Bot khuyên đợi.

---

## 7. Plan săn vàng — 4 giai đoạn

### Giai đoạn 1 — Tập gọi bot (hôm nay - tuần này)
- Cứ vài giờ bạn gõ `xau-agent hunt` 1 lần
- Xem panel, đọc Bull + Bear + Judge, **không cần đặt lệnh thật**
- Mục tiêu: làm quen cách bot suy nghĩ, xem khi nào AI nói GO khi nào SKIP

### Giai đoạn 2 — Để bot canh đêm (tuần 2-3)
- Gõ `xau-agent run` để bot tự quét mỗi 15 phút
- Khi nào có proposal, bạn ngó qua, gõ y/n
- Vẫn dry-run, không tiền thật
- Ghi sổ tay: lệnh nào bot đề nghị, lệnh đó giả định "thắng" hay "thua" sau 4 giờ

### Giai đoạn 3 — Live trên demo (tuần 4-5)
- Login MT5 vào tài khoản **demo** (đăng ký miễn phí ở Exness)
- Chạy `xau-agent run --live` — bot gửi lệnh thật vào demo
- Tiền giả nên thua không sao
- Mục tiêu: kiểm tra bot có gửi lệnh đúng giá không, SL/TP đặt đúng không

### Giai đoạn 4 — Live trên cent thật (tuần 6+)
- Chỉ khi 3 giai đoạn trên ổn (win rate ≥50% trên ≥30 lệnh)
- Chạy `xau-agent run --live` trên tài khoản cent thật
- Bắt đầu lot nhỏ nhất 0.01
- Quy tắc dừng: lỗ 10% tổng tiền → tắt bot, xem lại

---

## 8. Những gì bot CHƯA có (cần làm thêm sau)

Phiên bản hiện tại là MVP — đủ để chạy nhưng chưa đủ thông minh. Sau này cần thêm:

1. **Lọc theo giờ** — chỉ trade phiên London + NY (14h-3h sáng VN), né phiên Á (giá đi lình xình tốn quota)
2. **Né tin sốc** — đọc Tavily nếu có FOMC/CPI/NFP trong 1h → bỏ qua
3. **Tự tính lot theo % rủi ro** — đang fix 0.01, nên đổi sang "1% balance/lệnh"
4. **Ghi sổ tay tự động** — mỗi lệnh ghi vào file CSV để cuối tuần review
5. **Kill switch** — lỗ 3%/ngày tự tắt
6. **Trailing SL** — khi lệnh đã có lãi 1×ATR thì dời SL về hòa vốn

---

## 9. Bạn cần làm gì ngay bây giờ

Trả lời tôi 2 câu:

**Câu 1: Bạn muốn tôi đi thẳng giai đoạn nào?**
- (a) Tôi muốn tự gõ `hunt` vài lần nữa rồi mới quyết
- (b) Cho tôi xem `run` (loop) chạy thử 1 chu kỳ rồi quyết
- (c) Tôi muốn tạo demo Exness trước, làm xong báo lại

**Câu 2: Trong 6 thứ cần làm thêm (section 8), bạn muốn tôi làm thứ nào trước?**
- (1) Lọc giờ trade
- (2) Né tin sốc
- (3) Tự tính lot
- (4) Sổ tay CSV
- (5) Kill switch
- (6) Trailing SL
- (none) Tạm chưa, để bot bản hiện tại chạy trước

Trả lời gọn kiểu `a/3` hoặc `b/none` là đủ.
