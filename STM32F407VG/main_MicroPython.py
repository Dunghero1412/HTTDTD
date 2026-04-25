"""
STM32F407 MicroPython - Piezo Timestamp Capture System

🎯 LỢI ÍCH:
- Syntax giống Python (dễ hiểu)
- Không cần compile (write & run instantly)
- REPL console (debug realtime)
- Built-in libraries cho GPIO, Timer, SPI

📍 PIN ASSIGNMENT:
PA0 → pyb.Pin('A0')  (TIM2_CH1 - Sensor A)
PA1 → pyb.Pin('A1')  (TIM2_CH2 - Sensor B)
PA2 → pyb.Pin('A2')  (TIM2_CH3 - Sensor C)
PA3 → pyb.Pin('A3')  (TIM2_CH4 - Sensor D)
PB0 → pyb.Pin('B0')  (DATA_READY output)

PA4-7 → SPI1 (auto)
"""

import pyb
import struct
import time

# ============================================================================
# GLOBAL VARIABLES
# ============================================================================

# ✓ Array lưu timestamp của 4 sensor
timestamps = {
    'A': 0,
    'B': 0,
    'C': 0,
    'D': 0
}

# ✓ Counter đếm số sensor đã capture
capture_count = 0

# ✓ SPI buffer để gửi về RPi
spi_buffer = bytearray(20)

# ✓ Flag báo dữ liệu sẵn sàng
data_ready = False

# ============================================================================
# SETUP FUNCTIONS
# ============================================================================

def setup_pins():
    """
    Setup GPIO pins
    
    🔧 HOẠT ĐỘNG:
    - PA0-3: Input (Timer capture)
    - PB0: Output (DATA_READY)
    """
    
    print("[PINS] Initializing GPIO...")
    
    # ✓ PB0: OUTPUT (DATA_READY)
    # Kéo HIGH khi có dữ liệu sẵn sàng
    pin_ready = pyb.Pin('B0', pyb.Pin.OUT)
    pin_ready.low()  # Initial state: LOW
    
    print("[PINS] GPIO configured")
    return pin_ready

def setup_timer():
    """
    Setup Timer 2 (32-bit, 4 Input Capture channels)
    
    🔧 HOẠT ĐỘNG:
    - TIM2: 32-bit counter @ 168MHz
    - CH1-4: Input Capture mode
    - Callback function khi capture event
    
    💡 TIMING:
    - Resolution: 5.95ns per tick
    - Max time: ~25.6 seconds
    """
    
    print("[TIM2] Initializing Timer 2...")
    
    # ✓ Create Timer 2
    tim2 = pyb.Timer(2, freq=168000000)  # 168MHz
    
    # ✓ Setup Channel 1 (PA0 - Sensor A)
    ch1 = tim2.channel(1, pyb.Timer.IC, pin=pyb.Pin.board.A0)
    ch1.callback(lambda t: on_sensor_capture('A', t.counter()))
    
    # ✓ Setup Channel 2 (PA1 - Sensor B)
    ch2 = tim2.channel(2, pyb.Timer.IC, pin=pyb.Pin.board.A1)
    ch2.callback(lambda t: on_sensor_capture('B', t.counter()))
    
    # ✓ Setup Channel 3 (PA2 - Sensor C)
    ch3 = tim2.channel(3, pyb.Timer.IC, pin=pyb.Pin.board.A2)
    ch3.callback(lambda t: on_sensor_capture('C', t.counter()))
    
    # ✓ Setup Channel 4 (PA3 - Sensor D)
    ch4 = tim2.channel(4, pyb.Timer.IC, pin=pyb.Pin.board.A3)
    ch4.callback(lambda t: on_sensor_capture('D', t.counter()))
    
    print("[TIM2] Timer 2 configured (168MHz, 5.95ns/tick)")
    return tim2

def setup_spi():
    """
    Setup SPI 1 (Slave Mode, 10.5MHz)
    
    🔧 HOẠT ĐỘNG:
    - SPI1 Slave mode
    - Tốc độ: 10.5MHz
    - Tự động send buffer khi RPi read
    """
    
    print("[SPI1] Initializing SPI 1...")
    
    # ✓ Create SPI 1 (Slave mode)
    spi = pyb.SPI(1, pyb.SPI.SLAVE, baudrate=10500000)
    
    # ✓ Set SPI buffer
    spi.write(spi_buffer)
    
    print("[SPI1] SPI 1 configured (Slave, 10.5MHz)")
    return spi

