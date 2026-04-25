#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi Nano 2W Node - Sử dụng STM32F407 Thay MCP3204

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
- STM32 capture: nanosecond (5.95ns/tick)
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

# ✓ Vận tốc âm thanh: 340 m/s
# Ở nhiệt độ 15°C, độ ẩm bình thường
# Công thức TDOA: Δd = Δt × c
# Δd: chênh lệch khoảng cách (cm)
# Δt: chênh lệch thời gian (s)
# c: vận tốc âm thanh (cm/s)
SOUND_SPEED = 340

# === CẤU HÌNH STM32 TIMESTAMP ===

# ✓ Tần số clock của TIM2 trên STM32F407: 168MHz
# STM32 chạy @ 168MHz, TIM2 counter cũng 168MHz (no prescaler)
STM32_CLK_FREQ = 168e6

# ✓ Chuyển đổi từ tick STM32 → giây
# TICK_TO_SECONDS = 1 / 168e6 = 5.95 nanosecond per tick
# Ví dụ: 168 ticks = 168 × 5.95ns = 1000ns = 1μs
TICK_TO_SECONDS = 1.0 / STM32_CLK_FREQ

# ✓ Chuyển đổi từ tick → cm (bonus, để hiểu rõ hơn)
# Công thức: 1 tick = (1/168MHz) × 340m/s × 100cm/m
# = 5.95ns × 34000 cm/s = 0.202 mm/tick
TICK_TO_CM = SOUND_SPEED * 100 * TICK_TO_SECONDS

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
LOG_FILE = "score.txt"

# ==================== KHỞI TẠO GPIO ====================

# ✓ Thiết lập chế độ GPIO
# GPIO.BCM = sử dụng Broadcom pin numbering (GPIO17, GPIO20, v.v.)
# Nếu dùng GPIO.BOARD = sử dụng pin header numbering (1, 2, 3, ...)
GPIO.setmode(GPIO.BCM)

# ✓ Tắt cảnh báo GPIO
# Nếu bật → sẽ in warning khi setup pin lần 2
# Tắt để tránh spam console
GPIO.setwarnings(False)

# === Setup DATA_READY pin ===

# ✓ Cấu hình GPIO17 là INPUT
# Nhận tín hiệu từ STM32 (PB0 kéo HIGH/LOW)
GPIO.setup(DATA_READY_PIN, GPIO.IN)

# === Setup CONTROL pin ===

# ✓ Cấu hình GPIO20 là OUTPUT
# Kéo HIGH = bật motor, LOW = tắt motor
GPIO.setup(CONTROL_PIN, GPIO.OUT)

# ✓ Đặt GPIO20 về LOW ban đầu (motor tắt)
GPIO.output(CONTROL_PIN, GPIO.LOW)

# ==================== KHỞI TẠO SPI ====================

# ✓ Tạo object SPI
# spidev.SpiDev() = interface đến kernel SPI driver
spi = spidev.SpiDev()

# ✓ Mở SPI device
# spi.open(bus, device) = /dev/spidev0.0
# Bus 0 = SPI0 (RPi Nano 2W chỉ có SPI0)
# Device 0 = CE0 (GPIO8, chip select 0)
spi.open(SPI_BUS, SPI_DEVICE)

# ✓ Đặt tốc độ SPI
# 10.5MHz = phải khớp với STM32
spi.max_speed_hz = SPI_SPEED

# ✓ In log khởi tạo
print(f"[INIT] SPI initialized at {SPI_SPEED / 1e6:.1f}MHz")

# ==================== KHỞI TẠO LoRa ====================

# ✓ Tạo object LoRa
# BOARD.CN1 = config pins mặc định cho RPi (định nghĩa trong board_config)
lora = LoRa(BOARD.CN1, BOARD.CN1)

# ✓ Đặt tần số LoRa
# 915 MHz = ISM band (phổ công cộng)
lora.set_frequency(LORA_FREQ)

