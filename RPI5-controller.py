#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi 5 Controller - Điều khiển hệ thống bắn đạn thật qua LoRa
Author : DHR1412
"""

import RPi.GPIO as GPIO
import time
import sys
from datetime import datetime
from rpi_lora import LoRa
from rpi_lora.board_config import BOARD

# ==================== CẤU HÌNH ====================
# UART Configuration
UART_PORT = "/dev/ttyAMA1"  # UART 1 trên RPi 5
BAUD_RATE = 60000

# GPIO Buttons (BCM mode)
BUTTON_PINS = {
    2: "Node1",
    3: "Node2",
    4: "Node3",
    5: "Node4",
    6: "Node5",
    7: "A",      # Button 6 gửi lệnh "A UP"
    8: "Extra"
}

# LoRa Configuration
LORA_CONFIG = {
    'spi_bus': 0,
    'spi_device': 0,
    'pin_reset': 27,
    'pin_irq': 17,
    'freq': 915,  # MHz
}

# ==================== KHỞI TẠO ====================
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Khởi tạo các button
button_states = {}
for pin in BUTTON_PINS.keys():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    button_states[pin] = False

# Khởi tạo LoRa
lora = LoRa(BOARD.CN1, BOARD.CN1, baud=BAUD_RATE)
lora.set_frequency(LORA_CONFIG['freq'])

# Log file
LOG_FILE = "score.txt"

# ==================== HÀM HỖ TRỢ ====================
def log_data(message):
    """Ghi dữ liệu vào file log và console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + "\n")

def send_command(node_name, command):
    """Gửi lệnh qua LoRa"""
    try:
        msg = f"{node_name} {command}"
        lora.send(msg.encode())
        log_data(f"[TX] Sent: {msg}")
    except Exception as e:
        log_data(f"[ERROR] Failed to send: {e}")

def receive_data():
    """Nhận dữ liệu từ Node"""
    try:
        if lora.is_rx_busy():
            return None
        payload = lora.read()
        if payload:
            data = payload.decode()
            log_data(f"[RX] Received: {data}")
            return data
    except Exception as e:
        log_data(f"[ERROR] Failed to receive: {e}")
    return None

def parse_node_data(data):
    """
    Parse dữ liệu từ Node
    Format: "NODE 1, -26 , 30"
    Return: (node_name, x, y) hoặc (None, None, None)
    """
    try:
        parts = data.split(',')
        node_name = parts[0].strip()
        x = float(parts[1].strip())
        y = float(parts[2].strip())
        return (node_name, x, y)
    except:
        return (None, None, None)

# ==================== HIỂN THỊ DỮ LIỆU ====================
class ScoreDisplay:
    def __init__(self):
        self.scores = {
            "Node1": {"x": None, "y": None},
            "Node2": {"x": None, "y": None},
            "Node3": {"x": None, "y": None},
            "Node4": {"x": None, "y": None},
            "Node5": {"x": None, "y": None},
        }
    
    def update(self, node_name, x, y):
        """Cập nhật dữ liệu điểm"""
        if node_name in self.scores:
            self.scores[node_name]["x"] = x
            self.scores[node_name]["y"] = y
    
    def display(self):
        """Hiển thị dữ liệu dạng cột"""
        print("\n" + "="*60)
        print("SHOOTING RANGE SCORING SYSTEM")
        print("="*60)
        
        # Header
        header = "| " + " | ".join(f"{node:^12}" for node in self.scores.keys()) + " |"
        print(header)
        print("-" * len(header))
        
        # X coordinates
        x_row = "| " + " | ".join(
            f"{str(self.scores[node]['x']):^12}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"X: {x_row}")
        
        # Y coordinates
        y_row = "| " + " | ".join(
            f"{str(self.scores[node]['y']):^12}" 
            for node in self.scores.keys()
        ) + " |"
        print(f"Y: {y_row}")
        print("="*60 + "\n")

display = ScoreDisplay()

# ==================== MAIN LOOP ====================
def button_callback(channel):
    """Callback khi nút được bấm"""
    time.sleep(0.02)  # Debounce
    
    if GPIO.input(channel) == GPIO.LOW:  # Nút được bấm
        node_name = BUTTON_PINS[channel]
        
        # Toggle giữa UP và DOWN
        if button_states[channel] == False:
            send_command(node_name, "UP")
            button_states[channel] = True
        else:
            send_command(node_name, "DOWN")
            button_states[channel] = False

# Thiết lập interrupt cho các button
for pin in BUTTON_PINS.keys():
    GPIO.add_event_detect(pin, GPIO.FALLING, callback=button_callback, bouncetime=50)

def main():
    """Main loop"""
    log_data("="*60)
    log_data("CONTROLLER STARTED - RPi 5")
    log_data("="*60)
    
    try:
        while True:
            # Nhận dữ liệu từ Node
            data = receive_data()
            if data:
                node_name, x, y = parse_node_data(data)
                if node_name:
                    display.update(node_name, x, y)
                    display.display()
            
            time.sleep(0.1)  # Giảm CPU usage
    
    except KeyboardInterrupt:
        log_data("Controller stopped by user")
    except Exception as e:
        log_data(f"[ERROR] {e}")
    finally:
        GPIO.cleanup()
        lora.close()

if __name__ == "__main__":
    main()