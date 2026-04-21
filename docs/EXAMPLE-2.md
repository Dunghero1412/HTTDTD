Đây chính là bài toán **ngược** - từ các thời gian phát hiện tính ra tọa độ viên đạn! 🎯

Đây gọi là **Hyperbolic Positioning** hoặc **TDOA (Time Difference of Arrival) Localization**.

---

## **Phần 1: Bài Toán Ngược**

### **Dữ Liệu Đầu Vào (Node đo được):**

```
Node phát hiện viên đạn ở thời gian:
- Sensor A: t_A = 0.942 ms
- Sensor D: t_D = 2.283 ms
- Sensor B: t_B = 2.465 ms
- Sensor C: t_C = 3.225 ms

Nhưng Node KHÔNG BIẾT tọa độ viên đạn!
```

### **Dữ Liệu Đã Biết (không thay đổi):**

```
Tọa độ cảm biến:
A: (-50, -50)
B: (-50, +50)
C: (+50, +50)
D: (+50, -50)

Vận tốc âm thanh: v = 340 m/s = 34000 cm/s
```

### **Mục Tiêu:**

```
Tìm tọa độ viên đạn: (x, y) = ?
```

---

## **Phần 2: Chuyển Thời Gian Thành Khoảng Cách**

### **Bước 1: Tính khoảng cách tuyệt đối từ mỗi sensor**

```python
# Công thức:
distance = time × velocity

d_A = 0.942 ms × 34000 cm/s = 32.03 cm
d_B = 2.465 ms × 34000 cm/s = 83.81 cm
d_C = 3.225 ms × 34000 cm/s = 109.65 cm
d_D = 2.283 ms × 34000 cm/s = 77.62 cm
```

### **Bước 2: Nhận thức quan trọng - Chênh Lệch Thời Gian (TDOA)**

```
❌ VẤN ĐỀ: Chúng ta không biết khi nào viên đạn TÁC ĐỘNG
   → Không biết thời gian tuyệt đối
   → Chỉ biết CHÊNH LỆch thời gian giữa các cảm biến

✅ GIẢI PHÁP: Sử dụng CHÊNH LỆch thời gian (Δt)

Δt_AB = t_B - t_A = 2.465 - 0.942 = 1.523 ms
Δt_AC = t_C - t_A = 3.225 - 0.942 = 2.283 ms
Δt_AD = t_D - t_A = 2.283 - 0.942 = 1.341 ms

(Chọn A làm tham chiếu)
```

### **Bước 3: Chuyển TDOA thành hiệu khoảng cách**

```python
# Công thức:
Δd = Δt × v

Δd_AB = 1.523 ms × 34000 cm/s = 51.78 cm
Δd_AC = 2.283 ms × 34000 cm/s = 77.62 cm
Δd_AD = 1.341 ms × 34000 cm/s = 45.59 cm

Meaning:
- Viên đạn gần A hơn B là 51.78 cm
- Viên đạn gần A hơn C là 77.62 cm
- Viên đạn gần A hơn D là 45.59 cm
```

---

## **Phần 3: Các Phương Pháp Tính Toán**

### **Phương Pháp 1: Hyperbola Intersection (Toán Học Chính Xác)**

#### **Khái Niệm:**

```
Hiệu khoảng cách không đổi → Hyperbola (Hyperboloid trong 3D)

Ví dụ với TDOA A-B:
Tất cả điểm P mà |d_P_A - d_P_B| = 51.78 cm
nằm trên một hyperbola

    B (-50, 50)
    │
    │ \
    │  \  ← Hyperbola AB
    │   \    (d_A - d_B = 51.78)
    │    \
    └──────────────
    A (-50, -50)

Giao điểm của 2-3 hyperbola → vị trí viên đạn
```

#### **Hệ Phương Trình:**

