#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTDTD Setup Script - Hệ Thống Tính Điểm Tự Động Dùng Cho Bắn Súng

Cấu trúc thư mục mới:
    HTTDTD/
    ├── scripts/
    │   ├── CONTROLLER/
    │   │   └── CONTROLLER.py
    │   ├── NODE-A/
    │   │   └── NODE.py
    │   ├── NODE-B/
    │   │   └── NODE.py
    │   ├── NODE-C/
    │   │   └── NODE.py
    │   ├── NODE-D/
    │   │   └── NODE.py
    │   └── html/
    │       └── score_gui.html

Cách sử dụng:
    sudo python3 setup.py install controller
    sudo python3 setup.py install node 1a
    sudo python3 setup.py install node 2b
    sudo python3 setup.py install node 3c
    sudo python3 setup.py install node 4d
    sudo python3 setup.py uninstall controller
    sudo python3 setup.py uninstall node 1a
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path
from datetime import datetime

# ==================== CẤU HÌNH ====================

# Đường dẫn cài đặt
INSTALL_PATH = Path("/opt")
HTML_PATH = INSTALL_PATH / "html"
LOG_FILE = INSTALL_PATH / "setup.log"

# Tên user chạy services
SERVICE_USER = "pi"

# Các nhóm Node hợp lệ
VALID_NODE_GROUPS = ["A", "B", "C", "D"]

# Tên file trong các thư mục
CONTROLLER_SCRIPT = "CONTROLLER.py"
NODE_SCRIPT = "NODE.py"
HTML_FILE = "score_gui.html"

# ==================== HÀM HỖ TRỢ ====================

def log_message(message, level="INFO"):
    """
    Ghi log thông điệp
    
    Tham số:
        message (str): Thông điệp
        level (str): Mức độ (INFO, WARNING, ERROR, SUCCESS)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prefix_map = {
        "INFO": "ℹ️  INFO   ",
        "WARNING": "⚠️  WARNING",
        "ERROR": "❌ ERROR  ",
        "SUCCESS": "✅ SUCCESS"
    }
    prefix = prefix_map.get(level, "INFO")
    
    log_text = f"[{timestamp}] {prefix} | {message}"
    
    # In ra console
    print(log_text)
    
    # Ghi vào file log
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(log_text + "\n")
    except:
        pass

def run_command(cmd, description=""):
    """
    Chạy lệnh shell
    
    Tham số:
        cmd (str): Lệnh cần chạy
        description (str): Mô tả
    
    Trả về:
        bool: True nếu thành công, False nếu lỗi
    """
    try:
        if description:
            log_message(description)
        
        result = subprocess.run(cmd, shell=True, check=True, 
                              stdout=subprocess.PIPE, 
                              stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"Failed to execute: {cmd}", "ERROR")
        log_message(f"Error: {e.stderr.decode()}", "ERROR")
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
        path.mkdir(parents=True, exist_ok=True)
        # Đặt quyền cho user "pi"
        os.chown(path, 1000, 1000)  # UID 1000 = pi
        log_message(f"Thư mục được tạo: {path}")
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
        
        shutil.copy2(src, dst)
        os.chmod(dst, 0o755)
        os.chown(dst, 1000, 1000)  # UID 1000 = pi
        
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
                              Ví dụ: "1a", "2b", "NODE1A", "NODE2B"
    
    Trả về:
        tuple: (node_number, node_group, node_full_name)
               Ví dụ: (1, "A", "NODE1A")
               hoặc (None, None, None) nếu lỗi
    """
    node_input = node_name_input.upper()
    
    # Chuẩn hóa: "1A" -> "1A", "NODE1A" -> "1A"
    if node_input.startswith("NODE"):
        node_input = node_input[4:]  # Bỏ "NODE"
    
    # Parse số và nhóm
    # "1A" -> số=1, nhóm=A
    # "2B" -> số=2, nhóm=B
    
    try:
        # Tách số và ký tự
        node_number = None
        node_group = None
        
        # Tìm vị trí chuyển từ số sang chữ
        for i, char in enumerate(node_input):
            if char.isalpha():
                node_number = int(node_input[:i])
                node_group = node_input[i:].upper()
                break
        
        # Kiểm tra hợp lệ
        if node_number is None or node_group is None:
            log_message(f"Tên Node không hợp lệ: {node_name_input}", "ERROR")
            log_message("Ví dụ hợp lệ: 1a, 2b, 3c, 4d, NODE1A, NODE2B", "ERROR")
            return None, None, None
        
        # Kiểm tra nhóm
        if node_group not in VALID_NODE_GROUPS:
            log_message(f"Nhóm Node không hợp lệ: {node_group}", "ERROR")
            log_message(f"Nhóm hợp lệ: {', '.join(VALID_NODE_GROUPS)}", "ERROR")
            return None, None, None
        
        # Kiểm tra số
        if node_number < 1 or node_number > 5:
            log_message(f"Số Node không hợp lệ: {node_number}", "ERROR")
            log_message("Số Node phải từ 1 đến 5", "ERROR")
            return None, None, None
        
        # Tên đầy đủ
        node_full_name = f"NODE{node_number}{node_group}"
        
        return node_number, node_group, node_full_name
    
    except ValueError:
        log_message(f"Tên Node không hợp lệ: {node_name_input}", "ERROR")
        log_message("Ví dụ hợp lệ: 1a, 2b, 3c, 4d", "ERROR")
        return None, None, None

