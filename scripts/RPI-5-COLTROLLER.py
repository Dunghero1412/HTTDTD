#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi 5 Controller - Điều khiển hệ thống bắn đạn thật qua LoRa
Chương trình này chạy trên Raspberry Pi 5 để:
1. Đọc trạng thái 7 nút bấm (GPIO 2-8)
2. Gửi lệnh điều khiển đến 5 Node qua LoRa module SX1278
3. Nhận dữ liệu tọa độ từ các Node và hiển thị lên màn hình
4. Ghi log dữ liệu vào file score.txt
"""

# ==================== NHẬP THƯ VIỆN ====================
import RPi.GPIO as GPIO                    # Thư viện điều khiển GPIO trên Raspberry Pi
import time                                # Thư viện làm việc với thời gian
import sys                                 # Thư viện hệ thống
from datetime import datetime              # Thư viện xử lý ngày giờ
from rpi_lora import LoRa                  # Thư viện LoRa để giao tiếp không dây
from rpi_lora.board_config import BOARD    # Cấu hình board cho LoRa module

# ==================== CẤU HÌNH CHUNG ====================

# --- Cấu hình UART cho LoRa ---
UART_PORT = "/dev/ttyAMA1"                 # UART 1 trên RPi 5 nối với LoRa
BAUD_RATE = 60000                          # Tốc độ baud 60000 bps

# --- Cấu hình GPIO cho các nút bấm ---
# Các nút được nối vào GPIO 2-8 trên RPi 5
# Mỗi nút là loại Normally Open (NO) - khi bấm sẽ nối tới GND
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
# Tần số LoRa (915 MHz là tần số công nghiệp phổ dụng)
LORA_FREQUENCY = 915

# --- File log ---
# Tất cả dữ liệu sẽ được ghi vào file này
LOG_FILE = "score.txt"

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
    # False = chưa gửi lệnh "UP"
    # True = đã gửi lệnh "UP", lần bấm tiếp theo sẽ gửi "DOWN"
    button_states[pin] = False

# ==================== KHỞI TẠO LoRa ====================

# Khởi tạo LoRa module
# BOARD.CN1, BOARD.CN1 là cấu hình cho RPi 5
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
        "A UP" - kích hoạt lệnh A
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
        # is_rx_busy() trả về True nếu đang nhận, False nếu không
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
    
    Hoạt động:
    1. Tách dữ liệu bằng dấu phẩy
    2. Lấy tên Node
    3. Chuyển đổi x và y thành số (float)
    4. Trả về kết quả
    """
    try:
        # Tách dữ liệu bằng dấu phẩy: "NODE 1, -26 , 30"
        # -> ["NODE 1", " -26 ", " 30"]
        parts = data.split(',')
        
        # Lấy phần tên Node và loại bỏ khoảng trắng
        node_name = parts[0].strip()  # "NODE 1"
        
        # Chuyển đổi phần x thành số float
        x = float(parts[1].strip())   # -26.0
        
        # Chuyển đổi phần y thành số float
        y = float(parts[2].strip())   # 30.0
        
        # Trả về tuple (node_name, x, y)
        return (node_name, x, y)
    
    except:
        # Nếu lỗi khi phân tích, trả về None
        return (None, None, None)

# ==================== LỚP HIỂN THỊ DỮ LIỆU ====================

