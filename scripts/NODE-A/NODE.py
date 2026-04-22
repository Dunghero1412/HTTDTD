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
NODE_NAME = "NODE1A"

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

# ==================== HÀM GỬIỮ DỮ LIỆU ====================

def send_coordinates(x, y):
    """
    Gửi tọa độ viên đạn về Controller qua LoRa
    
    Định dạng: "NODE1, -26, 30"
    
    Tham số:
        x (float): Tọa độ X
        y (float): Tọa độ Y
    """
    try:
        # Tạo thông điệp gửi về Controller
        message = f"{NODE_NAME}, {x}, {y}"

        # Chuyển thông điệp từ string sang bytes và gửi
        lora.send(message.encode())

        # In thông báo đã gửi
        print(f"[TX] Sent: {message}")

    except Exception as e:
        # In lỗi nếu gửi thất bại
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
    Vòng lặp chính của chương trình
    
    Hoạt động:
    1. Liên tục kiểm tra LoRa nhận lệnh
    2. Khi nhận lệnh "A UP" hoặc "NODE UP", bắt đầu phát hiện viên đạn
    3. Khi nhận lệnh "EXTRA UP", GPIO luôn HIGH, không phát hiện
    4. Tính tọa độ và gửi về Controller
    5. Dừng khi nhận lệnh DOWN hoặc hết timeout
    """
    global control_active, control_timeout, impact_count, extra_mode_active

    try:
        # Vòng lặp chính - chạy liên tục
        while True:
            # Nhận lệnh từ Controller
            receive_command()

            # ===== CHỈ PHÁT HIỆN KHI EXTRA MODE KHÔNG ACTIVE =====
            if control_active and not extra_mode_active:
                # Kiểm tra xem timeout đã hết chưa
                if time.time() > control_timeout:
                    # Dừng điều khiển
                    control_active = False

                    # Đưa GPIO 20 về LOW
                    GPIO.output(CONTROL_PIN, GPIO.LOW)

                    # In thông báo
                    print("[TIMEOUT] Control timeout after 60s")

                else:
                    # Phát hiện viên đạn
                    detections = detect_impact()

                    # Nếu phát hiện được
                    if detections:
                        # Tăng counter đếm số lần phát hiện
                        impact_count += 1
                        print(f"[IMPACT] Detection #{impact_count}")

                        # Tính tọa độ viên đạn
                        x, y = triangulation(detections)

                        # Nếu tính toán thành công
                        if x is not None and y is not None:
                            # In tọa độ
                            print(f"[RESULT] Position: x={x}, y={y}")

                            # Gửi tọa độ về Controller (với CSMA)
                            wait_for_channel()
                            send_coordinates(x, y)

                        # Kiểm tra nếu đã phát hiện được 3 lần
                        if impact_count >= 3:
                            # Dừng điều khiển
                            control_active = False

                            # Đưa GPIO 20 về LOW
                            GPIO.output(CONTROL_PIN, GPIO.LOW)

                            # In thông báo
                            print("[COMPLETE] Received 3 impacts, deactivating")

            # ===== EXTRA MODE: GPIO LUÔN HIGH, KHÔNG PHÁT HIỆN =====
            elif extra_mode_active:
                # GPIO đã ở HIGH, chỉ chờ lệnh EXTRA DOWN
                # Không làm gì cả - vòng lặp tiếp tục kiểm tra lệnh
                print("[EXTRA] Waiting for EXTRA DOWN command...")
                
            # Delay 100ms để giảm CPU usage
            time.sleep(0.1)

    # Xử lý khi nhấn Ctrl+C
    except KeyboardInterrupt:
        print("\nNode stopped by user")

    # Xử lý các lỗi khác
    except Exception as e:
        print(f"[ERROR] {e}")

    # Dọn dẹp trước khi thoát
    finally:
        # Đưa GPIO 20 về LOW
        GPIO.output(CONTROL_PIN, GPIO.LOW)

        # Dọn dẹp GPIO
        GPIO.cleanup()

        # Đóng kết nối SPI
        spi.close()

        # Đóng LoRa
        lora.close()

        # In thông báo thoát
        print("Cleanup completed")

# ==================== CHẠY CHƯƠNG TRÌNH ====================

if __name__ == "__main__":
    # Gọi hàm main để chạy chương trình
    main()
