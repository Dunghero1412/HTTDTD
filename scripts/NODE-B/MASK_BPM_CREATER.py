#!/usr/bin/env python3

from PIL import Image, ImageDraw

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