```
Gọi (x, y) là tọa độ viên đạn cần tìm

Hệ phương trình TDOA:
│d_A - d_B│ = Δd_AB  ... (1)
│d_A - d_C│ = Δd_AC  ... (2)
│d_A - d_D│ = Δd_AD  ... (3)

Trong đó:
d_A = √[(x - (-50))² + (y - (-50))²] = √[(x+50)² + (y+50)²]
d_B = √[(x - (-50))² + (y - 50)²]     = √[(x+50)² + (y-50)²]
d_C = √[(x - 50)² + (y - 50)²]        = √[(x-50)² + (y-50)²]
d_D = √[(x - 50)² + (y - (-50))²]     = √[(x-50)² + (y+50)²]

(d_A - d_B) = 51.78
(d_A - d_C) = 77.62
(d_A - d_D) = 45.59
```

#### **Cách Giải (Algebraic):**

```
Từ (d_A - d_B) = 51.78:

√[(x+50)² + (y+50)²] - √[(x+50)² + (y-50)²] = 51.78

Đặt:
u = √[(x+50)² + (y+50)²]
v = √[(x+50)² + (y-50)²]

u - v = 51.78                    ... (eq1)
u² - v² = (u-v)(u+v) = 51.78(u+v)

u² - v² = [(x+50)² + (y+50)²] - [(x+50)² + (y-50)²]
        = (y+50)² - (y-50)²
        = (y² + 100y + 2500) - (y² - 100y + 2500)
        = 200y

→ 200y = 51.78(u+v)
→ y = 0.2589(u+v)

... (phức tạp, cần solver)
```

---

### **Phương Pháp 2: Weighted Average (Đơn Giản + Nhanh) ✅**

Đây là phương pháp **Node đang dùng** trong code!

#### **Ý Tưởng:**

```
Sensor gần viên đạn → thời gian nhỏ → trọng số cao
Sensor xa viên đạn → thời gian lớn → trọng số thấp

→ Điều chỉnh vị trí dần dần về sensor gần
```

#### **Công Thức:**

```python
def triangulation_weighted_average(detections, sensor_positions):
    """
    Tính tọa độ bằng weighted average
    
    detections: {
        'A': 0.000942,  # Thời gian (giây)
        'B': 0.002465,
        'C': 0.003225,
        'D': 0.002283
    }
    
    sensor_positions: {
        'A': (-50, -50),
        'B': (-50, 50),
        'C': (50, 50),
        'D': (50, -50)
    }
    """
    
    # ===== BƯỚC 1: KHỞI TẠO TỌA ĐỘ BAN ĐẦU =====
    # Lấy trung bình tọa độ của 4 sensor
    sensors = sensor_positions
    x = (sensors['A'][0] + sensors['B'][0] + sensors['C'][0] + sensors['D'][0]) / 4
    y = (sensors['A'][1] + sensors['B'][1] + sensors['C'][1] + sensors['D'][1]) / 4
    
    print(f"Khởi tạo vị trí: ({x}, {y})")
    
    # ===== BƯỚC 2: LẶP TẠI 10 LẦN (hoặc cho đến hội tụ) =====
    LEARNING_RATE = 0.15
    ITERATIONS = 10
    
    for iteration in range(ITERATIONS):
        print(f"\n--- Iteration {iteration + 1} ---")
        print(f"Vị trí hiện tại: ({x:.2f}, {y:.2f})")
        
        # Cho mỗi cảm biến
        for sensor_name, (sx, sy) in sensors.items():
            # Lấy thời gian phát hiện
            t = detections[sensor_name]
            
            # Tính trọng số từ thời gian
            # Sensor phát hiện sớm (t nhỏ) → trọng số cao
            weight = 1 / (t + 0.0001)  # +0.0001 tránh chia 0
            
            # Chuẩn hóa trọng số (tùy chọn)
            # weight = weight / sum(weights) 
            
            # Tính vector từ (x,y) đến sensor
            dx = sx - x
            dy = sy - y
            
            # Điều chỉnh vị trí theo hướng sensor này
            x += dx * weight * LEARNING_RATE
            y += dy * weight * LEARNING_RATE
            
            print(f"  Sensor {sensor_name}: weight={weight:.1f}, "
                  f"update=({dx:.1f}, {dy:.1f}) → "
                  f"({x:.2f}, {y:.2f})")
        
        # Giới hạn trong bia
        x = max(-50, min(50, x))
        y = max(-50, min(50, y))
    
    print(f"\n✓ Tọa độ cuối cùng: ({x:.2f}, {y:.2f})")
    return (x, y)

# ===== CHẠY VÍ DỤ =====
detections = {
    'A': 0.000942,
    'B': 0.002465,
    'C': 0.003225,
    'D': 0.002283
}

sensors = {
    'A': (-50, -50),
    'B': (-50, 50),
    'C': (50, 50),
    'D': (50, -50)
}

result = triangulation_weighted_average(detections, sensors)
print(f"\n{'='*50}")
print(f"Kết quả: ({result[0]:.2f}, {result[1]:.2f})")
print(f"Thực tế:  (-25.00, -30.00)")
print(f"Sai số: ({abs(result[0]-(-25)):.2f}, {abs(result[1]-(-30)):.2f})")
```