# ==================== SETUP CONTROLLER ====================

def setup_controller():
    """
    Cài đặt Controller (RPi 5)
    
    Hoạt động:
    1. Copy CONTROLLER.py → /opt/CONTROLLER.py
    2. Copy html/score_gui.html → /opt/html/score_gui.html
    3. Tạo systemd service: rpi5-controller.service
    4. Enable service và khởi động
    """
    
    log_message("=" * 60, "INFO")
    log_message("SETUP CONTROLLER - RPi 5", "INFO")
    log_message("=" * 60, "INFO")
    
    # ── Bước 1: Kiểm tra quyền root ──
    if not check_root():
        return False
    
    # ── Bước 2: Kiểm tra file nguồn ──
    current_dir = Path(__file__).parent
    controller_src = current_dir / "scripts" / "CONTROLLER" / CONTROLLER_SCRIPT
    html_src = current_dir / "html" / HTML_FILE
    
    if not check_file_exists(controller_src, "CONTROLLER.py"):
        return False
    
    if not check_file_exists(html_src, "HTML file"):
        return False
    
    # ── Bước 3: Tạo thư mục cài đặt ──
    if not create_directory(INSTALL_PATH):
        return False
    
    if not create_directory(HTML_PATH):
        return False
    
    # ── Bước 4: Copy file ──
    controller_dst = INSTALL_PATH / CONTROLLER_SCRIPT
    if not copy_file(controller_src, controller_dst, "Copy CONTROLLER.py"):
        return False
    
    html_dst = HTML_PATH / HTML_FILE
    if not copy_file(html_src, html_dst, "Copy HTML file"):
        return False
    
    # ── Bước 5: Tạo systemd service ──
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
    
    # ── Bước 6: Reload systemd ──
    if not run_command("systemctl daemon-reload", "Reload systemd daemon"):
        return False
    
    # ── Bước 7: Enable service ──
    if not run_command("systemctl enable rpi5-controller.service", 
                       "Enable service (chạy lúc boot)"):
        return False
    
    # ── Bước 8: Khởi động service ──
    if not run_command("systemctl start rpi5-controller.service", 
                       "Khởi động service"):
        return False
    
    # ── Bước 9: Kiểm tra trạng thái ──
    log_message("Kiểm tra trạng thái service...")
    run_command("systemctl status rpi5-controller.service --no-pager")
    
    # ── Hoàn thành ──
    log_message("=" * 60, "SUCCESS")
    log_message("CONTROLLER ĐÃ ĐƯỢC CÀI ĐẶT THÀNH CÔNG!", "SUCCESS")
    log_message("=" * 60, "SUCCESS")
    log_message(f"📍 Controller script: {controller_dst}", "INFO")
    log_message(f"📍 HTML file: {html_dst}", "INFO")
    log_message(f"📍 Service: rpi5-controller.service", "INFO")
    log_message("", "INFO")
    log_message("Lệnh hữu ích:", "INFO")
    log_message("  - Xem log:     journalctl -u rpi5-controller.service -f", "INFO")
    log_message("  - Dừng:        sudo systemctl stop rpi5-controller.service", "INFO")
    log_message("  - Khởi động lại: sudo systemctl restart rpi5-controller.service", "INFO")
    
    return True

