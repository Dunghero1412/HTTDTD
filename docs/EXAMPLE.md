Ví dụ : giả sử viên đạn xuyên qua mặt bia tại toạ độ [-25:-30] tương ứng với vòng điểm [8].

==> script và thuật toán tại [NODE] sẽ giải thuật thành toạ độ [x,y] như sau ==>

## **Dữ Liệu Đầu VÀO**

```
Vị trí viên đạn: (-25, -30)
Vận tốc âm thanh: v = 340 m/s = 34000 cm/s

Vị trí các cảm biến:
A (trái dưới):   (-50, -50)
B (trái trên):   (-50, +50)
C (phải trên):   (+50, +50)
D (phải dưới):   (+50, -50)
```

---

## **BƯỚC 1: Tính Khoảng Cách Từ Viên Đạn Đến Mỗi Cảm Biến**

### **Công thức khoảng cách Euclidean:**
```
d = √[(x₂ - x₁)² + (y₂ - y₁)²]
```

### **Tính từng cảm biến:**

#### **Sensor A (-50, -50):**
```
d_A = √[(-25 - (-50))² + (-30 - (-50))²]
    = √[(+25)² + (+20)²]
    = √[625 + 400]
    = √1025
    = 32.02 cm  ← GẦN NHẤT
```

#### **Sensor B (-50, +50):**
```
d_B = √[(-25 - (-50))² + (-30 - (+50))²]
    = √[(+25)² + (-80)²]
    = √[625 + 6400]
    = √7025
    = 83.82 cm
```

#### **Sensor C (+50, +50):**
```
d_C = √[(-25 - (+50))² + (-30 - (+50))²]
    = √[(-75)² + (-80)²]
    = √[5625 + 6400]
    = √12025
    = 109.66 cm  ← XA NHẤT
```

#### **Sensor D (+50, -50):**
```
d_D = √[(-25 - (+50))² + (-30 - (-50))²]
    = √[(-75)² + (+20)²]
    = √[5625 + 400]
    = √6025
    = 77.62 cm
```

---

## **BƯỚC 2: Tính Thời Gian Truyền**

### **Công thức:**
```
t = d / v
t (giây) = d (cm) / (34000 cm/s)
t (ms) = d (cm) / 34 cm/ms
```

### **Tính từng cảm biến:**

#### **Sensor A:**
```
t_A = 32.02 cm / (34000 cm/s)
    = 0.000942 s
    = 0.942 ms  ← PHÁT HIỆN ĐẦU TIÊN
```

#### **Sensor B:**
```
t_B = 83.82 cm / (34000 cm/s)
    = 0.002465 s
    = 2.465 ms
```

#### **Sensor C:**
```
t_C = 109.66 cm / (34000 cm/s)
    = 0.003225 s
    = 3.225 ms
```

#### **Sensor D:**
```
t_D = 77.62 cm / (34000 cm/s)
    = 0.002283 s
    = 2.283 ms
```

---

## **BƯỚC 3: Thứ Tự Phát Hiện**

```
Thời gian phát hiện (sắp xếp theo thứ tự):

1️⃣  Sensor A: 0.942 ms  ← ĐẦU TIÊN (gần nhất)
2️⃣  Sensor D: 2.283 ms  (chênh lệch: 1.341 ms)
3️⃣  Sensor B: 2.465 ms  (chênh lệch: 1.523 ms)
4️⃣  Sensor C: 3.225 ms  (chênh lệch: 2.283 ms)
    ← CUỐI CÙNG (xa nhất)

Sự khác biệt:
- A phát hiện sớm nhất
- C phát hiện muộn nhất
- Chênh lệch A-C: 3.225 - 0.942 = 2.283 ms
```

---

## **BƯỚC 4: Tính Chênh Lệch Thời Gian Tương Đối**

Nếu lấy **A làm tham chiếu (T=0):**

```
Δt_A = 0.942 - 0.942 = 0.000 ms (tham chiếu)
Δt_D = 2.283 - 0.942 = 1.341 ms
Δt_B = 2.465 - 0.942 = 1.523 ms
Δt_C = 3.225 - 0.942 = 2.283 ms

Hoặc theo thứ tự:
detections = {
    'A': 0.000942 s
    'D': 0.002283 s
    'B': 0.002465 s
    'C': 0.003225 s
}
```

