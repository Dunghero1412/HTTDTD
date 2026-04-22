#!/usr/bin/env python3


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