# ==================== SETUP NODE ====================

def setup_node(node_name_input):
    """
    Cài đặt Node (RPi Nano 2W)
    
    Tham số:
        node_name_input (str): Tên Node (VD: "1a", "2b", "NODE1A")
    
    Hoạt động:
    1. Parse tên Node để lấy số và nhóm
    2. Copy NODE.py từ thư mục NODE-{GROUP}/NODE.py
    3. Sửa biến NODE_NAME trong file
    4. Tạo systemd service
    5. Enable service và khởi động
    """
    
    # Parse tên Node
    node_number, node_group, node_full_name = parse_node_name(node_name_input)
    
    if node_full_name is None:
        return False
    
    log_message("=" * 60, "INFO")
    log_message(f"SETUP NODE - {node_full_name}", "INFO")
    log_message("=" * 60, "INFO")
    
    # ── Bước 1: Kiểm tra quyền root ──
    if not check_root():
        return False
    
    # ── Bước 2: Kiểm tra file nguồn ──
    current_dir = Path(__file__).parent
    node_src = current_dir / "scripts" / f"NODE-{node_group}" / NODE_SCRIPT
    
    if not check_file_exists(node_src, f"NODE.py (nhóm {node_group})"):
        return False
    
    # ── Bước 3: Tạo thư mục cài đặt ──
    if not create_directory(INSTALL_PATH):
        return False
    
    # ── Bước 4: Copy file và sửa NODE_NAME ──
    node_dst = INSTALL_PATH / f"NODE_{node_full_name}.py"
    
    try:
        log_message(f"Copy NODE.py từ NODE-{node_group}/ → {node_dst}")
        
        # Đọc file NODE.py
        with open(node_src, 'r') as f:
            content = f.read()
        
        # Sửa biến NODE_NAME
        # Tìm dòng: NODE_NAME = "NODE1"
        # Sửa thành: NODE_NAME = "NODE1A" (hoặc tên khác)
        old_pattern = 'NODE_NAME = "NODE1"'
        new_pattern = f'NODE_NAME = "{node_full_name}"'
        
        if old_pattern not in content:
            log_message(f"Không tìm thấy '{old_pattern}' trong file", "WARNING")
            log_message("Sẽ copy file nguyên bản mà không sửa NODE_NAME", "WARNING")
        else:
            content = content.replace(old_pattern, new_pattern)
            log_message(f"Sửa NODE_NAME → {node_full_name}", "SUCCESS")
        
        # Ghi file tại /opt
        with open(node_dst, 'w') as f:
            f.write(content)
        
        # Đặt quyền
        os.chmod(node_dst, 0o755)
        os.chown(node_dst, 1000, 1000)  # UID 1000 = pi
        
        log_message(f"File được tạo: {node_dst}", "SUCCESS")
    
    except Exception as e:
        log_message(f"Lỗi khi copy file: {e}", "ERROR")
        return False
    
    # ── Bước 5: Tạo systemd service ──
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
    
    # ── Bước 6: Reload systemd ──
    if not run_command("systemctl daemon-reload", "Reload systemd daemon"):
        return False
    
    # ── Bước 7: Enable service ──
    if not run_command(f"systemctl enable {service_name}", 
                       f"Enable service (chạy lúc boot)"):
        return False
    
    # ── Bước 8: Khởi động service ──
    if not run_command(f"systemctl start {service_name}", 
                       "Khởi động service"):
        return False
    
    # ── Bước 9: Kiểm tra trạng thái ──
    log_message(f"Kiểm tra trạng thái service...")
    run_command(f"systemctl status {service_name} --no-pager")
    
    # ── Hoàn thành ──
    log_message("=" * 60, "SUCCESS")
    log_message(f"NODE {node_full_name} ĐÃ ĐƯỢC CÀI ĐẶT THÀNH CÔNG!", "SUCCESS")
    log_message("=" * 60, "SUCCESS")
    log_message(f"📍 Node script: {node_dst}", "INFO")
    log_message(f"📍 Service: {service_name}", "INFO")
    log_message("", "INFO")
    log_message("Lệnh hữu ích:", "INFO")
    log_message(f"  - Xem log:     journalctl -u {service_name} -f", "INFO")
    log_message(f"  - Dừng:        sudo systemctl stop {service_name}", "INFO")
    log_message(f"  - Khởi động lại: sudo systemctl restart {service_name}", "INFO")
    
    return True

