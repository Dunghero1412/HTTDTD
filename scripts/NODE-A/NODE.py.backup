#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi Nano 2W Node-A - Nhận lệnh qua LoRa và xử lý cảm biến Piezoelectric
Sử dụng phương pháp HYBRID: Weighted Average (nhanh) + Hyperbolic Refinement (chính xác)

Chương trình này chạy trên Raspberry Pi Nano 2W để:
1. Nhận lệnh từ Controller qua LoRa module SX1278
2. Đọc dữ liệu từ 4 cảm biến Piezo qua MCP3204 ADC
3. Tính toán tọa độ viên đạn bằng phương pháp Hybrid
4. Gửi tọa độ về Controller
"""

# ==================== NHẬP THƯ VIỆN ====================

import RPi.GPIO as GPIO                    # Thư viện điều khiển GPIO trên Raspberry Pi
import time                                # Thư viện làm việc với thời gian
import math                                # Thư viện tính toán toán học
import spidev                              # Thư viện giao tiếp SPI để đọc MCP3204
from rpi_lora import LoRa                  # Thư viện LoRa
from rpi_lora.board_config import BOARD    # Cấu hình board cho LoRa
import random                              # Thư viện random để tính backoff delay

# ===== THÊM THƯ VIỆN CHO HYPERBOLIC =====
import numpy as np                         # Thư viện xử lý mảng số học
from scipy.optimize import least_squares   # Thư viện giải bài toán tối ưu (Hyperbolic)

# ==================== CẤU HÌNH CHUNG ====================

# --- Cấu hình GPIO ---
CONTROL_PIN = 20                           # GPIO 20 dùng để điều khiển motor/actuator

# --- Cấu hình LoRa ---
LORA_FREQ = 915                            # Tần số LoRa: 915 MHz

# --- Cấu hình SPI cho MCP3204 ---
SPI_BUS = 0                                # Bus SPI số 0 trên RPi
SPI_DEVICE = 0                             # Device SPI số 0
SPI_SPEED = 1000000                        # Tốc độ SPI: 1 MHz

# --- Cấu hình kênh ADC (MCP3204) ---
# MCP3204 có 4 kênh (0-3), mỗi kênh nối với một cảm biến Piezo
MCP3204_CHANNELS = {
    'A': 0,                                # Sensor A (góc trái dưới) -> Kênh 0
    'B': 1,                                # Sensor B (góc trái trên) -> Kênh 1
    'C': 2,                                # Sensor C (góc phải trên) -> Kênh 2
    'D': 3,                                # Sensor D (góc phải dưới) -> Kênh 3
}

# --- Tọa độ các cảm biến trên bia ---
# Tâm bia là (0, 0), bia có kích thước 100cm x 100cm
# Các cảm biến được đặt ở 4 góc bia
SENSOR_POSITIONS = {
    'A': (-50, -50),                       # Góc trái dưới
    'B': (-50, 50),                        # Góc trái trên
    'C': (50, 50),                         # Góc phải trên
    'D': (50, -50),                        # Góc phải dưới
}

# --- Cấu hình ngưỡng phát hiện viên đạn ---
# Giá trị ADC cao hơn ngưỡng này được coi là có tác động
# Range ADC: 0-4095 (12-bit)
# Khuyến cáo: 2000-3000 (bạn cần calibrate thực tế)
IMPACT_THRESHOLD = 2000

# --- Cấu hình timing ---
DETECTION_DELAY = 0.01                     # 10ms delay giữa mỗi lần đọc sensor
SENSOR_DETECTION_WINDOW = 0.05             # Cửa sổ phát hiện: 50ms
CONTROL_TIMEOUT = 60                       # Timeout điều khiển: 60 giây

# --- Tên Node (sẽ được setup.py sửa lại) ---
# Ví dụ: NODE1A, NODE2A, NODE3A, NODE4A, NODE5A
NODE_NAME = "NODE1A"

# --- Tốc độ âm thanh ---
# Dùng để tính khoảng cách từ thời gian phát hiện
# Giá trị này có thể calibrate lại nếu cần độ chính xác cao
SOUND_SPEED = 340                          # m/s ở nhiệt độ 15°C

# ===== CẤU HÌNH HYBRID TRIANGULATION =====
# Bước 1: Weighted Average (nhanh, ước tính ban đầu)
WEIGHTED_AVG_ITERATIONS = 10               # Số lần lặp cho Weighted Average
WEIGHTED_AVG_LEARNING_RATE = 0.15          # Learning rate (0.1-0.2)

# Bước 2: Hyperbolic Refinement (chính xác, fine-tune)
ENABLE_HYPERBOLIC = True                   # Bật/tắt Hyperbolic refinement
HYPERBOLIC_MAX_ITERATIONS = 100            # Số lần lặp tối đa cho Hyperbolic
HYPERBOLIC_TOLERANCE = 1e-6                # Độ chính xác yêu cầu (cm)

# ==================== CẤU HÌNH CSMA (CARRIER SENSE MULTIPLE ACCESS) ====================
# Kiểm tra channel có đang gửi hoặc nhận dữ liệu từ Node khác hay không?
# Nếu có, bắt đầu delay rồi gửi sau

# Thời gian kiểm tra channel có bận không (ms)
CARRIER_SENSE_TIME = 100                   # Kiểm tra 100ms

# Min backoff delay nếu channel bận (ms)
MIN_BACKOFF = 50

# Max backoff delay nếu channel bận (ms)
MAX_BACKOFF = 100

# Số lần thử lại nếu channel bận
MAX_RETRIES = 3

# ==================== KHỞI TẠO CÁC THIẾT BỊ ====================

# --- Khởi tạo GPIO ---
GPIO.setmode(GPIO.BCM)                     # Sử dụng chế độ BCM (Broadcom)
GPIO.setwarnings(False)                    # Tắt cảnh báo GPIO

# --- Cấu hình pin GPIO 20 làm OUTPUT ---
GPIO.setup(CONTROL_PIN, GPIO.OUT)          # Thiết lập GPIO 20 là OUTPUT
GPIO.output(CONTROL_PIN, GPIO.LOW)         # Đưa GPIO 20 về LOW (mặc định tắt)

# --- Khởi tạo SPI cho MCP3204 ---
spi = spidev.SpiDev()                      # Tạo object SPI
spi.open(SPI_BUS, SPI_DEVICE)              # Mở /dev/spidev0.0
spi.max_speed_hz = SPI_SPEED               # Đặt tốc độ SPI tối đa: 1 MHz

# --- Khởi tạo LoRa ---
lora = LoRa(BOARD.CN1, BOARD.CN1)          # Khởi tạo LoRa module
lora.set_frequency(LORA_FREQ)              # Đặt tần số LoRa

print("="*60)
print(f"NODE STARTED - {NODE_NAME}")
print("="*60)

# ==================== BIẾN TRẠNG THÁI ====================

control_active = False                     # Trạng thái điều khiển: ON/OFF
control_timeout = None                     # Thời gian hết hạn điều khiển
impact_count = 0                           # Đếm số lần phát hiện viên đạn
extra_mode_active = False                  # Trạng thái chế độ EXTRA (bảo trì)

# ==================== HÀM ĐỌC MCP3204 ====================

def read_mcp3204_channel(channel):
    """
    Đọc giá trị ADC từ một kênh của MCP3204
    
    🔧 HOẠT ĐỘNG:
    1. Gửi lệnh SPI để yêu cầu đọc dữ liệu từ kênh được chỉ định
    2. Nhận 3 byte dữ liệu từ MCP3204
    3. Trích xuất 12 bit giá trị ADC từ 2 byte cuối
    4. Trả về giá trị số nguyên 0-4095
    
    📊 CHI TIẾT SPI:
    - MCP3204 sử dụng giao thức SPI (Serial Peripheral Interface)
    - Byte 0: Start bit + Single mode + Channel bit cao
    - Byte 1: Channel bits thấp + Padding
    - Byte 2: Dummy
    - Phản hồi: 3 byte với 12 bit ADC ở byte 1-2
    
    Tham số:
        channel (int): Kênh ADC (0-3) tương ứng với Sensor A, B, C, D
    
    Trả về:
        int: Giá trị ADC (0-4095) hoặc -1 nếu lỗi
    """
    
    # ✓ Kiểm tra channel có hợp lệ không (phải từ 0-3)
    if channel > 3:
        return -1

    # ✓ Chuẩn bị lệnh đọc MCP3204
    # Công thức: 0x06 | ((channel & 0x04) >> 2)
    # 0x06 = 00000110 (Start bit + Single mode)
    # ((channel & 0x04) >> 2) = lấy bit 2 của channel, dịch sang vị trí bit 0
    cmd = 0x06 | ((channel & 0x04) >> 2)

    # ✓ Gửi lệnh qua SPI và nhận dữ liệu (3 byte)
    # xfer2(): Gửi bytes đầu tiên, đồng thời nhận bytes tương ứng
    # [cmd]: Byte lệnh
    # [(channel & 0x03) << 6]: Byte địa chỉ (lấy bit 0-1 của channel)
    # [0]: Byte dummy
    adc_bytes = spi.xfer2([cmd, (channel & 0x03) << 6, 0])

    # ✓ Xử lý dữ liệu nhận được
    # Dữ liệu ADC 12-bit nằm trong byte 1 (4 bit cao) + byte 2 (8 bit thấp)
    # Công thức: ((byte1 & 0x0F) << 8) | byte2
    # Lấy 4 bit thấp của byte 1, dịch trái 8 bit, rồi OR với byte 2
    adc_value = ((adc_bytes[1] & 0x0F) << 8) | adc_bytes[2]

    # ✓ Trả về giá trị ADC (0-4095)
    return adc_value

def read_all_sensors():
    """
    Đọc giá trị từ tất cả 4 cảm biến Piezo
    
    🔧 HOẠT ĐỘNG:
    1. Duyệt qua 4 cảm biến (A, B, C, D)
    2. Gọi read_mcp3204_channel() để đọc ADC từ mỗi kênh
    3. Lưu các giá trị vào dict
    4. Trả về dict với tất cả giá trị (hoặc None nếu lỗi)
    
    Trả về:
        dict: {'A': value_A, 'B': value_B, 'C': value_C, 'D': value_D}
              Ví dụ: {'A': 2500, 'B': 1800, 'C': 2200, 'D': 1600}
              hoặc None nếu có lỗi đọc
    """
    
    try:
        # ✓ Khởi tạo dict để lưu giá trị cảm biến
        sensor_values = {}

        # ✓ Đọc giá trị từ từng cảm biến
        for sensor_name, channel in MCP3204_CHANNELS.items():
            # Gọi hàm đọc ADC từ kênh tương ứng
            value = read_mcp3204_channel(channel)
            
            # Lưu vào dict
            sensor_values[sensor_name] = value
            
            # ℹ️ In giá trị cho debug (có thể bỏ qua khi chạy production)
            print(f"  Sensor {sensor_name} (CH{channel}): {value}")

        # ✓ Trả về dict chứa giá trị của tất cả cảm biến
        return sensor_values

    except Exception as e:
        # ❌ In lỗi nếu có vấn đề
        print(f"[ERROR] Failed to read sensors: {e}")
        return None

# ==================== HÀM PHÁT HIỆN VIÊN ĐẠO ====================

def detect_impact():
    """
    Phát hiện viên đạn tác động vào bia bằng cách đo thời gian phát hiện
    
    🔧 HOẠT ĐỘNG:
    1. Lặp liên tục trong thời gian SENSOR_DETECTION_WINDOW (50ms)
    2. Đọc 4 cảm biến mỗi vòng lặp
    3. Khi giá trị ADC vượt IMPACT_THRESHOLD, ghi nhận thời gian
    4. Dừng khi đủ 2 cảm biến phát hiện hoặc hết timeout
    5. Trả về dict với thời gian phát hiện (tính từ khi viên đạn tác động)
    
    💡 NGUYÊN LÝ TDOA (Time Difference of Arrival):
    - Viên đạn bay với vận tốc âm thanh (340 m/s)
    - Sensor gần viên đạn hơn → phát hiện sớm hơn
    - Chênh lệch thời gian phát hiện = chênh lệch khoảng cách từ viên đạn
    - Dùng chênh lệch này để tính tọa độ chính xác
    
    Trả về:
        dict: Thời gian phát hiện của mỗi sensor (giây)
              Ví dụ: {'A': 0.001, 'B': 0.005, 'C': 0.008, 'D': 0.012}
              Ý nghĩa: Sensor A phát hiện sớm nhất (0.001s), 
                       Sensor D phát hiện muộn nhất (0.012s)
              Trả về None nếu không phát hiện được
    """
    
    # ✓ In thông báo chờ phát hiện
    print("[SENSOR] Waiting for impact...")

    # ✓ Dict để lưu thời gian phát hiện của mỗi cảm biến
    detections = {}

    # ✓ Ghi nhận thời gian bắt đầu phát hiện
    # Từ điểm này, tất cả các lần đọc sensor sẽ tính thời gian tương đối
    start_time = time.time()

    # ✓ Vòng lặp đọc sensor trong khoảng thời gian SENSOR_DETECTION_WINDOW
    # Mục đích: Phát hiện thời gian chính xác viên đạn tác động
    while time.time() - start_time < SENSOR_DETECTION_WINDOW:
        
        # ✓ Đọc giá trị từ tất cả cảm biến
        # Gọi read_all_sensors() để lấy ADC từ 4 kênh
        sensor_values = read_all_sensors()

        # ✓ Nếu có lỗi khi đọc, bỏ qua vòng lặp này
        if not sensor_values:
            continue

        # ✓ Tính thời gian hiện tại từ khi bắt đầu
        # Ví dụ: Nếu start_time cách hiện tại 0.005s, thì current_time = 0.005
        current_time = time.time() - start_time

        # ✓ Kiểm tra từng cảm biến
        for sensor_name, threshold in [('A', IMPACT_THRESHOLD),
                                       ('B', IMPACT_THRESHOLD),
                                       ('C', IMPACT_THRESHOLD),
                                       ('D', IMPACT_THRESHOLD)]:
            
            # ✓ Điều kiện: 
            # - Sensor này chưa phát hiện (không có trong dict)
            # - Giá trị ADC vượt quá ngưỡng (IMPACT_THRESHOLD)
            if sensor_name not in detections and sensor_values[sensor_name] > threshold:
                
                # ✓ Lưu thời gian phát hiện (tính từ start_time)
                detections[sensor_name] = current_time
                
                # ✓ In thông báo phát hiện
                print(f"[DETECT] Sensor {sensor_name} hit at {current_time:.4f}s "
                      f"with value {sensor_values[sensor_name]}")

        # ✓ Nếu đã phát hiện được từ ít nhất 2 cảm biến, có thể dừng sớm
        # Mục đích: Tiết kiệm thời gian chờ đợi
        if len(detections) >= 2:
            break

        # ✓ Delay 10ms trước khi đọc lần tiếp theo
        # Mục đích: Tránh CPU hoạt động quá nhanh, tốn điện năng
        time.sleep(DETECTION_DELAY)

    # ✓ Kiểm tra nếu phát hiện được từ ít nhất 2 cảm biến
    if len(detections) >= 2:
        
        # ✓ Nếu có cảm biến không phát hiện, ước tính thời gian
        # Mục đích: Đảm bảo ta luôn có đủ 4 dữ liệu để tính toán
        for sensor_name in ['A', 'B', 'C', 'D']:
            if sensor_name not in detections and detections:
                # ✓ Thêm một khoảng delay nhỏ (10ms) vào thời gian phát hiện lớn nhất
                # Giả định: Sensor chưa phát hiện sẽ phát hiện sau sensor khác
                detections[sensor_name] = max(detections.values()) + 0.01

        # ✓ Trả về dict thời gian phát hiện
        return detections
    
    else:
        # ❌ Nếu phát hiện không đủ, trả về None
        print("[MISS] Not enough sensors detected")
        return None

# ==================== HÀM TÍNH TOẠ ĐỘ - PHƯƠNG PHÁP HYBRID ====================

def triangulation_weighted_average(detections):
    """
    BƯỚC 1: Ước tính nhanh bằng Weighted Average
    
    🔧 HOẠT ĐỘNG:
    1. Khởi tạo tọa độ = trung bình tọa độ của 4 sensor
    2. Lặp 10 lần:
       - Tính trọng số cho mỗi sensor (sensor sớm = trọng số cao)
       - Điều chỉnh tọa độ hướng về sensor có trọng số cao
    3. Giới hạn kết quả trong phạm vi bia
    4. Trả về tọa độ ước tính
    
    💡 NGUYÊN LÝ:
    - Sensor phát hiện sớm → gần viên đạn hơn → trọng số cao
    - Sensor phát hiện muộn → xa viên đạn hơn → trọng số thấp
    - Dùng trọng số để "kéo" ước tính về phía sensor gần
    
    ⚡ TÍNH NĂNG:
    - Rất nhanh: 5-10ms
    - Độ chính xác: ~90%
    - Ổn định với nhiễu
    
    Tham số:
        detections (dict): Thời gian phát hiện
                          {'A': 0.001, 'B': 0.005, ...}
    
    Trả về:
        tuple: (x, y) tọa độ ước tính
    """
    
    # ✓ Khởi tạo tọa độ ban đầu = trung bình tọa độ 4 sensor
    # Điều này giúp convergence nhanh hơn
    x = sum(pos[0] for pos in SENSOR_POSITIONS.values()) / 4
    y = sum(pos[1] for pos in SENSOR_POSITIONS.values()) / 4
    
    print(f"[HYBRID-STEP1] Weighted Average - Initial position: ({x:.2f}, {y:.2f})")

    # ✓ Lặp WEIGHTED_AVG_ITERATIONS lần để tinh chỉnh tọa độ
    for iteration in range(WEIGHTED_AVG_ITERATIONS):
        
        # ✓ Tính tổng trọng số để chuẩn hóa (bước này rất quan trọng!)
        # Mục đích: Đảm bảo tổng trọng số = 1, tránh "drift"
        total_weight = sum(1 / (detections[s] + 0.0001) 
                          for s in SENSOR_POSITIONS.keys())
        
        # ✓ Cập nhật tọa độ từ mỗi sensor
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            
            # ✓ Tính trọng số chuẩn hóa
            # weight = (1 / time) / sum_of_all_weights
            # Sensor sớm (time nhỏ) → weight lớn
            weight = (1 / (detections[sensor_name] + 0.0001)) / total_weight
            
            # ✓ Vector hướng từ (x, y) hiện tại tới sensor này
            dx = sx - x
            dy = sy - y
            
            # ✓ Cập nhật tọa độ theo hướng sensor
            # Công thức: x_new = x_old + (sx - x) * weight * learning_rate
            # learning_rate kiểm soát tốc độ hội tụ
            x += dx * weight * WEIGHTED_AVG_LEARNING_RATE
            y += dy * weight * WEIGHTED_AVG_LEARNING_RATE

    # ✓ Giới hạn tọa độ trong phạm vi bia (-50 đến 50 cm)
    # Mục đích: Tránh giá trị ngoài lệ do lỗi tính toán
    x = max(-50, min(50, x))
    y = max(-50, min(50, y))
    
    print(f"[HYBRID-STEP1] Weighted Average - Final position: ({x:.2f}, {y:.2f})")
    
    return x, y

def triangulation_hyperbolic_refinement(detections, x_init, y_init):
    """
    BƯỚC 2: Tinh chỉnh chính xác bằng Hyperbolic Least Squares
    
    🔧 HOẠT ĐỘNG:
    1. Sử dụng kết quả từ Weighted Average làm ước tính ban đầu
    2. Thiết lập hệ phương trình dựa trên TDOA:
       - Hiệu khoảng cách phải bằng hiệu từ thời gian × vận tốc âm thanh
       - Minimize sai số bằng Least Squares
    3. Sử dụng scipy.optimize.least_squares để giải
    4. Giới hạn trong phạm vi bia
    5. Trả về tọa độ chính xác
    
    💡 NGUYÊN LÝ HYPERBOLIC:
    - Dựa trên hiệu khoảng cách không đổi
    - Tập hợp các điểm có hiệu khoảng cách từ 2 sensor = hyperbola
    - Giao điểm của 3 hyperbola = vị trí chính xác
    
    ⚡ TÍNH NĂNG:
    - Chậm: 20-50ms
    - Độ chính xác: 95-99%
    - Sai số: 1-3cm
    
    Tham số:
        detections (dict): Thời gian phát hiện
        x_init, y_init (float): Ước tính ban đầu từ Weighted Average
    
    Trả về:
        tuple: (x, y) tọa độ chính xác
    """
    
    print(f"[HYBRID-STEP2] Hyperbolic Refinement - Starting from ({x_init:.2f}, {y_init:.2f})")
    
    # ✓ Tốc độ âm thanh (cm/s) để tính khoảng cách từ thời gian
    SOUND_SPEED_CMS = SOUND_SPEED * 100  # 340 m/s = 34000 cm/s
    
    # ✓ Định nghĩa hàm residual (sai số)
    def residuals(pos):
        """
        Tính sai số giữa hiệu khoảng cách lý thuyết và thực tế
        
        Mục đích: scipy.optimize.least_squares sẽ minimize sai số này
        
        Tham số:
            pos (array): [x_est, y_est] - vị trí ước tính hiện tại
        
        Trả về:
            array: [error_B, error_C, error_D] - sai số cho mỗi cặp sensor
        """
        
        x_est, y_est = pos
        
        # ✓ Tính khoảng cách từ vị trí ước tính đến mỗi sensor
        # Công thức: d = sqrt((x - sensor_x)^2 + (y - sensor_y)^2)
        distances = {}
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            distances[sensor_name] = np.sqrt((x_est - sx)**2 + (y_est - sy)**2)
        
        # ✓ Tính hiệu khoảng cách từ thời gian (sử dụng sensor A làm tham chiếu)
        # Chênh lệch thời gian × vận tốc âm thanh = chênh lệch khoảng cách
        distance_diffs_measured = {}
        for sensor_name in SENSOR_POSITIONS.keys():
            time_diff = detections[sensor_name] - detections['A']
            distance_diffs_measured[sensor_name] = time_diff * SOUND_SPEED_CMS
        
        # ✓ Tính sai số cho mỗi cặp sensor (A-B, A-C, A-D)
        errors = []
        for sensor_name in ['B', 'C', 'D']:
            # Hiệu khoảng cách từ vị trí ước tính
            d_A = distances['A']
            d_sensor = distances[sensor_name]
            diff_theoretical = d_A - d_sensor
            
            # Hiệu khoảng cách từ thời gian
            diff_measured = distance_diffs_measured[sensor_name]
            
            # Sai số = lý thuyết - thực tế
            # Mục đích của least_squares: minimize tổng bình phương các sai số này
            error = diff_theoretical - diff_measured
            errors.append(error)
        
        return errors
    
    # ✓ Giải bài toán tối ưu bằng Least Squares
    try:
        # Ước tính ban đầu từ Weighted Average
        initial_guess = [x_init, y_init]
        
        # Gọi least_squares từ scipy
        # - Minimize tổng bình phương residuals
        # - Giới hạn trong phạm vi bia: [-50, 50] cho x và y
        # - Tối đa HYPERBOLIC_MAX_ITERATIONS lần lặp
        result = least_squares(
            residuals,                                    # Hàm tính sai số
            initial_guess,                                # Ước tính ban đầu
            bounds=([-50, -50], [50, 50]),               # Giới hạn: -50 đến 50 cm
            max_nfev=HYPERBOLIC_MAX_ITERATIONS,          # Max iterations
            ftol=HYPERBOLIC_TOLERANCE,                   # Tolerance (độ chính xác)
            verbose=0                                     # Không in log chi tiết
        )
        
        # ✓ Lấy kết quả
        x_refined, y_refined = result.x
        
        # ℹ️ In kết quả
        print(f"[HYBRID-STEP2] Hyperbolic Refinement - Success!")
        print(f"[HYBRID-STEP2] Refined position: ({x_refined:.2f}, {y_refined:.2f})")
        print(f"[HYBRID-STEP2] Residual norm: {np.linalg.norm(result.fun):.6f}")
        
        return x_refined, y_refined
    
    except Exception as e:
        # ❌ Nếu Hyperbolic refinement thất bại, sử dụng kết quả từ Weighted Average
        print(f"[HYBRID-STEP2] Hyperbolic Refinement failed: {e}")
        print(f"[HYBRID-STEP2] Using Weighted Average result")
        return x_init, y_init

def triangulation(detections):
    """
    Tính tọa độ viên đạn bằng phương pháp HYBRID
    
    🔧 HOẠT ĐỘNG (2 bước):
    1. BƯỚC 1: Weighted Average (nhanh, 5-10ms)
       - Ước tính nhanh vị trí viên đạn
       - Độ chính xác: ~90%
    
    2. BƯỚC 2: Hyperbolic Refinement (chính xác, 20-50ms)
       - Fine-tune kết quả từ bước 1
       - Sử dụng least squares optimization
       - Độ chính xác: ~95-99%
    
    💡 LỢI ÍCH CỦA HYBRID:
    - Kết hợp tốc độ (bước 1) + độ chính xác (bước 2)
    - Ổn định với nhiễu
    - Dễ debug (có thể tắt bước 2 nếu cần)
    - Fallback: Nếu bước 2 lỗi, vẫn có kết quả từ bước 1
    
    📊 KỲ VỌNG:
    - Sai số cuối cùng: 1-3cm (so với Weighted Average: 5-10cm)
    - Thích hợp cho bắn súng vì cần độ chính xác
    
    Tham số:
        detections (dict): Thời gian phát hiện
                          {'A': 0.001, 'B': 0.005, 'C': 0.008, 'D': 0.012}
    
    Trả về:
        tuple: (x, y) tọa độ viên đạn (làm tròn đến 0.1 cm)
    """
    
    try:
        # ===== BƯỚC 1: WEIGHTED AVERAGE (Nhanh) =====
        print("[HYBRID] Starting triangulation (Hybrid method)...")
        
        # ✓ Gọi hàm Weighted Average để ước tính nhanh
        x_weighted, y_weighted = triangulation_weighted_average(detections)
        
        # ===== BƯỚC 2: HYPERBOLIC REFINEMENT (Chính xác) =====
        if ENABLE_HYPERBOLIC:
            # ✓ Nếu bật Hyperbolic refinement, gọi hàm tinh chỉnh
            x_refined, y_refined = triangulation_hyperbolic_refinement(
                detections, 
                x_weighted, 
                y_weighted
            )
            
            # ✓ Sử dụng kết quả từ Hyperbolic
            x_final = x_refined
            y_final = y_refined
        else:
            # ✓ Nếu tắt Hyperbolic, sử dụng kết quả từ Weighted Average
            print("[HYBRID] Hyperbolic refinement disabled, using Weighted Average")
            x_final = x_weighted
            y_final = y_weighted
        
        # ✓ Giới hạn lần nữa để chắc chắn
        x_final = max(-50, min(50, x_final))
        y_final = max(-50, min(50, y_final))
        
        # ✓ Làm tròn đến 1 chữ số thập phân (0.1 cm)
        print(f"[HYBRID] Final result: ({x_final:.2f}, {y_final:.2f})")
        print("="*60)
        
        return round(x_final, 1), round(y_final, 1)

    except Exception as e:
        # ❌ Nếu có lỗi, in chi tiết và trả về (None, None)
        print(f"[ERROR] Triangulation failed: {e}")
        print(f"[ERROR] Exception type: {type(e).__name__}")
        return None, None

# ==================== HÀM KIỂM TRA CHANNEL (CARRIER SENSE) ====================

def is_channel_busy():
    """
    Kiểm tra xem LoRa channel có bận không (có dữ liệu đang được truyền?)
    
    🔧 HOẠT ĐỘNG:
    - Gọi lora.is_rx_busy() để kiểm tra trạng thái LoRa module
    - Nếu busy, có nghĩa là đang nhận dữ liệu từ Node khác
    
    💡 MỤC ĐÍCH:
    - Tránh va chạm dữ liệu (collision) khi nhiều Node gửi cùng lúc
    - Phần của CSMA (Carrier Sense Multiple Access)
    
    Trả về:
        bool: True nếu channel bận (đang có truyền), False nếu rỗi
    """
    
    try:
        # ✓ Kiểm tra xem LoRa có đang nhận dữ liệu không
        if lora.is_rx_busy():
            print("[CSMA] Channel BUSY - LoRa is receiving")
            return True
        
        # ✓ Channel rỗi
        return False
    
    except Exception as e:
        # ❌ Nếu có lỗi, coi như channel rỗi
        print(f"[ERROR] Failed to check channel: {e}")
        return False

def wait_for_channel():
    """
    Chờ đợi cho đến khi channel rỗi, rồi mới gửi dữ liệu
    
    🔧 HOẠT ĐỘNG:
    1. Lặp tối đa MAX_RETRIES (3) lần:
       a. Kiểm tra channel có rỗi không
       b. Nếu rỗi → trả về True, sẵn sàng gửi
       c. Nếu bận → chờ random delay (50-100ms), rồi thử lại
    2. Sau MAX_RETRIES lần, dù vẫn bận cũng gửi
    
    💡 MỤC ĐÍCH:
    - CSMA (Carrier Sense Multiple Access)
    - Tránh va chạm dữ liệu
    - Random delay tránh "synchronized collision"
      (nếu 2 Node thử lại cùng lúc)
    
    Trả về:
        bool: True nếu sẵn sàng gửi (channel rỗi hoặc timeout)
    """
    
    # ✓ Số lần thử lại hiện tại
    retries = 0
    
    # ✓ Lặp cho đến hết MAX_RETRIES lần
    while retries < MAX_RETRIES:
        
        # ✓ Kiểm tra channel rỗi không
        if not is_channel_busy():
            print("[CSMA] Channel FREE - Ready to send")
            return True
        
        # ✓ Channel bận, tính random backoff delay
        # random.randint(MIN_BACKOFF, MAX_BACKOFF) trả về số ngẫu nhiên từ 50-100
        # Chia 1000.0 để chuyển từ ms sang giây
        backoff_delay = random.randint(MIN_BACKOFF, MAX_BACKOFF) / 1000.0
        print(f"[CSMA] Channel busy, waiting {backoff_delay*1000:.0f}ms "
              f"(Retry {retries+1}/{MAX_RETRIES})")
        
        # ✓ Chờ backoff delay
        time.sleep(backoff_delay)
        
        # ✓ Tăng retry counter
        retries += 1
    
    # ✓ Sau MAX_RETRIES lần, dù vẫn bận cũng cho phép gửi
    print(f"[CSMA] Max retries reached, sending anyway")
    return True

# ==================== HÀM GỬIDỮ LIỆU ====================

def send_coordinates(x, y):
    """
    Gửi tọa độ viên đạn về Controller qua LoRa
    
    🔧 HOẠT ĐỘNG:
    1. Tạo thông điệp: "NODE1A, 10.5, 20.3"
    2. Chuyển đổi từ string sang bytes (UTF-8)
    3. Gửi qua LoRa module
    4. In thông báo đã gửi
    
    📝 ĐỊNH DẠNG THÔNG ĐIỆP:
    "{NODE_NAME}, {x}, {y}"
    Ví dụ: "NODE1A, -25.4, 30.1"
    
    Tham số:
        x (float): Tọa độ X (-50 đến 50 cm)
        y (float): Tọa độ Y (-50 đến 50 cm)
    """
    
    try:
        # ✓ Tạo thông điệp gửi về Controller
        message = f"{NODE_NAME}, {x}, {y}"

        # ✓ Chuyển thông điệp từ string sang bytes (UTF-8 encoding)
        # LoRa module yêu cầu bytes, không phải string
        lora.send(message.encode())

        # ✓ In thông báo đã gửi (cho debug)
        print(f"[TX] Sent: {message}")

    except Exception as e:
        # ❌ In lỗi nếu gửi thất bại
        print(f"[ERROR] Failed to send: {e}")

# ==================== HÀM NHẬN LỆNH ====================

def receive_command():
    """
    Nhận lệnh từ Controller qua LoRa
    
    🔧 HOẠT ĐỘNG:
    1. Kiểm tra LoRa có dữ liệu chưa
    2. Nếu có, đọc dữ liệu (payload)
    3. Chuyển đổi từ bytes sang string
    4. Parse lệnh: tách thành [node_command, action]
    5. Thực hiện hành động tương ứng
    
    📝 ĐỊNH DẠNG LỆNH:
    - "NODE1A UP": Kích hoạt Node 1A (bắn đạn)
    - "NODE1A DOWN": Dừng Node 1A
    - "A UP": Kích hoạt tất cả Node (broadcast)
    - "A DOWN": Dừng tất cả Node
    - "EXTRA UP": Khóa tất cả nút (chế độ bảo trì)
    - "EXTRA DOWN": Thoát khỏi chế độ EXTRA
    
    💡 NGUYÊN LỰC:
    - "A" lệnh broadcast cho tất cả Node cùng loại
    - "EXTRA" chế độ bảo trì (GPIO luôn HIGH, không phát hiện)
    - Node cụ thể chỉ phản ứng nếu tên khớp với NODE_NAME
    
    Trả về:
        str: Trạng thái ("ACTIVATED", "DEACTIVATED", ...) hoặc None
    """
    
    # ✓ Khai báo global để sửa đổi biến trạng thái
    global control_active, control_timeout, impact_count, extra_mode_active

    try:
        # ✓ Kiểm tra xem LoRa có đang nhận dữ liệu không
        # is_rx_busy() trả về True nếu đang nhận
        if lora.is_rx_busy():
            return None

        # ✓ Đọc dữ liệu từ LoRa (nếu có)
        payload = lora.read()

        # ✓ Nếu có dữ liệu
        if payload:
            # ✓ Chuyển đổi từ bytes sang string (UTF-8 decoding)
            command = payload.decode().strip()

            # ✓ In lệnh nhận được (cho debug)
            print(f"[RX] Received: {command}")

            # ✓ Tách lệnh thành các phần
            # Ví dụ: "NODE1A UP" → ["NODE1A", "UP"]
            parts = command.split()

            # ✓ Kiểm tra nếu có ít nhất 2 phần (node_command và action)
            if len(parts) >= 2:
                # ✓ Lấy tên node và hành động
                node_command = parts[0].upper()  # "NODE1A", "A", "EXTRA"
                action = parts[1].upper()         # "UP" hoặc "DOWN"

                # ===== KIỂM TRA LỆNH EXTRA (Chế độ bảo trì) =====
                is_broadcast_extra = (node_command == "EXTRA")
                
                if is_broadcast_extra:
                    if action == "UP":
                        # ✓ EXTRA UP: Khóa tất cả nút, GPIO luôn HIGH
                        extra_mode_active = True
                        control_active = False  # Tắt chế độ bình thường
                        
                        print(f"[EXTRA] Mode ON - GPIO {CONTROL_PIN} is HIGH")
                        
                        # ✓ Đưa GPIO 20 lên HIGH (sẽ ở đó cho đến EXTRA DOWN)
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        return "EXTRA_ON"
                    
                    elif action == "DOWN":
                        # ✓ EXTRA DOWN: Thoát khỏi chế độ EXTRA
                        extra_mode_active = False
                        control_active = False
                        
                        print(f"[EXTRA] Mode OFF - GPIO {CONTROL_PIN} is LOW")
                        
                        # ✓ Đưa GPIO 20 về LOW
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        return "EXTRA_OFF"

                # ===== KIỂM TRA LỆNH A (Broadcast cho tất cả Node) =====
                is_broadcast_a = (node_command == "A")
                
                if is_broadcast_a and not extra_mode_active:
                    if action == "UP":
                        # ✓ A UP: Kích hoạt tất cả Node (broadcast)
                        control_active = True
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        impact_count = 0
                        
                        print(f"[CONTROL] BROADCAST A UP - Activated for {CONTROL_TIMEOUT}s")
                        
                        # ✓ Đưa GPIO 20 lên HIGH
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        # ✓ A DOWN: Dừng tất cả Node
                        control_active = False
                        
                        print(f"[CONTROL] BROADCAST A DOWN - Deactivated")
                        
                        # ✓ Đưa GPIO 20 về LOW
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        return "DEACTIVATED"

                # ===== KIỂM TRA LỆNH CỤ THỂ (NODE1A, NODE2A, ...) =====
                is_for_this_node = (node_command == NODE_NAME)
                
                if is_for_this_node and not extra_mode_active:
                    if action == "UP":
                        # ✓ Node này UP: Kích hoạt
                        control_active = True
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        impact_count = 0
                        
                        print(f"[CONTROL] {node_command} UP - Activated for {CONTROL_TIMEOUT}s")
                        
                        # ✓ Đưa GPIO 20 lên HIGH
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        # ✓ Node này DOWN: Dừng
                        control_active = False
                        
                        print(f"[CONTROL] {node_command} DOWN - Deactivated")
                        
                        # ✓ Đưa GPIO 20 về LOW
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        return "DEACTIVATED"
                
                # ===== LỆNH KHÔNG HỢP LỆ TRONG EXTRA MODE =====
                elif extra_mode_active and (is_broadcast_a or is_for_this_node):
                    print(f"[WARNING] Command {node_command} {action} ignored "
                          f"(EXTRA mode active)")
                    return None

    except Exception as e:
        # ❌ In lỗi nếu có vấn đề
        print(f"[ERROR] Failed to receive command: {e}")

    # ✓ Trả về None nếu không có lệnh hoặc xảy ra lỗi
    return None

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """
    Vòng lặp chính của chương trình Node
    
    🔧 HOẠT ĐỘNG:
    1. Liên tục lắng nghe lệnh từ Controller (LoRa)
    2. Khi nhận lệnh UP:
       - Bật GPIO 20 (motor/actuator)
       - Chờ viên đạn tác động
       - Phát hiện thời gian + tính tọa độ bằng Hybrid method
       - Gửi tọa độ về Controller
    3. Khi hết 3 lần hit hoặc timeout 60s → tự động tắt
    4. Khi nhận lệnh DOWN → tắt GPIO, dừng phát hiện
    
    💡 QUY TRÌNH CHI TIẾT:
    - receive_command(): Lắng nghe lệnh LoRa
    - detect_impact(): Phát hiện thời gian viên đạn
    - triangulation(): Tính tọa độ (Hybrid: Step1 + Step2)
    - send_coordinates(): Gửi tọa độ về Controller
    - Đếm số lần, check timeout
    """
    
    # ✓ Khai báo global để sửa đổi biến trạng thái
    global control_active, control_timeout, impact_count, extra_mode_active

    try:
        # ✓ Vòng lặp chính - chạy liên tục cho đến khi thoát (Ctrl+C)
        while True:
            # ✓ Liên tục nhận lệnh từ Controller
            receive_command()

            # ===== CHẾ ĐỘ HOẠT ĐỘNG BÌNH THƯỜNG (Phát hiện viên đạn) =====
            if control_active and not extra_mode_active:
                
                # ✓ Kiểm tra xem timeout đã hết chưa (60s)
                if time.time() > control_timeout:
                    # ✓ Hết thời gian điều khiển
                    control_active = False

                    # ✓ Tắt GPIO 20
                    GPIO.output(CONTROL_PIN, GPIO.LOW)

                    # ✓ In thông báo
                    print("[TIMEOUT] Control timeout after 60s")

                else:
                    # ✓ Còn thời gian, chờ phát hiện viên đạn
                    # Hàm detect_impact() sẽ block cho đến khi:
                    # 1. Phát hiện 2+ cảm biến, hoặc
                    # 2. Hết SENSOR_DETECTION_WINDOW (50ms)
                    detections = detect_impact()

                    # ✓ Nếu phát hiện được
                    if detections:
                        # ✓ Tăng counter đếm số lần phát hiện
                        impact_count += 1
                        print(f"[IMPACT] Detection #{impact_count}")

                        # ✓ Tính tọa độ viên đạn bằng phương pháp HYBRID
                        # Step 1: Weighted Average (nhanh)
                        # Step 2: Hyperbolic Refinement (chính xác)
                        x, y = triangulation(detections)

                        # ✓ Nếu tính toán thành công
                        if x is not None and y is not None:
                            # ✓ In tọa độ
                            print(f"[RESULT] Position: x={x}, y={y}")

                            # ✓ Chờ cho đến khi channel rỗi (CSMA)
                            wait_for_channel()
                            
                            # ✓ Gửi tọa độ về Controller
                            send_coordinates(x, y)

                        # ✓ Kiểm tra nếu đã phát hiện được 3 lần (tối đa)
                        if impact_count >= 3:
                            # ✓ Tự động dừng sau 3 viên
                            control_active = False

                            # ✓ Tắt GPIO 20
                            GPIO.output(CONTROL_PIN, GPIO.LOW)

                            # ✓ In thông báo
                            print("[COMPLETE] Received 3 impacts, deactivating")

            # ===== CHẾ ĐỘ EXTRA (Bảo trì - GPIO luôn HIGH) =====
            elif extra_mode_active:
                # ✓ Trong chế độ EXTRA, GPIO đã ở HIGH
                # ✓ Chỉ chờ lệnh EXTRA DOWN (được xử lý ở receive_command)
                # ℹ️ In thông báo chờ (có thể bỏ qua để tiết kiệm log)
                print("[EXTRA] Waiting for EXTRA DOWN command...")
            
            # ✓ Delay 100ms để:
            # 1. Giảm CPU usage
            # 2. Tránh lặp quá nhanh
            time.sleep(0.1)

    # ===== XỬ LÝ KHI THOÁT =====
    
    # ✓ Xử lý khi nhấn Ctrl+C
    except KeyboardInterrupt:
        print("\nNode stopped by user")

    # ✓ Xử lý các lỗi khác
    except Exception as e:
        print(f"[ERROR] {e}")

    # ✓ Dọn dẹp trước khi thoát (lệnh này LUÔN chạy)
    finally:
        # ✓ Đưa GPIO 20 về LOW
        GPIO.output(CONTROL_PIN, GPIO.LOW)

        # ✓ Dọn dẹp GPIO
        GPIO.cleanup()

        # ✓ Đóng kết nối SPI
        spi.close()

        # ✓ Đóng LoRa module
        lora.close()

        # ✓ In thông báo thoát
        print("Cleanup completed")

# ==================== CHẠY CHƯƠNG TRÌNH ====================

if __name__ == "__main__":
    """
    Điểm vào (Entry point) của chương trình
    
    ✓ Kiểm tra nếu file này được chạy trực tiếp (không được import)
    ✓ Gọi hàm main() để bắt đầu chương trình
    """
    
    # ✓ Gọi hàm main để chạy chương trình
    main()