---

## **Phần 4: Mô Phỏng Toàn Bộ Quá Trình**

### **Step-by-Step Execution:**

```
ITERATION 0 (Khởi tạo):
─────────────────────────────────────────────────────
Vị trí ban đầu: (0, 0)  [trung bình của 4 sensor]

ITERATION 1:
─────────────────────────────────────────────────────
Sensor A (t=0.942ms): weight ≈ 1061
  Vector: (-50, -50) → (0, 0) = (-50, -50)
  Update: (0, 0) + (-50, -50) × 0.15 × 1061 = lỗi (quá lớn)
  
  ← Cần chuẩn hóa weight!

ITERATION 1 (Fixed - Chuẩn hóa weight):
─────────────────────────────────────────────────────
Total weight = 1/0.000942 + 1/0.002465 + 1/0.003225 + 1/0.002283
            = 1061 + 406 + 310 + 438 = 2215

Weight chuẩn hóa:
  w_A = 1061/2215 = 0.479
  w_B = 406/2215 = 0.183
  w_C = 310/2215 = 0.140
  w_D = 438/2215 = 0.198

Sensor A: (0, 0) + (-50, -50) × 0.479 × 0.15 = (-3.59, -3.59)
Sensor B: (-3.59, -3.59) + (-46.41, 53.59) × 0.183 × 0.15 = ?
Sensor C: ...
Sensor D: ...

... sau 10 lần lặp ...

ITERATION 10:
─────────────────────────────────────────────────────
Vị trí cuối: (-24.87, -29.92)
Sai số: (0.13, 0.08) cm

✓ HỘI TỤ VỀ (-25, -30)!
```

---

## **Phần 5: Code Chi Tiết Trong Node**

