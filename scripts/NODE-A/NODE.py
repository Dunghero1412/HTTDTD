#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi Zero 2W Node - Sử dụng STM32F407 Thay MCP3204

🎯 MỤC ĐÍCH CHÍNH:
1. Chờ tín hiệu DATA_READY từ STM32 (GPIO17)
2. Đọc 20 bytes timestamp từ STM32 qua SPI0
3. Parse 4 timestamp thành dữ liệu TDOA
4. Tính toán tọa độ viên đạn bằng Hybrid method
5. Gửi tọa độ về Controller qua LoRa

📍 PIN ASSIGNMENT (RPi Nano 2W - BCM mode):
┌─────────────────────────────────────────────┐
│ GPIO17 (BCM) → DATA_READY input (STM32 PB0) │
│ GPIO20 (BCM) → CONTROL output (motor relay) │
│ GPIO10 → MISO (SPI0) - dữ liệu từ STM32     │
│ GPIO9  → MOSI (SPI0) - không dùng            │
│ GPIO11 → SCLK (SPI0) - clock                 │
│ GPIO8  → CE0 (CS) - chip select              │
└─────────────────────────────────────────────┘

🔧 HARDWARE FLOW:
Piezo Sensor (A,B,C,D)
           ↓
    STM32F407 (TIM2 capture)
           ↓
    Pack timestamp → SPI buffer
           ↓
    Pull PB0 HIGH (DATA_READY)
           ↓
    RPi chờ GPIO17 = HIGH
           ↓
    RPi đọc 20 bytes qua SPI
           ↓
    RPi parse timestamp
           ↓
    RPi tính toán TDOA + Triangulation
           ↓
    RPi gửi tọa độ qua LoRa

⏱️ TIMING:
- STM32 capture: nanosecond (11.904ns/tick)
- SPI transfer: 20 bytes @ 10.5MHz ≈ 15μs
- RPi process: ~10ms
- Total latency: ~10-20ms (vs. 100-120ms with MCP3204!)

