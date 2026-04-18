#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi 5 Controller - Điều khiển hệ thống bắn đạn thật qua LoRa
Chương trình này chạy trên Raspberry Pi 5 để:
1. Đọc trạng thái 7 nút bấm (GPIO 2-8)
2. Gửi lệnh điều khiển đến 5 Node qua LoRa module SX1278
3. Nhận dữ liệu tọa độ từ các Node và tính điểm
4. Hiển thị bảng điểm lên màn hình
5. Ghi log dữ liệu vào file score.txt
"""

# ==================== NHẬP THƯ VIỆN ====================
import RPi.GPIO as GPIO                    # Thư viện điều khiển GPIO trên Raspberry Pi
import time                                # Thư viện làm việc với thời gian
import sys                                 # Thư viện hệ thống
import math                                # Thư viện tính toán toán học
from datetime import datetime              # Thư viện xử lý ngày giờ
from rpi_lora import LoRa                  # Thư viện LoRa để giao tiếp không dây
from rpi_lora.board_config import BOARD    # Cấu hình board cho LoRa module
import json				   # json library
# ==================== CẤU HÌNH CHUNG ====================

# --- Cấu hình UART cho LoRa ---
UART_PORT = "/dev/ttyAMA1"                 # UART 1 trên RPi 5 nối với LoRa
BAUD_RATE = 60000                          # Tốc độ baud 60000 bps

# --- Cấu hình GPIO cho các nút bấm ---
# Các nút được nối vào GPIO 2-8 trên RPi 5
BUTTON_PINS = {
    2: "NODE1",                            # GPIO 2 -> Node 1
    3: "NODE2",                            # GPIO 3 -> Node 2
    4: "NODE3",                            # GPIO 4 -> Node 3
    5: "NODE4",                            # GPIO 5 -> Node 4
    6: "NODE5",                            # GPIO 6 -> Node 5
    7: "A",                                # GPIO 7 -> Nút A (gửi lệnh "A UP/DOWN")
    8: "Extra"                             # GPIO 8 -> Nút dự phòng
}

# --- Cấu hình LoRa ---
LORA_FREQUENCY = 915                       # Tần số LoRa: 915 MHz

# --- File log ---
LOG_FILE = "score.txt"                     # File lưu kết quả

# --- Cấu hình hệ thống tính điểm ---
# Định nghĩa các vòng điểm: (bán kính tối đa (cm), điểm số)
SCORING_RINGS = [
    (7.5, 10),                             # Vòng 1: Bullseye (0-7.5cm) → 10 điểm
    (15, 9),                               # Vòng 2 (7.5-15cm) → 9 điểm
    (22.5, 8),                             # Vòng 3 (15-22.5cm) → 8 điểm
    (30, 7),                               # Vòng 4 (22.5-30cm) → 7 điểm
    (37.5, 6),                             # Vòng 5 (30-37.5cm) → 6 điểm
    (45, 5),                               # Vòng 6 (37.5-45cm) → 5 điểm
    (50, 4),                               # Vòng 7 (45-50cm) → 4 điểm
    (float('inf'), 0)                      # Ngoài bia → 0 điểm
]

# Bán kính tối đa của bia (cm)
MAX_RADIUS = 50

# Timeout điều khiển: 60 giây
CONTROL_TIMEOUT = 60

# ==================== KHỞI TẠO GPIO ====================

# Sử dụng chế độ BCM (Broadcom) để đặt tên GPIO
GPIO.setmode(GPIO.BCM)

# Tắt cảnh báo GPIO (nếu có)
GPIO.setwarnings(False)

# --- Khởi tạo từng nút bấm ---
# Dict để lưu trạng thái hiện tại của mỗi nút
button_states = {}

# Duyệt qua tất cả các pin nút bấm
for pin in BUTTON_PINS.keys():
    # Cấu hình pin là INPUT (nhập dữ liệu)
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    # Khởi tạo trạng thái nút là False (chưa bấm)
    button_states[pin] = False

# ==================== KHỞI TẠO LoRa ====================

# Khởi tạo LoRa module
lora = LoRa(BOARD.CN1, BOARD.CN1, baud=BAUD_RATE)

# Đặt tần số LoRa
lora.set_frequency(LORA_FREQUENCY)

# In thông báo khởi tạo thành công
print(f"[INIT] LoRa initialized at {LORA_FREQUENCY}MHz")

# ==================== HÀM HỖ TRỢ ====================

def log_data(message):
    """
    Ghi dữ liệu vào file log và hiển thị trên console
    
    Tham số:
        message (str): Thông điệp cần ghi
    
    Hoạt động:
    1. Tạo timestamp (ngày giờ hiện tại)
    2. Thêm timestamp vào message
    3. In lên console
    4. Ghi vào file log
    """
    # Lấy thời gian hiện tại với định dạng "YYYY-MM-DD HH:MM:SS"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Tạo thông điệp hoàn chỉnh với timestamp
    log_message = f"[{timestamp}] {message}"
    
    # In lên console
    print(log_message)
    
    # Mở file log ở chế độ append (thêm vào cuối file)
    with open(LOG_FILE, 'a') as f:
        # Ghi thông điệp vào file với ký tự xuống dòng
        f.write(log_message + "\n")

def send_command(node_name, command):
    """
    Gửi lệnh điều khiển đến một Node qua LoRa
    
    Tham số:
        node_name (str): Tên Node (VD: "NODE1", "A")
        command (str): Lệnh cần gửi ("UP" hoặc "DOWN")
    
    Định dạng lệnh:
        "NODE1 UP" - kích hoạt Node 1
        "NODE1 DOWN" - dừng Node 1
    """
    try:
        # Tạo thông điệp gửi: "NODE1 UP" hoặc "NODE1 DOWN"
        message = f"{node_name} {command}"
        
        # Chuyển string thành bytes (UTF-8) và gửi qua LoRa
        lora.send(message.encode())
        
        # Ghi log thông điệp đã gửi (TX = Transmit)
        log_data(f"[TX] Sent: {message}")
    
    except Exception as e:
        # Nếu có lỗi, ghi vào log
        log_data(f"[ERROR] Failed to send: {e}")

def receive_data():
    """
    Nhận dữ liệu từ các Node qua LoRa
    
    Trả về:
        str: Dữ liệu nhận được (ví dụ: "NODE 1, -26 , 30")
        None: Nếu không có dữ liệu
    """
    try:
        # Kiểm tra xem LoRa có đang nhận dữ liệu không
        if lora.is_rx_busy():
            return None
        
        # Đọc payload (dữ liệu) từ LoRa
        payload = lora.read()
        
        # Nếu có dữ liệu
        if payload:
            # Chuyển đổi từ bytes sang string (UTF-8)
            data = payload.decode()
            
            # Ghi log dữ liệu nhận được (RX = Receive)
            log_data(f"[RX] Received: {data}")
            
            # Trả về dữ liệu
            return data
    
    except Exception as e:
        # Nếu có lỗi, ghi vào log
        log_data(f"[ERROR] Failed to receive: {e}")
    
    # Trả về None nếu không có dữ liệu hoặc có lỗi
    return None

def parse_node_data(data):
    """
    Phân tích dữ liệu nhận từ Node
    
    Tham số:
        data (str): Dữ liệu nhận từ Node
                   Định dạng: "NODE 1, -26 , 30"
    
    Trả về:
        tuple: (node_name, x, y) - ví dụ: ("NODE 1", -26.0, 30.0)
               hoặc (None, None, None) nếu lỗi
    """
    try:
        # Tách dữ liệu bằng dấu phẩy
        parts = data.split(',')
        
        # Lấy phần tên Node và loại bỏ khoảng trắng
        node_name = parts[0].strip()
        
        # Chuyển đổi phần x thành số float
        x = float(parts[1].strip())
        
        # Chuyển đổi phần y thành số float
        y = float(parts[2].strip())
        
        # Trả về tuple (node_name, x, y)
        return (node_name, x, y)
    
    except:
        # Nếu lỗi khi phân tích, trả về None
        return (None, None, None)

# ==================== HÀM TÍNH ĐIỂM ====================

def calculate_distance(x, y):
    """
    Tính khoảng cách từ tâm bia (0, 0) đến điểm (x, y)
    
    Tham số:
        x (float): Tọa độ X
        y (float): Tọa độ Y
    
    Trả về:
        float: Khoảng cách từ tâm (cm)
    
    Công thức: r = √(x² + y²)
    """
    # Tính khoảng cách Euclidean từ tâm (0, 0)
    distance = math.sqrt(x**2 + y**2)
    
    return distance

def get_ring(distance):
    """
    Xác định vòng điểm dựa trên khoảng cách
    
    Tham số:
        distance (float): Khoảng cách từ tâm (cm)
    
    Trả về:
        int: Số vòng (1-7) hoặc 0 nếu ngoài bia
    """
    # Duyệt qua các vòng để tìm vòng tương ứng
    for ring_num, (radius, _) in enumerate(SCORING_RINGS, 1):
        if distance <= radius:
            return ring_num
    
    return 0  # Ngoài bia

def calculate_score(x, y):
    """
    Tính điểm dựa trên tọa độ viên đạn
    
    Tham số:
        x (float): Tọa độ X (-50 đến 50 cm)
        y (float): Tọa độ Y (-50 đến 50 cm)
    
    Trả về:
        dict: {
            'score': điểm số,
            'distance': khoảng cách từ tâm (cm),
            'ring': số vòng,
            'ring_name': tên vòng
        }
    """
    # Tính khoảng cách từ tâm
    distance = calculate_distance(x, y)
    
    # Xác định vòng điểm
    ring = get_ring(distance)
    
    # Lấy điểm số từ SCORING_RINGS
    if ring > 0 and ring <= len(SCORING_RINGS):
        score = SCORING_RINGS[ring - 1][1]
    else:
        score = 0
    
    # Tên vòng
    ring_names = {
        0: "Ngoài bia",
        1: "Bullseye",
        2: "Vòng 2",
        3: "Vòng 3",
        4: "Vòng 4",
        5: "Vòng 5",
        6: "Vòng 6",
        7: "Vòng 7"
    }
    
    ring_name = ring_names.get(ring, "Lỗi")
    
    # Trả về dict kết quả
    return {
        'score': score,
        'distance': round(distance, 2),
        'ring': ring,
        'ring_name': ring_name,
        'x': x,
        'y': y
    }

# ==================== LỚP HIỂN THỊ DỮ LIỆU ====================

class ScoreDisplay:
    """
    Lớp để quản lý và hiển thị điểm số từ các Node
    
    Chức năng:
    - Lưu trữ dữ liệu tọa độ của mỗi Node
    - Tính toán điểm số dựa trên tọa độ
    - Hiển thị dữ liệu dạng bảng (cột)
    - Cập nhật dữ liệu khi nhận từ Node
    """
    
    def __init__(self):
        """
        Khởi tạo đối tượng ScoreDisplay
        
        Tạo dict để lưu điểm số của 5 Node
        Mỗi Node có: x, y, score, ring_name
        """
        # Dict lưu dữ liệu: {Node_name: {x, y, score, ring_name, shots: []}}
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
        
        Tham số:
            node_name (str): Tên Node (ví dụ: "NODE 1")
            x (float): Tọa độ X
            y (float): Tọa độ Y
        """
        # Chuẩn hóa tên Node: "NODE 1" -> "NODE1"
        node_key = node_name.replace(" ", "").upper()
        
        # Cập nhật dữ liệu nếu Node tồn tại
        if node_key in self.scores:
            # Cập nhật tọa độ
            self.scores[node_key]["x"] = x
            self.scores[node_key]["y"] = y
            
            # Tính điểm
            score_result = calculate_score(x, y)
            self.scores[node_key]["score"] = score_result['score']
            self.scores[node_key]["ring_name"] = score_result['ring_name']
            
            # Lưu lịch sử bắn (tối đa 3 viên)
            shot_info = {
                'x': x,
                'y': y,
                'score': score_result['score'],
                'ring': score_result['ring_name'],
                'distance': score_result['distance']
            }
            self.scores[node_key]["shots"].append(shot_info)
            
            # Ghi log kết quả
            log_data(f"[SCORE] {node_key}: ({x}, {y}) - {score_result['ring_name']} - {score_result['score']} điểm")
    

            # ← THÊM PHẦN NÀY: Ghi dữ liệu JSON cho HTML
            self.save_to_json()
    
    def save_to_json(self):
        """
        Ghi dữ liệu hiện tại vào file score_data.json
        Để HTML có thể đọc và hiển thị realtime
        """
        try:
            # Tạo cấu trúc dữ liệu để ghi JSON
            data = {
                'timestamp': datetime.now().isoformat(),
                'rounds': []
            }
            
            # Duyệt qua tất cả Node và lấy tất cả các viên bắn
            for node_key in self.scores.keys():
                for shot in self.scores[node_key]["shots"]:
                    data['rounds'].append({
                        'node': node_key,
                        'x': shot['x'],
                        'y': shot['y'],
                        'score': shot['score'],
                        'ring': shot['ring'],
                        'distance': shot['distance']
                    })
            
            # Ghi vào file JSON
            with open('score_data.json', 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            log_data(f"[ERROR] Failed to save JSON: {e}")
    

    def reset_round(self):
        """
        Reset dữ liệu cho vòng bắn mới
        Nếu Node chưa nhận 3 kết quả, thêm 0 điểm cho những viên thiếu
        """
        for node_key in self.scores.keys():
            # Nếu chưa nhận đủ 3 viên, thêm 0 điểm
            while len(self.scores[node_key]["shots"]) < 3:
                self.scores[node_key]["shots"].append({
                    'x': None,
                    'y': None,
                    'score': 0,
                    'ring': 'Miss',
                    'distance': None
                })
                log_data(f"[MISS] {node_key}: Viên bắn thứ {len(self.scores[node_key]['shots'])} thiếu - 0 điểm")
    
    self.save_to_json()

    def get_total_score(self, node_key):
        """
        Tính tổng điểm của một Node (3 viên bắn)
        
        Tham số:
            node_key (str): Tên Node
        
        Trả về:
            int: Tổng điểm
        """
        if node_key in self.scores:
            shots = self.scores[node_key]["shots"]
            if shots:
                return sum(shot['score'] for shot in shots)
        return 0
    
    def display(self):
        """
        Hiển thị điểm số dạng bảng trên console
        
        Định dạng:
        ============================================================
        SHOOTING RANGE SCORING SYSTEM
        ============================================================
        |      NODE1      |      NODE2      |      NODE3      | ...
        X:  |      -26      |       15       |       45       | ...
        Y:  |       30      |       -20      |       50       | ...
        Điểm:|       10      |        8       |        5       | ...
        Vòng:|   Bullseye    |    Vòng 3      |    Vòng 6      | ...
        ============================================================
        """
        # In dòng kẻ trên
        print("\n" + "="*80)
        
        # In tiêu đề
        print("SHOOTING RANGE SCORING SYSTEM".center(80))
        
        # In dòng kẻ dưới tiêu đề
        print("="*80)
        
        # --- In header (tên các Node) ---
        header = "| " + " | ".join(
            f"{node:^14}" for node in self.scores.keys()
        ) + " |"
        print(header)
        
        # In dòng kẻ dưới header
        print("-" * len(header))
        
        # --- In tọa độ X ---
        x_row = "| " + " | ".join(
            f"{str(self.scores[node]['x']):^14}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"X:   {x_row}")
        
        # --- In tọa độ Y ---
        y_row = "| " + " | ".join(
            f"{str(self.scores[node]['y']):^14}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"Y:   {y_row}")
        
        # --- In điểm số ---
        score_row = "| " + " | ".join(
            f"{str(self.scores[node]['score']):^14}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"Điểm:{score_row}")
        
        # --- In tên vòng ---
        ring_row = "| " + " | ".join(
            f"{str(self.scores[node]['ring_name']):^14}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"Vòng:{ring_row}")
        
        # In dòng kẻ cuối
        print("="*80 + "\n")

# Tạo đối tượng để hiển thị điểm
display = ScoreDisplay()

# ==================== XỬ LÝ SỰ KIỆN NÚT BẤM ====================

def button_callback(channel):
    """
    Callback function khi nút bấm được kích hoạt
    
    Tham số:
        channel (int): GPIO pin số của nút được bấm
    
    Hoạt động:
    1. Debounce (chống rung): chờ 20ms để đảm bảo đó là bấm thực
    2. Kiểm tra trạng thái hiện tại của nút
    3. Nếu chưa bấm (False), gửi lệnh "UP" và đổi trạng thái thành True
    4. Nếu đã bấm (True), gửi lệnh "DOWN" và đổi trạng thái thành False
    """
    # Debounce: chờ 20ms để đảm bảo đó là bấm thực
    time.sleep(0.02)
    
    # Kiểm tra lại trạng thái pin
    if GPIO.input(channel) == GPIO.LOW:
        # Lấy tên Node từ dict BUTTON_PINS
        node_name = BUTTON_PINS[channel]
        
        # Kiểm tra trạng thái hiện tại của nút
        if button_states[channel] == False:
            # Lần bấm đầu tiên: gửi "UP"
            send_command(node_name, "UP")
            # Cập nhật trạng thái: đã bấm
            button_states[channel] = True
        else:
            # Lần bấm thứ hai: gửi "DOWN"
            send_command(node_name, "DOWN")
            # Cập nhật trạng thái: chưa bấm
            button_states[channel] = False

# --- Thiết lập interrupt cho tất cả các nút bấm ---
for pin in BUTTON_PINS.keys():
    GPIO.add_event_detect(pin, GPIO.FALLING, callback=button_callback, bouncetime=50)

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """
    Vòng lặp chính của Controller
    
    Hoạt động:
    1. Ghi log khi chương trình bắt đầu
    2. Liên tục nhận dữ liệu từ các Node
    3. Phân tích dữ liệu nhận được
    4. Tính điểm
    5. Cập nhật và hiển thị lên màn hình
    6. Xử lý timeout (60s) - hạ bia và tính 0 điểm cho những viên thiếu
    7. Xử lý lỗi nếu có
    8. Dọn dẹp trước khi thoát
    """
    # Ghi log dòng kẻ
    log_data("="*80)
    
    # Ghi log thông báo bắt đầu
    log_data("CONTROLLER STARTED - RPi 5")
    
    # Ghi log dòng kẻ
    log_data("="*80)
    
    try:
        # Vòng lặp chính - chạy liên tục cho đến khi người dùng nhấn Ctrl+C
        while True:
            # Nhận dữ liệu từ các Node
            data = receive_data()
            
            # Nếu có dữ liệu
            if data:
                # Phân tích dữ liệu: tách tên Node, x, y
                node_name, x, y = parse_node_data(data)
                
                # Nếu phân tích thành công (không có lỗi)
                if node_name:
                    # Cập nhật dữ liệu vào display (bao gồm tính điểm)
                    display.update(node_name, x, y)
                    
                    # Hiển thị bảng điểm
                    display.display()
            
            # Delay 100ms để giảm CPU usage
            time.sleep(0.1)
    
    # Xử lý khi nhấn Ctrl+C
    except KeyboardInterrupt:
        # Ghi log thông báo dừng
        log_data("Controller stopped by user")
    
    # Xử lý các lỗi khác
    except Exception as e:
        # Ghi log lỗi
        log_data(f"[ERROR] {e}")
    
    # Dọn dẹp trước khi thoát (lệnh này LUÔN chạy)
    finally:
        # Ghi log dòng kẻ
        log_data("="*80)
        
        # Ghi log thông báo thoát
        log_data("Cleanup GPIO and LoRa...")
        
        # Dọn dẹp GPIO
        GPIO.cleanup()
        
        # Đóng kết nối LoRa
        lora.close()
        
        # Ghi log hoàn tất
        log_data("Cleanup completed")

# ==================== CHẠY CHƯƠNG TRÌNH ====================

if __name__ == "__main__":
    """
    Kiểm tra nếu file này được chạy trực tiếp (không được import)
    """
    # Gọi hàm main để bắt đầu chương trình
    main()