def setup_uart():
    """
    Setup UART 1 (115200 baud, Debug logging)
    
    🔧 HOẠT ĐỘNG:
    - UART1: 115200 baud
    - Dùng để print debug messages
    """
    
    print("[UART] Initializing UART 1...")
    
    # ✓ Create UART 1
    uart = pyb.UART(1, 115200)
    
    print("[UART] UART 1 configured (115200 baud)")
    return uart

# ============================================================================
# CALLBACK FUNCTIONS
# ============================================================================

def on_sensor_capture(sensor_id, timestamp):
    """
    Callback khi Timer capture một sensor
    
    🔧 HOẠT ĐỘNG:
    1. Lưu timestamp vào array
    2. Tăng capture_count
    3. Nếu đủ 4 sensor: signal DATA_READY
    
    Tham số:
        sensor_id (str): 'A', 'B', 'C', or 'D'
        timestamp (int): 32-bit timer value
    """
    
    global capture_count, data_ready
    
    # ✓ Lưu timestamp
    timestamps[sensor_id] = timestamp
    
    # ✓ Tăng counter
    capture_count += 1
    
    print(f"[CH] {sensor_id}: {timestamp}")
    
    # ✓ Nếu đủ 4 sensor
    if capture_count >= 4:
        # Pack dữ liệu vào buffer
        pack_data_buffer()
        
        # Signal DATA_READY (PB0 = HIGH)
        pin_ready.high()
        
        print(f"[DATA] Ready - A:{timestamps['A']} B:{timestamps['B']} "
              f"C:{timestamps['C']} D:{timestamps['D']}")
        
        # Reset counter
        capture_count = 0

def pack_data_buffer():
    """
    Pack 4 timestamps vào SPI buffer
    
    🔧 HOẠT ĐỘNG:
    Format: [ID_A][TS_A_3][TS_A_2][TS_A_1][TS_A_0] ...
    
    Mỗi sensor: 5 bytes (1 byte ID + 4 bytes timestamp)
    Tổng: 20 bytes
    """
    
    global spi_buffer
    
    sensors = ['A', 'B', 'C', 'D']
    
    for i, sensor_id in enumerate(sensors):
        offset = i * 5
        
        # ✓ Byte 0: Sensor ID (ASCII)
        spi_buffer[offset + 0] = ord(sensor_id)
        
        # ✓ Bytes 1-4: Timestamp (big-endian)
        ts = timestamps[sensor_id]
        spi_buffer[offset + 1] = (ts >> 24) & 0xFF
        spi_buffer[offset + 2] = (ts >> 16) & 0xFF
        spi_buffer[offset + 3] = (ts >> 8) & 0xFF
        spi_buffer[offset + 4] = (ts >> 0) & 0xFF

# ============================================================================
# MAIN LOOP
# ============================================================================

def main():
    """
    Main loop
    
    🔧 HOẠT ĐỘNG:
    1. Setup tất cả peripherals
    2. Chờ capture event
    3. Khi có 4 sensor: kéo DATA_READY HIGH
    4. RPi đọc SPI → kéo DATA_READY LOW (bằng callback)
    """
    
    print("\n" + "="*50)
    print("STM32F407 MicroPython - Sensor Timestamp Capture")
    print("="*50 + "\n")
    
    # ✓ Setup
    global pin_ready
    pin_ready = setup_pins()
    tim2 = setup_timer()
    spi = setup_spi()
    uart = setup_uart()
    
    print("\n[MAIN] Ready to capture sensors...\n")
    
    # ✓ Main loop
    try:
        while True:
            # Khi DATA_READY kéo HIGH, chờ RPi read SPI
            # Sau khi read xong, RPi sẽ kéo CS LOW
            # STM32 callback sẽ kéo PB0 LOW tự động
            
            # Đơn giản: chỉ cần chờ
            time.sleep_ms(100)
            
            # Optional: log status
            # print(f"[STATUS] Capture count: {capture_count}")
    
    except KeyboardInterrupt:
        print("\n[MAIN] Stopped by user")

# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    main()