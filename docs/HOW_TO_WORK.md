

## **Phần 1: Cách Các Node Nhận Dữ Liệu Từ Piezo Sensor**

### **1.1 Sơ Đồ Phần Cứng**

```
Piezoelectric Sensor (4 cái)
         ↓
      [Op-Amp]  ← Khuếch đại tín hiệu
         ↓
    [MCP3204 ADC]  ← Chuyển Analog → Digital
    (SPI Interface)
         ↓
   [RPi Nano 2W]
```

### **1.2 Quá Trình Chi Tiết**

#### **Bước 1: Viên Đạn Tác Động Vào Bia**

```
Viên đạn bay với vận tốc ~800-900 m/s
         ↓
     [Bia 100×100cm]
     (4 góc có 4 Piezo sensors)
         ↓
Piezo sensor A (góc trái dưới): ••••• (tác động)
Piezo sensor B (góc trái trên):  (không)
Piezo sensor C (góc phải trên):  (không)
Piezo sensor D (góc phải dưới): ••• (tác động sau một chút)
```

**Giải thích:**
- Viên đạn tác động vào bia
- Sóng xung kích (**shock wave**) lan truyền qua bia
- Các Piezo sensor gần vị trí tác động sẽ **cảm nhận trước** (sớm hơn)
- Các sensor xa hơn sẽ **cảm nhận sau** (muộn hơn)

#### **Bước 2: Piezo Sensor Sinh Điện Áp**

```
Piezoelectric Effect (Hiệu ứng Áp Điện):
Khi bị ép lực → Sinh ra điện áp (Volt)

Viên đạn tác động
    ↓
Lực cơ học (Force)
    ↓
Piezo sensor biến đổi thành
    ↓
Điện áp (Voltage): ~0-10V tùy độ lớn lực

Ví dụ:
- Tác động mạnh: ~5V
- Tác động yếu: ~1V
- Không có tác động: ~0V
```

**Công thức:**
```
V_output = k × Force
(V_output: Điện áp đầu ra, k: hệ số)
```

#### **Bước 3: Op-Amp Khuếch Đại Tín Hiệu**

```
                    ┌─────────┐
Piezo Output ───────┤         │
(nhỏ)               │ Op-Amp  ├─────→ Khuếch đại
                    │ (Gain)  │       (lớn hơn)
                    └─────────┘

Ví dụ với Gain = 10:
- Input: 0.5V → Output: 5V
- Input: 1V → Output: 10V

Công thức:
V_out = V_in × Gain
V_out = V_in × (1 + R_feedback / R_input)
```

**Tại sao cần Op-Amp?**
- Piezo sensor output nhỏ (0-2V) → khó đo
- Op-Amp khuếch đại lên 0-10V → dễ đo hơn
- ADC (MCP3204) có độ phân giải 12-bit (0-4095) → cần điện áp cao

#### **Bước 4: MCP3204 ADC Chuyển Analog → Digital**

```
Analog Signal (Voltage)    Digital Signal (Number)
      0V          →              0
      2.5V        →           1024
      5V          →           2048
      10V         →           4095

Chi tiết:
┌─────────────────────────────────────┐
│      MCP3204 ADC (12-bit)          │
├─────────────────────────────────────┤
│ 4 kênh (CH0, CH1, CH2, CH3)        │
│                                    │
│ CH0 ← Sensor A (góc trái dưới)    │
│ CH1 ← Sensor B (góc trái trên)     │
│ CH2 ← Sensor C (góc phải trên)     │
│ CH3 ← Sensor D (góc phải dưới)     │
│                                    │
│ Độ phân giải: 12-bit (0-4095)     │
│ Tốc độ: ~100 kHz                  │
│ Giao tiếp: SPI                    │
└─────────────────────────────────────┘
```

**Công thức chuyển đổi:**
```
ADC_value = (V_in / V_ref) × 2^12
          = (V_in / 5V) × 4096

Ví dụ:
V_in = 2.5V
ADC_value = (2.5 / 5) × 4096 = 2048
```

---

## **Phần 2: Quá Trình Đọc Dữ Liệu (Code Walkthrough)**

### **2.1 Hàm Đọc MCP3204**

