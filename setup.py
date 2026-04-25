#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTDTD Setup Script - Hệ Thống Tính Điểm Tự Động Dùng Cho Bắn Súng
Với hỗ trợ auto-flash STM32F407 qua ST-Link

🎯 CHỨC NĂNG:
1. Cài đặt Controller (RPi 5)
2. Cài đặt Node (RPi Nano 2W) - loại A, B, C, D
3. [NEW] Auto-flash STM32F407 firmware

📝 CẤU HÌNH THƯ MỤC:
HTTDTD/
├── scripts/
│   ├── CONTROLLER/CONTROLLER.py
│   ├── NODE-A/NODE.py
│   ├── NODE-B/NODE.py
│   ├── NODE-C/NODE.py
│   ├── NODE-D/NODE.py
│   ├── STM32/
│   │   ├── stm32_firmware.elf (compiled binary)
│   │   ├── stm32_firmware.hex (hex file)
│   │   └── Makefile (build script)
│   └── html/
│       └── score_gui.html
└── setup.py (file này)

🔧 CÁCH SỬ DỤNG:
# Cài đặt Controller (không flash STM32)
sudo python3 setup.py install controller

# Cài đặt Node 1A (không flash STM32)
sudo python3 setup.py install node 1a

# Cài đặt Node 1A + Flash STM32 (auto)
sudo python3 setup.py install node 1a --flash-stm32

# Cài đặt Node 2B + Flash STM32
sudo python3 setup.py install node 2b --flash-stm32

# Gỡ cài đặt
sudo python3 setup.py uninstall controller
sudo python3 setup.py uninstall node 1a

📋 PREREQUISITE:
# Cài đặt build tools
sudo apt-get update
sudo apt-get install -y \
    gcc-arm-none-eabi \
    stlink-tools \
    libusb-1.0-0-dev

# Kiểm tra
arm-none-eabi-gcc --version
st-flash --version

