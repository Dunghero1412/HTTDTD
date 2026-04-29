```markdown
# HTTDTD - Hệ Thống Tính Điểm Tự Động Dùng Cho Bắn Súng.

## DỰ ÁN ĐƯỢC TẠO BỞI Dunghero1412
## Người tạo dự án : Chiêm Dũng.
## Người bảo trì dự án : Chiêm Dũng.

**dự án đã được đăng ký giấy phép MIT license - bất kỳ cá nhân , tổ chức hoặc đơn vị nào cũng đều được phép clone , chỉnh sửa và sử dụng mã nguồn**

## 📋 Giới Thiệu Dự Án

**HTTDTD** là một hệ thống tính điểm tự động được thiết kế dành cho các trường bắn, sân tập bắn súng thật. Hệ thống sử dụng công nghệ **LoRa** (Long Range) để giao tiếp không dây giữa một bộ điều khiển trung tâm (RPi 5) và 5 bộ máy trạm (RPi Zero 2W), mỗi bộ được lắp đặt ở một bục bắn.

### 🎯 Tính Năng Chính

- **Tính điểm tự động**: Phát hiện viên đạn và tính toán tọa độ hit trên bia tự động
- **Giao tiếp LoRa**: Khoảng cách truyền lên tới vài km, không cần dây kết nối
- **Bảng điểm realtime**: Hiển thị tọa độ từ 5 Node trên màn hình controller theo thời gian thực
- **Lưu log tự động**: Tất cả dữ liệu điểm được lưu vào file `score.txt`
- **Giao diện đơn giản**: Chỉ cần bấm nút để điều khiển, không cần bàn phím chuột

```

---
<div align="center">


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-RPi5%20%7C%20RPi%20Zero%202W%20%7C%20STM32F407-red.svg)]()