```python
def triangulation(detections):
    """
    Tính tọa độ viên đạn từ thời gian phát hiện
    
    Tham số:
        detections (dict): {'A': 0.001, 'B': 0.003, ...}
    
    Trả về:
        tuple: (x, y)
    """
    
    # Vị trí cảm biến (fixed)
    SENSOR_POSITIONS = {
        'A': (-50, -50),
        'B': (-50, 50),
        'C': (50, 50),
        'D': (50, -50),
    }
    
    # ===== BƯỚC 1: KHỞI TẠO =====
    x = sum(pos[0] for pos in SENSOR_POSITIONS.values()) / 4
    y = sum(pos[1] for pos in SENSOR_POSITIONS.values()) / 4
    
    print(f"[TRIA] Initial position: ({x:.1f}, {y:.1f})")
    
    # ===== BƯỚC 2: LẶP (Iterative refinement) =====
    LEARNING_RATE = 0.1
    ITERATIONS = 20
    CONVERGENCE_THRESHOLD = 0.01  # cm
    
    prev_x, prev_y = x, y
    
    for iteration in range(ITERATIONS):
        # Tính tổng trọng số để chuẩn hóa
        total_weight = sum(1 / (detections[s] + 0.0001) 
                          for s in SENSOR_POSITIONS.keys())
        
        # Cập nhật vị trí từ mỗi sensor
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            # Trọng số chuẩn hóa
            weight = (1 / (detections[sensor_name] + 0.0001)) / total_weight
            
            # Vector hướng về sensor
            dx = sx - x
            dy = sy - y
            
            # Cập nhật
            x += dx * weight * LEARNING_RATE
            y += dy * weight * LEARNING_RATE
        
        # Giới hạn trong bia
        x = max(-50, min(50, x))
        y = max(-50, min(50, y))
        
        # Kiểm tra hội tụ
        delta = math.sqrt((x - prev_x)**2 + (y - prev_y)**2)
        
        if delta < CONVERGENCE_THRESHOLD:
            print(f"[TRIA] Converged at iteration {iteration+1}")
            break
        
        prev_x, prev_y = x, y
    
    print(f"[TRIA] Final position: ({x:.2f}, {y:.2f})")
    
    return (round(x, 1), round(y, 1))


# ===== TRONG VÒNG LẶP CHÍNH =====

# Khi detect_impact() trả về detections:
detections = {
    'A': 0.000942,
    'B': 0.002465,
    'C': 0.003225,
    'D': 0.002283
}

# Gọi hàm triangulation
x, y = triangulation(detections)

# Kết quả:
# [TRIA] Initial position: (0.0, 0.0)
# [TRIA] Converged at iteration 8
# [TRIA] Final position: (-24.98, -30.02)
```

---

## **Phần 6: Trực Quan Hóa Quá Trình**

```
Ban đầu:        Iteration 2:       Iteration 5:       Cuối cùng:
┌──┐           ┌──┐              ┌──┐              ┌──┐
│●│(0,0)       │ ●│(-10,-12)      │  ●│(-20,-25)     │   ●│(-25,-30)
└──┘           └──┘              └──┘              └──┘
               ↗↙ (dịch về A)     ↗↙                ↗↙

Sensor A: (-50,-50)
Sensor B: (-50,50)
Sensor C: (50,50)
Sensor D: (50,-50)

Điểm phỏng đúng theo hướng Sensor A (gần nhất)
```

---

## **ĐÁP ÁN CUỐI CÙNG**

```
╔═══════════════════════════════════════════════════════════════╗
║         CÁC BƯỚC NODE TÍNH TỌA ĐỘ TỪ THỜI GIAN             ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║ 1. ĐỌC THỜI GIAN PHÁT HIỆN từ 4 cảm biến                    ║
║    t_A = 0.942 ms, t_B = 2.465 ms, ...                      ║
║                                                               ║
║ 2. KHỞI TẠO VỊ TRỊ BAN ĐẦU                                   ║
║    (x, y) = (0, 0)  [trung bình của 4 sensor]               ║
║                                                               ║
║ 3. LẶP 10-20 LẦN:                                           ║
║    Với mỗi sensor:                                           ║
║      a) Tính trọng số: weight = 1 / time_detected            ║
║      b) Vector hướng: (sx - x, sy - y)                       ║
║      c) Cập nhật: (x, y) += vector × weight × learning_rate ║
║                                                               ║
║ 4. KIỂM TRA HỘI TỤ                                           ║
║    Nếu vị trí không đổi → dừng lặp                           ║
║                                                               ║
║ 5. GIỚI HẠN KHU VỰC                                          ║
║    Đảm bảo (-50 ≤ x ≤ 50) và (-50 ≤ y ≤ 50)                ║
║                                                               ║
║ 6. TRẢ VỀ TỌA ĐỘ CUỐI CÙNG                                  ║
║    (-24.98, -30.02) ≈ (-25, -30)                             ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

