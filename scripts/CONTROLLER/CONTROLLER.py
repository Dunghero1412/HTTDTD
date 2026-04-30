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
# Bia tròn 10 vòng đồng tâm, mỗi vòng rộng 7.5cm, tâm ở (0,0)
# (radius_max_cm, điểm)
SCORING_RINGS = [
    (7.5,  10),   # Vòng 10 – Bullseye
    (15.0,  9),   # Vòng 9
    (22.5,  8),   # Vòng 8
    (30.0,  7),   # Vòng 7
    (37.5,  6),   # Vòng 6
    (45.0,  5),   # Vòng 5
    (52.5,  4),   # Vòng 4
    (60.0,  3),   # Vòng 3
    (67.5,  2),   # Vòng 2
    (75.0,  1),   # Vòng 1
    (float('inf'), 0),  # Ngoài bia
]

# Bán kính tối đa của bia (cm) – vòng 1 ngoài cùng
MAX_RADIUS = 75

# Timeout điều khiển: 60 giây
# Sau khi bấm nút UP, nếu hết 60s mà không nhận đủ 3 viên → tự động OFF
CONTROL_TIMEOUT = 60

# ==================== KHỞI TẠO HARDWARE ====================
# Khai báo trước, khởi tạo trong setup() để tránh crash khi import
lora = None

def setup():
    """
    Khởi tạo GPIO và LoRa. Gọi một lần từ main().
    Tách khỏi module level để handle lỗi hardware sạch hơn.
    """
    global lora

    # ── GPIO ──────────────────────────────────────────────────
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    for pin in BUTTON_PINS.keys():
        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        button_states[pin] = False

    # Thiết lập interrupt — không sleep trong callback, dùng bouncetime
    for pin in BUTTON_PINS.keys():
        GPIO.add_event_detect(pin, GPIO.FALLING,
                              callback=button_callback, bouncetime=200)
    print(f"[INIT] GPIO ready ({len(BUTTON_PINS)} buttons)")

    # ── LoRa ──────────────────────────────────────────────────
    try:
        lora = LoRa(BOARD.CN1, BOARD.CN1, baud=BAUD_RATE)
        lora.set_frequency(LORA_FREQUENCY)
        print(f"[INIT] LoRa ready at {LORA_FREQUENCY}MHz")
    except Exception as e:
        print(f"[ERROR] LoRa init failed: {e}")
        GPIO.cleanup()
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
    Phân tích dữ liệu nhận từ Node.

    Định dạng: "NODE1A, -26.3, 30.1"
    Trả về:   ("NODE1A", -26.3, 30.1)

    Giữ nguyên tên đầy đủ (NODE1A, NODE2B, NODE3C...) để
    ScoreDisplay phân biệt đúng từng node theo dãy bia.
    """
    try:
        parts = data.split(',')
        if len(parts) < 3:
            return (None, None, None)

        # Chuẩn hóa khoảng trắng và chữ hoa, giữ nguyên suffix A/B/C
        node_name = parts[0].strip().upper().replace(" ", "")
        x = float(parts[1].strip())
        y = float(parts[2].strip())
        return (node_name, x, y)

    except (ValueError, IndexError, AttributeError):
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
    Xác định số điểm dựa trên khoảng cách từ tâm.
    Trả về (score, ring_name).
    """
    for radius, score in SCORING_RINGS:
        if distance <= radius:
            if score == 0:
                return 0, "Ngoài bia"
            return score, f"Vòng {score}"
    return 0, "Ngoài bia"


def calculate_score(x, y):
    """
    Tính điểm dựa trên tọa độ viên đạn.

    Trả về dict: score, distance, ring_name, x, y
    """
    distance = calculate_distance(x, y)
    score, ring_name = get_ring(distance)

    return {
        'score':    score,
        'distance': round(distance, 2),
        'ring_name': ring_name,
        'x': x,
        'y': y,
    }

#===================== XOÁ DỮ LIỆU JSON CHO ROUND MỚI ================

