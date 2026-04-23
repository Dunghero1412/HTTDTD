#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi 5 Controller - Điều khiển hệ thống bắn đạn thật qua LoRa

🎯 CHỨC NĂNG CHÍNH:
1. Đọc trạng thái 8 nút bấm (GPIO 2-8, 17)
2. Gửi lệnh điều khiển đến 5 Node qua LoRa module SX1278
3. Nhận dữ liệu tọa độ từ các Node và tính điểm
4. Hiển thị bảng điểm lên console
5. Ghi log dữ liệu vào file score.txt
6. Lưu dữ liệu JSON cho HTML realtime visualization

📊 CẤU TRÚC HỆ THỐNG:
┌─────────────────────────────────────────────┐
│        RPi 5 Controller (File này)          │
│  ┌──────────────────────────────────────┐  │
│  │  8 GPIO Button (Nút bấm)            │  │
│  │  GPIO2-8: NODE1-5, A, EXTRA         │  │
│  │  GPIO17: B                          │  │
│  └──────────────────────────────────────┘  │
│              ↕ LoRa Module                  │
│  ┌──────────────────────────────────────┐  │
│  │  5 RPi Nano Nodes (NODE1-5)          │  │
│  │  - Đọc cảm biến Piezo               │  │
│  │  - Tính tọa độ (Hybrid method)       │  │
│  │  - Gửi tọa độ về Controller          │  │
│  └──────────────────────────────────────┘  │
│                   ↓                         │
│  ┌──────────────────────────────────────┐  │
│  │  Hiển thị Điểm (Console + JSON)      │  │
│  │  - Bảng điểm realtime                │  │
│  │  - File score_data.json              │  │
│  │  - HTML visualizer                   │  │
│  └──────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
"""

# ==================== NHẬP THƯ VIỆN ====================

# ✓ Thư viện điều khiển GPIO trên Raspberry Pi
# Dùng để đọc nút bấm
import RPi.GPIO as GPIO

# ✓ Thư viện làm việc với thời gian
# Dùng cho delay, timeout, timestamp
import time

# ✓ Thư viện hệ thống
# Dùng cho sys.exit(), xử lý lỗi hệ thống
import sys

# ✓ Thư viện tính toán toán học
# Dùng cho tính khoảng cách (sqrt), trig functions
import math

# ✓ Thư viện xử lý ngày giờ
# Dùng cho tạo timestamp (ngày giờ hiện tại)
from datetime import datetime

# ✓ Thư viện LoRa để giao tiếp không dây
# Gửi/nhận dữ liệu với các Node
from rpi_lora import LoRa

# ✓ Cấu hình board cho LoRa module SX1278
# Định nghĩa các pin nối với LoRa (MISO, MOSI, CLK, CS)
from rpi_lora.board_config import BOARD

# ✓ Thư viện JSON để lưu/đọc dữ liệu
# Dùng để ghi file score_data.json cho HTML
import json

# ==================== CẤU HÌNH CHUNG ====================

# === CẤU HÌNH UART CHO LoRa ===
# UART 1 trên RPi 5 nối với LoRa module
UART_PORT = "/dev/ttyAMA1"

# Tốc độ baud: 57600 bps
# Đúng với cấu hình tiêu chuẩn tầm trung (100-600m) với tốc độ cao
# Tốc độ baud càng cao → tốc độ truyền dữ liệu càng nhanh → phạm vi càng ngắn
BAUD_RATE = 57600

# === CẤU HÌNH GPIO CHO CÁC NÚT BẤM ===
# Các nút được nối vào GPIO 2-8 và GPIO 17 trên RPi 5
# Khi bấm → GPIO chuyển từ HIGH sang LOW (nút kết nối đất)
BUTTON_PINS = {
    2: "NODE1",                            # GPIO 2  → Nút Node 1
    3: "NODE2",                            # GPIO 3  → Nút Node 2
    4: "NODE3",                            # GPIO 4  → Nút Node 3
    5: "NODE4",                            # GPIO 5  → Nút Node 4
    6: "NODE5",                            # GPIO 6  → Nút Node 5
    7: "A",                                # GPIO 7  → Nút A (broadcast cho tất cả)
    8: "EXTRA",                            # GPIO 8  → Nút EXTRA (chế độ bảo trì)
    17: "B"                                # GPIO 17 → Nút B (loại bia B)
}

# === CẤU HÌNH LoRa ===
# Tần số LoRa: 915 MHz (ISM band - công cộng, không cần phép)
# Phải khớp với tần số của tất cả Node
LORA_FREQUENCY = 915

# === CẤU HÌNH FILE LOG ===
# File lưu tất cả dữ liệu (timestamp + lệnh gửi + dữ liệu nhận)
# Dùng cho debug, kiểm tra lịch sử
LOG_FILE = "score.txt"

# === BIẾN TRẠNG THÁI CHẾ ĐỘ EXTRA ===
# Xác định xem chế độ EXTRA (bảo trì) có đang active không
# Khi EXTRA active:
# - GPIO luôn HIGH (tắt điều khiển)
# - Tất cả nút khác bị khóa
# - Chỉ nút EXTRA có thể tắt chế độ này
extra_mode_active = False

# === CẤU HÌNH HỆ THỐNG TÍNH ĐIỂM ===
# Định nghĩa các vòng điểm: (bán kính tối đa (cm), điểm số)
# Bia hình tròn 100cm × 100cm, tâm ở (0, 0)
SCORING_RINGS = [
    (7.5, 10),                             # Vòng 1: Bullseye (0-7.5cm) → 10 điểm
    (15, 9),                               # Vòng 2 (7.5-15cm) → 9 điểm
    (22.5, 8),                             # Vòng 3 (15-22.5cm) → 8 điểm
    (30, 7),                               # Vòng 4 (22.5-30cm) → 7 điểm
    (37.5, 6),                             # Vòng 5 (30-37.5cm) → 6 điểm
    (45, 5),                               # Vòng 6 (37.5-45cm) → 5 điểm
    (50, 4),                               # Vòng 7 (45-50cm) → 4 điểm
    (float('inf'), 0)                      # Ngoài bia (>50cm) → 0 điểm
]

# Bán kính tối đa của bia (cm)
MAX_RADIUS = 50

# Timeout điều khiển: 60 giây
# Sau khi bấm nút UP, nếu hết 60s mà không nhận đủ 3 viên → tự động OFF
CONTROL_TIMEOUT = 60

# ==================== KHỞI TẠO GPIO ====================

# ✓ Sử dụng chế độ BCM (Broadcom) để đặt tên GPIO
# BCM: Sử dụng số BCM (GPIO2, GPIO3, ...) thay vì số vật lý trên header
GPIO.setmode(GPIO.BCM)

# ✓ Tắt cảnh báo GPIO
# Tránh in ra console những cảnh báo không cần thiết
GPIO.setwarnings(False)

# === Khởi tạo từng nút bấm ===
# Dict để lưu trạng thái hiện tại của mỗi nút
# False = chưa bấm / đã release, True = đang bấm / đã active
button_states = {}

# ✓ Duyệt qua tất cả các pin nút bấm
for pin in BUTTON_PINS.keys():
    # ✓ Cấu hình pin là INPUT (nhập dữ liệu từ nút)
    # pull_up_down=GPIO.PUD_UP: Khi nút thả → GPIO = HIGH (~3.3V)
    # Khi nút bấm → GPIO = LOW (~0V) kết nối tới GND
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # ✓ Khởi tạo trạng thái nút là False (chưa bấm)
    button_states[pin] = False

# ==================== KHỞI TẠO LoRa ====================

# ✓ Khởi tạo LoRa module
# BOARD.CN1: Cấu hình pin mặc định cho LoRa
# baud=BAUD_RATE: Đặt tốc độ baud UART
try:
    lora = LoRa(BOARD.CN1, BOARD.CN1, baud=BAUD_RATE)
    
    # ✓ Đặt tần số LoRa
    # Phải khớp với tần số của tất cả Node
    lora.set_frequency(LORA_FREQUENCY)
    
    # ✓ In thông báo khởi tạo thành công
    print(f"[INIT] LoRa initialized at {LORA_FREQUENCY}MHz")

except Exception as e:
    # ❌ Nếu lỗi khởi tạo, in lỗi và thoát
    print(f"[ERROR] Failed to initialize LoRa: {e}")
    sys.exit(1)

# ==================== HÀM HỖ TRỢ ====================

def log_data(message):
    """
    Ghi dữ liệu vào file log và hiển thị trên console
    
    🔧 HOẠT ĐỘNG:
    1. Lấy timestamp hiện tại (ngày giờ)
    2. Kết hợp timestamp + message
    3. In lên console (cho xem realtime)
    4. Ghi vào file log (lưu lịch sử)
    
    💡 NGUYÊN LÝ:
    - Mọi sự kiện quan trọng đều ghi log
    - Dễ debug nếu có lỗi
    - Có thể review lịch sử sau này
    
    Tham số:
        message (str): Thông điệp cần ghi
                      Ví dụ: "[TX] Sent: NODE1 UP"
    """
    
    # ✓ Lấy thời gian hiện tại với định dạng "YYYY-MM-DD HH:MM:SS"
    # Ví dụ: "2024-04-19 10:25:30"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ✓ Tạo thông điệp hoàn chỉnh với timestamp
    # Ví dụ: "[2024-04-19 10:25:30] [TX] Sent: NODE1 UP"
    log_message = f"[{timestamp}] {message}"
    
    # ✓ In lên console (hiển thị ngay realtime)
    print(log_message)
    
    # ✓ Mở file log ở chế độ append (thêm vào cuối file)
    # 'a': append mode - không xóa nội dung cũ, chỉ thêm vào cuối
    with open(LOG_FILE, 'a') as f:
        # ✓ Ghi thông điệp vào file với ký tự xuống dòng \n
        f.write(log_message + "\n")

def send_command(node_name, command):
    """
    Gửi lệnh điều khiển đến một Node qua LoRa
    
    🔧 HOẠT ĐỘNG:
    1. Kết hợp node_name + command thành 1 thông điệp
    2. Chuyển string → bytes (UTF-8 encoding)
    3. Gửi qua LoRa module
    4. Ghi log kết quả
    
    📝 ĐỊNH DẠNG LỆNH:
    - "NODE1 UP" - kích hoạt Node 1
    - "NODE1 DOWN" - dừng Node 1
    - "A UP" - broadcast cho tất cả Node (lệnh chung)
    - "A DOWN" - dừng tất cả Node
    - "EXTRA UP" - chế độ bảo trì (GPIO luôn HIGH)
    - "EXTRA DOWN" - thoát khỏi EXTRA mode
    - "B UP" - kích hoạt Node loại B
    - "B DOWN" - dừng Node loại B
    
    Tham số:
        node_name (str): Tên Node hoặc lệnh
                        Ví dụ: "NODE1", "A", "EXTRA", "B"
        command (str): Lệnh cần gửi
                      Ví dụ: "UP" hoặc "DOWN"
    """
    
    try:
        # ✓ Tạo thông điệp gửi: kết hợp node_name + command
        # Ví dụ: "NODE1" + " " + "UP" → "NODE1 UP"
        message = f"{node_name} {command}"
        
        # ✓ Chuyển string thành bytes (UTF-8 encoding)
        # LoRa module yêu cầu bytes, không phải string
        # message.encode() → b'NODE1 UP'
        lora.send(message.encode())
        
        # ✓ Ghi log thông điệp đã gửi
        # [TX] = Transmit (gửi dữ liệu)
        log_data(f"[TX] Sent: {message}")
    
    except Exception as e:
        # ❌ Nếu có lỗi, ghi vào log
        log_data(f"[ERROR] Failed to send: {e}")

def receive_data():
    """
    Nhận dữ liệu từ các Node qua LoRa
    
    🔧 HOẠT ĐỘNG:
    1. Kiểm tra xem LoRa có đang nhận dữ liệu không
    2. Nếu không nhận → return None (không có dữ liệu)
    3. Nếu có nhận → đọc payload (dữ liệu)
    4. Chuyển bytes → string (UTF-8 decoding)
    5. Ghi log dữ liệu nhận được
    6. Trả về string dữ liệu
    
    📝 ĐỊNH DẠNG DỮ LIỆU NHẬN:
    - "NODE1, -26, 30" - Node 1 bắn ở (-26, 30)
    - "NODE2, -200, -200" - Node 2 bắn miss (ngoài bia)
    
    Trả về:
        str: Dữ liệu nhận được
             Ví dụ: "NODE1, -26, 30"
        None: Nếu không có dữ liệu hoặc có lỗi
    """
    
    try:
        # ✓ Kiểm tra xem LoRa có đang nhận dữ liệu không
        # is_rx_busy() trả về True nếu đang nhận
        # Nếu đang nhận, không thể đọc → return None
        if lora.is_rx_busy():
            return None
        
        # ✓ Đọc payload (dữ liệu) từ LoRa
        # payload là bytes (ví dụ: b'NODE1, -26, 30')
        payload = lora.read()
        
        # ✓ Nếu có dữ liệu
        if payload:
            # ✓ Chuyển đổi từ bytes sang string (UTF-8 decoding)
            # b'NODE1, -26, 30' → "NODE1, -26, 30"
            data = payload.decode()
            
            # ✓ Ghi log dữ liệu nhận được
            # [RX] = Receive (nhận dữ liệu)
            log_data(f"[RX] Received: {data}")
            
            # ✓ Trả về string dữ liệu
            return data
    
    except Exception as e:
        # ❌ Nếu có lỗi, ghi vào log
        log_data(f"[ERROR] Failed to receive: {e}")
    
    # ✓ Trả về None nếu không có dữ liệu hoặc có lỗi
    return None

def parse_node_data(data):
    """
    Phân tích dữ liệu nhận từ Node
    
    🔧 HOẠT ĐỘNG:
    1. Tách dữ liệu bằng dấu phẩy (,)
    2. Trích xuất tên Node (phần đầu)
    3. Chuyển đổi x, y thành float
    4. Kiểm tra nếu lỗi
    5. Trả về tuple (node_name, x, y)
    
    📝 ĐỊNH DẠNG DỮ LIỆU:
    Đầu vào:  "NODE1, -26, 30"
    Đầu ra:   ("NODE1", -26.0, 30.0)
    
    📝 TRƯỜNG HỢP ĐẶC BIỆT:
    Nếu Node bắn miss (ngoài bia):
    Đầu vào:  "NODE1, -200, -200"
    Đầu ra:   ("NODE1", -200.0, -200.0)
    Controller sẽ nhận diện đây là miss khi tính điểm
    
    Tham số:
        data (str): Dữ liệu nhận từ Node
                   Ví dụ: "NODE1, -26, 30"
    
    Trả về:
        tuple: (node_name, x, y)
               Ví dụ: ("NODE1", -26.0, 30.0)
               hoặc (None, None, None) nếu lỗi
    """
    
    try:
        # ✓ Tách dữ liệu bằng dấu phẩy (,)
        # "NODE1, -26, 30" → ["NODE1", " -26", " 30"]
        parts = data.split(',')
        
        # ✓ Lấy phần tên Node (phần đầu) và loại bỏ khoảng trắng
        # parts[0] = "NODE1" hoặc " NODE1 " → strip() → "NODE1"
        node_name = parts[0].strip()
        
        # ✓ Chuyển đổi phần x thành số float
        # parts[1] = " -26" → strip() → "-26" → float() → -26.0
        x = float(parts[1].strip())
        
        # ✓ Chuyển đổi phần y thành số float
        # parts[2] = " 30" → strip() → "30" → float() → 30.0
        y = float(parts[2].strip())
        
        # ✓ Trả về tuple (node_name, x, y)
        return (node_name, x, y)
    
    except:
        # ❌ Nếu lỗi khi phân tích (dữ liệu không hợp lệ)
        # Trả về tuple (None, None, None)
        return (None, None, None)

# ==================== HÀM TÍNH ĐIỂM ====================

def calculate_distance(x, y):
    """
    Tính khoảng cách từ tâm bia (0, 0) đến điểm (x, y)
    
    🔧 HOẠT ĐỘNG:
    - Sử dụng công thức Euclidean distance
    - Tính độ lớn của vector (x, y) từ gốc tọa độ
    
    📐 CÔNG THỨC:
    r = √(x² + y²)
    
    Ví dụ:
    - (x=0, y=0) → r = 0 (bullseye)
    - (x=3, y=4) → r = √(9+16) = 5cm
    - (x=10, y=20) → r = √(100+400) = 22.4cm
    
    Tham số:
        x (float): Tọa độ X (-50 đến 50 cm)
        y (float): Tọa độ Y (-50 đến 50 cm)
    
    Trả về:
        float: Khoảng cách từ tâm (cm)
               Giá trị từ 0 đến ~71cm (nếu vượt bia)
    """
    
    # ✓ Tính khoảng cách Euclidean từ tâm (0, 0)
    # Công thức: r = √(x² + y²)
    distance = math.sqrt(x**2 + y**2)
    
    # ✓ Trả về khoảng cách
    return distance

def get_ring(distance):
    """
    Xác định vòng điểm dựa trên khoảng cách
    
    🔧 HOẠT ĐỘNG:
    1. Duyệt qua danh sách SCORING_RINGS
    2. Tìm vòng đầu tiên có radius > distance
    3. Trả về số vòng tương ứng
    4. Nếu không tìm thấy (vượt bia) → trả về 0
    
    📊 BẢNG VÒNG ĐIỂM:
    Vòng 1: 0-7.5cm → 10 điểm
    Vòng 2: 7.5-15cm → 9 điểm
    Vòng 3: 15-22.5cm → 8 điểm
    Vòng 4: 22.5-30cm → 7 điểm
    Vòng 5: 30-37.5cm → 6 điểm
    Vòng 6: 37.5-45cm → 5 điểm
    Vòng 7: 45-50cm → 4 điểm
    Ngoài bia: >50cm → 0 điểm (vòng 0)
    
    Tham số:
        distance (float): Khoảng cách từ tâm (cm)
    
    Trả về:
        int: Số vòng (1-7) hoặc 0 nếu ngoài bia
    """
    
    # ✓ Duyệt qua các vòng để tìm vòng tương ứng
    # enumerate(SCORING_RINGS, 1): Bắt đầu numbering từ 1
    # ring_num = 1, 2, 3, ... (số thứ tự)
    # (radius, score) = tuple từ SCORING_RINGS
    for ring_num, (radius, _) in enumerate(SCORING_RINGS, 1):
        # ✓ Kiểm tra nếu distance <= radius
        # Nếu có → điểm này thuộc vòng này
        if distance <= radius:
            # ✓ Trả về số vòng
            return ring_num
    
    # ✓ Nếu không tìm thấy (vượt bia) → trả về 0
    return 0

def calculate_score(x, y):
    """
    Tính điểm dựa trên tọa độ viên đạn
    
    🔧 HOẠT ĐỘNG:
    1. Tính khoảng cách từ tâm bằng calculate_distance()
    2. Xác định vòng điểm bằng get_ring()
    3. Lấy điểm số từ SCORING_RINGS
    4. Lấy tên vòng từ dict ring_names
    5. Trả về dict kết quả đầy đủ
    
    📊 KẾT QUẢ:
    {
        'score': điểm số (0-10),
        'distance': khoảng cách từ tâm (cm),
        'ring': số vòng (0-7),
        'ring_name': tên vòng (string),
        'x': tọa độ X,
        'y': tọa độ Y
    }
    
    Ví dụ:
    - Nhập: x=-2, y=3
    - Khoảng cách: 3.6cm
    - Vòng: 1 (Bullseye)
    - Điểm: 10
    
    Tham số:
        x (float): Tọa độ X (-50 đến 50 cm, hoặc -200 nếu miss)
        y (float): Tọa độ Y (-50 đến 50 cm, hoặc -200 nếu miss)
    
    Trả về:
        dict: Kết quả tính điểm đầy đủ
    """
    
    # ✓ Tính khoảng cách từ tâm
    distance = calculate_distance(x, y)
    
    # ✓ Xác định vòng điểm
    ring = get_ring(distance)
    
    # ✓ Lấy điểm số từ SCORING_RINGS
    if ring > 0 and ring <= len(SCORING_RINGS):
        # ring = 1 → SCORING_RINGS[0][1] = điểm vòng 1
        # ring = 2 → SCORING_RINGS[1][1] = điểm vòng 2, v.v.
        score = SCORING_RINGS[ring - 1][1]
    else:
        # Vòng 0 (ngoài bia) → 0 điểm
        score = 0
    
    # ✓ Dict tên các vòng
    ring_names = {
        0: "Ngoài bia",                    # Vòng 0 (ngoài bia)
        1: "Bullseye",                     # Vòng 1 (10 điểm)
        2: "Vòng 2",                       # Vòng 2 (9 điểm)
        3: "Vòng 3",                       # Vòng 3 (8 điểm)
        4: "Vòng 4",                       # Vòng 4 (7 điểm)
        5: "Vòng 5",                       # Vòng 5 (6 điểm)
        6: "Vòng 6",                       # Vòng 6 (5 điểm)
        7: "Vòng 7"                        # Vòng 7 (4 điểm)
    }
    
    # ✓ Lấy tên vòng từ dict
    # dict.get(key, default) → lấy giá trị, nếu không có → "Lỗi"
    ring_name = ring_names.get(ring, "Lỗi")
    
    # ✓ Trả về dict kết quả đầy đủ
    return {
        'score': score,                    # Điểm số (0-10)
        'distance': round(distance, 2),    # Khoảng cách (làm tròn 2 chữ số)
        'ring': ring,                      # Số vòng (0-7)
        'ring_name': ring_name,            # Tên vòng (string)
        'x': x,                            # Tọa độ X (lưu lại)
        'y': y                             # Tọa độ Y (lưu lại)
    }

# ==================== LỚP HIỂN THỊ DỮ LIỆU ====================

class ScoreDisplay:
    """
    Lớp để quản lý và hiển thị điểm số từ các Node
    
    🔧 CHỨC NĂNG:
    1. Lưu trữ dữ liệu tọa độ của mỗi Node
    2. Tính toán điểm số dựa trên tọa độ
    3. Hiển thị dữ liệu dạng bảng (cột)
    4. Cập nhật dữ liệu khi nhận từ Node
    5. Ghi dữ liệu JSON cho HTML visualization
    
    📊 CẤU TRÚC DỮ LIỆU:
    self.scores = {
        "NODE1": {
            'x': -26.0,
            'y': 30.0,
            'score': 8,
            'ring_name': "Vòng 3",
            'shots': [
                {'x': -26, 'y': 30, 'score': 8, 'ring': 'Vòng 3', 'distance': 38.2},
                {'x': 10, 'y': 15, 'score': 9, 'ring': 'Vòng 2', 'distance': 18.0},
                {'x': 0, 'y': 0, 'score': 10, 'ring': 'Bullseye', 'distance': 0.0}
            ]
        },
        ...
    }
    """
    
    def __init__(self):
        """
        Khởi tạo đối tượng ScoreDisplay
        
        🔧 HOẠT ĐỘNG:
        - Tạo dict lưu dữ liệu cho 5 Node
        - Mỗi Node có: x, y, score, ring_name, shots (lịch sử bắn)
        
        💡 MỤC ĐÍCH:
        - Chuẩn bị cấu trúc để lưu dữ liệu
        - Khởi tạo tất cả Node với None/empty (chưa có dữ liệu)
        """
        
        # ✓ Dict lưu dữ liệu: {Node_name: {x, y, score, ring_name, shots: []}}
        # Khởi tạo 5 Node từ NODE1 đến NODE5
        self.scores = {
            "NODE1": {"x": None, "y": None, "score": None, "ring_name": None, "shots": []},
            "NODE2": {"x": None, "y": None, "score": None, "ring_name": None, "shots": []},
            "NODE3": {"x": None, "y": None, "score": None, "ring_name": None, "shots": []},
            "NODE4": {"x": None, "y": None, "score": None, "ring_name": None, "shots": []},
            "NODE5": {"x": None, "y": None, "score": None, "ring_name": None, "shots": []},
        }
    
    def update(self, node_name, x, y):
        """
        Cập nhật dữ liệu tọa độ của một Node và tính điểm
        
        🔧 HOẠT ĐỘNG:
        1. Chuẩn hóa tên Node (loại bỏ khoảng trắng, chuyển uppercase)
        2. Cập nhật tọa độ x, y
        3. Tính điểm bằng calculate_score()
        4. Lưu lịch sử bắn vào list shots
        5. Ghi log kết quả
        6. Ghi dữ liệu JSON cho HTML
        
        Tham số:
            node_name (str): Tên Node
                            Ví dụ: "NODE1", "NODE 1" (sẽ chuẩn hóa)
            x (float): Tọa độ X (-50 đến 50 cm)
            y (float): Tọa độ Y (-50 đến 50 cm)
        """
        
        # ✓ Chuẩn hóa tên Node: "NODE 1" → "NODE1"
        # replace(" ", "") → loại bỏ tất cả khoảng trắng
        # upper() → chuyển thành chữ hoa
        node_key = node_name.replace(" ", "").upper()
        
        # ✓ Cập nhật dữ liệu nếu Node tồn tại
        if node_key in self.scores:
            # ✓ Cập nhật tọa độ X
            self.scores[node_key]["x"] = x
            
            # ✓ Cập nhật tọa độ Y
            self.scores[node_key]["y"] = y
            
            # ✓ Tính điểm bằng hàm calculate_score()
            score_result = calculate_score(x, y)
            
            # ✓ Cập nhật điểm số
            self.scores[node_key]["score"] = score_result['score']
            
            # ✓ Cập nhật tên vòng
            self.scores[node_key]["ring_name"] = score_result['ring_name']
            
            # ✓ Lưu lịch sử bắn (lưu thông tin chi tiết của viên đạn này)
            shot_info = {
                'x': x,                                   # Tọa độ X
                'y': y,                                   # Tọa độ Y
                'score': score_result['score'],           # Điểm số
                'ring': score_result['ring_name'],        # Tên vòng
                'distance': score_result['distance']      # Khoảng cách từ tâm
            }
            
            # ✓ Thêm vào danh sách shots (tối đa 3 viên)
            self.scores[node_key]["shots"].append(shot_info)
            
            # ✓ Ghi log kết quả
            log_data(f"[SCORE] {node_key}: ({x}, {y}) - "
                    f"{score_result['ring_name']} - {score_result['score']} điểm")
            
            # ✓ Ghi dữ liệu JSON cho HTML visualization
            self.save_to_json()
    
    def save_to_json(self):
        """
        Ghi dữ liệu hiện tại vào file score_data.json
        
        🔧 HOẠT ĐỘNG:
        1. Tạo dict dữ liệu với timestamp hiện tại
        2. Duyệt qua tất cả Node và lấy tất cả viên bắn
        3. Thêm mỗi viên vào list 'rounds'
        4. Ghi dict thành JSON file
        
        📝 ĐỊNH DẠNG JSON:
        {
            "timestamp": "2024-04-19T10:25:30.123456",
            "rounds": [
                {
                    "node": "NODE1",
                    "x": -26.0,
                    "y": 30.0,
                    "score": 8,
                    "ring": "Vòng 3",
                    "distance": 38.2
                },
                ...
            ]
        }
        
        💡 MỤC ĐÍCH:
        - HTML file có thể đọc JSON này để visualization
        - Realtime update điểm số trên trình duyệt
        """
        
        try:
            # ✓ Tạo cấu trúc dữ liệu để ghi JSON
            data = {
                'timestamp': datetime.now().isoformat(),  # Timestamp hiện tại
                'rounds': []                              # List chứa tất cả viên bắn
            }
            
            # ✓ Duyệt qua tất cả Node
            for node_key in self.scores.keys():
                # ✓ Duyệt qua tất cả viên bắn của Node này
                for shot in self.scores[node_key]["shots"]:
                    # ✓ Thêm thông tin viên bắn vào list rounds
                    data['rounds'].append({
                        'node': node_key,                  # Tên Node
                        'x': shot['x'],                    # Tọa độ X
                        'y': shot['y'],                    # Tọa độ Y
                        'score': shot['score'],            # Điểm số
                        'ring': shot['ring'],              # Tên vòng
                        'distance': shot['distance']       # Khoảng cách từ tâm
                    })
            
            # ✓ Ghi vào file JSON
            # 'w': write mode - tạo file mới (ghi đè nếu tồn tại)
            # indent=2: format đẹp (2 spaces)
            # ensure_ascii=False: cho phép Unicode (chữ Việt, v.v.)
            with open('score_data.json', 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        
        except Exception as e:
            # ❌ Nếu có lỗi khi ghi JSON
            log_data(f"[ERROR] Failed to save JSON: {e}")
    
    def reset_round(self):
        """
        Reset dữ liệu cho vòng bắn mới
        
        🔧 HOẠT ĐỘNG:
        1. Duyệt qua tất cả Node
        2. Kiểm tra nếu Node chưa nhận đủ 3 viên
        3. Thêm viên miss (0 điểm) cho những viên thiếu
        4. Ghi log thông báo miss
        5. Cập nhật JSON
        
        💡 MỤC ĐÍCH:
        - Đảm bảo tất cả Node có đủ 3 viên bắn
        - Nếu Node không bắn 3 viên trong thời gian → coi là miss
        - Tính tổng điểm của vòng (tối đa 3 viên)
        """
        
        # ✓ Duyệt qua tất cả Node
        for node_key in self.scores.keys():
            # ✓ Nếu chưa nhận đủ 3 viên, thêm 0 điểm
            # while loop tiếp tục cho đến khi shots có đúng 3 phần tử
            while len(self.scores[node_key]["shots"]) < 3:
                # ✓ Thêm viên miss (0 điểm)
                self.scores[node_key]["shots"].append({
                    'x': None,                            # Tọa độ X (không biết)
                    'y': None,                            # Tọa độ Y (không biết)
                    'score': 0,                           # Điểm số = 0
                    'ring': 'Miss',                       # Tên vòng = Miss
                    'distance': None                      # Khoảng cách (không biết)
                })
                
                # ✓ Ghi log thông báo miss
                log_data(f"[MISS] {node_key}: Viên bắn thứ "
                        f"{len(self.scores[node_key]['shots'])} thiếu - 0 điểm")
        
        # ✓ Cập nhật JSON sau khi thêm các viên miss
        self.save_to_json()
    
    def get_total_score(self, node_key):
        """
        Tính tổng điểm của một Node (3 viên bắn)
        
        🔧 HOẠT ĐỘNG:
        1. Kiểm tra Node tồn tại
        2. Duyệt qua tất cả viên bắn
        3. Cộng điểm của mỗi viên
        4. Trả về tổng điểm
        
        📊 CÔNG THỨC:
        Tổng = Viên 1 + Viên 2 + Viên 3
        Ví dụ: 10 + 8 + 5 = 23 điểm
        
        Tham số:
            node_key (str): Tên Node (ví dụ: "NODE1")
        
        Trả về:
            int: Tổng điểm (0-30)
        """
        
        # ✓ Kiểm tra Node tồn tại
        if node_key in self.scores:
            # ✓ Lấy list viên bắn
            shots = self.scores[node_key]["shots"]
            
            # ✓ Nếu có viên bắn
            if shots:
                # ✓ Cộng điểm của tất cả viên bắn
                # sum() → cộng tất cả
                # shot['score'] for shot in shots → lấy điểm của mỗi viên
                return sum(shot['score'] for shot in shots)
        
        # ✓ Nếu Node không tồn tại hoặc không có viên → trả về 0
        return 0
    
    def display(self):
        """
        Hiển thị điểm số dạng bảng trên console
        
        🔧 HOẠT ĐỘNG:
        1. In dòng kẻ trên
        2. In tiêu đề (SHOOTING RANGE SCORING SYSTEM)
        3. In header (tên các Node)
        4. In tọa độ X của mỗi Node
        5. In tọa độ Y của mỗi Node
        6. In điểm số của mỗi Node
        7. In tên vòng của mỗi Node
        8. In dòng kẻ dưới
        
        📊 ĐỊNH DẠNG:
        ================================================================================
        SHOOTING RANGE SCORING SYSTEM
        ================================================================================
        |      NODE1      |      NODE2      |      NODE3      |      NODE4      | NODE5 |
        X:   |      -26      |       15       |       45       |       10       |  -30  |
        Y:   |       30      |       -20      |       50       |        5       |  25   |
        Điểm:|       10      |        8       |        5       |        7       |   6   |
        Vòng:|   Bullseye    |    Vòng 3      |    Vòng 6      |    Vòng 4      | Vòng 5|
        ================================================================================
        """
        
        # ✓ In dòng kẻ trên (=== =)
        print("\n" + "="*80)
        
        # ✓ In tiêu đề (căn giữa, chiều rộng 80)
        print("SHOOTING RANGE SCORING SYSTEM".center(80))
        
        # ✓ In dòng kẻ dưới tiêu đề
        print("="*80)
        
        # === In header (tên các Node) ===
        # Tạo dòng header: |  NODE1  |  NODE2  | ...
        header = "| " + " | ".join(
            f"{node:^14}"      # Tên Node, căn giữa, rộng 14 ký tự
            for node in self.scores.keys()
        ) + " |"
        print(header)
        
        # ✓ In dòng kẻ dưới header (---)
        print("-" * len(header))
        
        # === In tọa độ X ===
        # Tạo dòng X: |  -26  |  15  | ...
        x_row = "| " + " | ".join(
            f"{str(self.scores[node]['x']):^14}"   # Giá trị X, căn giữa
            for node in self.scores.keys()
        ) + " |"
        print(f"X:   {x_row}")
        
        # === In tọa độ Y ===
        # Tạo dòng Y: |  30  |  -20  | ...
        y_row = "| " + " | ".join(
            f"{str(self.scores[node]['y']):^14}"   # Giá trị Y, căn giữa
            for node in self.scores.keys()
        ) + " |"
        print(f"Y:   {y_row}")
        
        # === In điểm số ===
        # Tạo dòng Điểm: |  10  |  8  | ...
        score_row = "| " + " | ".join(
            f"{str(self.scores[node]['score']):^14}"   # Điểm số, căn giữa
            for node in self.scores.keys()
        ) + " |"
        print(f"Điểm:{score_row}")
        
        # === In tên vòng ===
        # Tạo dòng Vòng: |  Bullseye  |  Vòng 3  | ...
        ring_row = "| " + " | ".join(
            f"{str(self.scores[node]['ring_name']):^14}"   # Tên vòng, căn giữa
            for node in self.scores.keys()
        ) + " |"
        print(f"Vòng:{ring_row}")
        
        # ✓ In dòng kẻ cuối
        print("="*80 + "\n")

# ✓ Tạo đối tượng để hiển thị điểm
display = ScoreDisplay()

# ==================== XỬ LÝ SỰ KIỆN NÚT BẤM ====================

def button_callback(channel):
    """
    Callback function khi nút bấm được kích hoạt
    
    🔧 HOẠT ĐỘNG:
    1. Debounce (chống rung): chờ 20ms
    2. Kiểm tra xem EXTRA mode có active không
    3. Nếu EXTRA active:
       - Chỉ nút EXTRA (GPIO 8) có thể hoạt động
       - Nút khác bị khóa
    4. Nếu không EXTRA:
       - Kiểm tra loại nút (A, EXTRA, NODE1-5)
       - Toggle trạng thái: False→True (UP), True→False (DOWN)
       - Gửi lệnh tương ứng
    
    💡 LOGIC TOGGLE:
    - Lần bấm 1: state = False → gửi "UP" → state = True
    - Lần bấm 2: state = True → gửi "DOWN" → state = False
    - Lần bấm 3: state = False → gửi "UP" → state = True, ...
    
    Tham số:
        channel (int): GPIO pin số của nút được bấm
                      Ví dụ: 2, 3, 4, 5, 6, 7, 8, 17
    """
    
    # ✓ Khai báo global để sửa đổi biến trạng thái
    global extra_mode_active
    
    # ✓ Debounce: chờ 20ms để đảm bảo đó là bấm thực
    # Mục đích: tránh "bounce" (rung lên rung xuống) của nút cơ
    time.sleep(0.02)
    
    # ✓ Kiểm tra lại trạng thái pin sau khi debounce
    # GPIO.LOW = 0V = nút được bấm
    # GPIO.HIGH = 3.3V = nút được thả
    if GPIO.input(channel) == GPIO.LOW:
        
        # ✓ Lấy tên Node từ dict BUTTON_PINS
        # Ví dụ: channel=2 → BUTTON_PINS[2] = "NODE1"
        node_name = BUTTON_PINS[channel]
        
        # ===== KIỂM TRA NẾU EXTRA MODE ĐANG ACTIVE =====
        if extra_mode_active:
            # ✓ Trong chế độ EXTRA, chỉ nút EXTRA (GPIO 8) có thể hoạt động
            if channel == 8:
                # ✓ Bấm EXTRA lần nữa → Thoát khỏi EXTRA mode
                extra_mode_active = False
                
                # ✓ Gửi lệnh EXTRA DOWN
                send_command("EXTRA", "DOWN")
                
                # ✓ Ghi log
                log_data("[CONTROL] EXTRA mode OFF - All buttons unlocked")
                
                return
            else:
                # ✓ Các nút khác bị khóa
                log_data(f"[WARNING] Button {node_name} is locked "
                        f"(EXTRA mode active)")
                return
        
        # ===== CHẾ ĐỘ BÌNH THƯỜNG (EXTRA không active) =====
        
        # ✓ Nút A: Lệnh broadcast cho tất cả Node
        if node_name == "A":
            if button_states[channel] == False:
                # ✓ Lần bấm đầu tiên: gửi "A UP"
                send_command("A", "UP")
                # ✓ Cập nhật trạng thái thành True
                button_states[channel] = True
            else:
                # ✓ Lần bấm thứ hai: gửi "A DOWN"
                send_command("A", "DOWN")
                # ✓ Cập nhật trạng thái thành False
                button_states[channel] = False
        
        # ✓ Nút EXTRA: Khóa tất cả, chế độ bảo trì
        elif node_name == "EXTRA":
            if button_states[channel] == False:
                # ✓ Lần bấm đầu tiên: gửi "EXTRA UP" (khóa tất cả nút)
                extra_mode_active = True  # ← SET FLAG
                send_command("EXTRA", "UP")
                button_states[channel] = True
                
                log_data("[CONTROL] EXTRA mode ON - All buttons locked")
            else:
                # ✓ Lần bấm thứ hai: gửi "EXTRA DOWN"
                extra_mode_active = False  # ← CLEAR FLAG
                send_command("EXTRA", "DOWN")
                button_states[channel] = False
                
                log_data("[CONTROL] EXTRA mode OFF - All buttons unlocked")
        
        # ✓ Nút B: Loại bia B (hình chữ nhật 150×42cm)
        elif node_name == "B":
            if button_states[channel] == False:
                # ✓ Lần bấm đầu tiên: gửi "B UP"
                send_command("B", "UP")
                button_states[channel] = True
            else:
                # ✓ Lần bấm thứ hai: gửi "B DOWN"
                send_command("B", "DOWN")
                button_states[channel] = False
        
        # ✓ NODE1, NODE2, NODE3, NODE4, NODE5
        else:
            if button_states[channel] == False:
                # ✓ Lần bấm đầu tiên: gửi "UP"
                send_command(node_name, "UP")
                button_states[channel] = True
            else:
                # ✓ Lần bấm thứ hai: gửi "DOWN"
                send_command(node_name, "DOWN")
                button_states[channel] = False

# === Thiết lập interrupt cho tất cả các nút bấm ===
# Interrupt = ngắt (khi sự kiện xảy ra, tự động gọi callback)
for pin in BUTTON_PINS.keys():
    # ✓ Thêm event detect:
    # - pin: GPIO pin
    # - GPIO.FALLING: phát hiện khi GPIO từ HIGH → LOW (bấm nút)
    # - callback: hàm sẽ gọi khi phát hiện sự kiện
    # - bouncetime: ignore bounce trong 50ms
    GPIO.add_event_detect(pin, GPIO.FALLING, 
                          callback=button_callback, bouncetime=50)

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """
    Vòng lặp chính của Controller
    
    🔧 HOẠT ĐỘNG:
    1. Ghi log khi chương trình bắt đầu
    2. Liên tục nhận dữ liệu từ các Node
    3. Phân tích dữ liệu nhận được
    4. Cập nhật điểm vào display
    5. Hiển thị bảng điểm lên console
    6. Delay 100ms để giảm CPU usage
    7. Xử lý lỗi nếu có
    8. Dọn dẹp trước khi thoát
    
    💡 FLOW:
    while True:
        ↓ receive_data() - nhận từ Node
        ↓ parse_node_data() - phân tích
        ↓ display.update() - cập nhật
        ↓ display.display() - hiển thị
        ↓ time.sleep(0.1) - chờ 100ms
        ↑ lặp lại
    """
    
    # ✓ Ghi log dòng kẻ
    log_data("="*80)
    
    # ✓ Ghi log thông báo bắt đầu
    log_data("CONTROLLER STARTED - RPi 5")
    
    # ✓ Ghi log dòng kẻ
    log_data("="*80)
    
    try:
        # ✓ Vòng lặp chính - chạy liên tục cho đến khi người dùng nhấn Ctrl+C
        while True:
            # ✓ Nhận dữ liệu từ các Node
            data = receive_data()
            
            # ✓ Nếu có dữ liệu
            if data:
                # ✓ Phân tích dữ liệu: tách tên Node, x, y
                node_name, x, y = parse_node_data(data)
                
                # ✓ Nếu phân tích thành công (node_name != None)
                if node_name:
                    # ✓ Cập nhật dữ liệu vào display (bao gồm tính điểm)
                    display.update(node_name, x, y)
                    
                    # ✓ Hiển thị bảng điểm lên console
                    display.display()
            
            # ✓ Delay 100ms để giảm CPU usage
            # CPU không bị "busy waiting" (chạy liên tục 100%)
            time.sleep(0.1)
    
    # === Xử lý khi nhấn Ctrl+C ===
    except KeyboardInterrupt:
        # ✓ Ghi log thông báo dừng
        log_data("Controller stopped by user")
    
    # === Xử lý các lỗi khác ===
    except Exception as e:
        # ✓ Ghi log lỗi
        log_data(f"[ERROR] {e}")
    
    # === Dọn dẹp trước khi thoát ===
    # ✓ Lệnh finally LUÔN chạy (dù có exception hay không)
    finally:
        # ✓ Ghi log dòng kẻ
        log_data("="*80)
        
        # ✓ Ghi log thông báo thoát
        log_data("Cleanup GPIO and LoRa...")
        
        # ✓ Dọn dẹp GPIO
        # Trả tất cả pin về trạng thái mặc định
        GPIO.cleanup()
        
        # ✓ Đóng kết nối LoRa
        lora.close()
        
        # ✓ Ghi log hoàn tất
        log_data("Cleanup completed")

# ==================== CHẠY CHƯƠNG TRÌNH ====================

if __name__ == "__main__":
    """
    Kiểm tra nếu file này được chạy trực tiếp (không được import)
    
    💡 MỤC ĐÍCH:
    - if __name__ == "__main__": chỉ chạy khi file được chạy trực tiếp
    - Nếu file được import từ file khác, khối này sẽ không chạy
    - Điều này cho phép tái sử dụng code
    """
    
    # ✓ Gọi hàm main để bắt đầu chương trình
    main()