class ScoreDisplay:
    """
    Lớp để quản lý và hiển thị điểm số từ các Node
    
    Chức năng:
    - Lưu trữ dữ liệu tọa độ của mỗi Node
    - Hiển thị dữ liệu dạng bảng (cột)
    - Cập nhật dữ liệu khi nhận từ Node
    """
    
    def __init__(self):
        """
        Khởi tạo đối tượng ScoreDisplay
        
        Tạo dict để lưu điểm số của 5 Node
        Mỗi Node có 2 giá trị: x và y
        """
        # Dict lưu dữ liệu: {Node_name: {x: value, y: value}}
        self.scores = {
            "NODE1": {"x": None, "y": None},   # Node 1
            "NODE2": {"x": None, "y": None},   # Node 2
            "NODE3": {"x": None, "y": None},   # Node 3
            "NODE4": {"x": None, "y": None},   # Node 4
            "NODE5": {"x": None, "y": None},   # Node 5
        }
    
    def update(self, node_name, x, y):
        """
        Cập nhật dữ liệu tọa độ của một Node
        
        Tham số:
            node_name (str): Tên Node (ví dụ: "NODE 1")
            x (float): Tọa độ X
            y (float): Tọa độ Y
        """
        # Chuẩn hóa tên Node: "NODE 1" -> "NODE1"
        node_key = node_name.replace(" ", "").upper()
        
        # Cập nhật dữ liệu nếu Node tồn tại
        if node_key in self.scores:
            self.scores[node_key]["x"] = x
            self.scores[node_key]["y"] = y
    
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
        ============================================================
        """
        # In dòng kẻ trên
        print("\n" + "="*60)
        
        # In tiêu đề
        print("SHOOTING RANGE SCORING SYSTEM")
        
        # In dòng kẻ dưới tiêu đề
        print("="*60)
        
        # --- In header (tên các Node) ---
        # Tạo header: "|     NODE1     |     NODE2     | ..."
        header = "| " + " | ".join(
            f"{node:^12}" for node in self.scores.keys()
        ) + " |"
        print(header)
        
        # In dòng kẻ dưới header
        print("-" * len(header))
        
        # --- In tọa độ X ---
        # Tạo dòng X: "|     -26      |      15      | ..."
        x_row = "| " + " | ".join(
            f"{str(self.scores[node]['x']):^12}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"X: {x_row}")
        
        # --- In tọa độ Y ---
        # Tạo dòng Y: "|      30      |      -20     | ..."
        y_row = "| " + " | ".join(
            f"{str(self.scores[node]['y']):^12}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"Y: {y_row}")
        
        # In dòng kẻ cuối
        print("="*60 + "\n")

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
    # Debounce: chờ 20ms để đảm bảo đó là bấm thực (không phải rung)
    time.sleep(0.02)
    
    # Kiểm tra lại trạng thái pin (phải ở mức LOW khi bấm)
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
# Khi GPIO chuyển từ HIGH -> LOW (nút được bấm), gọi button_callback
for pin in BUTTON_PINS.keys():
    # add_event_detect():
    # - pin: GPIO pin cần giám sát
    # - GPIO.FALLING: giám sát lúc pin từ HIGH -> LOW
    # - callback: hàm sẽ gọi khi event xảy ra
    # - bouncetime: độ trễ debounce (50ms)
    GPIO.add_event_detect(pin, GPIO.FALLING, callback=button_callback, bouncetime=50)

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """
    Vòng lặp chính của Controller
    
    Hoạt động:
    1. Ghi log khi chương trình bắt đầu
    2. Liên tục nhận dữ liệu từ các Node
    3. Phân tích dữ liệu nhận được
    4. Cập nhật và hiển thị lên màn hình
    5. Xử lý lỗi nếu có
    6. Dọn dẹp trước khi thoát
    """
    # Ghi log dòng kẻ (dấu phân cách)
    log_data("="*60)
    
    # Ghi log thông báo bắt đầu
    log_data("CONTROLLER STARTED - RPi 5")
    
    # Ghi log dòng kẻ (dấu phân cách)
    log_data("="*60)
    
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
                    # Cập nhật dữ liệu vào display
                    display.update(node_name, x, y)
                    
                    # Hiển thị bảng điểm
                    display.display()
            
            # Delay 100ms để giảm CPU usage (tránh chiếm tài nguyên)
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
        log_data("="*60)
        
        # Ghi log thông báo thoát
        log_data("Cleanup GPIO and LoRa...")
        
        # Dọn dẹp GPIO (đặt tất cả pin về trạng thái ban đầu)
        GPIO.cleanup()
        
        # Đóng kết nối LoRa
        lora.close()
        
        # Ghi log hoàn tất
        log_data("Cleanup completed")

# ==================== CHẠY CHƯƠNG TRÌNH ====================

if __name__ == "__main__":
    """
    Kiểm tra nếu file này được chạy trực tiếp (không được import)
    Nếu vậy, gọi hàm main()
    """
    # Gọi hàm main để bắt đầu chương trình
    main()