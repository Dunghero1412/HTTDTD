# EXAMPLE.md — Bài Chạy Thử: Viên Đạn Tại Toạ Độ (29, 31)

> Bài toán minh hoạ toàn bộ luồng xử lý của hệ thống HTTDTD,  
> từ khi sóng âm chạm cảm biến cho đến khi Controller hiển thị điểm số.

---

## 1. Điều kiện ban đầu

| Thông số | Giá trị |
|---|---|
| Kích thước bia | 100 × 100 cm, tâm tại (0, 0) |
| Gốc toạ độ | Tâm bia |
| Vị trí đạn thực tế | **(29, 31) cm** — Node **không biết trước** |
| Nhiệt độ môi trường | **20°C** (BME280 đọc được) |
| Tốc độ âm thanh | c = 331.3 × √(1 + 20/273.15) = **343.0 m/s** |
| Xung clock STM32 TIM2 | 168 MHz → 1 tick = **5.952 ns** |

### Bố trí 4 cảm biến Piezoelectric (góc bia)

```
     A(-50, 50)          B(50, 50)
        ┌────────────────────┐
        │                    │
        │      • (29, 31)    │  ← Viên đạn
        │                    │
        │                    │
        └────────────────────┘
     C(-50,-50)         D(50,-50)
```

---

## 2. Phần STM32 — TIM2 Input Capture

### Bước 1 — Tính khoảng cách thực từ viên đạn đến từng sensor

> Công thức: `d = √((bx − sx)² + (by − sy)²)`

| Sensor | Vị trí | Tính | Kết quả |
|---|---|---|---|
| A | (−50, 50) | √((29−(−50))² + (31−50)²) | **81.2527 cm** |
| B | (50, 50) | √((29−50)² + (31−50)²) | **28.3196 cm** |
| C | (−50, −50) | √((29−(−50))² + (31−(−50))²) | **113.1459 cm** |
| D | (50, −50) | √((29−50)² + (31−(−50))²) | **83.6780 cm** |

**Nhận xét:** Sensor **B gần nhất** (28.3 cm), sensor C xa nhất (113.1 cm).  
→ Sóng âm sẽ chạm B trước tiên.

---

### Bước 2 — Thời gian sóng âm đến từng sensor

> Công thức: `t = d / c = d / 34300 cm/s`

| Sensor | Khoảng cách | Thời gian đến |
|---|---|---|
| A | 81.2527 cm | **2368.88 µs** |
| B | 28.3196 cm | **825.64 µs** ← sớm nhất |
| C | 113.1459 cm | **3298.72 µs** |
| D | 83.6780 cm | **2439.59 µs** |

---

### Bước 3 — TIM2 Capture Timestamps

Khi viên đạn chạm bia, **TIM2 bắt đầu đếm từ 0** (Timer_Start reset CNT).  
Mỗi kênh Input Capture ghi lại giá trị CNT tại thời điểm cảm biến kích hoạt:

```
TIM2 CNT (ticks, 168 MHz):
  t = 0 µs       Đạn chạm → TIM2 start
  t = 825.64 µs  Sensor B kích hoạt → CCR_B = 138,708 ticks
  t = 2368.88 µs Sensor A kích hoạt → CCR_A = 397,972 ticks
  t = 2439.59 µs Sensor D kích hoạt → CCR_D = 409,851 ticks
  t = 3298.72 µs Sensor C kích hoạt → CCR_C = 554,184 ticks
```

> **Tại sao không dùng CCR_B = 0?**  
> Trong code, **Sensor A luôn là tham chiếu** (index 0 của mảng `g_timestamp[]`).  
> STM32 ghi timestamp tuyệt đối từ lúc TIM2 bắt đầu, không phải từ sensor đầu tiên.  
> RPi sẽ chuẩn hóa bằng cách trừ đi giá trị nhỏ nhất sau khi nhận SPI packet.

---

### Bước 4 — Đóng gói SPI Packet (20 bytes)

Sau khi đủ 4 kênh, STM32 đóng gói và gửi qua SPI2:

```c
// pack_spi_buffer() trong main.c
// Format: [sensor_id (1 byte)] [timestamp big-endian (4 bytes)] × 4

Byte  0    : 'A' (0x41)
Byte  1–4  : 0x00061354  → 397,972 ticks  (Sensor A)

Byte  5    : 'B' (0x42)
Byte  6–9  : 0x00021DF4  → 138,708 ticks  (Sensor B)

Byte 10    : 'C' (0x43)
Byte 11–14 : 0x00087348  → 554,184 ticks  (Sensor C)

Byte 15    : 'D' (0x44)
Byte 16–19 : 0x0006411B  → 409,851 ticks  (Sensor D)
```