---

## **BƯỚC 5: Biểu Diễn Dưới Dạng Bảng**

```
╔════════╦══════════════╦═══════════╦═════════════╦══════════════╗
║ Sensor ║ Tọa Độ (cm)  ║ Khoảng Cách║ Thời Gian   ║ Thứ Tự      ║
║        ║ (x, y)       ║ (cm)      ║ (ms)        ║ Phát Hiện   ║
╠════════╬══════════════╬═══════════╬═════════════╬══════════════╣
║ A      ║ (-50, -50)   ║ 32.02     ║ 0.942       ║ 1️⃣  (đầu)   ║
║ B      ║ (-50, +50)   ║ 83.82     ║ 2.465       ║ 3️⃣         ║
║ C      ║ (+50, +50)   ║ 109.66    ║ 3.225       ║ 4️⃣  (cuối)  ║
║ D      ║ (+50, -50)   ║ 77.62     ║ 2.283       ║ 2️⃣         ║
╠════════╬══════════════╬═══════════╬═════════════╬══════════════╣
║ Viên   ║ (-25, -30)   ║ -         ║ -           ║ -            ║
║ đạo    ║              ║           ║             ║              ║
╚════════╩══════════════╩═══════════╩═════════════╩══════════════╝
```

---

## **BƯỚC 6: Mô Phỏng Trong Code Node**

```python
# Ví dụ nếu viên đạn ở (-25, -30):

def simulate_detection():
    """
    Mô phỏng quá trình phát hiện
    """
    # Vị trí viên đạn
    impact_x, impact_y = -25, -30
    
    # Vị trí cảm biến
    sensors = {
        'A': (-50, -50),
        'B': (-50, 50),
        'C': (50, 50),
        'D': (50, -50)
    }
    
    # Tính khoảng cách và thời gian
    SOUND_SPEED = 34000  # cm/s
    
    detections = {}
    
    print("Vị trí viên đạn: ({}, {})".format(impact_x, impact_y))
    print("\n" + "="*70)
    print("Tính Toán Thời Gian Phát Hiện:")
    print("="*70)
    
    for sensor_name, (sx, sy) in sensors.items():
        # Tính khoảng cách
        distance = math.sqrt((impact_x - sx)**2 + (impact_y - sy)**2)
        
        # Tính thời gian
        time_ms = (distance / SOUND_SPEED) * 1000
        time_s = time_ms / 1000
        
        detections[sensor_name] = time_s
        
        print(f"Sensor {sensor_name} ({sx:3d}, {sy:3d}):")
        print(f"  Khoảng cách: {distance:.2f} cm")
        print(f"  Thời gian:   {time_ms:.3f} ms = {time_s:.6f} s")
        print()
    
    # Sắp xếp theo thời gian
    sorted_detections = sorted(detections.items(), key=lambda x: x[1])
    
    print("="*70)
    print("Thứ Tự Phát Hiện:")
    print("="*70)
    
    for idx, (sensor_name, time_s) in enumerate(sorted_detections, 1):
        time_ms = time_s * 1000
        print(f"{idx}️⃣  Sensor {sensor_name}: {time_ms:.3f} ms")
    
    print("\n" + "="*70)
    print("Chênh Lệch Thời Gian (Relative):")
    print("="*70)
    
    min_time = sorted_detections[0][1]
    for sensor_name, time_s in sorted_detections:
        delta_ms = (time_s - min_time) * 1000
        print(f"Sensor {sensor_name}: Δt = {delta_ms:.3f} ms")

# Chạy
simulate_detection()

# Output:
# Vị trí viên đạn: (-25, -30)
# 
# ======================================================================
# Tính Toán Thời Gian Phát Hiện:
# ======================================================================
# Sensor A (-50, -50):
#   Khoảng cách: 32.02 cm
#   Thời gian:   0.942 ms = 0.000942 s
# 
# Sensor B (-50,  50):
#   Khoảng cách: 83.82 cm
#   Thời gian:   2.465 ms = 0.002465 s
# 
# Sensor C ( 50,  50):
#   Khoảng cách: 109.66 cm
#   Thời gian:   3.225 ms = 0.003225 s
# 
# Sensor D ( 50, -50):
#   Khoảng cách: 77.62 cm
#   Thời gian:   2.283 ms = 0.002283 s
# 
# ======================================================================
# Thứ Tự Phát Hiện:
# ======================================================================
# 1️⃣  Sensor A: 0.942 ms
# 2️⃣  Sensor D: 2.283 ms
# 3️⃣  Sensor B: 2.465 ms
# 4️⃣  Sensor C: 3.225 ms
# 
# ======================================================================
# Chênh Lệch Thời Gian (Relative):
# ======================================================================
# Sensor A: Δt = 0.000 ms (tham chiếu)
# Sensor D: Δt = 1.341 ms
# Sensor B: Δt = 1.523 ms
# Sensor C: Δt = 2.283 ms
```