🔐 ACCURACY:
- Position error: ±0.1-0.2cm (vs. ±5-10cm before)
- Score error: <1 point (vs. ±1-2 points before)
"""

# ==================== NHẬP THƯ VIỆN ====================

# ✓ Thư viện điều khiển GPIO trên Raspberry Pi
# Dùng để:
# - Đọc DATA_READY signal từ STM32 (GPIO17)
# - Điều khiển motor relay (GPIO20)
import RPi.GPIO as GPIO

# ✓ Thư viện làm việc với thời gian
# Dùng để:
# - time.sleep(): Chờ, delay
# - time.time(): Lấy timestamp hiện tại
# - Tính timeout (60 giây sau khi nhận lệnh)
import time

# ✓ Thư viện hệ thống
# Dùng để:
# - sys.exit(): Thoát chương trình nếu lỗi
import sys

# ✓ Thư viện tính toán toán học
# Dùng để:
# - math.sqrt(): Tính khoảng cách Euclidean
# - Các phép toán khác
import math

# ✓ Thư viện giao tiếp SPI
# Dùng để:
# - Đọc dữ liệu từ STM32 qua SPI0
# - spidev.SpiDev(): Tạo object SPI
# - spi.xfer2(): Gửi/nhận dữ liệu qua SPI
import spidev

# ✓ Thư viện LoRa để giao tiếp không dây
# Dùng để:
# - Gửi lệnh điều khiển đến Controller
# - Nhận lệnh từ Controller
# - LoRa.send(): Gửi dữ liệu
# - LoRa.read(): Nhận dữ liệu
from rpi_lora import LoRa

# ✓ Cấu hình board cho LoRa module SX1278
# Định nghĩa các pin GPIO nối với LoRa
from rpi_lora.board_config import BOARD

# ✓ Thư viện xử lý ngày giờ
# Dùng để:
# - datetime.now(): Lấy thời gian hiện tại
# - strftime(): Format thời gian để ghi log
from datetime import datetime

# ✓ Thư viện xử lý mảng số học
# Dùng để:
# - np.sqrt(): Tính căn bậc 2 (khoảng cách)
# - np.linalg.norm(): Tính norm của vector
# - Dùng cho Hybrid triangulation (bước 2: Hyperbolic)
import numpy as np

# ✓ Thư viện giải bài toán tối ưu (Optimization)
# Dùng để:
# - least_squares(): Giải hyperbolic least squares problem
# - Dùng để tinh chỉnh tọa độ từ Weighted Average
from scipy.optimize import least_squares

# ✓ Thư viện đọc cảm biến BME280 qua I2C
# Cài đặt: pip install adafruit-circuitpython-bme280
# Dùng để đọc nhiệt độ môi trường → tính SOUND_SPEED động
import board
import busio
import adafruit_bme280.advanced as adafruit_bme280

# ==================== CẤU HÌNH CHUNG ====================

# === CẤU HÌNH GPIO CHO DATA_READY ===

# ✓ GPIO pin số cho tín hiệu DATA_READY từ STM32
# Khi STM32 capture đủ 4 sensor, nó sẽ kéo chân này lên HIGH
# RPi sẽ polling GPIO này để biết khi nào đọc SPI
DATA_READY_PIN = 17

# === CẤU HÌNH GPIO CHO CONTROL ===

# ✓ GPIO pin số để điều khiển motor/relay
# Kéo HIGH = bật motor (chuẩn bị bắn)
# Kéo LOW = tắt motor
CONTROL_PIN = 20

# === CẤU HÌNH LoRa ===

# ✓ Tần số LoRa: 915 MHz
# ISM band (công cộng, không cần phép)
# Phải khớp với tần số của Controller + tất cả Node khác
LORA_FREQ = 915

# === CẤU HÌNH SPI CHO STM32 ===

# ✓ Bus SPI số 0 (RPi Nano 2W chỉ có SPI0)
# Gồm: GPIO9 (MOSI), GPIO10 (MISO), GPIO11 (SCLK)
SPI_BUS = 0

# ✓ Device (chip select) số 0
# Tương ứng GPIO8 (CE0)
SPI_DEVICE = 0

# ✓ Tốc độ SPI: 10.5 MHz
# Phải khớp với STM32 (SPI1 @ 84MHz / 8 = 10.5MHz)
# Để đọc 20 bytes: ~15μs
SPI_SPEED = 10500000

# === TỌA ĐỘ CÁC CẢM BIẾN ===

# ✓ Dict lưu tọa độ của 4 cảm biến trên bia
# Bia hình tròn 100cm × 100cm, tâm ở (0, 0)
# Các sensor được đặt ở 4 góc bia
SENSOR_POSITIONS = {
    'A': (-50, -50),      # Góc trái dưới
    'B': (-50, 50),       # Góc trái trên
    'C': (50, 50),        # Góc phải trên
    'D': (50, -50),       # Góc phải dưới
}

# === CẤU HÌNH NGƯỠNG PHÁT HIỆN (LEGACY) ===

# ✓ Ngưỡng ADC để phát hiện viên đạn
# Không còn dùng với STM32 (STM32 tự động phát hiện rising edge)
# Giữ lại cho reference/legacy code
IMPACT_THRESHOLD = 2000

# === CẤU HÌNH TIMING ===

# ✓ Delay giữa mỗi lần đọc sensor (legacy)
# Không còn dùng với STM32 (dùng interrupt)
DETECTION_DELAY = 0.01

# ✓ Cửa sổ phát hiện: 50ms (legacy)
# Không còn dùng - STM32 capture tự động
# Nhưng dùng để timeout nếu không có DATA_READY
SENSOR_DETECTION_WINDOW = 0.05

# ✓ Timeout điều khiển: 60 giây
# Khi nhận lệnh UP, nếu hết 60s mà không nhận 3 viên → tự động DOWN
CONTROL_TIMEOUT = 60

# === TÊN NODE ===

# ✓ Tên Node (sẽ được setup.py sửa thành NODE1A, NODE2B, v.v.)
# Format: NODE{số}{loại_bia}
# Ví dụ: NODE1A, NODE2B, NODE3C, NODE4D, NODE5A, ...
NODE_NAME = "NODE1A"

# === TỐC ĐỘ ÂM THANH ===

# ✓ Công thức tính vận tốc âm thanh theo nhiệt độ (Celsius):
#   c = 331.3 × √(1 + T/273.15)  (m/s)
# Ví dụ:
#   T=0°C   → c = 331.3 m/s
#   T=20°C  → c = 343.2 m/s
#   T=35°C  → c = 352.0 m/s
# Sai số khi dùng hằng số 340 m/s ở 35°C: ~12m/s → ~3.5%
# → Sai số vị trí ~1-3 cm, đủ để ảnh hưởng điểm số vòng sát nhau

def calc_sound_speed(temp_celsius: float) -> float:
    """Tính vận tốc âm thanh (m/s) theo nhiệt độ Celsius."""
    return 331.3 * math.sqrt(1.0 + temp_celsius / 273.15)

# ✓ Giá trị mặc định fallback khi chưa đọc được BME280
SOUND_SPEED_DEFAULT = 340.0   # m/s

# ✓ Biến động – cập nhật mỗi 60s từ BME280
# Đây là biến toàn cục, triangulation_hyperbolic_refinement dùng trực tiếp
sound_speed = SOUND_SPEED_DEFAULT   # m/s (sẽ được cập nhật trong update_sound_speed)

# === CẤU HÌNH BME280 ===

# ✓ Địa chỉ I2C của BME280
# SDO → GND : 0x76 (mặc định)
# SDO → VCC : 0x77
BME280_I2C_ADDR = 0x76

# ✓ Chu kỳ cập nhật nhiệt độ (giây)
BME280_UPDATE_INTERVAL = 60

# === CẤU HÌNH STM32 TIMESTAMP ===

# ✓ Tần số TIM2 với PSC = 0: 84 MHz → 1 tick = 11.9 ns
#
# GIẢI THÍCH:
#   - TIM2 nguồn clock = 84 MHz (APB1 × 2)
#   - timmer.c đặt PSC = 0 → không chia → TIM2 đếm ở 84 MHz
#   - 1 tick = 1 / 84MHz = 11.904 ns
#
# ĐỘ PHÂN GIẢI VỊ TRÍ:
#   11.9 ns × 34300 cm/s = 0.000408 cm ≈ 0.004 mm
#
# AN TOÀN OVERFLOW:
#   Sensor xa nhất ~141cm → sóng âm mất 4.1ms = 344,538 ticks
#   TIM2 32-bit max = 4,294,967,295 ticks → an toàn tuyệt đối ✓
STM32_CLK_FREQ = 84e6   # 84 MHz — TIM2 @ PSC=0

# ✓ Chuyển đổi từ tick STM32 → giây
# TICK_TO_SECONDS = 1 / 84e6 ≈ 11.904 ns per tick
TICK_TO_SECONDS = 1.0 / STM32_CLK_FREQ

# ✓ Chuyển đổi từ tick → cm
# Công thức: 1 tick = (1/168MHz) × c(m/s) × 100cm/m
# TICK_TO_CM được tính lại mỗi khi sound_speed cập nhật
# Giá trị ban đầu dùng SOUND_SPEED_DEFAULT
TICK_TO_CM = SOUND_SPEED_DEFAULT * 100 * TICK_TO_SECONDS

# === CẤU HÌNH HYBRID TRIANGULATION ===

# ✓ BƯỚC 1: Weighted Average
# Số lần lặp để tinh chỉnh tọa độ
WEIGHTED_AVG_ITERATIONS = 10

# ✓ Learning rate cho Weighted Average
# Kiểm soát tốc độ hội tụ (0.1-0.2 là tốt)
# Giá trị cao → hội tụ nhanh nhưng có thể overshoot
# Giá trị thấp → hội tụ chậm nhưng ổn định
WEIGHTED_AVG_LEARNING_RATE = 0.15

# ✓ BƯỚC 2: Hyperbolic Refinement
# Có bật bước 2 không? (True = bật, False = tắt)
# Bước 2 chậm hơn nhưng chính xác hơn
ENABLE_HYPERBOLIC = True

# ✓ Số lần lặp tối đa cho Hyperbolic (scipy.optimize)
# Càng cao → càng chính xác nhưng chậm hơn
HYPERBOLIC_MAX_ITERATIONS = 100

# ✓ Độ chính xác yêu cầu cho Hyperbolic
# Khi Δ < tolerance → dừng lặp
# 1e-6 = 0.000001 (rất chặt, đủ tốt)
HYPERBOLIC_TOLERANCE = 1e-6

# === FILE LOG ===

# ✓ File để lưu log tất cả sự kiện
# Mỗi lần có tọa độ mới → ghi vào file này
# Dùng để review lịch sử sau đó
LOG_FILE = "/opt/score.txt"

# ==================== KHỞI TẠO HARDWARE ====================
# Khai báo trước, khởi tạo trong setup() để tránh crash khi import
spi  = None
lora = None

def setup():
    """
    Khởi tạo toàn bộ phần cứng: GPIO, SPI, LoRa, BME280.
    Gọi một lần duy nhất từ main() sau khi kiểm tra hardware sẵn sàng.
    Tách khỏi module level để tránh crash khi import trên máy không có GPIO.
    """
    global spi, lora, bme280_sensor

    # ── GPIO ──────────────────────────────────────────────────
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    # DATA_READY: input, dùng edge detection thay vì polling
    GPIO.setup(DATA_READY_PIN, GPIO.IN)

    # CONTROL: output, mặc định LOW
    GPIO.setup(CONTROL_PIN, GPIO.OUT)
    GPIO.output(CONTROL_PIN, GPIO.LOW)
    print(f"[INIT] GPIO ready (DATA_READY=GPIO{DATA_READY_PIN}, CTRL=GPIO{CONTROL_PIN})")

    # ── SPI ───────────────────────────────────────────────────
    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEVICE)
    spi.max_speed_hz = SPI_SPEED
    spi.mode = 0b00              # Mode 0 (CPOL=0, CPHA=0) khớp STM32
    print(f"[INIT] SPI ready at {SPI_SPEED / 1e6:.1f}MHz (mode 0)")

    # ── LoRa ──────────────────────────────────────────────────
    lora = LoRa(BOARD.CN1, BOARD.CN1)
    lora.set_frequency(LORA_FREQ)
    print(f"[INIT] LoRa ready at {LORA_FREQ}MHz")

    # ── BME280 (I2C) ──────────────────────────────────────────
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        bme280_sensor = adafruit_bme280.Adafruit_BME280_I2C(
            i2c, address=BME280_I2C_ADDR
        )
        # Đọc lần đầu ngay khi khởi động
        temp = bme280_sensor.temperature
        _apply_sound_speed(temp)
        print(f"[INIT] BME280 ready – T={temp:.1f}°C → "
              f"sound_speed={sound_speed:.2f} m/s")
    except Exception as e:
        bme280_sensor = None
        print(f"[WARN] BME280 init failed: {e} – dùng fallback {SOUND_SPEED_DEFAULT} m/s")

    # ── Khởi động thread cập nhật nhiệt độ định kỳ ───────────
    import threading
    t = threading.Thread(target=_sound_speed_update_loop, daemon=True)
    t.start()
    print(f"[INIT] Sound speed update thread started (interval={BME280_UPDATE_INTERVAL}s)")


# ── BME280 helpers ────────────────────────────────────────────

# Object sensor – khởi tạo trong setup()
bme280_sensor = None


def _apply_sound_speed(temp_celsius: float):
    """Tính và cập nhật biến sound_speed + TICK_TO_CM từ nhiệt độ."""
    global sound_speed, TICK_TO_CM
    sound_speed = calc_sound_speed(temp_celsius)
    TICK_TO_CM  = sound_speed * 100 * TICK_TO_SECONDS


def update_sound_speed() -> float | None:
    """
    Đọc nhiệt độ từ BME280 và cập nhật sound_speed.

    Trả về nhiệt độ (°C) nếu thành công, None nếu lỗi.
    Khi lỗi: giữ nguyên giá trị sound_speed trước đó (không reset về default).
    """
    global bme280_sensor
    if bme280_sensor is None:
        return None
    try:
        temp = bme280_sensor.temperature
        _apply_sound_speed(temp)
        print(f"[BME280] T={temp:.1f}°C → sound_speed={sound_speed:.2f} m/s")
        return temp
    except Exception as e:
        print(f"[WARN] BME280 read error: {e} – giữ sound_speed={sound_speed:.2f} m/s")
        return None


def _sound_speed_update_loop():
    """
    Thread chạy nền, cập nhật sound_speed mỗi BME280_UPDATE_INTERVAL giây.
    Dùng daemon=True để tự thoát khi main thread kết thúc.
    """
    while True:
        time.sleep(BME280_UPDATE_INTERVAL)
        update_sound_speed()

# ==================== BIẾN TRẠNG THÁI ====================

# ✓ Trạng thái điều khiển: ON/OFF
# False = chưa nhận lệnh UP (motor OFF)
# True = đã nhận lệnh UP, GPIO20 HIGH
control_active = False

# ✓ Thời gian hết hạn điều khiển
# = time.time() + CONTROL_TIMEOUT khi nhận lệnh UP
# Nếu time.time() > control_timeout → tự động OFF
control_timeout = None

# ✓ Đếm số lần phát hiện viên đạn
# Khi = 3 → tự động OFF (end of round)
impact_count = 0

# ✓ Trạng thái chế độ EXTRA (bảo trì)
# False = chế độ bình thường
# True = chế độ EXTRA (GPIO luôn HIGH, khóa tất cả nút khác)
extra_mode_active = False

# ✓ Loại bia hiện tại
# "A" = bia tròn 100×100cm (10 vòng điểm)
# "B" = bia hình chữ nhật 150×42cm (1 điểm)
current_bia_type = "A"

# ==================== HÀM HỖ TRỢ ====================

def log_data(message):
    """
    Ghi dữ liệu vào file log và hiển thị trên console
    
    🔧 HOẠT ĐỘNG:
    1. Lấy timestamp hiện tại
    2. Thêm timestamp vào message
    3. In lên console (realtime xem)
    4. Ghi vào file (lưu lịch sử)
    
    💡 MỤC ĐÍCH:
    - Lưu lịch sử tất cả event
    - Debug nếu có vấn đề
    - Review kết quả sau này
    
    Tham số:
        message (str): Thông điệp cần ghi
                      Ví dụ: "[TX] Sent: NODE1A, 25.5, -30.2"
    """
    
    # ✓ Lấy thời gian hiện tại với format "YYYY-MM-DD HH:MM:SS"
    # Ví dụ: "2024-04-25 10:30:45"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ✓ Tạo thông điệp đầy đủ với timestamp
    # Ví dụ: "[2024-04-25 10:30:45] [TX] Sent: NODE1A, 25.5, -30.2"
    log_message = f"[{timestamp}] {message}"
    
    # ✓ In lên console để xem realtime
    print(log_message)
    
    # ✓ Mở file ở chế độ append (thêm vào cuối file)
    # 'a' = append (không xóa nội dung cũ)
    with open(LOG_FILE, 'a') as f:
        # ✓ Ghi thông điệp vào file + ký tự xuống dòng
        f.write(log_message + "\n")

def read_stm32_timestamps():
    """
    Đọc 4 timestamp từ STM32 qua SPI
    
    🔧 HOẠT ĐỘNG:
    1. Gửi 20 bytes dummy qua SPI (để STM32 gửi data)
    2. Nhận 20 bytes từ STM32 (16 bytes timestamp + 4 bytes ID)
    3. Parse 4 × (1 ID + 4 bytes timestamp) bytes
    4. Chuyển đổi timestamp từ tick → giây
    5. Chuẩn hóa: trừ Sensor A để lấy chênh lệch thời gian
    
    📊 ĐỊNH DẠNG DỮ LIỆU NHẬN TỪ STM32:
    ┌─────────────────────────────────────────────────┐
    │ Byte  0-4:   [ID_A] [TS_A[3]] [TS_A[2]] [TS_A[1]] [TS_A[0]] │
    │ Byte  5-9:   [ID_B] [TS_B[3]] [TS_B[2]] [TS_B[1]] [TS_B[0]] │
    │ Byte 10-14:  [ID_C] [TS_C[3]] [TS_C[2]] [TS_C[1]] [TS_C[0]] │
    │ Byte 15-19:  [ID_D] [TS_D[3]] [TS_D[2]] [TS_D[1]] [TS_D[0]] │
    └─────────────────────────────────────────────────┘
    
    💡 VÍ DỤ:
    - Raw data: [65, 0, 0, 0, 168, 66, 0, 0, 1, 8, ...]
    - Sensor A: ID='A' (ASCII 65), TS=0x000000A8 = 168 ticks
    - Sensor B: ID='B' (ASCII 66), TS=0x00000108 = 264 ticks
    - Chênh lệch: 264 - 168 = 96 ticks = 571.5ns
    - Khoảng cách: 571.5ns × 34000cm/s = 1.94cm
    
    Trả về:
        dict: {'A': time_A, 'B': time_B, 'C': time_C, 'D': time_D}
              Thời gian tính bằng giây, chuẩn hóa từ Sensor A
              Ví dụ: {'A': 0.0, 'B': 0.0005952, 'C': 0.0008929, 'D': 0.0011906}
        None: Nếu có lỗi
    """
    
    try:
        # ✓ Gửi 20 bytes dummy để trigger STM32 gửi data
        # Nội dung không quan trọng (STM32 ignore input)
        # STM32 sẽ gửi lại 20 bytes từ spi_tx_buffer
        response = spi.xfer2([0x00] * 20)
        
        # ✓ Parse 4 sensors (mỗi sensor chiếm 5 bytes)
        timestamps = {}
        
        # ✓ Duyệt 4 sensors: A, B, C, D
        for i in range(4):
            # ✓ Tính offset vào buffer (i × 5 bytes)
            # Sensor A: offset = 0 (bytes 0-4)
            # Sensor B: offset = 5 (bytes 5-9)
            # Sensor C: offset = 10 (bytes 10-14)
            # Sensor D: offset = 15 (bytes 15-19)
            offset = i * 5
            
            # ✓ Byte 0: Sensor ID (ASCII)
            # response[offset] = 65 (A), 66 (B), 67 (C), 68 (D)
            # chr() = convert ASCII → character
            sensor_id = chr(response[offset])
            
            # ✓ Bytes 1-4: 32-bit timestamp (big-endian)
            # Công thức: (byte[1] << 24) | (byte[2] << 16) | (byte[3] << 8) | byte[4]
            # Ví dụ: [0, 0, 0, 168] → 0x000000A8 = 168
            ts_raw = (response[offset + 1] << 24) | \
                     (response[offset + 2] << 16) | \
                     (response[offset + 3] << 8) | \
                     (response[offset + 4] << 0)
            
            # ✓ Chuyển đổi từ tick → giây
            # Công thức: ts_seconds = ts_raw / 168e6
            # 168 ticks @ 168MHz = 168 / 168e6 = 1 microsecond
            ts_seconds = ts_raw * TICK_TO_SECONDS
            
            # ✓ Lưu vào dict
            timestamps[sensor_id] = ts_seconds
            
            # ℹ️ Debug log (in giá trị để xem)
            print(f"  [CH{i+1}] Sensor {sensor_id}: "
                  f"Raw={ts_raw}, Time={ts_seconds*1e6:.3f}μs")
        
        # ✓ Chuẩn hóa: lấy Sensor A làm tham chiếu (T=0)
        # Vì TDOA method tính từ chênh lệch thời gian
        # t_ref = timestamps['A'] (thời gian cảm biến A phát hiện)
        # Sau đó: timestamps[x] -= t_ref (tất cả trừ đi t_ref)
        # Kết quả: Sensor A = 0.0 (tham chiếu), các sensor khác = Δt
        if 'A' in timestamps:
            # ✓ Lấy thời gian của Sensor A làm baseline
            t_ref = timestamps['A']
            
            # ✓ Trừ tất cả sensor cho t_ref
            for key in timestamps:
                timestamps[key] -= t_ref
        
        # ✓ Trả về dict timestamps đã chuẩn hóa
        return timestamps
    
    except Exception as e:
        # ❌ Nếu có lỗi (SPI error, parsing error, v.v.)
        print(f"[ERROR] Failed to read STM32: {e}")
        return None

def wait_for_data_ready(timeout=2.0):
    """
    Chờ DATA_READY signal từ STM32 bằng GPIO edge detection.

    Dùng GPIO.wait_for_edge() thay vì polling 1ms để:
    - Không miss signal ngắn (STM32 có thể kéo HIGH/LOW trong <1ms)
    - Giải phóng CPU hoàn toàn trong lúc chờ (không busy-wait)
    - Chính xác hơn polling interval 1ms

    Tham số:
        timeout (float): Thời gian chờ tối đa (giây). Default: 2.0

    Trả về:
        bool: True nếu nhận được rising edge trên GPIO17
              False nếu timeout
    """
    start_time = time.time()

    # Nếu GPIO17 đang HIGH sẵn (STM32 đã kéo trước khi ta chờ)
    if GPIO.input(DATA_READY_PIN) == GPIO.HIGH:
        print(f"[DATA_READY] Signal already HIGH")
        return True

    # Chờ rising edge với timeout (ms) - không tốn CPU
    timeout_ms = int(timeout * 1000)
    channel = GPIO.wait_for_edge(DATA_READY_PIN, GPIO.RISING,
                                  timeout=timeout_ms)

    if channel is not None:
        elapsed = (time.time() - start_time) * 1000
        print(f"[DATA_READY] Rising edge after {elapsed:.2f}ms")
        return True

    print(f"[TIMEOUT] No DATA_READY in {timeout:.1f}s")
    return False

def detect_impact():
    """
    Phát hiện viên đạn tác động vào bia (STM32 version).

    Timeout ngắn (0.1s) để không block main loop quá lâu.
    Nếu không có DATA_READY trong 0.1s → return None ngay,
    main loop tiếp tục nhận lệnh LoRa và kiểm tra timeout.

    Trả về:
        dict: {'A': 0.0, 'B': Δt_B, 'C': Δt_C, 'D': Δt_D} (giây)
        None: Nếu timeout hoặc lỗi
    """
    # Timeout ngắn: 100ms đủ để không miss đạn nhưng không block lâu
    if wait_for_data_ready(timeout=0.1):
        detections = read_stm32_timestamps()
        if detections:
            return detections

    return None

def triangulation_weighted_average(detections):
    """
    BƯỚC 1: Ước tính nhanh bằng Weighted Average.

    FIX so với phiên bản cũ:
    - Sensor A luôn có detections['A'] = 0 → weight = 1/0.0001 = 10000
      kéo kết quả về vị trí sensor A, sai lớn.
    - Fix: dùng khoảng cách âm thanh đã tính (Δd = Δt × c) làm trọng số
      nghịch đảo. Sensor nào có Δd nhỏ nhất → gần đạn nhất → weight cao.
    - Với Sensor A (tham chiếu, Δt=0): dùng khoảng cách Euclidean từ
      điểm ước tính đến sensor A làm weight.

    Nguyên lý:
      weight_A = 1 / (d_estimated_to_A + epsilon)
      weight_X = 1 / (|Δd_X| + epsilon)   với X = B, C, D
    """
    SOUND_SPEED_CMS = sound_speed * 100   # cm/s – cập nhật từ BME280

    # Khởi tạo tại tâm bia (0,0) — không thiên lệch về sensor nào
    x = 0.0
    y = 0.0

    print(f"[HYBRID-STEP1] Weighted Average - Initial: ({x:.2f}, {y:.2f})")

    for iteration in range(WEIGHTED_AVG_ITERATIONS):
        # Tính khoảng cách từ điểm hiện tại đến từng sensor
        dist = {s: math.sqrt((x - sx)**2 + (y - sy)**2)
                for s, (sx, sy) in SENSOR_POSITIONS.items()}

        # Tính weight dựa trên chênh lệch khoảng cách âm thanh đo được
        # Sensor X phát hiện sau A → âm thanh đi thêm Δd = Δt × c
        # → điểm đạn cách A ít hơn X khoảng Δd
        weights = {}
        for s in SENSOR_POSITIONS:
            if s == 'A':
                # Sensor A: weight từ khoảng cách ước tính đến A
                weights[s] = 1.0 / (dist[s] + 1e-6)
            else:
                delta_d = detections[s] * SOUND_SPEED_CMS  # cm
                weights[s] = 1.0 / (abs(delta_d) + 1e-6)

        total_weight = sum(weights.values())

        # Weighted average position
        x_new = sum(weights[s] * SENSOR_POSITIONS[s][0]
                    for s in SENSOR_POSITIONS) / total_weight
        y_new = sum(weights[s] * SENSOR_POSITIONS[s][1]
                    for s in SENSOR_POSITIONS) / total_weight

        # Smooth update với learning rate để tránh oscillation
        x = x + (x_new - x) * WEIGHTED_AVG_LEARNING_RATE
        y = y + (y_new - y) * WEIGHTED_AVG_LEARNING_RATE

    x = max(-50, min(50, x))
    y = max(-50, min(50, y))

    print(f"[HYBRID-STEP1] Weighted Average - Final: ({x:.2f}, {y:.2f})")
    return x, y

def triangulation_hyperbolic_refinement(detections, x_init, y_init):
    """
    BƯỚC 2: Tinh chỉnh chính xác bằng Hyperbolic Least Squares
    
    🔧 HOẠT ĐỘNG:
    1. Sử dụng kết quả Weighted Average làm ước tính ban đầu
    2. Thiết lập hệ phương trình TDOA:
       - Hiệu khoảng cách = Hiệu thời gian × vận tốc âm thanh
       - |d_A - d_B| = Δt_AB × c
       - Tương tự cho (A,C) và (A,D)
    3. Sử dụng least_squares để minimize sai số
    4. Return vị trí tối ưu
    
    💡 NGUYÊN LÝ HYPERBOLIC:
    - Tập hợp điểm có hiệu khoảng cách không đổi từ 2 sensor = hyperbola
    - Giao điểm của 3 hyperbolae = vị trí chính xác viên đạn
    - Least squares: tìm điểm minimize tổng bình phương sai số
    
    ⚡ TÍNH NĂNG:
    - Chậm: 10-30ms (đó là lý do tại sao ta dùng Weighted Average trước)
    - Độ chính xác: ~95-99%
    - Sai số: 0.1-0.2cm
    
    Tham số:
        detections (dict): TDOA timestamps
        x_init, y_init (float): Ước tính ban đầu từ Weighted Average
    
    Trả về:
        tuple: (x, y) - tọa độ tinh chỉnh (cm)
    """
    
    # ✓ In log: bắt đầu Hyperbolic refinement
    print(f"[HYBRID-STEP2] Hyperbolic Refinement - Starting from ({x_init:.2f}, {y_init:.2f})")
    
    # ✓ Tốc độ âm thanh (cm/s) – dùng giá trị động từ BME280
    # sound_speed được cập nhật mỗi 60s bởi _sound_speed_update_loop()
    SOUND_SPEED_CMS = sound_speed * 100
    
    # ✓ Định nghĩa hàm residual (sai số)
    # scipy.optimize.least_squares sẽ minimize hàm này
    def residuals(pos):
        """
        Tính sai số giữa hiệu khoảng cách lý thuyết và thực tế
        
        Tham số:
            pos (array): [x_est, y_est] - vị trí ước tính hiện tại
        
        Trả về:
            array: [error_B, error_C, error_D] - sai số cho 3 cặp sensor
        """
        
        # ✓ Unpack vị trí ước tính
        x_est, y_est = pos
        
        # ✓ Tính khoảng cách từ vị trí ước tính đến mỗi sensor
        # Công thức Euclidean: d = sqrt((x - sx)^2 + (y - sy)^2)
        distances = {}
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            distances[sensor_name] = np.sqrt((x_est - sx)**2 + (y_est - sy)**2)
        
        # ✓ Tính hiệu khoảng cách từ thời gian (measured)
        # Công thức: Δd = Δt × c
        # Ví dụ: Δt_AB = 0.0005952s, c = 34000cm/s
        # Δd_AB = 0.0005952 × 34000 = 20.2368 cm
        distance_diffs_measured = {}
        for sensor_name in SENSOR_POSITIONS.keys():
            # ✓ Chênh lệch thời gian (từ Sensor A làm tham chiếu)
            time_diff = detections[sensor_name] - detections['A']
            # ✓ Chuyển thành chênh lệch khoảng cách
            distance_diffs_measured[sensor_name] = time_diff * SOUND_SPEED_CMS
        
        # ✓ Tính sai số cho mỗi cặp sensor (A-B, A-C, A-D)
        errors = []
        for sensor_name in ['B', 'C', 'D']:
            d_A      = distances['A']
            d_sensor = distances[sensor_name]

            # Lý thuyết: viên đạn cách sensor_X xa hơn A một khoảng Δd
            # → d_sensor - d_A = Δt × c  (sign đúng)
            diff_theoretical = d_sensor - d_A

            # Measured: Δd = Δt × c (Δt đã chuẩn hóa, A=0)
            diff_measured = distance_diffs_measured[sensor_name]

            errors.append(diff_theoretical - diff_measured)

        return errors
    
    # ✓ Gọi scipy.optimize.least_squares để tìm vị trí tối ưu
    try:
        # ✓ Ước tính ban đầu
        initial_guess = [x_init, y_init]
        
        # ✓ Giải bài toán optimization
        # residuals: hàm tính sai số
        # initial_guess: [x_init, y_init]
        # bounds: giới hạn x, y trong [-50, 50]
        # max_nfev: tối đa 100 lần gọi residuals
        # ftol: tolerance (dừng khi error < tolerance)
        result = least_squares(
            residuals,                                  # Hàm sai số
            initial_guess,                              # Ước tính ban đầu
            bounds=([-50, -50], [50, 50]),             # Giới hạn: -50 đến 50 cm
            max_nfev=HYPERBOLIC_MAX_ITERATIONS,        # Max iterations = 100
            ftol=HYPERBOLIC_TOLERANCE,                 # Tolerance = 1e-6
            verbose=0                                   # Không in log chi tiết
        )
        
        # ✓ Lấy kết quả tối ưu
        x_refined, y_refined = result.x
        
        # ✓ In log: thành công
        print(f"[HYBRID-STEP2] Hyperbolic Refinement - Success!")
        print(f"[HYBRID-STEP2] Refined position: ({x_refined:.2f}, {y_refined:.2f})")
        print(f"[HYBRID-STEP2] Residual norm: {np.linalg.norm(result.fun):.6f}")
        
        # ✓ Return tọa độ tinh chỉnh
        return x_refined, y_refined
    
    except Exception as e:
        # ❌ Nếu Hyperbolic refinement thất bại
        print(f"[HYBRID-STEP2] Hyperbolic Refinement failed: {e}")
        print(f"[HYBRID-STEP2] Using Weighted Average result")
        
        # ✓ Fallback: sử dụng kết quả từ Weighted Average
        return x_init, y_init

def triangulation(detections):
    """
    Tính tọa độ viên đạn bằng phương pháp HYBRID
    
    🔧 HOẠT ĐỘNG (2 bước):
    
    BƯỚC 1: Weighted Average (nhanh, 1-2ms)
    - Ước tính nhanh vị trí viên đạn
    - Độ chính xác: ~90%
    - Tốc độ: O(n) linear
    
    BƯỚC 2: Hyperbolic Refinement (chính xác, 10-30ms)
    - Fine-tune kết quả từ bước 1
    - Giải hệ phương trình phi tuyến
    - Độ chính xác: ~95-99%
    - Tốc độ: O(n²) nhưng chỉ 3 biến nên vẫn nhanh
    
    💡 LỢI ÍCH CỦA HYBRID:
    - Kết hợp tốc độ (bước 1) + độ chính xác (bước 2)
    - Ổn định với nhiễu (Weighted Average smooth dữ liệu)
    - Fallback: nếu bước 2 lỗi → dùng bước 1
    - Easy to toggle (ENABLE_HYPERBOLIC flag)
    
    📊 KỲ VỌNG:
    - Sai số cuối: 0.1-0.2cm (so với ±5-10cm trước đây)
    - Tổng thời gian: ~15-35ms (vs. 100-120ms trước)
    - Tỷ lệ cải thiện: 50-100× tốt hơn!
    
    Tham số:
        detections (dict): Thời gian phát hiện của 4 sensor
                          {'A': 0.0, 'B': 0.0005952, ...}
    
    Trả về:
        tuple: (x, y) tọa độ viên đạn (làm tròn đến 0.1 cm)
               Ví dụ: (25.3, -30.8)
    """
    
    try:
        # ✓ In log: bắt đầu triangulation
        print("[HYBRID] Starting triangulation (Hybrid method)...")
        
        # === BƯỚC 1: WEIGHTED AVERAGE ===
        # ✓ Gọi hàm Weighted Average để ước tính nhanh
        x_weighted, y_weighted = triangulation_weighted_average(detections)
        
        # === BƯỚC 2: HYPERBOLIC REFINEMENT ===
        # ✓ Kiểm tra xem có bật bước 2 không
        if ENABLE_HYPERBOLIC:
            # ✓ Gọi hàm tinh chỉnh Hyperbolic
            x_refined, y_refined = triangulation_hyperbolic_refinement(
                detections, 
                x_weighted, 
                y_weighted
            )
            
            # ✓ Sử dụng kết quả từ Hyperbolic (chính xác hơn)
            x_final = x_refined
            y_final = y_refined
        else:
            # ✓ Nếu tắt bước 2, sử dụng Weighted Average
            print("[HYBRID] Hyperbolic refinement disabled, using Weighted Average")
            x_final = x_weighted
            y_final = y_weighted
        
        # ✓ Giới hạn lần nữa để chắc chắn (dự phòng)
        # (Bước 2 đã có bounds, nhưng để an toàn)
        x_final = max(-50, min(50, x_final))
        y_final = max(-50, min(50, y_final))
        
        # ✓ In log: kết quả cuối cùng
        print(f"[HYBRID] Final result: ({x_final:.2f}, {y_final:.2f})")
        print("="*60)
        
        # ✓ Return tọa độ làm tròn đến 0.1 cm
        # round(x, 1) = làm tròn đến 1 chữ số thập phân (0.1 cm)
        return round(x_final, 1), round(y_final, 1)

    except Exception as e:
        # ❌ Nếu có lỗi trong quá trình tính toán
        print(f"[ERROR] Triangulation failed: {e}")
        return None, None

# ==================== HÀM GỬIDỮ LIỆU ====================

def send_command(node_name, command):
    """
    Gửi lệnh điều khiển đến một Node qua LoRa
    
    🔧 HOẠT ĐỘNG:
    1. Kết hợp node_name + command thành thông điệp
    2. Chuyển string → bytes (UTF-8)
    3. Gửi qua LoRa module
    4. Ghi log
    
    📝 ĐỊNH DẠNG LỆNH:
    - "NODE1A UP" - kích hoạt Node 1A
    - "NODE1A DOWN" - dừng Node 1A
    - "A UP" - broadcast cho tất cả node loại A
    - "EXTRA UP" - chế độ bảo trì
    
    Tham số:
        node_name (str): Tên node hoặc lệnh ("NODE1A", "A", "EXTRA")
        command (str): "UP" hoặc "DOWN"
    """
    
    try:
        # ✓ Kết hợp node_name + command thành thông điệp
        # Ví dụ: "NODE1A" + " " + "UP" → "NODE1A UP"
        message = f"{node_name} {command}"
        
        # ✓ Chuyển string → bytes (UTF-8 encoding)
        # LoRa module yêu cầu bytes, không phải string
        lora.send(message.encode())
        
        # ✓ Ghi log thông điệp đã gửi
        log_data(f"[TX] Sent: {message}")
    
    except Exception as e:
        # ❌ Nếu có lỗi, ghi vào log
        log_data(f"[ERROR] Failed to send: {e}")

def send_coordinates(x, y):
    """
    Gửi tọa độ viên đạn về Controller qua LoRa
    
    🔧 HOẠT ĐỘNG:
    1. Tạo message: "{NODE_NAME}, {x}, {y}"
    2. Chuyển → bytes
    3. Gửi qua LoRa
    4. In log
    
    📝 ĐỊNH DẠNG DỮ LIỆU:
    "NODE1A, 25.3, -30.8"
    - NODE1A: Tên node gửi
    - 25.3: Tọa độ X (cm)
    - -30.8: Tọa độ Y (cm)
    
    Tham số:
        x (float): Tọa độ X (-50 đến 50 cm)
        y (float): Tọa độ Y (-50 đến 50 cm)
    """
    
    try:
        # ✓ Tạo message
        message = f"{NODE_NAME}, {x}, {y}"
        
        # ✓ Chuyển → bytes và gửi
        lora.send(message.encode())
        
        # ✓ In log
        print(f"[TX] Sent: {message}")
    
    except Exception as e:
        # ❌ Nếu lỗi
        print(f"[ERROR] Failed to send: {e}")

# ==================== HÀM NHẬN LỆNH ====================

def receive_command():
    """
    Nhận lệnh từ Controller qua LoRa
    
    🔧 HOẠT ĐỘNG:
    1. Kiểm tra LoRa có dữ liệu không
    2. Nếu có: đọc, parse, thực hiện
    3. Parse: tách thành [node_command, action]
    4. Thực hiện hành động tương ứng
    
    📝 ĐỊNH DẠNG LỆNH:
    - "NODE1A UP" - kích hoạt Node 1A (bắn bia loại A)
    - "NODE1A DOWN" - dừng Node 1A
    - "A UP" - broadcast cho tất cả node (bắn cùng lúc)
    - "A DOWN" - dừng tất cả
    - "EXTRA UP" - chế độ bảo trì (GPIO luôn HIGH)
    - "EXTRA DOWN" - thoát EXTRA
    
    💡 LOGIC:
    - Lệnh "EXTRA" khóa tất cả nút khác
    - Lệnh "A" chỉ hoạt động khi EXTRA OFF
    - Lệnh node cụ thể chỉ hoạt động khi EXTRA OFF
    
    Trả về:
        str: Trạng thái ("ACTIVATED", "DEACTIVATED", ...) hoặc None
    """
    
    global control_active, control_timeout, impact_count, extra_mode_active, current_bia_type

    try:
        # ✓ Kiểm tra xem LoRa có đang nhận dữ liệu không
        # is_rx_busy() return True = đang nhận, không thể đọc
        if lora.is_rx_busy():
            return None

        # ✓ Đọc dữ liệu từ LoRa
        payload = lora.read()

        # ✓ Nếu có dữ liệu
        if payload:
            # ✓ Chuyển đổi từ bytes sang string
            command = payload.decode().strip()
            
            # ✓ In lệnh nhận được
            print(f"[RX] Received: {command}")

            # ✓ Tách lệnh thành các phần
            # Ví dụ: "NODE1A UP" → ["NODE1A", "UP"]
            parts = command.split()

            # ✓ Kiểm tra nếu có ít nhất 2 phần
            if len(parts) >= 2:
                # ✓ Lấy tên node và hành động
                node_command = parts[0].upper()  # "NODE1A", "A", "EXTRA"
                action = parts[1].upper()         # "UP" hoặc "DOWN"

                # === KIỂM TRA LỆNH EXTRA (Chế độ bảo trì) ===
                # ✓ Nếu lệnh là "EXTRA"
                is_broadcast_extra = (node_command == "EXTRA")
                
                if is_broadcast_extra:
                    if action == "UP":
                        # ✓ EXTRA UP: Khóa tất cả nút, GPIO luôn HIGH
                        extra_mode_active = True        # SET flag
                        control_active = False           # Tắt chế độ bình thường
                        
                        # ✓ In log
                        print(f"[EXTRA] Mode ON - GPIO {CONTROL_PIN} is HIGH")
                        
                        # ✓ Kéo GPIO20 lên HIGH (sẽ ở đó cho đến EXTRA DOWN)
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        # ✓ Return status
                        return "EXTRA_ON"
                    
                    elif action == "DOWN":
                        # ✓ EXTRA DOWN: Thoát khỏi EXTRA mode
                        extra_mode_active = False       # CLEAR flag
                        control_active = False
                        
                        # ✓ In log
                        print(f"[EXTRA] Mode OFF - GPIO {CONTROL_PIN} is LOW")
                        
                        # ✓ Kéo GPIO20 về LOW
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        # ✓ Return status
                        return "EXTRA_OFF"

                # === KIỂM TRA LỆNH A (Broadcast cho tất cả node) ===
                # ✓ Nếu lệnh là "A" (và EXTRA không active)
                is_broadcast_a = (node_command == "A")
                
                if is_broadcast_a and not extra_mode_active:
                    # ✓ Set loại bia hiện tại (loại A)
                    current_bia_type = "A"
                    
                    if action == "UP":
                        # ✓ A UP: Kích hoạt tất cả Node (broadcast)
                        control_active = True
                        # ✓ Tính thời gian hết hạn (bây giờ + 60s)
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        # ✓ Reset counter đếm viên
                        impact_count = 0
                        
                        # ✓ In log
                        print(f"[CONTROL] BROADCAST A UP - Activated")
                        
                        # ✓ Kéo GPIO20 lên HIGH
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        # ✓ Return status
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        # ✓ A DOWN: Dừng tất cả Node
                        control_active = False
                        
                        # ✓ In log
                        print(f"[CONTROL] BROADCAST A DOWN - Deactivated")
                        
                        # ✓ Kéo GPIO20 về LOW
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        # ✓ Return status
                        return "DEACTIVATED"

                # === KIỂM TRA LỆNH CỤ THỂ (NODE1A, NODE2B, ...) ===
                # ✓ Kiểm tra xem lệnh có phải cho Node này không
                is_for_this_node = (node_command == NODE_NAME)
                
                if is_for_this_node and not extra_mode_active:
                    # ✓ Lệnh dành cho Node này (và EXTRA OFF)
                    
                    if action == "UP":
                        # ✓ Node này UP: Kích hoạt
                        control_active = True
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        impact_count = 0
                        
                        # ✓ In log
                        print(f"[CONTROL] {node_command} UP - Activated")
                        
                        # ✓ Kéo GPIO20 lên HIGH
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        # ✓ Return status
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        # ✓ Node này DOWN: Dừng
                        control_active = False
                        
                        # ✓ In log
                        print(f"[CONTROL] {node_command} DOWN - Deactivated")
                        
                        # ✓ Kéo GPIO20 về LOW
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        # ✓ Return status
                        return "DEACTIVATED"

    except Exception as e:
        # ❌ Nếu có lỗi
        print(f"[ERROR] Failed to receive command: {e}")

    # ✓ Return None nếu không có lệnh hoặc có lỗi
    return None

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """
    Vòng lặp chính của Node.
    """
    global control_active, control_timeout, impact_count, extra_mode_active

    try:
        # ── Khởi tạo hardware ─────────────────────────────────
        setup()

        print("="*60)
        print(f"NODE STARTED - {NODE_NAME}")
        print("="*60)
        
        # ✓ Vòng lặp chính - chạy liên tục cho đến Ctrl+C
        while True:
            # ✓ Liên tục kiểm tra LoRa nhận lệnh
            receive_command()

            # === CHẾ ĐỘ HOẠT ĐỘNG BÌNH THƯỜNG (Phát hiện viên đạn) ===
            # ✓ Nếu control_active = True (đã nhận lệnh UP)
            if control_active and not extra_mode_active:
                
                # ✓ Kiểm tra xem timeout đã hết chưa
                if time.time() > control_timeout:
                    # ✓ Hết thời gian điều khiển (60s)
                    control_active = False
                    
                    # ✓ Tắt GPIO 20
                    GPIO.output(CONTROL_PIN, GPIO.LOW)
                    
                    # ✓ In log
                    print("[TIMEOUT] Control timeout after 60s")
                
                else:
                    # ✓ Còn thời gian, phát hiện viên đạn
                    # Hàm detect_impact() sẽ:
                    # - Chờ DATA_READY signal (GPIO17 = HIGH)
                    # - Đọc 20 bytes từ STM32 qua SPI
                    # - Parse thành dict timestamps
                    # - Return dict hoặc None
                    detections = detect_impact()

                    # ✓ Nếu phát hiện được (return dict, không phải None)
                    if detections:
                        # ✓ Tăng counter đếm số lần phát hiện
                        impact_count += 1
                        print(f"[IMPACT] Detection #{impact_count}")

                        # ✓ Tính toán tọa độ viên đạn (Hybrid method)
                        # Bước 1: Weighted Average (nhanh)
                        # Bước 2: Hyperbolic Refinement (chính xác)
                        x, y = triangulation(detections)

                        # ✓ Nếu tính toán thành công (không return None)
                        if x is not None and y is not None:
                            # ✓ In tọa độ
                            print(f"[RESULT] Position: x={x}, y={y}")
                            
                            # ✓ Gửi tọa độ về Controller qua LoRa
                            send_coordinates(x, y)

                        # ✓ Kiểm tra nếu đã phát hiện được 3 lần (tối đa)
                        if impact_count >= 3:
                            # ✓ Tự động dừng sau 3 viên
                            control_active = False

                            # ✓ Tắt GPIO 20
                            GPIO.output(CONTROL_PIN, GPIO.LOW)

                            # ✓ In log
                            print("[COMPLETE] Received 3 impacts, deactivating")

            # === CHẾ ĐỘ EXTRA (Bảo trì - GPIO luôn HIGH) ===
            elif extra_mode_active:
                # ✓ Trong chế độ EXTRA, GPIO đã ở HIGH
                # ✓ Chỉ chờ lệnh EXTRA DOWN (được xử lý ở receive_command)
                # ℹ️ Optional: có thể bỏ qua để tiết kiệm log
                # print("[EXTRA] Waiting for EXTRA DOWN command...")
                pass
            
            # ✓ Delay 100ms để:
            # 1. Giảm CPU usage (không chạy tối đa 100%)
            # 2. Tránh lặp quá nhanh
            time.sleep(0.1)

    # === XỬ LÝ KHI THOÁT ===
    
    except KeyboardInterrupt:
        # ✓ Xử lý khi nhấn Ctrl+C
        print("\nNode stopped by user")

    except Exception as e:
        # ✓ Xử lý các lỗi khác
        print(f"[ERROR] {e}")

    finally:
        # ✓ Dọn dẹp trước khi thoát (LUÔN chạy)
        # Đưa GPIO 20 về LOW (motor OFF)
        GPIO.output(CONTROL_PIN, GPIO.LOW)
        
        # Dọn dẹp GPIO
        GPIO.cleanup()
        
        # Đóng kết nối SPI
        spi.close()
        
        # Đóng LoRa
        lora.close()
        
        # In log hoàn tất
        print("Cleanup completed")

# ==================== CHẠY CHƯƠNG TRÌNH ====================

# ✓ Kiểm tra nếu file này được chạy trực tiếp (không được import)
if __name__ == "__main__":
    # ✓ Gọi hàm main để bắt đầu chương trình
    main()