# ==================== UNINSTALL ====================

def uninstall_controller():
    """
    Gỡ cài đặt Controller
    """
    log_message("=" * 60, "WARNING")
    log_message("UNINSTALL CONTROLLER", "WARNING")
    log_message("=" * 60, "WARNING")
    
    if not check_root():
        return False
    
    # Dừng service
    run_command("systemctl stop rpi5-controller.service", "Dừng service")
    run_command("systemctl disable rpi5-controller.service", "Disable service")
    
    # Xóa service file
    service_path = Path("/etc/systemd/system/rpi5-controller.service")
    try:
        service_path.unlink()
        log_message(f"Xóa: {service_path}", "SUCCESS")
    except:
        pass
    
    # Reload systemd
    run_command("systemctl daemon-reload", "Reload systemd daemon")
    
    # Xóa controller file
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
    # Parse tên Node
    node_number, node_group, node_full_name = parse_node_name(node_name_input)
    
    if node_full_name is None:
        return False
    
    log_message("=" * 60, "WARNING")
    log_message(f"UNINSTALL NODE - {node_full_name}", "WARNING")
    log_message("=" * 60, "WARNING")
    
    if not check_root():
        return False
    
    service_name = f"rpi-nano-{node_full_name.lower()}.service"
    
    # Dừng service
    run_command(f"systemctl stop {service_name}", "Dừng service")
    run_command(f"systemctl disable {service_name}", "Disable service")
    
    # Xóa service file
    service_path = Path("/etc/systemd/system") / service_name
    try:
        service_path.unlink()
        log_message(f"Xóa: {service_path}", "SUCCESS")
    except:
        pass
    
    # Reload systemd
    run_command("systemctl daemon-reload", "Reload systemd daemon")
    
    # Xóa node file
    node_path = INSTALL_PATH / f"NODE_{node_full_name}.py"
    try:
        node_path.unlink()
        log_message(f"Xóa: {node_path}", "SUCCESS")
    except:
        log_message(f"Không thể xóa: {node_path}", "WARNING")
    
    log_message(f"Node {node_full_name} đã được gỡ cài đặt", "SUCCESS")
    return True

# ==================== MAIN ====================

def main():
    """
    Hàm chính - Xử lý arguments
    """
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
  │   └── html/score_gui.html
  └── setup.py

Ví dụ sử dụng:
  sudo python3 setup.py install controller
  sudo python3 setup.py install node 1a
  sudo python3 setup.py install node 2b
  sudo python3 setup.py install node 3c
  sudo python3 setup.py install node 4d
  sudo python3 setup.py uninstall controller
  sudo python3 setup.py uninstall node 1a
        """
    )
    
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
    
    args = parser.parse_args()
    
    # ── Xử lý arguments ──
    if args.target == 'controller':
        if args.action == 'install':
            success = setup_controller()
        else:  # uninstall
            success = uninstall_controller()
    
    elif args.target == 'node':
        if args.node_name is None:
            log_message("Lỗi: Cần chỉ định tên Node", "ERROR")
            log_message("Ví dụ: sudo python3 setup.py install node 1a", "ERROR")
            return 1
        
        if args.action == 'install':
            success = setup_node(args.node_name)
        else:  # uninstall
            success = uninstall_node(args.node_name)
    
    # ── Kết quả ──
    if success:
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