⏱️ TIMING:
- Cài đặt Node (không flash): ~5-10 giây
- Flash STM32: ~30-60 giây (tùy kích thước firmware)
- Tổng: ~40-70 giây (với --flash-stm32)
"""

import os
import sys
import shutil
import subprocess
import argparse
import json
from pathlib import Path
from datetime import datetime

# ============================================================================
# CẤU HÌNH CHUNG
# ============================================================================

# ✓ Đường dẫn cài đặt
INSTALL_PATH = Path("/opt")
HTML_PATH = INSTALL_PATH / "html"
LOG_FILE = INSTALL_PATH / "setup.log"

# ✓ Tên user chạy services
SERVICE_USER = "pi"

# ✓ Các nhóm Node hợp lệ
VALID_NODE_GROUPS = ["A", "B", "C", "D"]

# ✓ Tên file trong các thư mục
CONTROLLER_SCRIPT = "CONTROLLER.py"
NODE_SCRIPT = "NODE.py"
HTML_FILE = "score_gui.html"

# ✓ CẤU HÌNH STM32 FLASH
STM32_FIRMWARE_DIR = Path(__file__).parent / "scripts" / "STM32"
STM32_FIRMWARE_ELF = STM32_FIRMWARE_DIR / "stm32_firmware.elf"
STM32_FIRMWARE_HEX = STM32_FIRMWARE_DIR / "stm32_firmware.hex"
STM32_MAKEFILE = STM32_FIRMWARE_DIR / "Makefile"

# ============================================================================
# HÀM HỖ TRỢ - LOGGING
# ============================================================================

def log_message(message, level="INFO"):
    """
    Ghi log thông điệp
    
    🔧 HOẠT ĐỘNG:
    1. Lấy timestamp hiện tại
    2. Tạo message với prefix (INFO, WARNING, ERROR, SUCCESS)
    3. In lên console
    4. Ghi vào file log
    
    Tham số:
        message (str): Thông điệp cần ghi
        level (str): Mức độ (INFO, WARNING, ERROR, SUCCESS)
    """
    
    # ✓ Lấy timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ✓ Tạo prefix dựa trên level
    prefix_map = {
        "INFO": "ℹ️  INFO   ",
        "WARNING": "⚠️  WARNING",
        "ERROR": "❌ ERROR  ",
        "SUCCESS": "✅ SUCCESS"
    }
    prefix = prefix_map.get(level, "INFO")
    
    # ✓ Tạo log message
    log_text = f"[{timestamp}] {prefix} | {message}"
    
    # ✓ In ra console
    print(log_text)
    
    # ✓ Ghi vào file log
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_text + "\n")
    except:
        pass

def run_command(cmd, description="", check=True):
    """
    Chạy lệnh shell
    
    🔧 HOẠT ĐỘNG:
    1. In log mô tả
    2. Chạy lệnh
    3. Nếu lỗi: in error message
    4. Return True/False
    
    Tham số:
        cmd (str): Lệnh cần chạy
        description (str): Mô tả
        check (bool): Có throw exception nếu lỗi không?
    
    Trả về:
        bool: True nếu thành công, False nếu lỗi
    """
    
    try:
        if description:
            log_message(description)
        
        # ✓ Chạy lệnh
        result = subprocess.run(
            cmd, 
            shell=True, 
            check=check,
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        # ✓ Nếu stdout có output
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line:
                    print(f"  {line}")
        
        return True
    
    except subprocess.CalledProcessError as e:
        log_message(f"Failed to execute: {cmd}", "ERROR")
        if e.stderr:
            log_message(f"Error: {e.stderr}", "ERROR")
        return False
    except Exception as e:
        log_message(f"Exception: {e}", "ERROR")
        return False

def check_root():
    """
    Kiểm tra xem script có chạy với quyền root không
    
    Trả về:
        bool: True nếu là root, False nếu không
    """
    
    if os.geteuid() != 0:
        log_message("Script phải chạy với quyền root (sudo)", "ERROR")
        log_message("Vui lòng chạy: sudo python3 setup.py ...", "ERROR")
        return False
    return True

def check_file_exists(file_path, description=""):
    """
    Kiểm tra xem file có tồn tại không
    
    Tham số:
        file_path (Path): Đường dẫn file
        description (str): Mô tả file
    
    Trả về:
        bool: True nếu tồn tại, False nếu không
    """
    
    if not file_path.exists():
        log_message(f"File không tồn tại: {description} ({file_path})", "ERROR")
        return False
    return True

def create_directory(path):
    """
    Tạo thư mục nếu chưa tồn tại
    
    Tham số:
        path (Path): Đường dẫn thư mục
    
    Trả về:
        bool: True nếu thành công
    """
    
    try:
        # ✓ Tạo thư mục (với parents=True để tạo parent dirs)
        path.mkdir(parents=True, exist_ok=True)
        
        # ✓ Đặt owner là user "pi" (UID 1000)
        os.chown(path, 1000, 1000)
        
        log_message(f"Thư mục được tạo: {path}", "SUCCESS")
        return True
    
    except Exception as e:
        log_message(f"Lỗi khi tạo thư mục: {e}", "ERROR")
        return False

def copy_file(src, dst, description=""):
    """
    Copy file từ src đến dst
    
    Tham số:
        src (Path): File nguồn
        dst (Path): File đích
        description (str): Mô tả
    
    Trả về:
        bool: True nếu thành công
    """
    
    try:
        if description:
            log_message(description)
        
        # ✓ Copy file
        shutil.copy2(src, dst)
        
        # ✓ Đặt quyền executable
        os.chmod(dst, 0o755)
        
        # ✓ Đặt owner
        os.chown(dst, 1000, 1000)
        
        log_message(f"Copied: {src} → {dst}", "SUCCESS")
        return True
    
    except Exception as e:
        log_message(f"Lỗi khi copy file: {e}", "ERROR")
        return False

def parse_node_name(node_name_input):
    """
    Parse tên Node từ input
    
    Tham số:
        node_name_input (str): Input từ command line
                              Ví dụ: "1a", "2b", "NODE1A"
    
    Trả về:
        tuple: (node_number, node_group, node_full_name)
               Ví dụ: (1, "A", "NODE1A")
               hoặc (None, None, None) nếu lỗi
    """
    
    # ✓ Chuyển thành uppercase
    node_input = node_name_input.upper()
    
    # ✓ Chuẩn hóa: "NODE1A" → "1A"
    if node_input.startswith("NODE"):
        node_input = node_input[4:]
    
    try:
        # ✓ Parse số và nhóm
        node_number = None
        node_group = None
        
        # ✓ Tìm vị trí chuyển từ số sang chữ
        for i, char in enumerate(node_input):
            if char.isalpha():
                node_number = int(node_input[:i])
                node_group = node_input[i:].upper()
                break
        
        # ✓ Kiểm tra hợp lệ
        if node_number is None or node_group is None:
            log_message(f"Tên Node không hợp lệ: {node_name_input}", "ERROR")
            log_message("Ví dụ hợp lệ: 1a, 2b, 3c, 4d, NODE1A, NODE2B", "ERROR")
            return None, None, None
        
        # ✓ Kiểm tra nhóm
        if node_group not in VALID_NODE_GROUPS:
            log_message(f"Nhóm Node không hợp lệ: {node_group}", "ERROR")
            log_message(f"Nhóm hợp lệ: {', '.join(VALID_NODE_GROUPS)}", "ERROR")
            return None, None, None
        
        # ✓ Kiểm tra số
        if node_number < 1 or node_number > 5:
            log_message(f"Số Node không hợp lệ: {node_number}", "ERROR")
            log_message("Số Node phải từ 1 đến 5", "ERROR")
            return None, None, None
        
        # ✓ Tên đầy đủ
        node_full_name = f"NODE{node_number}{node_group}"
        
        return node_number, node_group, node_full_name
    
    except ValueError:
        log_message(f"Tên Node không hợp lệ: {node_name_input}", "ERROR")
        return None, None, None

# ============================================================================
# STM32 BUILD & FLASH FUNCTIONS
# ============================================================================

def check_build_tools():
    """
    Kiểm tra xem các build tools có được cài đặt không
    
    🔧 CẦN CÓ:
    - arm-none-eabi-gcc (compiler)
    - st-flash (programmer)
    - libusb-1.0 (library)
    
    Trả về:
        bool: True nếu tất cả tools có, False nếu thiếu
    """
    
    log_message("Kiểm tra build tools...", "INFO")
    
    # ✓ Kiểm tra arm-none-eabi-gcc
    result = subprocess.run(
        "arm-none-eabi-gcc --version",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    if result.returncode != 0:
        log_message("Cần cài đặt: arm-none-eabi-gcc", "ERROR")
        log_message("Chạy: sudo apt-get install gcc-arm-none-eabi", "ERROR")
        return False
    
    # ✓ Kiểm tra st-flash
    result = subprocess.run(
        "st-flash --version",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    if result.returncode != 0:
        log_message("Cần cài đặt: stlink-tools", "ERROR")
        log_message("Chạy: sudo apt-get install stlink-tools", "ERROR")
        return False
    
    log_message("Build tools OK ✓", "SUCCESS")
    return True

def build_stm32_firmware():
    """
    Biên dịch STM32 firmware từ source
    
    🔧 HOẠT ĐỘNG:
    1. Kiểm tra Makefile tồn tại
    2. Chạy 'make clean' để xóa build cũ
    3. Chạy 'make' để biên dịch
    4. Kiểm tra output file (.elf) tồn tại
    5. Tạo hex file cho flashing
    
    Trả về:
        bool: True nếu biên dịch thành công
    """
    
    log_message("Biên dịch STM32 firmware...", "INFO")
    
    # ✓ Kiểm tra Makefile
    if not check_file_exists(STM32_MAKEFILE, "Makefile cho STM32"):
        return False
    
    # ✓ Change directory đến STM32 folder
    original_dir = os.getcwd()
    
    try:
        # ✓ CD đến thư mục STM32
        os.chdir(STM32_FIRMWARE_DIR)
        
        # ✓ Clean build cũ
        log_message("  Cleaning old build...")
        if not run_command("make clean", check=False):
            log_message("Warning: make clean failed, continuing...", "WARNING")
        
        # ✓ Build firmware
        log_message("  Building firmware (this may take 1-2 minutes)...")
        if not run_command("make", "  Compiling..."):
            log_message("Lỗi khi biên dịch STM32 firmware", "ERROR")
            return False
        
        # ✓ Kiểm tra output file
        if not check_file_exists(STM32_FIRMWARE_ELF, "STM32 firmware ELF"):
            return False
        
        # ✓ Tạo hex file từ elf
        hex_cmd = f"arm-none-eabi-objcopy -O ihex {STM32_FIRMWARE_ELF} {STM32_FIRMWARE_HEX}"
        if not run_command(hex_cmd, "  Creating hex file..."):
            log_message("Lỗi khi tạo hex file", "ERROR")
            return False
        
        log_message("STM32 firmware build thành công ✓", "SUCCESS")
        return True
    
    finally:
        # ✓ CD lại thư mục gốc
        os.chdir(original_dir)

def flash_stm32_firmware():
    """
    Flash STM32 firmware qua ST-Link
    
    🔧 HOẠT ĐỘNG:
    1. Kiểm tra ST-Link kết nối (probe)
    2. Kiểm tra firmware file tồn tại
    3. Flash firmware qua st-flash
    4. Verify flash (tùy chọn)
    5. In success message
    
    ⚠️ REQUIRE:
    - ST-Link V2 kết nối qua USB
    - STM32F407VG Discovery board kết nối
    - Firmware file (hex hoặc elf)
    
    Trả về:
        bool: True nếu flash thành công
    """
    
    log_message("Flash STM32 firmware qua ST-Link...", "INFO")
    
    # ✓ Kiểm tra ST-Link probe
    log_message("  Checking ST-Link connection...")
    result = subprocess.run(
        "st-flash --probe",
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    if result.returncode != 0:
        log_message("Lỗi: Không thể kết nối ST-Link", "ERROR")
        log_message("  - Kiểm tra ST-Link kết nối USB", "ERROR")
        log_message("  - Kiểm tra STM32F407 board kết nối", "ERROR")
        log_message("  - Kiểm tra cáp SWD (SWDIO, SWCLK, GND)", "ERROR")
        return False
    
    # ✓ In ST-Link info
    for line in result.stdout.strip().split('\n'):
        if line:
            log_message(f"    {line}", "INFO")
    
    # ✓ Kiểm tra firmware file
    if not check_file_exists(STM32_FIRMWARE_ELF, "STM32 firmware ELF"):
        return False
    
    # ✓ Flash firmware
    log_message("  Flashing firmware (this may take 30-60 seconds)...", "INFO")
    
    # ✓ Chọn file để flash
    # st-flash hỗ trợ cả .elf và .hex
    firmware_file = STM32_FIRMWARE_ELF
    if STM32_FIRMWARE_HEX.exists():
        firmware_file = STM32_FIRMWARE_HEX
    
    # ✓ Flash command
    flash_cmd = f"st-flash write {firmware_file} 0x08000000"
    if not run_command(flash_cmd):
        log_message("Lỗi khi flash STM32", "ERROR")
        return False
    
    log_message("STM32 flash thành công ✓", "SUCCESS")
    return True

def flash_stm32_workflow():
    """
    Workflow đầy đủ để build + flash STM32
    
    🔧 HOẠT ĐỘNG:
    1. Kiểm tra build tools có sẵn
    2. Build firmware từ source
    3. Flash firmware qua ST-Link
    4. In summary
    
    Trả về:
        bool: True nếu toàn bộ thành công
    """
    
    log_message("="*60, "INFO")
    log_message("STM32 AUTO-FLASH WORKFLOW", "INFO")
    log_message("="*60, "INFO")
    
    # ✓ Check build tools
    if not check_build_tools():
        log_message("\n⚠️  Cài đặt missing tools:", "WARNING")
        log_message("  sudo apt-get install -y gcc-arm-none-eabi stlink-tools", "WARNING")
        return False
    
    # ✓ Build firmware
    log_message("\n[STEP 1/2] Building STM32 firmware...", "INFO")
    if not build_stm32_firmware():
        return False
    
    # ✓ Flash firmware
    log_message("\n[STEP 2/2] Flashing STM32 firmware...", "INFO")
    log_message("⚠️  ENSURE:", "WARNING")
    log_message("  1. ST-Link V2 kết nối qua USB", "WARNING")
    log_message("  2. STM32F407 Discovery board kết nối", "WARNING")
    log_message("  3. Cáp SWD đúng (SWDIO, SWCLK, GND)", "WARNING")
    
    # ✓ Chờ người dùng confirm
    input("\nNhấn ENTER khi sẵn sàng flash (Ctrl+C để hủy)...")
    
    if not flash_stm32_firmware():
        return False
    
    # ✓ Success
    log_message("\n" + "="*60, "SUCCESS")
    log_message("STM32 AUTO-FLASH THÀNH CÔNG!", "SUCCESS")
    log_message("="*60, "SUCCESS")
    return True

# ============================================================================
# SETUP FUNCTIONS
# ============================================================================

def setup_controller():
    """
    Cài đặt Controller (RPi 5)
    """
    
    log_message("="*80, "INFO")
    log_message("SETUP CONTROLLER - RPi 5", "INFO")
    log_message("="*80, "INFO")
    
    # ✓ Kiểm tra quyền root
    if not check_root():
        return False
    
    # ✓ Kiểm tra file nguồn
    current_dir = Path(__file__).parent
    controller_src = current_dir / "scripts" / "CONTROLLER" / CONTROLLER_SCRIPT
    html_src = current_dir / "html" / HTML_FILE
    
    if not check_file_exists(controller_src, "CONTROLLER.py"):
        return False
    if not check_file_exists(html_src, "HTML file"):
        return False
    
    # ✓ Tạo thư mục cài đặt
    if not create_directory(INSTALL_PATH):
        return False
    if not create_directory(HTML_PATH):
        return False
    
    # ✓ Copy file
    controller_dst = INSTALL_PATH / CONTROLLER_SCRIPT
    if not copy_file(controller_src, controller_dst, "Copy CONTROLLER.py"):
        return False
    
    html_dst = HTML_PATH / HTML_FILE
    if not copy_file(html_src, html_dst, "Copy HTML file"):
        return False
    
    # ✓ Tạo systemd service
    service_content = f"""[Unit]