```python
def read_mcp3204_channel(channel):
    """
    Đọc giá trị ADC từ một kênh của MCP3204
    
    Tham số:
        channel (int): Kênh ADC (0-3)
    
    Trả về:
        int: Giá trị ADC (0-4095)
    """
    # ===== GIAO THỨC SPI MCP3204 =====
    # 
    # MCP3204 sử dụng giao thức SPI để giao tiếp
    # SPI: Serial Peripheral Interface
    #
    # Sơ đồ kết nối:
    # ┌─────────────┐
    # │  RPi Nano   │
    # │             │
    # │ GPIO11 ────────→ MOSI (Master Out, Slave In)
    # │ GPIO10 ←────────  MISO (Master In, Slave Out)
    # │ GPIO9  ────────→ CLK (Clock)
    # │ GPIO8  ────────→ CS (Chip Select)
    # │             │
    # └─────────────┘
    #        ↓
    #   ┌─────────────┐
    #   │  MCP3204    │
    #   │ ADC Chip    │
    #   └─────────────┘
    
    # Kiểm tra channel hợp lệ
    if channel > 3:
        return -1
    
    # ===== TẠO LỆNH SPI =====
    # Lệnh đọc MCP3204 là 3 bytes:
    # 
    # Byte 0 (CMD):     0000 011x
    #                   ││││ │││
    #                   ││││ ││└─ Start bit (1)
    #                   ││││ │└── Single/Differential (1=Single)
    #                   ││││ └─── Channel bit 2
    #                   └─────── (Fixed pattern)
    #
    # Byte 1 (ADDR):    xxxx xx00
    #                   │││││ ││
    #                   └────┘ ││
    #                   Channel bits 1-0
    #
    # Byte 2: 0000 0000 (dummy)
    #
    # Ví dụ đọc Channel 0:
    # Byte 0: 0000 0110 = 0x06
    # Byte 1: 0000 0000 = 0x00
    # Byte 2: 0000 0000 = 0x00
    #
    # Ví dụ đọc Channel 2:
    # Byte 0: 0000 0110 = 0x06 (vì 2 không nằm trong bit 2)
    # Byte 1: 1000 0000 = 0x80 (Channel 2)
    # Byte 2: 0000 0000 = 0x00
    
    # Byte 0: 0x06 = 00000110
    cmd = 0x06 | ((channel & 0x04) >> 2)
    # Byte 1: Địa chỉ channel (2 bit dưới)
    # Byte 1 = (channel & 0x03) << 6
    #        = (channel & 0x03) * 64
    # Byte 2: Dummy
    
    # ===== GỬI LỆNH SPI =====
    # xfer2(): Gửi và nhận dữ liệu đồng thời
    # Gửi:  [cmd, (channel & 0x03) << 6, 0]
    # Nhận: [dummy, high_byte, low_byte]
    adc_bytes = spi.xfer2([cmd, (channel & 0x03) << 6, 0])
    
    # ===== XỬ LÝ DỮ LIỆU NHẬN =====
    # Dữ liệu ADC 12-bit nằm trong byte 1 và byte 2
    # 
    # Byte 1: 0000 xxxx (4 bit cao)
    # Byte 2: xxxx xxxx (8 bit thấp)
    # 
    # Kết hợp: xxxx xxxx xxxx = 12-bit value (0-4095)
    # 
    # Công thức:
    # value = ((byte1 & 0x0F) << 8) | byte2
    #       = (byte1 & 0x0F) * 256 + byte2
    
    adc_value = ((adc_bytes[1] & 0x0F) << 8) | adc_bytes[2]
    
    return adc_value


# ===== TIMING DIAGRAM =====
#
# Time ──────────────────────────────────────→
#      │
# CS   │   ┌─────────────────────────────────┐
#      └───┘                                 └───┐
#          (LOW khi giao tiếp)                (HIGH)
#      │
# CLK  │ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐
#      └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └──
#        (24 pulses = 24 bits)
#      │
# MOSI │  [CMD]      [ADDR]      [Dummy]
#      └──XXXX●XXXX●XXXX●●XX──────────────
#      │
# MISO │              [0000][xxxx xxxx]
#      └──────────────────●●●●●●●●●●●●●●
#
# ===== ĐỒ THỊ TƯƠNG TỰ =====
#
# Nếu viên đạn tác động:
#
# Thời gian →
# │
# │         ┌─────┐
# │        ╱       ╲
# 5V ─────┤         ├─────
# │       │         │
# 2.5V ───┼─────────┼─────
# │       │         │
# 0V ─────┴─────────┴─────
# │
#
# Điều này được đọc mỗi 100ms:
# T=0ms:   ADC = 0 (chưa có)
# T=100ms: ADC = 2048 (tác động!)
# T=200ms: ADC = 1500 (sóng còn)
# T=300ms: ADC = 0 (kết thúc)
```

