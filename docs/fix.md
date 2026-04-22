
---

## **Phần 1: Chọn Định Dạng File Mask**

### **Khuyến Nghị: PNG hoặc PBM (Portable Bitmap)**

```
Ưu điểm từng định dạng:

1️⃣  PNG (Khuyến cáo nhất ✅)
   - Hỗ trợ transparent (alpha channel)
   - Dễ tạo trong Photoshop, GIMP
   - Thư viện Python hỗ trợ tốt (Pillow)
   - Kích thước file nhỏ

2️⃣  PBM (Portable Bitmap)
   - Siêu đơn giản (chỉ là text)
   - Không cần thư viện đặc biệt
   - Dễ debug (có thể xem trực tiếp)
   - Dễ tạo bằng code

3️⃣  JPEG
   - ❌ Không nên (lossy compression)

4️⃣  BMP
   - ⚠️ File lớn
```

**Mình sẽ dùng PNG + fallback PBM** để bạn chọn.

---

## **Phần 2: Tính Toán Kích Thước Mask**

### **Dữ Liệu Bia Loại B:**

```
Kích thước bia: 150 cm (W) × 42 cm (H)
Tâm toạ độ: (0, 0)

Phạm vi:
- X: -75 đến 75 cm
- Y: -21 đến 21 cm

Vị trí sensor:
- A: (-75, -21) [góc trái dưới]
- B: (-75, +21) [góc trái trên]
- C: (+75, +21) [góc phải trên]
- D: (+75, -21) [góc phải dưới]

Pixel scaling:
- Để độ chính xác tốt: 1 cm = 4 pixel
- Kích thước mask: 600 × 168 pixel
  (600 = 150 × 4, 168 = 42 × 4)
```

---

## **Phần 3: Tạo File Mask**

### **Cách 1: Tạo PNG bằng Python (Dễ nhất)**

```python
from PIL import Image, ImageDraw

def create_bia_b_mask():
    """
    Tạo file mask PNG cho bia loại B (150×42 cm)
    
    Quy tắc:
    - Trắng (255, 255, 255): Vùng tính điểm
    - Đen (0, 0, 0): Vùng không tính điểm
    """
    
    # Kích thước mask: 600 × 168 pixel (1 cm = 4 pixel)
    PIXEL_PER_CM = 4
    WIDTH_CM = 150
    HEIGHT_CM = 42
    
    width_px = WIDTH_CM * PIXEL_PER_CM  # 600
    height_px = HEIGHT_CM * PIXEL_PER_CM  # 168
    
    # Tạo hình ảnh trắng (mặc định là vùng tính điểm)
    img = Image.new('RGB', (width_px, height_px), color='white')
    draw = ImageDraw.Draw(img)
    
    # ===== VẼ CÁC VÙNG KHÔNG TÍNH ĐIỂM (TÔ ĐEN) =====
    
    # Tâm bia ở (0, 0) → Pixel (300, 84)
    center_px_x = width_px // 2  # 300
    center_px_y = height_px // 2  # 84
    
    # Ví dụ 1: Vùng lỗ hình tròn ở giữa
    # Tâm: (0, 0), bán kính: 5 cm = 20 pixel
    circle_center_x = center_px_x
    circle_center_y = center_px_y
    circle_radius_px = 5 * PIXEL_PER_CM  # 20 pixel
    
    draw.ellipse(
        [
            circle_center_x - circle_radius_px,
            circle_center_y - circle_radius_px,
            circle_center_x + circle_radius_px,
            circle_center_y + circle_radius_px
        ],
        fill='black'
    )
    
    # Ví dụ 2: Vùng hình chữ nhật ở dưới
    # Tâm: (0, -15), chiều rộng: 20 cm, cao: 10 cm
    rect_center_x = center_px_x  # 0 cm → 300 px
    rect_center_y = center_px_y + 15 * PIXEL_PER_CM  # -15 cm → 84 + 60 = 144 px
    rect_width_px = 20 * PIXEL_PER_CM  # 80
    rect_height_px = 10 * PIXEL_PER_CM  # 40
    
    draw.rectangle(
        [
            rect_center_x - rect_width_px // 2,
            rect_center_y - rect_height_px // 2,
            rect_center_x + rect_width_px // 2,
            rect_center_y + rect_height_px // 2
        ],
        fill='black'
    )
    
    # Lưu file
    img.save('bia_b_mask.png')
    print("✓ Mask file created: bia_b_mask.png (600×168 pixels)")
    
    # Hiển thị thông tin
    print(f"  - White area: Valid (counted)")
    print(f"  - Black area: Invalid (not counted)")
    print(f"  - Pixel per cm: {PIXEL_PER_CM}")
    print(f"  - Center: ({center_px_x}, {center_px_y})")

# Chạy
create_bia_b_mask()
```

### **Cách 2: Tạo PBM (Plain Text)**

