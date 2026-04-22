#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi Nano 2W Node - Nhận lệnh qua LoRa và xử lý cảm biến Piezoelectric
Chương trình này chạy trên Raspberry Pi Nano 2W để:
1. Nhận lệnh từ Controller qua LoRa module SX1278
2. Đọc dữ liệu từ 4 cảm biến Piezo qua MCP3204 ADC
3. Tính toán tọa độ viên đạn và gửi về Controller
"""

# ==================== NHẬP THƯ VIỆN ====================
import RPi.GPIO as GPIO                    # Thư viện điều khiển GPIO trên Raspberry Pi
import time                                # Thư viện làm việc với thời gian
import math                                # Thư viện tính toán toán học
import spidev                              # Thư viện giao tiếp SPI để đọc MCP3204
from rpi_lora import LoRa                  # Thư viện LoRa
from rpi_lora.board_config import BOARD    # Cấu hình board cho LoRa
import random                              # Thư viện random số liệu cho function delay if channel busy
from PIL import Image
import numpy as np

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

# --- Tên Node (tùy chỉnh cho mỗi Node) ---
# NODE1, NODE2, NODE3, NODE4, NODE5
NODE_NAME = "NODE1B"

# --- Tốc độ âm thanh ---
# Dùng để tính khoảng cách từ thời gian phát hiện
SOUND_SPEED = 340                          # m/s ở nhiệt độ 15°C

# ==================== CẤU HÌNH CSMA (CARRIER SENSE MULTIPLE ACCESS) ====================
# Kiểm tra channel có đang gửi or nhận kết quả từ node khác hay không? Nếu có bắt đầu delay rồi gửi sau.

# Thời gian kiểm tra channel có bận không (ms)
CARRIER_SENSE_TIME = 100  # Kiểm tra 100ms

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
extra_mode_active = False                  # trạng thái extra mode

# ==================== HÀM ĐỌC MCP3204 ====================

def read_mcp3204_channel(channel):
    """
    Đọc giá trị ADC từ một kênh của MCP3204
    
    Tham số:
        channel (int): Kênh ADC (0-3)
    
    Trả về:
        int: Giá trị ADC (0-4095) hoặc -1 nếu lỗi
    
    Chi tiết giao thức MCP3204:
    - MCP3204 sử dụng giao thức SPI
    - Gửi 3 byte để lệnh và nhận 3 byte dữ liệu
    - Byte đầu: Start bit + Single/Differential + Channel select
    - 12 bit giá trị ADC nằm trong byte 1 và 2
    """
    # Kiểm tra channel có hợp lệ không (0-3)
    if channel > 3:
        return -1

    # Chuẩn bị lệnh đọc MCP3204
    # 0x06 = 00000110 (Start bit + Single mode)
    # Bit 2 của channel được đưa vào bit 2 của cmd
    cmd = 0x06 | ((channel & 0x04) >> 2)

    # Gửi lệnh qua SPI và nhận dữ liệu (3 byte)
    # xfer2(): Gửi bytes đầu tiên, nhận bytes tương ứng
    adc_bytes = spi.xfer2([cmd, (channel & 0x03) << 6, 0])

    # Xử lý dữ liệu nhận được
    # Dữ liệu ADC 12-bit nằm trong byte 1 (4 bit) + byte 2 (8 bit)
    adc_value = ((adc_bytes[1] & 0x0F) << 8) | adc_bytes[2]

    # Trả về giá trị ADC
    return adc_value

def read_all_sensors():
    """
    Đọc giá trị từ tất cả 4 cảm biến
    
    Trả về:
        dict: {'A': value_A, 'B': value_B, 'C': value_C, 'D': value_D}
              hoặc None nếu có lỗi
    """
    try:
        # Khởi tạo dict để lưu giá trị cảm biến
        sensor_values = {}

        # Đọc giá trị từ từng cảm biến
        for sensor_name, channel in MCP3204_CHANNELS.items():
            # Đọc giá trị ADC từ kênh tương ứng
            value = read_mcp3204_channel(channel)
            sensor_values[sensor_name] = value
            # In giá trị cho debug
            print(f"  Sensor {sensor_name} (CH{channel}): {value}")

        # Trả về dict chứa giá trị của tất cả cảm biến
        return sensor_values

    except Exception as e:
        # In lỗi nếu có vấn đề
        print(f"[ERROR] Failed to read sensors: {e}")
        return None

# ==================== HÀM PHÁT HIỆN VIÊN ĐẠO ====================

def detect_impact():
    """
    Phát hiện viên đạn tác động vào bia
    
    Hoạt động:
    1. Liên tục đọc các cảm biến trong khoảng thời gian nhất định
    2. Khi giá trị ADC vượt quá ngưỡng, ghi nhận thời gian phát hiện
    3. Trả về dict chứa thời gian phát hiện của mỗi cảm biến
    
    Trả về:
        dict: Thời gian phát hiện của mỗi sensor (giây)
              ví dụ: {'A': 0.001, 'B': 0.005, 'C': 0.008, 'D': 0.012}
              hoặc None nếu không phát hiện được
    """
    # In thông báo chờ phát hiện
    print("[SENSOR] Waiting for impact...")

    # Dict để lưu thời gian phát hiện của mỗi cảm biến
    detections = {}

    # Ghi nhận thời gian bắt đầu phát hiện
    start_time = time.time()

    # Vòng lặp đọc sensor trong khoảng thời gian SENSOR_DETECTION_WINDOW
    while time.time() - start_time < SENSOR_DETECTION_WINDOW:
        # Đọc giá trị từ tất cả cảm biến
        sensor_values = read_all_sensors()

        # Nếu có lỗi khi đọc, bỏ qua
        if not sensor_values:
            continue

        # Tính thời gian hiện tại từ khi bắt đầu (tính từ start_time)
        current_time = time.time() - start_time

        # Kiểm tra từng cảm biến
        for sensor_name, threshold in [('A', IMPACT_THRESHOLD),
                                       ('B', IMPACT_THRESHOLD),
                                       ('C', IMPACT_THRESHOLD),
                                       ('D', IMPACT_THRESHOLD)]:
            # Nếu sensor này chưa phát hiện và giá trị vượt ngưỡng
            if sensor_name not in detections and sensor_values[sensor_name] > threshold:
                # Lưu thời gian phát hiện
                detections[sensor_name] = current_time
                # In thông báo
                print(f"[DETECT] Sensor {sensor_name} hit at {current_time:.4f}s "
                      f"with value {sensor_values[sensor_name]}")

        # Nếu đã phát hiện được từ ít nhất 2 cảm biến, có thể dừng
        if len(detections) >= 2:
            break

        # Delay 10ms trước khi đọc lần tiếp theo
        time.sleep(DETECTION_DELAY)

    # Kiểm tra nếu phát hiện được từ ít nhất 2 cảm biến
    if len(detections) >= 2:
        # Nếu có cảm biến không phát hiện, ước tính thời gian
        # dựa trên cảm biến gần nhất
        for sensor_name in ['A', 'B', 'C', 'D']:
            if sensor_name not in detections and detections:
                # Thêm một khoảng delay nhỏ vào thời gian phát hiện lớn nhất
                detections[sensor_name] = max(detections.values()) + 0.01

        # Trả về dict thời gian phát hiện
        return detections
    else:
        # Nếu phát hiện không đủ, trả về None
        print("[MISS] Not enough sensors detected")
        return None

# ==================== HÀM TÍNH TOẠ ĐỘ ====================

def triangulation(detections):
    """
    Tính tọa độ (x, y) của viên đạn dựa trên thời gian phát hiện
    
    Nguyên lý:
    - Viên đạn chuyển động với vận tốc âm thanh (340 m/s)
    - Dựa trên sự chênh lệch thời gian phát hiện giữa các cảm biến (TDOA)
    - Có thể tính được vị trí chính xác của viên đạn
    
    Tham số:
        detections (dict): Thời gian phát hiện của mỗi sensor
                          ví dụ: {'A': 0.001, 'B': 0.005, 'C': 0.008, 'D': 0.012}
    
    Trả về:
        tuple: (x, y) tọa độ viên đạn, hoặc (None, None) nếu lỗi
    """
    try:
        # Tính khoảng cách từ thời gian dựa trên vận tốc âm thanh
        # Công thức: khoảng cách = vận tốc * thời gian
        # Chuyển đổi m/s -> cm/s: 340 * 100 = 34000 cm/s
        distance_A = detections['A'] * SOUND_SPEED * 100  # cm
        distance_B = detections['B'] * SOUND_SPEED * 100  # cm
        distance_C = detections['C'] * SOUND_SPEED * 100  # cm
        distance_D = detections['D'] * SOUND_SPEED * 100  # cm

        # Lấy tọa độ của các cảm biến
        x_A, y_A = SENSOR_POSITIONS['A']  # (-50, -50)
        x_B, y_B = SENSOR_POSITIONS['B']  # (-50, 50)
        x_C, y_C = SENSOR_POSITIONS['C']  # (50, 50)
        x_D, y_D = SENSOR_POSITIONS['D']  # (50, -50)

        # ===== PHƯƠNG PHÁP TÍNH TOẠ ĐỘ =====
        # Sử dụng phương pháp Trung bình trọng số (Weighted Average)
        # vì nó đơn giản và hiệu quả với 4 sensor

        # Bước 1: Tính trung bình tọa độ ban đầu
        x = (x_A + x_B + x_C + x_D) / 4
        y = (y_A + y_B + y_C + y_D) / 4

        # Bước 2: Tinh chỉnh dựa trên khoảng cách phát hiện
        # Cảm biến phát hiện sớm hơn (thời gian nhỏ hơn)
        # có khả năng gần viên đạn hơn
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            # Lấy khoảng cách của sensor này
            distance = detections[sensor_name]

            # Tính trọng số: ngịch đảo với khoảng cách
            # Khoảng cách nhỏ -> trọng số lớn
            weight = 1 / (distance + 0.1)  # +0.1 để tránh chia cho 0

            # Điều chỉnh tọa độ hướng về sensor
            x += (sx - x) * weight * 0.1
            y += (sy - y) * weight * 0.1

        # Bước 3: Giới hạn tọa độ trong phạm vi bia (-50 đến 50 cm)
        x = max(-50, min(50, x))
        y = max(-50, min(50, y))

        # Trả về tọa độ làm tròn đến 1 chữ số thập phân
        return round(x, 1), round(y, 1)

    except Exception as e:
        # In lỗi nếu có vấn đề trong tính toán
        print(f"[ERROR] Triangulation error: {e}")
        return None, None


# ==================== HÀM KIỂM TRA CHANNEL (CARRIER SENSE) ====================

def is_channel_busy():
    """
    Kiểm tra xem LoRa channel có bận không
    (có dữ liệu đang được truyền?)
    
    Trả về:
        bool: True nếu channel bận, False nếu rỗi
    """
    try:
        # Kiểm tra xem LoRa có đang nhận dữ liệu không
        if lora.is_rx_busy():
            print("[CSMA] Channel BUSY - LoRa is receiving")
            return True
        
        return False
    
    except Exception as e:
        print(f"[ERROR] Failed to check channel: {e}")
        return False

def wait_for_channel():
    """
    Chờ đợi cho đến khi channel rỗi, sau đó gửi dữ liệu
    
    Hoạt động:
    1. Kiểm tra xem channel có bận không
    2. Nếu bận, chờ random delay (50-500ms)
    3. Lặp lại tối đa 3 lần
    4. Nếu vẫn bận sau 3 lần, gửi bình thường
    
    Trả về:
        bool: True nếu có thể gửi, False nếu không
    """
    retries = 0
    
    while retries < MAX_RETRIES:
        # Kiểm tra channel
        if not is_channel_busy():
            print("[CSMA] Channel FREE - Ready to send")
            return True
        
        # Channel bận, tính backoff delay
        backoff_delay = random.randint(MIN_BACKOFF, MAX_BACKOFF) / 1000.0  # Convert ms to seconds
        print(f"[CSMA] Channel busy, waiting {backoff_delay*1000:.0f}ms (Retry {retries+1}/{MAX_RETRIES})")
        
        # Chờ
        time.sleep(backoff_delay)
        
        # Tăng retry counter
        retries += 1
    
    # Sau MAX_RETRIES lần, vẫn gửi
    print(f"[CSMA] Max retries reached, sending anyway")
    return True

# ==================== CẤU HÌNH BIA LOẠI B ====================

# Kích thước bia: 150 cm × 42 cm
BIA_B_WIDTH_CM = 150
BIA_B_HEIGHT_CM = 42

# Pixel scaling
PIXEL_PER_CM = 4

# Kích thước mask: 600 × 168 pixel
MASK_WIDTH_PX = BIA_B_WIDTH_CM * PIXEL_PER_CM  # 600
MASK_HEIGHT_PX = BIA_B_HEIGHT_CM * PIXEL_PER_CM  # 168

# Vị trí sensor (cm)
SENSOR_POSITIONS_B = {
    'A': (-75, -21),   # Góc trái dưới
    'B': (-75, 21),    # Góc trái trên
    'C': (75, 21),     # Góc phải trên
    'D': (75, -21),    # Góc phải dưới
}

# Tâm bia (tâm toạ độ)
BIA_B_CENTER_X = 0
BIA_B_CENTER_Y = 0

# ==================== LOAD MASK ====================

def load_mask_file(filename):
    """
    Load file mask (PNG hoặc PBM)
    
    Trả về:
        np.array: Mảng nhị phân (0=invalid, 1=valid)
    """
    try:
        if filename.endswith('.png'):
            # Load PNG
            img = Image.open(filename).convert('L')  # Grayscale
            mask_array = np.array(img)
            
            # Chuyển thành nhị phân: > 128 = 1 (valid), <= 128 = 0 (invalid)
            mask_binary = (mask_array > 128).astype(np.uint8)
            
            print(f"[MASK] Loaded PNG mask: {filename}")
            print(f"       Size: {mask_binary.shape}")
            return mask_binary
        
        elif filename.endswith('.pbm'):
            # Load PBM (text format)
            with open(filename, 'r') as f:
                # Bỏ qua header
                magic = f.readline().strip()  # P1
                width, height = map(int, f.readline().split())
                
                # Đọc dữ liệu pixel
                mask_list = []
                for line in f:
                    pixels = list(map(int, line.split()))
                    mask_list.extend(pixels)
                
                mask_array = np.array(mask_list).reshape((height, width))
                
                print(f"[MASK] Loaded PBM mask: {filename}")
                print(f"       Size: {mask_array.shape}")
                return mask_array
        
        else:
            print(f"[ERROR] Unsupported mask format: {filename}")
            return None
    
    except FileNotFoundError:
        print(f"[ERROR] Mask file not found: {filename}")
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load mask: {e}")
        return None

# Load mask khi khởi động
MASK_B = load_mask_file('bia_b_mask.png')  # Hoặc 'bia_b_mask.pbm'

# ==================== HÀM KIỂM TRA MASK ====================

def is_point_valid_on_mask_b(x, y, mask_array):
    """
    Kiểm tra xem điểm (x, y) có nằm trong vùng tính điểm (trắng) không
    
    Tham số:
        x, y (float): Tọa độ viên đạn (-75 đến 75, -21 đến 21) cm
        mask_array (np.array): Mảng mask nhị phân
    
    Trả về:
        bool: True nếu điểm hợp lệ (trắng), False nếu không hợp lệ (đen)
    """
    if mask_array is None:
        print("[WARNING] Mask not loaded, all points are valid")
        return True
    
    # Chuyển tọa độ cm → pixel
    # Tâm (0, 0) ở pixel (300, 84)
    center_px_x = MASK_WIDTH_PX // 2
    center_px_y = MASK_HEIGHT_PX // 2
    
    pixel_x = int(center_px_x + x * PIXEL_PER_CM)
    pixel_y = int(center_px_y - y * PIXEL_PER_CM)  # Y đảo ngược
    
    # Kiểm tra xem pixel có nằm trong mask không
    if pixel_x < 0 or pixel_x >= mask_array.shape[1]:
        print(f"[DEBUG] X out of bounds: {pixel_x}")
        return False
    if pixel_y < 0 or pixel_y >= mask_array.shape[0]:
        print(f"[DEBUG] Y out of bounds: {pixel_y}")
        return False
    
    # Lấy giá trị pixel
    # 1 = trắng (valid), 0 = đen (invalid)
    pixel_value = mask_array[pixel_y, pixel_x]
    
    return bool(pixel_value)

# ==================== HÀM TÍNH ĐIỂM BIA B ====================

def calculate_score_b(x, y):
    """
    Tính điểm cho bia loại B (150×42 cm)
    
    Đặc điểm:
    - Không có vòng điểm (không tính khoảng cách từ tâm)
    - Nếu điểm nằm trong vùng trắng → 1 điểm
    - Nếu điểm nằm trong vùng đen → 0 điểm (miss)
    - Nếu vượt bia → gửi (-200, -200)
    
    Tham số:
        x, y (float): Tọa độ viên đạn
    
    Trả về:
        dict: {
            'score': 1 hoặc 0,
            'valid': True/False,
            'is_hit': True/False (nằm trên bia hay không)
        }
    """
    # Kiểm tra xem điểm có nằm trong phạm vi bia không
    if x < -75 or x > 75 or y < -21 or y > 21:
        # Vượt bia → miss
        return {
            'score': 0,
            'valid': False,
            'is_hit': False,
            'reason': 'Outside bia range'
        }
    
    # Kiểm tra mask
    is_valid = is_point_valid_on_mask_b(x, y, MASK_B)
    
    if is_valid:
        # Nằm trên vùng trắng → 1 điểm (hit)
        return {
            'score': 1,
            'valid': True,
            'is_hit': True,
            'reason': 'Valid zone'
        }
    else:
        # Nằm trên vùng đen → 0 điểm (hit nhưng no score)
        return {
            'score': 0,
            'valid': False,
            'is_hit': True,
            'reason': 'Black zone (no score)'
        }

# ==================== HÀM GỬIỮ DỮ LIỆU ====================

def send_coordinates_b(x, y, score_info):
    """
    Gửi tọa độ viên đạn về Controller
    
    Định dạng:
    - Hit: "NODE1B, 10, 5"
    - Miss: "NODE1B, -200, -200"
    
    Tham số:
        x, y (float): Tọa độ
        score_info (dict): Thông tin điểm
    """
    try:
        wait_for_channel()
        
        # Nếu miss → gửi (-200, -200)
        if not score_info['is_hit']:
            message = f"{NODE_NAME}, -200, -200"
        else:
            message = f"{NODE_NAME}, {x}, {y}"
        
        lora.send(message.encode())
        print(f"[TX] Sent: {message} (Score: {score_info['score']})")

    except Exception as e:
        print(f"[ERROR] Failed to send: {e}")


# ==================== HÀM NHẬN LỆNH =====================

def receive_command():
    """
    Nhận lệnh từ Controller qua LoRa
    
    Định dạng lệnh:
        - "NODE1 UP": Kích hoạt Node 1 cụ thể (chế độ bình thường)
        - "NODE1 DOWN": Dừng Node 1 cụ thể
        - "A UP": Điều khiển tất cả Node (chế độ bình thường)
        - "A DOWN": Dừng tất cả Node
        - "EXTRA UP": Khóa tất cả nút, GPIO luôn HIGH (chế độ bảo trì)
        - "EXTRA DOWN": Thoát khỏi chế độ EXTRA, GPIO về LOW
    
    Hoạt động:
    1. Kiểm tra LoRa có dữ liệu chưa
    2. Nếu có, đọc dữ liệu
    3. Parse lệnh và thực hiện
    
    Trả về:
        str: Trạng thái ("ACTIVATED", "DEACTIVATED") hoặc None
    """
    global control_active, control_timeout, impact_count, extra_mode_active

    try:
        # Kiểm tra xem LoRa có đang nhận dữ liệu không
        if lora.is_rx_busy():
            return None

        # Đọc dữ liệu từ LoRa
        payload = lora.read()

        # Nếu có dữ liệu
        if payload:
            # Chuyển đổi từ bytes sang string
            command = payload.decode().strip()

            # In lệnh nhận được
            print(f"[RX] Received: {command}")

            # Tách lệnh thành các phần
            # Ví dụ: "NODE1 UP" -> ["NODE1", "UP"]
            parts = command.split()

            # Kiểm tra nếu có ít nhất 2 phần
            if len(parts) >= 2:
                # Lấy tên node và hành động
                node_command = parts[0].upper()  # "NODE1", "A", "EXTRA"
                action = parts[1].upper()         # "UP" hoặc "DOWN"

                # ===== KIỂM TRA LỆNH BROADCAST (A, EXTRA) =====
                is_broadcast_a = (node_command == "A")
                is_broadcast_extra = (node_command == "EXTRA")
                is_for_this_node = (node_command == NODE_NAME)

                # ===== KIỂM TRA LỆNH EXTRA =====
                if is_broadcast_extra:
                    if action == "UP":
                        # EXTRA UP: Khóa tất cả nút, GPIO luôn HIGH
                        extra_mode_active = True
                        control_active = False  # Tắt chế độ bình thường
                        
                        print(f"[EXTRA] Mode ON - GPIO {CONTROL_PIN} is HIGH")
                        
                        # GPIO 20 lên HIGH (sẽ ở đó cho đến khi EXTRA DOWN)
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        return "EXTRA_ON"
                    
                    elif action == "DOWN":
                        # EXTRA DOWN: Thoát khỏi chế độ EXTRA, GPIO về LOW
                        extra_mode_active = False
                        control_active = False
                        
                        print(f"[EXTRA] Mode OFF - GPIO {CONTROL_PIN} is LOW")
                        
                        # GPIO 20 về LOW
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        return "EXTRA_OFF"

                # ===== KIỂM TRA LỆNH A (CHỈ KHI KHÔNG CÓ EXTRA MODE) =====
                elif is_broadcast_a and not extra_mode_active:
                    if action == "UP":
                        # A UP: Kích hoạt tất cả Node (chế độ bình thường)
                        control_active = True
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        impact_count = 0
                        
                        print(f"[CONTROL] BROADCAST A UP - Activated for {CONTROL_TIMEOUT}s")
                        
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        # A DOWN: Dừng tất cả Node
                        control_active = False
                        
                        print(f"[CONTROL] BROADCAST A DOWN - Deactivated")
                        
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        return "DEACTIVATED"

                # ===== KIỂM TRA LỆNH CỤ THỂ (NODE1, NODE2, ...) =====
                # CHỈ HỢP LỆ KHI EXTRA MODE KHÔNG ACTIVE
                elif is_for_this_node and not extra_mode_active:
                    if action == "UP":
                        # Node này UP: Kích hoạt
                        control_active = True
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        impact_count = 0
                        
                        print(f"[CONTROL] {node_command} UP - Activated for {CONTROL_TIMEOUT}s")
                        
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        # Node này DOWN: Dừng
                        control_active = False
                        
                        print(f"[CONTROL] {node_command} DOWN - Deactivated")
                        
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        
                        return "DEACTIVATED"
                
                # ===== LỆNH KHÔNG HỢP LỆ TRONG EXTRA MODE =====
                elif extra_mode_active and (is_broadcast_a or is_for_this_node):
                    print(f"[WARNING] Command {node_command} {action} ignored (EXTRA mode active)")
                    return None

    except Exception as e:
        # In lỗi nếu có vấn đề
        print(f"[ERROR] Failed to receive command: {e}")

    # Trả về None nếu không có lệnh hoặc xảy ra lỗi
    return None

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """
    Vòng lặp chính (sửa để hỗ trợ loại bia B)
    """
    global control_active, control_timeout, impact_count, extra_mode_active, current_bia_type

    try:
        while True:
            receive_command()

            if control_active and not extra_mode_active:
                if time.time() > control_timeout:
                    control_active = False
                    GPIO.output(CONTROL_PIN, GPIO.LOW)
                    print("[TIMEOUT] Control timeout after 60s")
                else:
                    detections = detect_impact()

                    if detections:
                        impact_count += 1
                        print(f"[IMPACT] Detection #{impact_count}")

                        x, y = triangulation(detections)

                        if x is not None and y is not None:
                            print(f"[RESULT] Position: x={x}, y={y}")

                            # ===== TÍNH ĐIỂM DỰA TRÊN LOẠI BIA =====
                            if current_bia_type == "B":
                                # Loại bia B: chỉ có 1 điểm nếu hit
                                score_info = calculate_score_b(x, y)
                                
                                print(f"[SCORE_B] {score_info['reason']}: "
                                      f"{score_info['score']} điểm")
                            else:
                                # Loại bia A: 10 vòng điểm
                                distance = calculate_distance(x, y)
                                ring = get_ring(distance)
                                score = SCORING_RINGS[ring - 1][1] if (ring > 0 and ring <= len(SCORING_RINGS)) else 0
                                
                                score_info = {
                                    'score': score,
                                    'is_hit': True
                                }
                                
                                print(f"[SCORE_A] Ring {ring}: {score} điểm")
                            
                            # Gửi dữ liệu
                            send_coordinates_b(x, y, score_info) if current_bia_type == "B" else send_coordinates(x, y, score_info)

                        if impact_count >= 3:
                            control_active = False
                            GPIO.output(CONTROL_PIN, GPIO.LOW)
                            print("[COMPLETE] Received 3 impacts, deactivating")

            elif extra_mode_active:
                print("[EXTRA] Waiting for EXTRA DOWN command...")
            
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nNode stopped by user")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        GPIO.output(CONTROL_PIN, GPIO.LOW)
        GPIO.cleanup()
        spi.close()
        lora.close()
        print("Cleanup completed")

if __name__ == "__main__":
    main()