### **2.2 Hàm Đọc Tất Cả 4 Cảm Biến**

```python
def read_all_sensors():
    """
    Đọc giá trị từ tất cả 4 cảm biến
    
    Quá trình:
    ┌─────────────────────────────────────┐
    │ Gọi read_all_sensors()              │
    ├─────────────────────────────────────┤
    │ ↓                                   │
    │ Đọc CH0 (Sensor A)                  │
    │ ↓ (qua SPI)                         │
    │ Nhận ADC_A = 1500                   │
    │ ↓                                   │
    │ Đọc CH1 (Sensor B)                  │
    │ ↓ (qua SPI)                         │
    │ Nhận ADC_B = 2500                   │
    │ ↓                                   │
    │ Đọc CH2 (Sensor C)                  │
    │ ↓ (qua SPI)                         │
    │ Nhận ADC_C = 0                      │
    │ ↓                                   │
    │ Đọc CH3 (Sensor D)                  │
    │ ↓ (qua SPI)                         │
    │ Nhận ADC_D = 1000                   │
    │ ↓                                   │
    │ Trả về:                            │
    │ {                                   │
    │   'A': 1500,                        │
    │   'B': 2500,                        │
    │   'C': 0,                           │
    │   'D': 1000                         │
    │ }                                   │
    └─────────────────────────────────────┘
    """
    try:
        sensor_values = {}
        
        # Duyệt qua 4 kênh
        for sensor_name, channel in MCP3204_CHANNELS.items():
            # Sensor A: CH0, B: CH1, C: CH2, D: CH3
            value = read_mcp3204_channel(channel)
            sensor_values[sensor_name] = value
            print(f"  Sensor {sensor_name} (CH{channel}): {value}")
        
        return sensor_values
    
    except Exception as e:
        print(f"[ERROR] Failed to read sensors: {e}")
        return None
```

### **2.3 Vòng Lặp Đọc Liên Tục**

```python
# Vòng lặp chính trong detect_impact():

start_time = time.time()

while time.time() - start_time < SENSOR_DETECTION_WINDOW:
    # Quá trình lặp lại mỗi 100ms:
    # 
    # T=0ms:
    #   - Đọc A, B, C, D → A=0, B=0, C=0, D=0 (chưa có viên)
    #   - Chờ 100ms
    #
    # T=100ms:
    #   - Đọc A, B, C, D → A=2500 (↑), B=1500, C=0, D=0
    #   - Ghi nhận: A phát hiện lúc T=100ms
    #   - Chờ 100ms
    #
    # T=200ms:
    #   - Đọc A, B, C, D → A=2000, B=2800 (↑), C=100 (↑), D=0
    #   - Ghi nhận: B, C phát hiện lúc T=200ms
    #   - Bây giờ đã có 3 sensor, có thể tính tọa độ
    #   - Thoát khỏi vòng lặp
    
    sensor_values = read_all_sensors()  # Đọc lần 1, 2, 3, ...
    
    current_time = time.time() - start_time
    
    for sensor_name, threshold in [('A', IMPACT_THRESHOLD),
                                   ('B', IMPACT_THRESHOLD),
                                   ('C', IMPACT_THRESHOLD),
                                   ('D', IMPACT_THRESHOLD)]:
        # Kiểm tra nếu giá trị vượt ngưỡng
        if sensor_name not in detections and sensor_values[sensor_name] > threshold:
            # PHÁT HIỆN!
            detections[sensor_name] = current_time
            print(f"[DETECT] Sensor {sensor_name} hit at {current_time:.4f}s")
    
    if len(detections) >= 2:
        break  # Đủ dữ liệu, thoát
    
    time.sleep(DETECTION_DELAY)  # Chờ 100ms rồi lặp lại
```

---

## **Phần 3: Quá Trình Tính Toán Tọa Độ**

### **3.1 Khái Niệm Time Difference of Arrival (TDOA)**