```python
def create_bia_b_mask_pbm():
    """
    Tạo file mask PBM (Plain Text - dễ debug)
    
    Format PBM:
    P1          # Magic number (ASCII)
    600 168     # Width Height
    0 0 0 ...   # Pixel data (0=black, 1=white)
    """
    
    PIXEL_PER_CM = 4
    WIDTH_CM = 150
    HEIGHT_CM = 42
    
    width_px = WIDTH_CM * PIXEL_PER_CM  # 600
    height_px = HEIGHT_CM * PIXEL_PER_CM  # 168
    
    # Khởi tạo mask (tất cả trắng - 1)
    mask = [[1 for _ in range(width_px)] for _ in range(height_px)]
    
    center_x = width_px // 2
    center_y = height_px // 2
    
    # ===== VẼ VÙNG KHÔNG TÍNH ĐIỂM (0 = ĐEN) =====
    
    # Vùng tròn: Tâm (0, 0), bán kính 5 cm = 20 pixel
    circle_radius_px = 5 * PIXEL_PER_CM
    for y in range(height_px):
        for x in range(width_px):
            dist = ((x - center_x)**2 + (y - center_y)**2) ** 0.5
            if dist <= circle_radius_px:
                mask[y][x] = 0
    
    # Vùng chữ nhật: Tâm (0, -15), 20×10 cm
    rect_center_x = center_x
    rect_center_y = center_y + 15 * PIXEL_PER_CM
    rect_width_px = 20 * PIXEL_PER_CM
    rect_height_px = 10 * PIXEL_PER_CM
    
    for y in range(height_px):
        for x in range(width_px):
            if (abs(x - rect_center_x) <= rect_width_px // 2 and
                abs(y - rect_center_y) <= rect_height_px // 2):
                mask[y][x] = 0
    
    # Lưu file PBM
    with open('bia_b_mask.pbm', 'w') as f:
        f.write('P1\n')  # Magic number
        f.write(f'{width_px} {height_px}\n')  # Width Height
        
        # Ghi dữ liệu pixel
        for row in mask:
            f.write(' '.join(map(str, row)) + '\n')
    
    print("✓ PBM mask file created: bia_b_mask.pbm")

# Chạy
create_bia_b_mask_pbm()
```

### **Cách 3: Tạo Mask Bằng GIMP (GUI)**

```
Các bước:
1. Mở GIMP
2. File → New → 600×168 pixels, white background
3. Vẽ hình người / các vùng lỗ bằng màu đen
4. Lưu: File → Export As → bia_b_mask.png
```

---

## **Phần 4: Code Node.py Cho Loại Bia B**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi Nano 2W Node B - Bắn bia hình chữ nhật 150×42cm với mask
"""

# ... (import giữ nguyên) ...

from PIL import Image
import numpy as np

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

# ==================== SỬA HÀM GỬI DỮ LIỆU ====================

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

# ==================== SỬA VÒNG LẶP CHÍNH ====================

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
```

---

## **Phần 5: Sửa Controller & Setup**

### **Sửa Controller.py**

```python
# Thêm nút B vào BUTTON_PINS
BUTTON_PINS = {
    2: "NODE1",
    3: "NODE2",
    4: "NODE3",
    5: "NODE4",
    6: "NODE5",
    7: "A",
    8: "Extra",
    17: "B",  # ← THÊM DÒNG NÀY (GPIO 17 cho nút B)
}
```

### **Sửa setup.py**

```python
# Trong hàm setup_node(), sửa phần thay đổi NODE_NAME:

def setup_node(node_name):
    # ...
    
    # Chuẩn hóa tên Node
    node_name = node_name.upper()
    
    # Hỗ trợ cả NODE1 và NODE1B
    if not (node_name.startswith("NODE") or node_name.startswith("B")):
        node_name = "NODE" + node_name
    
    # ...
    
    # Sửa biến NODE_NAME
    old_pattern = 'NODE_NAME = "NODE1"'
    new_pattern = f'NODE_NAME = "{node_name}"'
    # ...
```

---

## **Bảng Tóm Tắt**

```
┌──────────────────┬──────────────────────┬──────────────────────┐
│ Loại Bia         │ Bia A (Tròn)        │ Bia B (Hình Chữ Nhật)│
├──────────────────┼──────────────────────┼──────────────────────┤
│ Kích thước        │ 100×100 cm          │ 150×42 cm            │
│ Sensor vị trí     │ 4 góc (-50,-50)...  │ 4 góc (-75,-21)...   │
│ Tính điểm         │ 10 vòng (0-10)      │ 1 điểm (0-1)         │
│ Lệnh              │ "A UP/DOWN"         │ "B UP/DOWN"          │
│ Node tên          │ NODE1, NODE2, ...   │ NODE1B, NODE2B, ...  │
│ Mask              │ Không cần            │ bia_b_mask.png       │
│ Miss              │ Vượt bia            │ (-200, -200)         │
└──────────────────┴──────────────────────┴──────────────────────┘
```

---

## **Cách Tạo Mask Nhanh Nhất**

```bash
# 1. Tạo mask từ Python
python3 << 'EOF'
from PIL import Image, ImageDraw

img = Image.new('RGB', (600, 168), 'white')
draw = ImageDraw.Draw(img)

# Vẽ lỗ ở giữa
draw.ellipse([280, 64, 320, 104], fill='black')

img.save('bia_b_mask.png')
print("✓ Created bia_b_mask.png")
EOF

# 2. Copy vào Node
scp bia_b_mask.png pi@<node-ip>:/opt/
```

---