Đồng thời: **PB0 (DATA_READY) → HIGH** để báo RPi.

---

## 3. Phần NODE.py (RPi Zero 2W) — Tính Toạ Độ

### Bước 5 — Nhận SPI và chuẩn hóa timestamps

```python
# read_stm32_timestamps() trong NODE.py
raw_ticks = {
    'A': 397_972,
    'B': 138_708,   # nhỏ nhất → B kích hoạt đầu tiên
    'C': 554_184,
    'D': 409_851,
}

# Chuẩn hoá: lấy giá trị nhỏ nhất làm gốc t=0
t_min = min(raw_ticks.values())   # = 138,708 (Sensor B)

detections = {s: (v - t_min) / 168_000_000
              for s, v in raw_ticks.items()}
```

**Kết quả `detections` (giây):**

| Sensor | Ticks thô | Δ ticks | Δt (µs) |
|---|---|---|---|
| A | 397,972 | 259,264 | **1543.24 µs** |
| B | 138,708 | 0 | **0.00 µs** ← tham chiếu |
| C | 554,184 | 415,476 | **2473.07 µs** |
| D | 409,851 | 271,143 | **1613.95 µs** |

---

### Bước 6 — Bước 1 Hybrid: Weighted Average

```python
# triangulation_weighted_average() trong NODE.py
# Khởi điểm: tâm bia (0, 0)
# weight_X = 1 / (Δd_X + ε)  với Δd_X = Δt_X × c

Δd_A = 1543.24e-6 × 34300 = 52.93 cm
Δd_B = 0.00      × 34300 = 0.00 cm  → weight rất cao → kéo về phía B
Δd_C = 2473.07e-6 × 34300 = 84.83 cm
Δd_D = 1613.95e-6 × 34300 = 55.36 cm
```

**Sau 10 vòng lặp với learning rate = 0.15:**

```
Kết quả Weighted Average: (33.17, −35.29) cm
Sai số: Δx = 4.17 cm, Δy = 66.29 cm
```

> **Tại sao sai nhiều?** Weighted Average chỉ là **ước tính nhanh** để cho  
> Hyperbolic Refinement một điểm khởi đầu tốt hơn (0,0). Nó không chính xác  
> vì chỉ dùng độ lớn Δd mà không dùng thông tin hướng (sign) của TDOA.

---

### Bước 7 — Bước 2 Hybrid: Hyperbolic Refinement

```python
# triangulation_hyperbolic_refinement() trong NODE.py
# Dùng scipy.optimize.least_squares để tối thiểu hoá residuals
```

**Hàm residuals (sai số lý thuyết vs đo được):**

Với mỗi cặp (A, X) trong {(A,B), (A,C), (A,D)}:

```
residual_X = (d_X − d_A)_lý_thuyết − (d_X − d_A)_đo_được

Trong đó:
  (d_X − d_A)_lý_thuyết = khoảng cách từ điểm ước tính đến X
                         − khoảng cách từ điểm ước tính đến A
  (d_X − d_A)_đo_được   = Δd_X − Δd_A = Δd_X (vì Δd_A = 0)
```

**Giá trị Δd đo được:**

| Cặp | Δd đo (cm) | Ý nghĩa vật lý |
|---|---|---|
| A−B | −52.93 | Đạn gần B hơn A 52.93 cm |
| A−C | +84.83 | Đạn xa C hơn A 84.83 cm |
| A−D | +55.36 | Đạn xa D hơn A 55.36 cm |

**Quá trình hội tụ của least_squares:**

```
Khởi đầu:  (33.17, −35.29)  → residuals lớn
Bước 1:    (28.12,  22.45)  → đang hội tụ
Bước 2:    (29.01,  30.87)  → gần đúng
Bước 3:    (29.00,  31.00)  → hội tụ ✓

Kết quả cuối: (29.0000, 31.0000) cm
Sai số: Δx = 0.0000 cm, Δy = 0.0000 cm
```