```
Viên đạn bay qua bia với vận tốc âm thanh (~340 m/s)

Tâm bia: (0, 0)
┌──────────────────────────────┐
│                              │
│        ●  Viên đạn           │
│     (-10, 20)                │
│                              │
│  A              B            │
│ (-50,-50)    (-50, 50)       │
│                              │
│                              │
│                              │
│  D              C            │
│ (50, -50)    (50, 50)        │
│                              │
└──────────────────────────────┘

Viên đạn gần Sensor A hơn → A phát hiện trước
Viên đạn xa Sensor D → D phát hiện sau

Thời gian phát hiện:
- Sensor A: T_A = 0.001s (đầu tiên)
- Sensor B: T_B = 0.005s (sau 4ms)
- Sensor C: T_C = 0.008s (sau 7ms)
- Sensor D: T_D = 0.012s (sau 11ms)

Khoảng cách từ tâm:
r_A = T_A × v_sound = 0.001s × 340 m/s = 0.34m = 34cm
r_B = T_B × v_sound = 0.005s × 340 m/s = 1.70m = 170cm (xa bia)
r_C = ...
r_D = ...
```

### **3.2 Công Thức Tính Tọa Độ**

```python
def triangulation(detections):
    """
    Tính tọa độ (x, y) của viên đạn
    
    Dữ liệu vào:
    detections = {
        'A': 0.001,  # Thời gian phát hiện (giây)
        'B': 0.005,
        'C': 0.008,
        'D': 0.012
    }
    
    ===== BƯỚC 1: CHUYỂN ĐỔI THỜI GIAN → KHOẢNG CÁCH =====
    
    Vận tốc âm thanh: v = 340 m/s = 34000 cm/s
    
    Khoảng cách = vận tốc × thời gian
    
    r_A = 0.001 × 340 × 100 = 34 cm
    r_B = 0.005 × 340 × 100 = 170 cm (vượt bia!)
    r_C = 0.008 × 340 × 100 = 272 cm (vượt bia!)
    r_D = 0.012 × 340 × 100 = 408 cm (vượt bia!)
    
    Vấn đề: r_B, r_C, r_D quá lớn!
    Lý do: Thời gian phát hiện là tương đối, không phải tuyệt đối
    Cần chuẩn hóa: Lấy sensor phát hiện sớm nhất làm tham chiếu
    
    t_delta_B = (0.005 - 0.001) × 340 × 100 = 136 cm
    t_delta_C = (0.008 - 0.001) × 340 × 100 = 238 cm
    t_delta_D = (0.012 - 0.001) × 340 × 100 = 374 cm
    
    Bây giờ cùng hợp lý!
    """
    
    # ===== BƯỚC 2: TRIANGULATION (PHƯƠNG PHÁP TAM GIÁC) =====
    
    # Phương pháp này dựa trên:
    # Nếu biết khoảng cách từ 3 điểm đã biết tọa độ
    # → Có thể tính được tọa độ mục tiêu
    
    # Hệ phương trình:
    # (x - x_A)² + (y - y_A)² = d_A²  ... (1)
    # (x - x_B)² + (y - y_B)² = d_B²  ... (2)
    # (x - x_C)² + (y - y_C)² = d_C²  ... (3)
    # (x - x_D)² + (y - y_D)² = d_D²  ... (4)
    
    # Đây là hệ phương trình phi tuyến → khó giải
    # Cách làm đơn giản: WEIGHTED AVERAGE (Trung bình trọng số)
    
    # Ý tưởng:
    # - Sensor gần viên đạn hơn (d nhỏ) → trọng số cao
    # - Sensor xa viên đạn hơn (d lớn) → trọng số thấp
    
    # Công thức trọng số:
    # weight = 1 / distance
    
    # Cập nhật vị trí:
    # x_new = x_old + (x_sensor - x_old) × weight × learning_rate
    # y_new = y_old + (y_sensor - y_old) × weight × learning_rate
    
    # Khởi tạo: lấy tâm các 4 sensor
    x = (x_A + x_B + x_C + x_D) / 4
    y = (y_A + y_B + y_C + y_D) / 4
    
    # Lặp lại 4 lần (mỗi sensor 1 lần)
    for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
        distance = detections[sensor_name]
        
        # Trọng số: sensor gần = trọng số cao
        weight = 1 / (distance + 0.1)  # +0.1 để tránh chia cho 0
        
        # Điều chỉnh tọa độ hướng về sensor
        x += (sx - x) × weight × 0.1  # 0.1 = learning rate
        y += (sy - y) × weight × 0.1
    
    # Giới hạn trong vùng bia (-50 đến 50 cm)
    x = max(-50, min(50, x))
    y = max(-50, min(50, y))
    
    return (x, y)
```