**Phát triển bởi [Chiêm Dũng](https://github.com/Dunghero1412)**

</div>

---

## 📋 Mục lục

- [Giới thiệu](#-giới-thiệu)
- [Nguyên lý hoạt động](#-nguyên-lý-hoạt-động)
- [Thuật toán Hybrid](#-thuật-toán-hybrid-wa--hyperbolic-refinement)
- [Phần cứng](#-phần-cứng)
  - [Cấu hình Controller](#controller--raspberry-pi-5)
  - [Cấu hình Node](#node--rpi-zero-2w--stm32f407vg)
  - [Sơ đồ kết nối](#sơ-đồ-kết-nối)
- [Phần mềm](#-phần-mềm)
- [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
- [Cài đặt](#-cài-đặt)
- [Khởi động hệ thống](#-khởi-động-hệ-thống)
- [Vận hành](#-vận-hành)
- [Định dạng log và kết quả](#-định-dạng-log-và-kết-quả)
- [Xử lý sự cố](#-xử-lý-sự-cố)
- [Tài liệu bổ sung](#-tài-liệu-bổ-sung)
- [Giấy phép](#-giấy-phép)
- [Liên hệ](#-liên-hệ)

---

## 🎯 Giới thiệu

**HTTDTD** là hệ thống tính điểm tự động cho các bài bắn súng AK trong huấn luyện quân sự. Thay vì chấm điểm thủ công sau mỗi lượt bắn, hệ thống phát hiện và định vị điểm chạm của viên đạn theo thời gian thực bằng cách thu nhận **sóng N-Wave** — sóng áp suất siêu âm đặc trưng do viên đạn bay ở tốc độ cao (Mach ~2.1 ≈ 714 m/s) tạo ra.

**Điểm nổi bật:**
- Phát hiện sóng N-Wave bằng cảm biến Piezoelectric — không cần đạn chạm bia trực tiếp
- Timestamp phần cứng độ phân giải **5.95 ns** nhờ TIM2 32-bit của STM32F407VG
- Thuật toán **Hybrid (Weighted Average + Hyperbolic Refinement)** — sai số < 2 cm
- Tốc độ âm thanh được cập nhật động qua cảm biến **BME280** mỗi 60 giây
- Hỗ trợ **15 node** (5 node × 3 dãy A/B/C), điều khiển từ xa qua **LoRa 915 MHz**

---

## ⚙️ Nguyên lý hoạt động

```
                    Viên đạn (Mach 2.1)
                          │
                          ▼
              ┌───────────────────────┐
              │    Sóng N-Wave        │  ← Cone sóng âm siêu âm
              │  lan ra xung quanh   │     tốc độ 343 m/s ở 20°C
              └───────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
     Piezo A         Piezo B/C/D     Piezo ...
     (góc bia)       (các góc còn lại)
          │               │
          ▼               ▼
     ┌─────────────────────────────┐
     │   STM32F407VG – TIM2       │
     │   Input Capture 4 kênh     │  ← Ghi timestamp phần cứng
     │   Độ phân giải: 5.95 ns    │     khi mỗi sensor kích hoạt
     └─────────────────────────────┘
                    │
                    │ SPI (20 bytes)
                    ▼
     ┌─────────────────────────────┐
     │   RPi Zero 2W               │
     │   NODE.py                   │  ← TDOA + Hybrid triangulation
     │   Tính toạ độ (x, y)        │
     └─────────────────────────────┘
                    │
                    │ LoRa 915 MHz
                    ▼
     ┌─────────────────────────────┐
     │   Raspberry Pi 5            │
     │   CONTROLLER.py             │  ← Tính điểm + hiển thị
     │   score_gui.html            │
     └─────────────────────────────┘
```

### Chuỗi sự kiện chi tiết

| Bước | Thực hiện bởi | Nội dung | Thời gian |
|---|---|---|---|
| 1 | Vật lý | Sóng N-Wave lan đến 4 cảm biến Piezo | ~0–10 ms |
| 2 | STM32 TIM2 | Capture timestamp 4 kênh đồng thời | ~5 µs |
| 3 | STM32 | Đóng gói SPI packet 20 bytes, kéo PB0 HIGH | ~1 µs |
| 4 | RPi Zero 2W | Nhận SPI, chuẩn hóa Δt, tính toạ độ | ~2 ms |
| 5 | RPi Zero 2W | Gửi kết quả qua LoRa | ~50–150 ms |
| 6 | RPi 5 | Tính điểm, cập nhật bảng điểm | ~1 ms |

---

## 🧮 Thuật toán Hybrid (WA + Hyperbolic Refinement)

Hệ thống dùng phương pháp **Hybrid 2 bước** để cân bằng giữa tốc độ và độ chính xác.

### Bước 1 — Weighted Average (Ước tính nhanh)

Dùng chênh lệch khoảng cách âm thanh `Δd = Δt × c` để tính trọng số cho từng sensor:

```
weight_X = 1 / (|Δd_X| + ε)
```

Sensor nào sensor sóng âm sớm nhất (Δd nhỏ) → gần đạn nhất → weight cao → kéo ước tính về phía đó.

> Ưu điểm: Cực nhanh (~0.5 ms), không phân kỳ.  
> Nhược điểm: Sai số 5–20 cm vì không dùng thông tin hướng TDOA.  
> Vai trò: Cung cấp điểm khởi đầu tốt cho bước tiếp theo.

### Bước 2 — Hyperbolic Refinement (Tinh chỉnh)

Dùng `scipy.optimize.least_squares` để tối thiểu hóa **residuals**:

```
residual_X = (d_X − d_ref)_lý_thuyết − (d_X − d_ref)_đo_được

Với:
  d_X   = khoảng cách từ điểm ước tính đến sensor X
  d_ref = khoảng cách từ điểm ước tính đến sensor tham chiếu (A)
  Δd_đo = Δt_X × c(T)   ← c(T) tính từ BME280
```

Hàm này hội tụ từ điểm khởi đầu của WA trong 3–5 vòng lặp với sai số < 2 cm.

> Công thức tốc độ âm theo nhiệt độ:
> ```
> c(T) = 331.3 × √(1 + T / 273.15)   [m/s]
> ```

**Ví dụ thực tế:** Xem [`docs/EXAMPLE.md`](docs/EXAMPLE.md) với bài toán minh hoạ đầy đủ tại toạ độ (29, 31) cm.

---

## 🔧 Phần cứng

### Controller — Raspberry Pi 5

| Linh kiện | Số lượng | Ghi chú |
|---|---|---|
| Raspberry Pi 5 | 1 | 4GB RAM trở lên |
| LoRa SX1278 | 1 | 915 MHz, UART |
| Nút bấm | 8 | Có điện trở pull-up 10kΩ |

### Node — RPi Zero 2W + STM32F407VG

| Linh kiện | Số lượng / Node | Ghi chú |
|---|---|---|
| Raspberry Pi Zero 2W | 1 | OS Lite 64-bit |
| STM32F407VG | 1 | 168 MHz, TIM2 32-bit |
| LoRa SX1278 | 1 | 915 MHz, UART |
| BME280 | 1 | I2C, đo nhiệt độ |
| Piezoelectric Sensor | 4 | 1 ở mỗi góc bia |
| Pre-amp + Buffer | 4 | OPA2134 hoặc MCP6004 |
| ADC Comparator | 4 | Mạch điều kiện tín hiệu |

---

### Sơ đồ kết nối

#### Controller (RPi 5)

```
RPi 5 GPIO                    Nút bấm (×8)
─────────────────────────────────────────────
GP2  (GPIO INPUT, pull-up) ── Nút NODE1
GP3  (GPIO INPUT, pull-up) ── Nút NODE2
GP4  (GPIO INPUT, pull-up) ── Nút NODE3
GP5  (GPIO INPUT, pull-up) ── Nút NODE4
GP6  (GPIO INPUT, pull-up) ── Nút NODE5
GP7  (GPIO INPUT, pull-up) ── Nút ALL (tất cả)
GP8  (GPIO INPUT, pull-up) ── Nút EXTRA
GP17 (GPIO INPUT, pull-up) ── Nút dự phòng
                   GND ─────── Một chân mỗi nút (khi bấm → GND)

RPi 5 UART1                   LoRa SX1278
─────────────────────────────────────────────
GPIO14 (UART1 TX) ──────────── RXD
GPIO15 (UART1 RX) ──────────── TXD
3.3V ───────────────────────── VCC
GND ────────────────────────── GND
GND ────────────────────────── M0, M1    (Transparent mode)
```

#### Node (RPi Zero 2W ↔ STM32F407VG)

```
RPi Zero 2W SPI0              STM32F407VG SPI2
─────────────────────────────────────────────
GPIO10 (MOSI) ──────────────── PB15 (SPI2_MOSI)
GPIO9  (MISO) ──────────────── PB14 (SPI2_MISO)
GPIO11 (SCLK) ──────────────── PB13 (SPI2_SCK)
GPIO8  (CE0)  ──────────────── PB12 (SPI2_NSS)
GPIO17 (INPUT)──────────────── PB0  (DATA_READY)

RPi Zero 2W I2C               BME280
─────────────────────────────────────────────
GPIO2  (SDA)  ──────────────── SDA
GPIO3  (SCL)  ──────────────── SCL
3.3V ───────────────────────── VCC, SDO→GND  (địa chỉ 0x76)
GND ────────────────────────── GND

RPi Zero 2W UART1             LoRa SX1278
─────────────────────────────────────────────
GPIO14 (TX)   ──────────────── RXD
GPIO15 (RX)   ──────────────── TXD
3.3V ───────────────────────── VCC
GND ────────────────────────── GND, M0, M1

STM32F407VG TIM2              Piezoelectric Sensors
─────────────────────────────────────────────
PA0 (TIM2_CH1, AF01) ───────── Sensor A (Góc Trên-Trái)
PA1 (TIM2_CH2, AF01) ───────── Sensor B (Góc Trên-Phải)
PA2 (TIM2_CH3, AF01) ───────── Sensor C (Góc Dưới-Trái)
PA3 (TIM2_CH4, AF01) ───────── Sensor D (Góc Dưới-Phải)
```

> Sơ đồ chi tiết dạng SVG: xem [`docs/wiring_diagram.svg`](docs/wiring_diagram.svg) và [`docs/wiring_diagram_controller.svg`](docs/wiring_diagram_controller.svg)

---

## 💻 Phần mềm

### Controller — Raspberry Pi OS 64-bit (Desktop)

| Thư viện | Phiên bản | Mục đích |
|---|---|---|
| `RPi.GPIO` | ≥ 0.7.1 | Điều khiển GPIO nút bấm |
| `pyserial` | ≥ 3.5 | Giao tiếp UART với LoRa |
| `pylorahat` | latest | Thư viện LoRa SX1278 |

### Node — Raspberry Pi OS Lite 64-bit

| Thư viện | Phiên bản | Mục đích |
|---|---|---|
| `spidev` | ≥ 3.6 | Đọc SPI từ STM32 |
| `RPi.GPIO` | ≥ 0.7.1 | GPIO DATA_READY, CONTROL |
| `pyserial` | ≥ 3.5 | UART LoRa |
| `pylorahat` | latest | Thư viện LoRa SX1278 |
| `scipy` | ≥ 1.11 | Hyperbolic Refinement (least_squares) |
| `adafruit-circuitpython-bme280` | ≥ 2.6 | Cảm biến nhiệt độ |
| `adafruit-blinka` | ≥ 8.0 | CircuitPython trên RPi |

> ⚠️ **Không cần chạy pip thủ công.** `setup.py` tự động cài tất cả thư viện trên.

---

## 📁 Cấu trúc thư mục

```
HTTDTD/
│
├── scripts/                        # Mã nguồn thực thi chính
│   ├── CONTROLLER/
│   │   └── CONTROLLER.py           # Chương trình Controller (RPi 5)
│   │
│   ├── NODE_A/                     # Node dãy A (đợt bắn 1)
│   │   └── NODE.py
│   ├── NODE_B/                     # Node dãy B (đợt bắn 2)
│   │   ├── NODE.py
│   │   └── MASK.py                 # Mask vùng không tính điểm
│   ├── NODE_C/                     # Node dãy C (đợt bắn 3)
│   │   ├── NODE.py
│   │   └── MASK.py
│   ├── NODE_D/                     # Node dãy D (mở rộng)
│   │   ├── NODE.py
│   │   └── MASK.py
│   │
│   └── STM32/                      # Firmware STM32F407VG
│       ├── src/
│       │   ├── main.c              # Vòng lặp chính, TIM2 IRQ Handler
│       │   ├── system.c            # Cấu hình clock 168 MHz, NVIC
│       │   ├── gpio.c              # PA0–PA3 (TIM2), PB0 (DATA_READY), SPI2
│       │   ├── timmer.c            # TIM2 Input Capture 4 kênh
│       │   └── spi.c               # SPI2 Slave + DMA TX
│       ├── inc/                    # Header files + CMSIS STM32F4
│       ├── lib/
│       │   ├── startup/
│       │   │   └── startup_stm32f407xx.s   # Vector table, Reset_Handler
│       │   └── ld/
│       │       └── stm32f407vg.ld  # Linker script
│       └── Makefile
│
├── html/
│   └── score_gui.html              # Giao diện hiển thị điểm trên trình duyệt
│
├── docs/
│   ├── wiring_diagram.svg          # Sơ đồ nối dây Node
│   ├── wiring_diagram_controller.svg  # Sơ đồ nối dây Controller
│   ├── wiring_diagram_node_stm32.svg  # Sơ đồ Node (STM32 version)
│   ├── schematic_piezo_4ch.svg     # Sơ đồ mạch tín hiệu Piezo 4 kênh
│   ├── EXAMPLE.md                  # Bài toán mô phỏng minh hoạ thuật toán
│   └── INSTALL_HARDWARE.md         # Hướng dẫn lắp đặt phần cứng chi tiết
│
├── setup.py                        # Script cài đặt tự động (cả lib lẫn service)
└── README.md
```

---

## 🚀 Cài đặt

### Yêu cầu chung

- RPi 5 và RPi Zero 2W đã cài Raspberry Pi OS tương ứng
- STM32F407VG đã nạp firmware (xem [`scripts/STM32/`](scripts/STM32/))
- Kết nối phần cứng đúng theo sơ đồ ở phần trên
- Kết nối Internet lần đầu để tải thư viện

### Các bước cài đặt

**1. Clone repository**
```bash
git clone https://github.com/Dunghero1412/HTTDTD.git
cd HTTDTD
```

**2. Chạy setup.py**

Trên máy **Controller (RPi 5)**:
```bash
sudo python3 setup.py install controller
```

Trên máy **Node** (ví dụ: Node 1 dãy A, Node 3 dãy B, Node 5 dãy C):
```bash
sudo python3 setup.py install node1a
sudo python3 setup.py install node3b
sudo python3 setup.py install node5c
```

> `setup.py` sẽ tự động:
> - Cài toàn bộ thư viện pip cần thiết
> - Bật I2C, SPI, UART trên RPi
> - Tạo systemd service để tự khởi động khi boot

**3. Nạp firmware STM32** (nếu chưa làm)
```bash
cd scripts/STM32
make
# Flash qua ST-Link:
openocd -f interface/stlink.cfg -f target/stm32f4x.cfg \
        -c "program stm32_firmware.bin 0x08000000 verify reset exit"
```

---

## 🔌 Khởi động hệ thống

> **Thứ tự bắt buộc: Controller trước → Các Node sau**

### Bước 1 — Khởi động Controller

```bash
# Trên RPi 5:
cd HTTDTD/scripts/CONTROLLER
python3 CONTROLLER.py
```

Hoặc nếu đã cài service:
```bash
sudo systemctl start httdtd-controller
sudo systemctl status httdtd-controller
```

Chờ xuất hiện log:
```
[INIT] GPIO ready (8 buttons)
[INIT] LoRa ready at 915.0MHz
========================================
CONTROLLER STARTED - RPi 5
========================================
```

### Bước 2 — Khởi động từng Node

```bash
# Trên mỗi RPi Zero 2W:
cd HTTDTD/scripts/NODE_A   # hoặc NODE_B, NODE_C...
python3 NODE.py
```

Chờ xuất hiện log:
```
[INIT] GPIO ready
[INIT] SPI ready at 10.0MHz (mode 0)
[INIT] LoRa ready at 915.0MHz
[INIT] BME280 ready – T=26.3°C → sound_speed=345.78 m/s
[INIT] Sound speed update thread started (interval=60s)
============================
NODE STARTED - NODE1A
============================
```

---

## 🎮 Vận hành

### Điều khiển bằng nút bấm (Controller)

| Nút | GPIO | Chức năng | Nhấn lần 1 | Nhấn lần 2 |
|---|---|---|---|---|
| Nút 1 | GP2 | Node 1 | UP (bật bia) | DOWN (hạ bia) |
| Nút 2 | GP3 | Node 2 | UP | DOWN |
| Nút 3 | GP4 | Node 3 | UP | DOWN |
| Nút 4 | GP5 | Node 4 | UP | DOWN |
| Nút 5 | GP6 | Node 5 | UP | DOWN |
| Nút ALL | GP7 | Tất cả | UP tất cả | DOWN tất cả |
| Nút EXTRA | GP8 | Chế độ bảo trì | Khoá các nút khác | Mở khoá |

### Luồng vận hành một lượt bắn

```
1. Nhấn nút tương ứng → bia nâng lên (GPIO20 = HIGH)
2. Xạ thủ bắn (tối đa 3 viên / lượt)
3. Sau mỗi viên: Node tự động tính toạ độ và gửi về Controller
4. Controller hiển thị điểm từng viên lên bảng điểm
5. Sau 3 viên hoặc timeout 60s → bia tự hạ xuống
6. Điểm được ghi vào score_data.json và log
```

### Giao diện web (tùy chọn)

Mở `html/score_gui.html` trên trình duyệt để xem điểm chạm trực quan trên mặt bia ảo.

---

## 📄 Định dạng log và kết quả

### Mẫu file log (`httdtd.log`)

```
2024-11-15 14:32:05 | [INIT] Controller started
2024-11-15 14:32:18 | [CMD]  Sent: NODE1A:UP
2024-11-15 14:32:24 | [RAW]  NODE1A, 29.0, 31.0
2024-11-15 14:32:24 | [SCORE] NODE1A | Viên 1 | x=29.00 y=31.00 | r=42.45cm | Vòng 5 | 5 điểm
2024-11-15 14:32:31 | [SCORE] NODE1A | Viên 2 | x=-12.30 y=8.50 | r=15.07cm | Vòng 9 | 9 điểm
2024-11-15 14:32:38 | [SCORE] NODE1A | Viên 3 | x=3.10 y=-2.80 | r=4.17cm  | Vòng 10 | 10 điểm
2024-11-15 14:32:38 | [TOTAL] NODE1A | Tổng: 24/30 điểm
2024-11-15 14:32:39 | [CMD]  Sent: NODE1A:DOWN
```

### Mẫu file kết quả (`score_data.json`)

```json
{
  "session": "2024-11-15_14:32:05",
  "rounds": {
    "NODE1A": {
      "shots": [
        {"viên": 1, "x": 29.0,  "y": 31.0,  "r": 42.45, "ring": "Vòng 5",  "score": 5},
        {"viên": 2, "x": -12.3, "y": 8.5,   "r": 15.07, "ring": "Vòng 9",  "score": 9},
        {"viên": 3, "x": 3.1,   "y": -2.8,  "r": 4.17,  "ring": "Vòng 10", "score": 10}
      ],
      "total": 24
    },
    "NODE2A": {
      "shots": [
        {"viên": 1, "x": null, "y": null, "r": null, "ring": "Miss", "score": 0},
        {"viên": 2, "x": null, "y": null, "r": null, "ring": "Miss", "score": 0},
        {"viên": 3, "x": null, "y": null, "r": null, "ring": "Miss", "score": 0}
      ],
      "total": 0
    }
  },
  "grand_total": {
    "day_A": 85,
    "day_B": 72,
    "day_C": 91
  }
}
```

---

## 🛠️ Xử lý sự cố

### Node không kết nối được LoRa

| Triệu chứng | Nguyên nhân | Giải pháp |
|---|---|---|
| `[ERROR] LoRa init failed` | UART chưa bật | `sudo raspi-config → Interface → Serial → Enable` |
| Không nhận được lệnh | Sai tần số | Kiểm tra cả Controller và Node đều dùng **915 MHz** |
| Mất packet ngẫu nhiên | Khoảng cách quá xa | Giảm khoảng cách hoặc tăng gain anten |
| Module LoRa không phản hồi | M0/M1 sai | Đảm bảo M0 và M1 đều nối **GND** |

### STM32 không gửi dữ liệu

| Triệu chứng | Nguyên nhân | Giải pháp |
|---|---|---|
| `[TIMEOUT] No DATA_READY` | STM32 chưa capture | Kiểm tra nguồn 3.3V cho STM32 |
| SPI trả về toàn `0x00` | NSS không kéo xuống | Kiểm tra dây GPIO8 (CE0) → PB12 |
| Timestamp không hợp lý | TIM2 PSC sai | Rebuild firmware, kiểm tra `timer.c` PSC=83 |
| Chỉ 1–3 sensor hoạt động | Cảm biến hỏng/lỏng | Kiểm tra kết nối PA0–PA3, đo tín hiệu OPA output |

### Điểm số sai vị trí

| Triệu chứng | Nguyên nhân | Giải pháp |
|---|---|---|
| Sai số > 5 cm | Nhiệt độ môi trường lệch | Kiểm tra BME280 (`i2cdetect -y 1`) |
| Kết quả luôn lệch một hướng | Cảm biến lắp sai góc | Kiểm tra thứ tự A/B/C/D theo đúng sơ đồ |
| Điểm nhảy loạn | Nhiễu điện | Thêm tụ bypass 100nF gần OPA, dùng cáp có màn chắn |
| `MISS` liên tục | Ngưỡng ADC comparator quá cao | Chỉnh VRef của mạch comparator |

### BME280 không đọc được

```bash
# Kiểm tra địa chỉ I2C:
i2cdetect -y 1
# Nên thấy 0x76 hoặc 0x77

# Nếu không thấy: kiểm tra dây SDA/SCL và nguồn 3.3V
# Đảm bảo I2C đã bật:
sudo raspi-config → Interface Options → I2C → Enable
sudo reboot
```

---

## 📚 Tài liệu bổ sung

| File | Nội dung |
|---|---|
| [`docs/EXAMPLE.md`](docs/EXAMPLE.md) | Bài toán mô phỏng đầy đủ với viên đạn tại (29, 31) cm |
| [`docs/INSTALL_HARDWARE.md`](docs/INSTALL_HARDWARE.md) | Hướng dẫn lắp đặt phần cứng chi tiết |
| [`docs/wiring_diagram.svg`](docs/wiring_diagram.svg) | Sơ đồ nối dây Node (SVG) |
| [`docs/wiring_diagram_controller.svg`](docs/wiring_diagram_controller.svg) | Sơ đồ nối dây Controller (SVG) |
| [`docs/schematic_piezo_4ch.svg`](docs/schematic_piezo_4ch.svg) | Sơ đồ mạch tín hiệu Piezo 4 kênh |

---

## 📜 Giấy phép

```
MIT License

Copyright (c) 2024 Chiêm Dũng (Dunghero1412)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

---

## 📬 Liên hệ

Nếu gặp sự cố hoặc có đóng góp, vui lòng liên hệ:

| Kênh | Địa chỉ |
|---|---|
| 📧 Email | [dhr1412.vn@gmail.com](mailto:dhr1412.vn@gmail.com) |
| 🐦 X (Twitter) | [@dungchiem171708](https://x.com/dungchiem171708) |
| 💻 GitHub | [Dunghero1412](https://github.com/Dunghero1412) |
| 🐛 Bug Report | [Issues](https://github.com/Dunghero1412/HTTDTD/issues) |

---

<div align="center">
  <sub>Made with ❤️ by Chiêm Dũng · HTTDTD v2.0</sub>
</div>