Description=RPi 5 Shooting Range Controller
After=network.target

[Service]
Type=simple
User={SERVICE_USER}
WorkingDirectory={INSTALL_PATH}
ExecStart=/usr/bin/python3 {INSTALL_PATH / CONTROLLER_SCRIPT}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    service_path = Path("/etc/systemd/system/rpi5-controller.service")
    try:
        log_message("Tạo service file: rpi5-controller.service")
        with open(service_path, 'w') as f:
            f.write(service_content)
        os.chmod(service_path, 0o644)
        log_message("Service file được tạo", "SUCCESS")
    except Exception as e:
        log_message(f"Lỗi khi tạo service file: {e}", "ERROR")
        return False
    
    # ✓ Reload systemd
    if not run_command("systemctl daemon-reload", "Reload systemd daemon"):
        return False
    
    # ✓ Enable service
    if not run_command("systemctl enable rpi5-controller.service", 
                       "Enable service (chạy lúc boot)"):
        return False
    
    # ✓ Khởi động service
    if not run_command("systemctl start rpi5-controller.service", 
                       "Khởi động service"):
        return False
    
    # ✓ Kiểm tra status
    run_command("systemctl status rpi5-controller.service --no-pager")
    
    # ✓ Success
    log_message("="*80, "SUCCESS")
    log_message("CONTROLLER ĐÃ ĐƯỢC CÀI ĐẶT THÀNH CÔNG!", "SUCCESS")
    log_message("="*80, "SUCCESS")
    log_message(f"📍 Controller script: {controller_dst}", "INFO")
    log_message(f"📍 HTML file: {html_dst}", "INFO")
    log_message("📍 Service: rpi5-controller.service", "INFO")
    
    return True