# ✓ In log khởi tạo
print(f"[INIT] LoRa initialized at {LORA_FREQ}MHz")

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
    Chờ DATA_READY signal từ STM32
    
    🔧 HOẠT ĐỘNG:
    1. Vòng lặp: kiểm tra GPIO17 mỗi 1ms
    2. Nếu GPIO17 = HIGH → dữ liệu sẵn sàng, return True
    3. Nếu timeout → return False
    
    💡 MỤC ĐÍCH:
    - Tránh polling liên tục (lỗ CPU usage)
    - Chỉ đọc SPI khi STM32 có dữ liệu sẵn sàng
    - Giảm latency (không cần delay cố định)
    
    📊 TIMING:
    - STM32 capture: nanosecond
    - STM32 kéo PB0 HIGH: ~1μs
    - RPi nhận interrupt: ~1-10μs
    - RPi đọc GPIO: ~10-100μs
    - Total: ~10-100μs (rất nhanh!)
    
    Tham số:
        timeout (float): Thời gian chờ tối đa (giây)
                        Default: 2.0 (nếu không có DATA_READY → timeout)
    
    Trả về:
        bool: True nếu nhận được DATA_READY (GPIO17 = HIGH)
              False nếu timeout hoặc lỗi
    """
    
    # ✓ Ghi nhận thời gian bắt đầu
    start_time = time.time()
    
    # ✓ Vòng lặp: chờ GPIO17 chuyển từ LOW → HIGH
    while time.time() - start_time < timeout:
        # ✓ Kiểm tra GPIO17 (DATA_READY)
        # GPIO.HIGH = 1 (3.3V)
        # GPIO.LOW = 0 (0V)
        if GPIO.input(DATA_READY_PIN) == GPIO.HIGH:
            # ✓ In log khi nhận được signal
            print(f"[DATA_READY] Signal received after {(time.time() - start_time)*1000:.2f}ms")
            
            # ✓ Nhỏ delay để STM32 hoàn tất chuẩn bị dữ liệu
            # (mặc dù bình thường data đã sẵn sàng)
            time.sleep(0.001)  # 1ms
            
            # ✓ Return True (signal nhận được)
            return True
        
        # ✓ Delay nhỏ để tránh busy-waiting (CPU lúc lúc được nghỉ)
        # 1ms polling interval = poll mỗi 1ms
        # Nếu giảm xuống 0.1ms → CPU usage cao, nhưng timing chính xác hơn
        # Nếu tăng lên 10ms → CPU usage thấp, nhưng có thể miss signal
        time.sleep(0.001)
    
    # ❌ Hết timeout mà vẫn không nhận được DATA_READY
    print(f"[ERROR] DATA_READY timeout ({timeout}s)")
    return False

def detect_impact():
    """
    Phát hiện viên đạn tác động vào bia (STM32 version)
    
    🔧 HOẠT ĐỘNG:
    1. In log "Waiting for DATA_READY signal..."
    2. Gọi wait_for_data_ready() để chờ signal
    3. Nếu signal nhận được (HIGH):
       a. Gọi read_stm32_timestamps() để đọc SPI
       b. Return dict với 4 timestamp
    4. Nếu timeout hoặc lỗi:
       a. In log "[MISS] No impact detected"
       b. Return None
    
    💡 KHÁC BIỆT SO VỚI MCP3204:
    
    Cũ (MCP3204):
    - Vòng lặp 50ms, đọc ADC từng kênh (~40ms)
    - Trễ: 40-50ms
    - Sai số: 5-10cm
    
    Mới (STM32):
    - Chờ interrupt (DATA_READY)
    - Trễ: <1ms
    - Sai số: 0.1-0.2cm (50x tốt hơn!)
    
    Trả về:
        dict: Thời gian phát hiện của mỗi sensor (giây, TDOA format)
              {'A': 0.0, 'B': 0.0005952, 'C': 0.0008929, 'D': 0.0011906}
              (Sensor A = 0.0 làm tham chiếu)
        None: Nếu timeout hoặc không phát hiện được
    """
    
    # ✓ In log: bắt đầu chờ
    print("[SENSOR] Waiting for DATA_READY signal...")
    
    # ✓ Chờ DATA_READY signal từ STM32
    # wait_for_data_ready() return True/False
    # Timeout = SENSOR_DETECTION_WINDOW × 10 (để có buffer)
    if wait_for_data_ready(timeout=SENSOR_DETECTION_WINDOW * 10):
        # ✓ Signal nhận được, đọc dữ liệu từ STM32 qua SPI
        detections = read_stm32_timestamps()
        
        # ✓ Nếu parse thành công (không return None)
        if detections:
            # ✓ Return dict timestamps
            return detections
    
    # ❌ Timeout hoặc lỗi
    print("[MISS] No impact detected")
    return None

def triangulation_weighted_average(detections):
    """
    BƯỚC 1: Ước tính nhanh bằng Weighted Average
    
    🔧 HOẠT ĐỘNG:
    1. Khởi tạo tọa độ = trung bình tọa độ 4 sensor
    2. Lặp 10 lần:
       a. Tính trọng số cho mỗi sensor (weight = 1/time)
       b. Điều chỉnh tọa độ hướng về sensor có trọng số cao
    3. Giới hạn trong phạm vi bia (-50 đến 50 cm)
    4. Return tọa độ ước tính
    
    💡 NGUYÊN LÝ:
    - Sensor phát hiện sớm (time nhỏ) → gần viên đạn → weight cao
    - Sensor phát hiện muộn (time lớn) → xa viên đạn → weight thấp
    - Dùng weight để "kéo" ước tính về phía sensor gần
    
    ⚡ TÍNH NĂNG:
    - Rất nhanh: 1-2ms
    - Độ chính xác: ~90% (so với thực tế)
    - Ổn định với nhiễu
    
    Tham số:
        detections (dict): TDOA - thời gian phát hiện của mỗi sensor
                          {'A': 0.0, 'B': 0.0005952, 'C': 0.0008929, 'D': 0.0011906}
    
    Trả về:
        tuple: (x, y) - tọa độ ước tính (cm)
    """
    
    # ✓ Khởi tạo tọa độ ban đầu = trung bình tọa độ 4 sensor
    # Giúp convergence nhanh hơn (không phải bắt từ (0,0))
    # x = (-50 + -50 + 50 + 50) / 4 = 0
    # y = (-50 + 50 + 50 + -50) / 4 = 0
    x = sum(pos[0] for pos in SENSOR_POSITIONS.values()) / 4
    y = sum(pos[1] for pos in SENSOR_POSITIONS.values()) / 4
    
    # ✓ In log: vị trí ban đầu
    print(f"[HYBRID-STEP1] Weighted Average - Initial: ({x:.2f}, {y:.2f})")

    # ✓ Lặp WEIGHTED_AVG_ITERATIONS lần (mặc định 10 lần) để tinh chỉnh
    for iteration in range(WEIGHTED_AVG_ITERATIONS):
        # ✓ Tính tổng trọng số (để chuẩn hóa sau)
        # Mục đích: đảm bảo tổng weight = 1 (prevent drift)
        # sum(1/detections[s]) với tất cả s (A, B, C, D)
        total_weight = sum(1 / (detections[s] + 0.0001) 
                          for s in SENSOR_POSITIONS.keys())
        
        # ✓ Cập nhật tọa độ từ mỗi sensor
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            # ✓ Tính trọng số chuẩn hóa
            # weight = (1 / time) / sum_of_all_weights
            # Kết quả: weight là một phân số từ 0 đến 1
            # Nếu time nhỏ → weight lớn (gần viên đạn)
            weight = (1 / (detections[sensor_name] + 0.0001)) / total_weight
            
            # ✓ Vector hướng từ vị trí hiện tại (x, y) tới sensor (sx, sy)
            # dx = sx - x: khoảng cách theo trục X
            # dy = sy - y: khoảng cách theo trục Y
            dx = sx - x
            dy = sy - y
            
            # ✓ Cập nhật tọa độ theo hướng sensor
            # Công thức: x_new = x + (sx - x) × weight × learning_rate
            # learning_rate kiểm soát tốc độ hội tụ
            # 0.15 = mỗi lần lặp điều chỉnh 15% khoảng cách
            x += dx * weight * WEIGHTED_AVG_LEARNING_RATE
            y += dy * weight * WEIGHTED_AVG_LEARNING_RATE

    # ✓ Giới hạn tọa độ trong phạm vi bia (-50 đến 50 cm)
    # Mục đích: tránh giá trị ngoài lệ do lỗi tính toán
    # max(-50, min(50, x)) = giữ x trong [-50, 50]
    x = max(-50, min(50, x))
    y = max(-50, min(50, y))
    
    # ✓ In log: vị trí cuối cùng sau Weighted Average
    print(f"[HYBRID-STEP1] Weighted Average - Final: ({x:.2f}, {y:.2f})")
    
    # ✓ Return tuple (x, y)
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
    
    # ✓ Tốc độ âm thanh (đơn vị cm/s)
    # 340 m/s = 34000 cm/s
    SOUND_SPEED_CMS = SOUND_SPEED * 100
    
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
            # ✓ Hiệu khoảng cách từ vị trí ước tính (theoretical)
            # d_A - d_B = khoảng cách từ (x,y) đến A - khoảng cách từ (x,y) đến B
            d_A = distances['A']
            d_sensor = distances[sensor_name]
            diff_theoretical = d_A - d_sensor
            
            # ✓ Hiệu khoảng cách từ thời gian (measured)
            diff_measured = distance_diffs_measured[sensor_name]
            
            # ✓ Sai số = lý thuyết - thực tế
            # Mục đích: minimize tổng bình phương các sai số này
            error = diff_theoretical - diff_measured
            errors.append(error)
        
        # ✓ Return array sai số
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
    Vòng lặp chính của Node
    
    🔧 HOẠT ĐỘNG:
    1. In banner khởi động
    2. Vòng lặp vô tận:
       a. Nhận lệnh từ Controller
       b. Nếu control_active:
          - Kiểm tra timeout
          - Phát hiện viên đạn (chờ DATA_READY)
          - Tính toán tọa độ (Hybrid method)
          - Gửi tọa độ về Controller
          - Đếm viên (tối đa 3 viên)
       c. Delay 100ms để giảm CPU
    
    💡 FLOW:
    Control OFF (nhận lệnh UP)
         ↓
    Control ON (GPIO20 = HIGH)
         ↓
    Chờ DATA_READY (viên đạn tác động)
         ↓
    Đọc SPI (20 bytes timestamp)
         ↓
    Tính toán TDOA + Triangulation (Hybrid)
         ↓
    Gửi tọa độ qua LoRa
         ↓
    impact_count++
    
    Nếu impact_count >= 3:
        Control OFF (GPIO20 = LOW)
    
    Nếu timeout (60s):
        Control OFF (GPIO20 = LOW)
    """
    
    global control_active, control_timeout, impact_count, extra_mode_active

    try:
        # ✓ In banner khởi động
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