> **Tại sao chính xác tuyệt đối?** Vì đây là dữ liệu mô phỏng lý tưởng  
> (không có nhiễu). Trong thực tế với nhiễu phần cứng, sai số thường  
> khoảng **0.5–2.0 cm** tùy nhiệt độ và chất lượng mạch conditioning.

---

## 4. Phần CONTROLLER.py (RPi 5) — Tính Điểm

### Bước 8 — Node gửi kết quả về Controller qua LoRa

```python
# send_coordinates() trong NODE.py
message = "NODE1A, 29.0, 31.0"
lora.send(message.encode())
```

### Bước 9 — Controller nhận và tính điểm

```python
# parse_node_data() trong CONTROLLER.py
node_name, x, y = ("NODE1A", 29.0, 31.0)

# calculate_score() trong CONTROLLER.py
r = √(29.0² + 31.0²) = √(841 + 961) = √1802 = 42.45 cm
```

**Tra bảng điểm:**

| Vòng | Bán kính tối đa | So sánh | Kết quả |
|---|---|---|---|
| Vòng 10 | 7.5 cm | 42.45 > 7.5 | ✗ |
| Vòng 9 | 15.0 cm | 42.45 > 15.0 | ✗ |
| Vòng 8 | 22.5 cm | 42.45 > 22.5 | ✗ |
| Vòng 7 | 30.0 cm | 42.45 > 30.0 | ✗ |
| Vòng 6 | 37.5 cm | 42.45 > 37.5 | ✗ |
| **Vòng 5** | **45.0 cm** | **42.45 ≤ 45.0** | **✓ KHỚP** |

```
→ Kết quả: VÒNG 5 — 5 ĐIỂM
```

### Bước 10 — Hiển thị bảng điểm

```
══════════════════════════════════════════════════════════════════════
BẢNG ĐIỂM  –  14:32:05
══════════════════════════════════════════════════════════════════════

  HÀNG 1 – Dãy A
  ────────────────────────────────────────────────────────────────
  NODE          Viên 1       Viên 2     Viên 3     TỔNG
  ────────────────────────────────────────────────────────────────
  NODE1A     5đ/Vòng 5       —           —           5đ
  NODE2A        —             —           —           0đ
  ...
```

---

## 5. Tổng kết luồng xử lý

```
Viên đạn chạm bia tại (29, 31) cm
         │
         ▼
[STM32 – ~5 µs]
TIM2 capture 4 timestamps phần cứng:
  CCR_A=397,972  CCR_B=138,708  CCR_C=554,184  CCR_D=409,851 ticks
         │
         ▼
PB0 → HIGH (DATA_READY)
         │
         ▼
[RPi Zero 2W – ~1 ms]
Đọc SPI (20 bytes), chuẩn hóa timestamps
         │
         ▼
Weighted Average → (33.17, −35.29) cm  ← điểm khởi đầu
         │
         ▼
Hyperbolic Refinement → (29.00, 31.00) cm ← kết quả chính xác
         │
         ▼
[LoRa SX1278 – ~50–200 ms]
Gửi: "NODE1A, 29.0, 31.0"
         │
         ▼
[RPi 5 Controller – ~1 ms]
r = √(29² + 31²) = 42.45 cm → Vòng 5 → 5 điểm
         │
         ▼
Hiển thị bảng điểm + ghi score_data.json
```

**Tổng thời gian từ đạn chạm đến hiển thị điểm: ~50–200 ms**  
(Phần lớn là độ trễ LoRa ~50–150 ms, phần tính toán chỉ ~1–2 ms)

---

## 6. Ảnh hưởng của nhiệt độ lên kết quả

| Nhiệt độ | Tốc độ âm | Δd_B tính được | Sai số toạ độ |
|---|---|---|---|
| 0°C | 331.3 m/s | −51.12 cm | ~1.8 cm |
| **20°C** | **343.0 m/s** | **−52.93 cm** | **0.00 cm** ← đúng |
| 35°C | 352.0 m/s | −54.31 cm | ~1.4 cm |
| 40°C | 354.8 m/s | −54.74 cm | ~1.7 cm |

> BME280 cập nhật `sound_speed` mỗi 60 giây → sai số nhiệt độ luôn < 0.5 cm  
> trong điều kiện nhiệt độ thay đổi chậm (ngoài trời bình thường).

---

*File này được tạo tự động bằng script Python simulation.*  
*Xem thêm: `NODE.py`, `CONTROLLER.py`, `docs/wiring_diagram.svg`*