def setup_node(node_name_input, flash_stm32=False):
    """
    Cài đặt Node (RPi Nano 2W)
    
    Tham số:
        node_name_input (str): Tên Node (VD: "1a", "2b")
        flash_stm32 (bool): Có flash STM32 không?
    """
    
    # ✓ Parse tên Node
    node_number, node_group, node_full_name = parse_node_name(node_name_input)
    
    if node_full_name is None:
        return False
    
    log_message("="*80, "INFO")
    log_message(f"SETUP NODE - {node_full_name}", "INFO")
    log_message("="*80, "INFO")
    
    # ✓ Kiểm tra quyền root
    if not check_root():
        return False
    
    # ✓ Kiểm tra file nguồn
    current_dir = Path(__file__).parent
    node_src = current_dir / "scripts" / f"NODE-{node_group}" / NODE_SCRIPT
    
    if not check_file_exists(node_src, f"NODE.py (nhóm {node_group})"):
        return False
    
    # ✓ Tạo thư mục cài đặt
    if not create_directory(INSTALL_PATH):
        return False
    
    # ✓ Copy file và sửa NODE_NAME
    node_dst = INSTALL_PATH / f"NODE_{node_full_name}.py"
    
    try:
        log_message(f"Copy NODE.py từ NODE-{node_group}/ → {node_dst}")
        
        # ✓ Đọc file
        with open(node_src, 'r') as f:
            content = f.read()
        
        # ✓ Sửa NODE_NAME
        old_pattern = 'NODE_NAME = "NODE1A"'
        new_pattern = f'NODE_NAME = "{node_full_name}"'
        
        if old_pattern not in content:
            log_message(f"Không tìm thấy '{old_pattern}' trong file", "WARNING")
            log_message("Sẽ copy file nguyên bản mà không sửa NODE_NAME", "WARNING")
        else:
            content = content.replace(old_pattern, new_pattern)
            log_message(f"Sửa NODE_NAME → {node_full_name}", "SUCCESS")
        
        # ✓ Ghi file
        with open(node_dst, 'w') as f:
            f.write(content)
        
        # ✓ Set quyền
        os.chmod(node_dst, 0o755)
        os.chown(node_dst, 1000, 1000)
        
        log_message(f"File được tạo: {node_dst}", "SUCCESS")
    
    except Exception as e:
        log_message(f"Lỗi khi copy file: {e}", "ERROR")
        return False
    
    # ✓ Tạo systemd service
    service_name = f"rpi-nano-{node_full_name.lower()}.service"
    service_content = f"""[Unit]
Description=RPi Nano 2W Shooting Range {node_full_name}
After=network.target

[Service]
Type=simple
User={SERVICE_USER}
WorkingDirectory={INSTALL_PATH}
ExecStart=/usr/bin/python3 {node_dst}
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    service_path = Path("/etc/systemd/system") / service_name
    try:
        log_message(f"Tạo service file: {service_name}")
        with open(service_path, 'w') as f:
            f.write(service_content)
        os.chmod(service_path, 0o644)
        log_message("Service file được tạo", "SUCCESS")
    except Exception as e:
        log_message(f"Lỗi khi tạo service file: {e}", "ERROR")
        return False
    
    # ✓ Reload systemd
    if not run_command("systemctl daemon-reload", "Reload systemd daemon"):
        return False
    
    # ✓ Enable service
    if not run_command(f"systemctl enable {service_name}", 
                       f"Enable service (chạy lúc boot)"):
        return False
    
    # ✓ Khởi động service
    if not run_command(f"systemctl start {service_name}", 
                       "Khởi động service"):
        return False
    
    # ✓ Kiểm tra status
    run_command(f"systemctl status {service_name} --no-pager")
    
    # === FLASH STM32 (nếu có --flash-stm32) ===
    if flash_stm32:
        log_message("\n" + "="*80, "INFO")
        
        # ✓ Flash STM32
        if not flash_stm32_workflow():
            log_message("\n⚠️  WARNING: STM32 flash failed, nhưng Node setup thành công", "WARNING")
            log_message("Bạn có thể flash STM32 sau bằng lệnh:", "WARNING")
            log_message("  sudo python3 setup.py install node 1a --flash-stm32", "WARNING")
        else:
            log_message("\n✓ STM32 flash thành công!", "SUCCESS")
    
    # ✓ Success
    log_message("="*80, "SUCCESS")
    log_message(f"NODE {node_full_name} ĐÃ ĐƯỢC CÀI ĐẶT THÀNH CÔNG!", "SUCCESS")
    log_message("="*80, "SUCCESS")
    log_message(f"📍 Node script: {node_dst}", "INFO")
    log_message(f"📍 Service: {service_name}", "INFO")
    log_message("", "INFO")
    log_message("Lệnh hữu ích:", "INFO")
    log_message(f"  - Xem log:     journalctl -u {service_name} -f", "INFO")
    log_message(f"  - Dừng:        sudo systemctl stop {service_name}", "INFO")
    log_message(f"  - Khởi động lại: sudo systemctl restart {service_name}", "INFO")
    
    return True

def uninstall_controller():
    """
    Gỡ cài đặt Controller
    """
    
    log_message("="*80, "WARNING")
    log_message("UNINSTALL CONTROLLER", "WARNING")
    log_message("="*80, "WARNING")
    
    if not check_root():
        return False
    
    # ✓ Dừng service
    run_command("systemctl stop rpi5-controller.service", "Dừng service")
    run_command("systemctl disable rpi5-controller.service", "Disable service")
    
    # ✓ Xóa service file
    service_path = Path("/etc/systemd/system/rpi5-controller.service")
    try:
        service_path.unlink()
        log_message(f"Xóa: {service_path}", "SUCCESS")
    except:
        pass
    
    # ✓ Reload systemd
    run_command("systemctl daemon-reload", "Reload systemd daemon")
    
    # ✓ Xóa file
    controller_path = INSTALL_PATH / CONTROLLER_SCRIPT
    try:
        controller_path.unlink()
        log_message(f"Xóa: {controller_path}", "SUCCESS")
    except:
        log_message(f"Không thể xóa: {controller_path}", "WARNING")
    
    log_message("Controller đã được gỡ cài đặt", "SUCCESS")
    return True

def uninstall_node(node_name_input):
    """
    Gỡ cài đặt Node
    """
    
    # ✓ Parse tên Node
    node_number, node_group, node_full_name = parse_node_name(node_name_input)
    
    if node_full_name is None:
        return False
    
    log_message("="*80, "WARNING")
    log_message(f"UNINSTALL NODE - {node_full_name}", "WARNING")
    log_message("="*80, "WARNING")
    
    if not check_root():
        return False
    
    service_name = f"rpi-nano-{node_full_name.lower()}.service"
    
    # ✓ Dừng service
    run_command(f"systemctl stop {service_name}", "Dừng service")
    run_command(f"systemctl disable {service_name}", "Disable service")
    
    # ✓ Xóa service file
    service_path = Path("/etc/systemd/system") / service_name
    try:
        service_path.unlink()
        log_message(f"Xóa: {service_path}", "SUCCESS")
    except:
        pass
    
    # ✓ Reload systemd
    run_command("systemctl daemon-reload", "Reload systemd daemon")
    
    # ✓ Xóa node file
    node_path = INSTALL_PATH / f"NODE_{node_full_name}.py"
    try:
        node_path.unlink()
        log_message(f"Xóa: {node_path}", "SUCCESS")
    except:
        log_message(f"Không thể xóa: {node_path}", "WARNING")
    
    log_message(f"Node {node_full_name} đã được gỡ cài đặt", "SUCCESS")
    return True

# ============================================================================
# MAIN
# ============================================================================

def main():
    """
    Hàm chính - Xử lý arguments
    """
    
    # ✓ Parser
    parser = argparse.ArgumentParser(
        description="HTTDTD Setup - Hệ Thống Tính Điểm Tự Động Dùng Cho Bắn Súng",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Cấu trúc thư mục:
  HTTDTD/
  ├── scripts/
  │   ├── CONTROLLER/CONTROLLER.py
  │   ├── NODE-A/NODE.py
  │   ├── NODE-B/NODE.py
  │   ├── NODE-C/NODE.py
  │   ├── NODE-D/NODE.py
  │   ├── STM32/
  │   │   ├── Makefile
  │   │   ├── src/
  │   │   └── ...
  │   └── html/score_gui.html
  └── setup.py

Ví dụ sử dụng:
  # Cài đặt Controller (không flash STM32)
  sudo python3 setup.py install controller
  
  # Cài đặt Node 1A (không flash STM32)
  sudo python3 setup.py install node 1a
  
  # Cài đặt Node 1A + Auto-flash STM32 ⭐
  sudo python3 setup.py install node 1a --flash-stm32
  
  # Cài đặt Node 2B + Auto-flash STM32
  sudo python3 setup.py install node 2b --flash-stm32
  
  # Gỡ cài đặt
  sudo python3 setup.py uninstall controller
  sudo python3 setup.py uninstall node 1a

Yêu cầu (cho --flash-stm32):
  sudo apt-get install -y gcc-arm-none-eabi stlink-tools libusb-1.0-0-dev
        """
    )
    
    # ✓ Arguments
    parser.add_argument(
        'action',
        choices=['install', 'uninstall'],
        help='Hành động: install hoặc uninstall'
    )
    
    parser.add_argument(
        'target',
        choices=['controller', 'node'],
        help='Đối tượng: controller hoặc node'
    )
    
    parser.add_argument(
        'node_name',
        nargs='?',
        default=None,
        help='Tên Node khi cài đặt node (VD: 1a, 2b, 3c, 4d)'
    )
    
    # ✓ Flag --flash-stm32 (chỉ cho install node)
    parser.add_argument(
        '--flash-stm32',
        action='store_true',
        help='Auto-compile và flash STM32F407 firmware (chỉ cho "install node")'
    )
    
    # ✓ Parse arguments
    args = parser.parse_args()
    
    # ✓ Xử lý arguments
    if args.target == 'controller':
        # ✓ Nếu target là controller, ignorenode_name
        
        if args.action == 'install':
            success = setup_controller()
        else:  # uninstall
            success = uninstall_controller()
    
    elif args.target == 'node':
        # ✓ Nếu target là node, cần node_name
        
        if args.node_name is None:
            log_message("Lỗi: Cần chỉ định tên Node", "ERROR")
            log_message("Ví dụ: sudo python3 setup.py install node 1a", "ERROR")
            log_message("       sudo python3 setup.py install node 2b --flash-stm32", "ERROR")
            return 1
        
        if args.action == 'install':
            # ✓ Nếu --flash-stm32, prompt user confirm
            flash_stm32 = args.flash_stm32
            if flash_stm32:
                log_message("\n⚠️  WARNING: STM32 auto-flash enabled", "WARNING")
                log_message("Ensure ST-Link V2 và STM32F407 board được kết nối", "WARNING")
                confirm = input("\nTiếp tục? (y/n): ").strip().lower()
                if confirm != 'y':
                    log_message("Hủy cài đặt", "INFO")
                    return 1
            
            success = setup_node(args.node_name, flash_stm32=flash_stm32)
        else:  # uninstall
            success = uninstall_node(args.node_name)
    
    # ✓ Return status
    if success:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())