def clear_score_json(file_path="/opt/score.json"):
    """
    Xóa nội dung file JSON, ghi lại cấu trúc rỗng hợp lệ.
    """
    try:
        # Ghi cấu trúc rỗng: {"rounds": []}
        with open(file_path, 'w') as f:
            json.dump({"rounds": []}, f, indent=2)
        log_data(f"[JSON] Cleared content of {file_path}")
    except Exception as e:
        log_data(f"[ERROR] Failed to clear JSON: {e}")

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
        
        # ✓ Dict lưu dữ liệu: 15 node (5 node × 3 dãy A/B/C)
        # Dãy A = đợt bắn 1, Dãy B = đợt bắn 2, Dãy C = đợt bắn 3
        _empty = lambda: {"x": None, "y": None, "score": None,
                          "ring_name": None, "shots": []}
        self.scores = {
            # ── Dãy A (hàng 1) ────────────────────────────────
            "NODE1A": _empty(), "NODE2A": _empty(), "NODE3A": _empty(),
            "NODE4A": _empty(), "NODE5A": _empty(),
            # ── Dãy B (hàng 2) ────────────────────────────────
            "NODE1B": _empty(), "NODE2B": _empty(), "NODE3B": _empty(),
            "NODE4B": _empty(), "NODE5B": _empty(),
            # ── Dãy C (hàng 3) ────────────────────────────────
            "NODE1C": _empty(), "NODE2C": _empty(), "NODE3C": _empty(),
            "NODE4C": _empty(), "NODE5C": _empty(),
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
        Pad miss cho những viên thiếu rồi clear shots cho vòng tiếp theo.

        FIX: Sau khi pad, lưu tổng điểm vào history rồi clear shots[],
             tránh điểm vòng cũ bị cộng dồn vào vòng mới.
        """
        for node_key in self.scores.keys():
            # Pad viên miss còn thiếu
            while len(self.scores[node_key]["shots"]) < 3:
                self.scores[node_key]["shots"].append({
                    'x': None, 'y': None,
                    'score': 0, 'ring': 'Miss', 'distance': None
                })
                log_data(f"[MISS] {node_key}: viên "
                         f"{len(self.scores[node_key]['shots'])} – 0 điểm")

        self.save_to_json()

        # Clear cho vòng bắn tiếp theo
        for node_key in self.scores.keys():
            self.scores[node_key]["shots"]     = []
            self.scores[node_key]["x"]         = None
            self.scores[node_key]["y"]         = None
            self.scores[node_key]["score"]     = None
            self.scores[node_key]["ring_name"] = None
    
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
        Hiển thị bảng điểm nhóm theo dãy A / B / C.
        """
        print("\n" + "=" * 70)
        print("BẢNG ĐIỂM  –  " + datetime.now().strftime('%H:%M:%S'))
        print("=" * 70)

        for row_label, suffix in [("HÀNG 1", "A"),
                                   ("HÀNG 2", "B"),
                                   ("HÀNG 3", "C")]:
            print(f"\n  {row_label} – Dãy {suffix}")
            print("  " + "-" * 64)
            print(f"  {'NODE':<10} {'Viên 1':>12} {'Viên 2':>12} "
                  f"{'Viên 3':>12} {'TỔNG':>6}")
            print("  " + "-" * 64)

            row_total = 0
            for i in range(1, 6):
                key   = f"NODE{i}{suffix}"
                shots = self.scores[key]["shots"]
                total = self.get_total_score(key)
                row_total += total

                def fmt(idx):
                    if idx < len(shots):
                        s = shots[idx]
                        return "Miss" if s['score'] == 0 \
                               else f"{s['score']}đ/{s['ring']}"
                    return "—"

                print(f"  {key:<10} {fmt(0):>12} {fmt(1):>12} "
                      f"{fmt(2):>12} {total:>5}đ")

            print(f"  {'Tổng dãy ' + suffix:<10} {'':>12} {'':>12} "
                  f"{'':>12} {row_total:>5}đ")

        print("\n" + "=" * 70 + "\n")

# ==================== VÒNG LẶP CHÍNH ====================

def button_callback(channel):
    """
    Callback khi nút bấm được kích hoạt (GPIO FALLING edge).

    FIX: Bỏ time.sleep(0.02) trong callback — sleep trong interrupt context
         block thread GPIO và có thể miss event khác. Debounce đã được
         xử lý bởi bouncetime=200 trong add_event_detect().
    """
    global extra_mode_active

    # Kiểm tra lại sau edge (loại bỏ false trigger)
    if GPIO.input(channel) != GPIO.LOW:
        return

    node_name = BUTTON_PINS[channel]

    # ── EXTRA mode active: chỉ nút EXTRA được phép ────────────
    if extra_mode_active:
        if channel == 8:
            extra_mode_active = False
            send_command("EXTRA", "DOWN")
            log_data("[CONTROL] EXTRA mode OFF")
        else:
            log_data(f"[WARNING] {node_name} locked (EXTRA mode active)")
        return

    # ── Chế độ bình thường ────────────────────────────────────
    if node_name == "A":
        if not button_states[channel]:
            send_command("A", "UP")
            button_states[channel] = True
        else:
            send_command("A", "DOWN")
            button_states[channel] = False

    elif node_name == "EXTRA":
        if not button_states[channel]:
            extra_mode_active = True
            send_command("EXTRA", "UP")
            button_states[channel] = True
            log_data("[CONTROL] EXTRA mode ON")
        else:
            extra_mode_active = False
            send_command("EXTRA", "DOWN")
            button_states[channel] = False
            log_data("[CONTROL] EXTRA mode OFF")
            clear_score_json()       # xoá dữ liệu round cho đợt tiếp theo (chỉ khả dụng sau khi đã báo bia).

    elif node_name == "B":
        if not button_states[channel]:
            send_command("B", "UP")
            button_states[channel] = True
        else:
            send_command("B", "DOWN")
            button_states[channel] = False

    else:  # NODE1 .. NODE5
        if not button_states[channel]:
            send_command(node_name, "UP")
            button_states[channel] = True
        else:
            send_command(node_name, "DOWN")
            button_states[channel] = False

# ==================== BIẾN TRẠNG THÁI NÚT BẤM ====================
button_states = {}  # Khởi tạo trong setup()

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """Vòng lặp chính của Controller."""

    # ── Khởi tạo hardware ─────────────────────────────────────
    setup()
    display = ScoreDisplay()

    log_data("=" * 80)
    log_data("CONTROLLER STARTED - RPi 5")
    log_data("=" * 80)
    
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