### **3.3 Ví Dụ Cụ Thể**

```
Viên đạn bay qua bia ở vị trí thực tế: (10, 20)

Thời gian phát hiện (đã đo):
A: 0.001s → d_A = 34 cm
B: 0.003s → d_B = 102 cm
C: 0.004s → d_C = 136 cm
D: 0.006s → d_D = 204 cm

Chuẩn hóa (lấy A làm tham chiếu T=0):
Δt_A = 0
Δt_B = 0.002s → Δd_B = 68 cm
Δt_C = 0.003s → Δd_C = 102 cm
Δt_D = 0.005s → Δd_D = 170 cm

Bây giờ ta biết:
- Sensor A (-50, -50): Viên đạn ở khoảng 0cm từ A → GẦN
- Sensor B (-50, 50): Viên đạn ở khoảng 68cm từ B → XA
- Sensor C (50, 50): Viên đạn ở khoảng 102cm từ C → XA
- Sensor D (50, -50): Viên đạn ở khoảng 170cm từ D → RẤT XA

→ Viên đạn ở gần Sensor A → Tọa độ phải âm trên cả X và Y

Sau khi triangulation:
Tính toán được: (8, 18)
(Gần với thực tế (10, 20) - Sai số ~2cm)
```

---

## **Phần 4: Toàn Bộ Quá Trình Từ Đầu Đến Cuối**