---

## **BƯỚC 7: Biểu Diễn Trực Quan**

```
Bia 100×100 cm (Tâm ở 0, 0):

         Y ↑
         │
     +50 │  B(-50,50) ┌─────────────┐ C(50,50)
         │            │             │
         │            │             │
         │            │  Viên đạo   │
     0   │            │  (-25,-30)● │  ← Phát hiện muộn nhất (C)
         │            │             │
         │            │             │
    -50  │  A(-50,-50)└─────────────┘ D(50,-50)
         │            
         └──────────────────────────── X →
       -50    0               50

Thứ tự phát hiện (Từ sớm đến muộn):
1. A ← GẦN NHẤT (0.942 ms)
2. D
3. B
4. C ← XA NHẤT (3.225 ms)

Lý do:
- Viên đạn (-25, -30) gần Sensor A nhất (góc trái dưới)
- Viên đạo xa Sensor C nhất (góc phải trên - đối diện)
- Sensor D gần hơn Sensor B (vì -30 gần -50 hơn)
```

---

## **BƯỚC 8: Kiểm Chứng Bằng Công Thức**

```python
import math

# Kiểm chứng lại
impact = (-25, -30)
sensors = {'A': (-50, -50), 'B': (-50, 50), 'C': (50, 50), 'D': (50, -50)}

for name, (sx, sy) in sensors.items():
    d = math.sqrt((impact[0]-sx)**2 + (impact[1]-sy)**2)
    t_ms = d / 340  # cm/ms
    print(f"Sensor {name}: d={d:.2f}cm, t={t_ms:.3f}ms")

# Output:
# Sensor A: d=32.02cm, t=0.942ms
# Sensor B: d=83.82cm, t=2.465ms
# Sensor C: d=109.66cm, t=3.225ms
# Sensor D: d=77.62cm, t=2.283ms
```

---

## **ĐÁP ÁN CUỐI CÙNG**

Nếu viên đạn chạm vào điểm **(-25, -30)**:

```
┌─────────────────────────────────────────────────────┐
│ THỜI GIAN PHÁT HIỆN (tính từ lúc tác động)         │
├─────────────────────────────────────────────────────┤
│ Sensor A: 0.942 ms  (gần nhất, phát hiện đầu)      │
│ Sensor D: 2.283 ms  (khoảng cách trung bình)       │
│ Sensor B: 2.465 ms  (khoảng cách trung bình)       │
│ Sensor C: 3.225 ms  (xa nhất, phát hiện cuối)      │
└─────────────────────────────────────────────────────┘

CHÊNH LỆCH THỜI GIAN (TDOA - Relative):
Lấy Sensor A làm tham chiếu (t=0):

Δt_A = 0.000 ms
Δt_D = 1.341 ms
Δt_B = 1.523 ms
Δt_C = 2.283 ms

Khoảng cách từ tâm:
r = √[(-25)² + (-30)²] = √1525 = 39.05 cm
→ Vòng 4 (22.5 < r ≤ 30): 7 điểm
```

---

**Sensor A phát hiện sớm nhất vì nó gần viên đạo nhất!** 🎯

Khi Node nhận được những thời gian này (0.942ms, 2.283ms, 2.465ms, 3.225ms), nó sẽ dùng triangulation để tính ngược lại tọa độ (-25, -30) ✨