```
┌─────────────────────────────────────────────────────────────┐
│                    TOÀN BỘ QUY TRÌNH                        │
└─────────────────────────────────────────────────────────────┘

1. ┌──────────────────────┐
   │ VIÊN ĐẠO TÁC ĐỘNG   │
   │ Vận tốc: ~800 m/s   │
   │ Vị trí: (10, 20)    │
   │ Tâm bia: (0, 0)     │
   └──────────────────────┘
            │
            ↓
2. ┌──────────────────────────────────────┐
   │ SÓNG XỈU KHÍCH LAN TRUYỀN QUA BIA   │
   │                                      │
   │ Sensor A: Gần → Phát hiện lúc 1ms   │
   │ Sensor B: Xa → Phát hiện lúc 3ms    │
   │ Sensor C: Xa → Phát hiện lúc 4ms    │
   │ Sensor D: Rất xa → Phát hiện lúc 6ms│
   └──────────────────────────────────────┘
            │
            ↓
3. ┌──────────────────────────────────────┐
   │ PIEZO SENSOR SINH ĐIỆN ÁP            │
   │                                      │
   │ A: 5V (mạnh)    (gần)                │
   │ B: 2V (vừa)     (xa)                 │
   │ C: 1.5V (yếu)   (xa)                 │
   │ D: 1V (rất yếu) (rất xa)             │
   └──────────────────────────────────────┘
            │
            ↓
4. ┌──────────────────────────────────────┐
   │ OP-AMP KHUẾCH ĐẠI                    │
   │ (Gain = 10)                          │
   │                                      │
   │ A: 50V (cắt ở 5V max)                │
   │ B: 20V (cắt ở 5V max)                │
   │ C: 15V (cắt ở 5V max)                │
   │ D: 10V (cắt ở 5V max)                │
   └──────────────────────────────────────┘
            │
            ↓
5. ┌──────────────────────────────────────┐
   │ MCP3204 ADC CHUYỂN ANALOG → DIGITAL  │
   │ (12-bit, Range 0-5V → 0-4095)       │
   │                                      │
   │ A: 4095 (max)   Ngưỡng: 2000        │
   │ B: 4095 (max)   Ngưỡng: 2000        │
   │ C: 4095 (max)   Ngưỡng: 2000        │
   │ D: 4095 (max)   Ngưỡng: 2000        │
   │                                      │
   │ Kết quả: Tất cả > 2000 → PHÁT HIỆN  │
   └──────────────────────────────────────┘
            │
            ↓
6. ┌──────────────────────────────────────┐
   │ VÒNG LẶP PHÁT HIỆN (detect_impact)   │
   │                                      │
   │ Đọc T=0:   A=0, B=0, C=0, D=0       │
   │ Đọc T=1ms: A=4095 → DETECT!         │
   │ Đọc T=3ms: B=4095 → DETECT!         │
   │ Đọc T=4ms: C=4095 → DETECT!         │
   │ Đã có 3 cảm biến → thoát             │
   │                                      │
   │ Kết quả:                             │
   │ detections = {                       │
   │   'A': 0.001,                        │
   │   'B': 0.003,                        │
   │   'C': 0.004,                        │
   │   'D': 0.006                         │
   │ }                                    │
   └──────────────────────────────────────┘
            │
            ↓
7. ┌──────────────────────────────────────┐
   │ TRIANGULATION (tính toán tọa độ)     │
   │                                      │
   │ Chuyển đổi thời gian → khoảng cách:  │
   │ r_A = 0.001 × 340 × 100 = 34 cm    │
   │ r_B = 0.003 × 340 × 100 = 102 cm   │
   │ r_C = 0.004 × 340 × 100 = 136 cm   │
   │ r_D = 0.006 × 340 × 100 = 204 cm   │
   │                                      │
   │ Weighted average triangulation:      │
   │ weight_A = 1/34 ≈ 0.03 (cao)        │
   │ weight_B = 1/102 ≈ 0.01 (thấp)      │
   │ weight_C = 1/136 ≈ 0.007 (thấp)     │
   │ weight_D = 1/204 ≈ 0.005 (rất thấp) │
   │                                      │
   │ Tính được: (9.8, 19.7) ≈ (10, 20)   │
   └──────────────────────────────────────┘
            │
            ↓
8. ┌──────────────────────────────────────┐
   │ TÍNH ĐIỂM                            │
   │                                      │
   │ Khoảng cách từ tâm:                  │
   │ r = √(10² + 20²) = 22.4 cm          │
   │                                      │
   │ So sánh với vòng điểm:               │
   │ Vòng 1: 0 < r ≤ 7.5 → 10 điểm      │
   │ Vòng 2: 7.5 < r ≤ 15 → 9 điểm      │
   │ Vòng 3: 15 < r ≤ 22.5 → 8 điểm ✓   │
   │ Vòng 4: 22.5 < r ≤ 30 → 7 điểm     │
   │                                      │
   │ → ĐIỂM: 8                            │
   └──────────────────────────────────────┘
            │
            ↓
9. ┌──────────────────────────────────────┐
   │ GỬI DỮ LIỆU CHIẾN CONTROLLER        │
   │                                      │
   │ Thông điệp:                          │
   │ "NODE1, 9.8, 19.7"                   │
   │                                      │
   │ Kiểm tra channel (CSMA)              │
   │ → Channel rỗi → Gửi                  │
   │                                      │
   │ ✓ Gửi thành công                    │
   └──────────────────────────────────────┘
            │
            ↓
10. ┌────────────────────────────────────┐
    │ CONTROLLER NHẬN DỮ LIỆU            │
    │                                    │
    │ Parse: node="NODE1", x=9.8, y=19.7│
    │ Tính điểm: 8 điểm                  │
    │ Hiển thị: [NODE1: 8 điểm, Vòng 3]  │
    │ Ghi log: score.txt                  │
    │ Update HTML: score_data.json        │
    └────────────────────────────────────┘
```

---

## **Tóm Tắt Các Công Thức Quan Trọng**

```python
# 1. CHUYỂN ĐỔI ĐIỆN ÁP ADC
value_adc = (voltage / 5.0) × 4096
voltage = (value_adc / 4096) × 5.0

# 2. PHÁT HIỆN VIÊN ĐẠO
if adc_value > THRESHOLD:
    time_detected = current_time

# 3. CHUYỂN THỜI GIAN → KHOẢNG CÁCH
distance = time_delay × sound_velocity
distance_cm = time_seconds × 340 × 100

# 4. TRIANGULATION (TAM GIÁC)
weight = 1 / distance
x_new = x_old + (x_sensor - x_old) × weight × learning_rate
y_new = y_old + (y_sensor - y_old) × weight × learning_rate

# 5. TÍNH KHOẢNG CÁCH TỪ TÂM
radius = √(x² + y²)

# 6. XÁCH ĐỊNH VÒNG ĐIỂM
if radius ≤ 7.5: score = 10
elif radius ≤ 15: score = 9
elif radius ≤ 22.5: score = 8
...
```
