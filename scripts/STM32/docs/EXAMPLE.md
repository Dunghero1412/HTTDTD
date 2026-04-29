
##EXAMPLE.md - Hệ thống định vị âm thanh với STM32F407VG

###📌 Mục lục

1. Tổng quan hệ thống
2. Bố trí cảm biến và kịch bản ví dụ
3. Nguyên lý định vị TDOA
4. Luồng xử lý trong STM32
5. Giải thích code chi tiết
   · 5.1. Cấu hình hệ thống (system.c)
   · 5.2. Cấu hình GPIO (gpio.c)
   · 5.3. Cấu hình TIM2 (timmer.c)
   · 5.4. Cấu hình SPI2 + DMA (spi.c)
   · 5.5. Xử lý ngắt TIM2 (main.c)
   · 5.6. Đóng gói dữ liệu (main.c)
   · 5.7. Vòng lặp chính (main.c)
6. Dạng dữ liệu gửi qua SPI
7. Timing diagram
8. Xử lý lỗi và timeout
9. Kết luận

---

###🎯 Tổng quan hệ thống

Hệ thống gồm:

Thành phần Chức năng
4 cảm biến piezoelectric Chuyển đổi rung động âm thanh thành tín hiệu điện
Mạch preamp + buffer + comparator Khuếch đại, lọc nhiễu, tạo xung số (0-3.3V)
STM32F407VG Ghi nhận thời gian (timestamp) khi có xung từ mỗi cảm biến
Raspberry Pi Nhận dữ liệu timestamp qua SPI, tính toán vị trí nguồn âm bằng giải thuật TDOA

Mục tiêu: Xác định tọa độ nguồn phát âm thanh dựa trên sự chênh lệch thời gian tín hiệu đến giữa các cảm biến.

---

###📐 Bố trí cảm biến và kịch bản ví dụ

Sơ đồ bố trí (hình vuông cạnh 100 cm)

```
                    100 cm
           B(-50,50) +---------+ C(50,50)
                     |         |
                     |    O    |   O = tâm (0,0)
                     |  (0,0)  |
           A(-50,-50)+---------+ D(50,-50)
                     |         |
                     |<------->|
                       100 cm
```

Cảm biến Vị trí (x, y) Góc phần tư Kênh TIM2 Chân STM32
A (-50, -50) Trái dưới CH1 PA0
B (-50, +50) Trái trên CH2 PA1
C (+50, +50) Phải trên CH3 PA2
D (+50, -50) Phải dưới CH4 PA3

###🔉 Kịch bản ví dụ

· Nguồn âm thanh tại tọa độ: (27 cm, 37 cm)
· Thời điểm phát: Khi TIM2 đã đếm được 290 tick
· TIM2 tần số: 84 MHz → 1 tick = 11.9 ns
· Vận tốc âm thanh: 343 m/s = 34,300 cm/s

---

###🧮 Nguyên lý định vị TDOA

TDOA (Time Difference of Arrival) là phương pháp xác định vị trí nguồn âm dựa trên sự chênh lệch thời gian tín hiệu đến giữa các cặp cảm biến.

Công thức cơ bản

Khoảng cách từ nguồn S(x,y) đến cảm biến Mi(xi,yi):

```
di = √[(x - xi)² + (y - yi)²]
```

Chênh lệch thời gian giữa hai cảm biến i và j:

```
ΔTij = (di - dj) / v
```

Trong đó v = 34,300 cm/s (vận tốc âm thanh).

Áp dụng vào ví dụ

Với nguồn âm tại (27, 37):

Cảm biến Khoảng cách (cm) Thời gian truyền (µs) Số tick TIM2
A (-50,-50) 116.2 3,387 284,500
B (-50,50) 78.1 2,277 191,300
C (50,50) 26.4 770 64,700
D (50,-50) 90.0 2,624 220,400

Thời điểm mỗi cảm biến ghi nhận tín hiệu (phát tại tick 290):

Cảm biến Công thức Kết quả (tick)
C 290 + 64,700 64,990
B 290 + 191,300 191,590
D 290 + 220,400 220,690
A 290 + 284,500 284,790

Sắp xếp theo thứ tự đến

1. C đến đầu tiên (gần nhất) – tick 64,990
2. B – tick 191,590
3. D – tick 220,690
4. A – tick 284,790 (xa nhất)

---

###🔄 Luồng xử lý trong STM32

```
┌─────────────────────────────────────────────────────────────────────┐
│                          KHỞI TẠO HỆ THỐNG                          │
│  SystemClock_Config() → GPIO_Init() → Timer_Init() → SPI_Init()     │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     VÒNG LẶP CHÍNH (main loop)                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ 1. Reset capture_flags = 0, data_ready_flag = 0             │    │
│  │ 2. Timer_Start() → TIM2 bắt đầu đếm                         │    │
│  │ 3. Chờ data_ready_flag hoặc timeout                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   NGẮT TIM2 (TIM2_IRQHandler)                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Mỗi khi sensor kích hoạt:                                    │    │
│  │ • Đọc giá trị TIM2->CCRx (timestamp)                         │    │
│  │ • Lưu vào sensor_data[idx]                                   │    │
│  │ • Set bit tương ứng trong capture_flags                      │    │
│  │                                                              │    │
│  │ KHI capture_flags == 0x0F (đủ 4 sensor):                     │    │
│  │   ✓ Dừng TIM2                                                │    │
│  │   ✓ pack_spi_buffer() → đóng gói 20 byte                     │    │
│  │   ✓ SPI_SetTxBuffer() → nạp buffer vào DMA                   │    │
│  │   ✓ GPIO_DataReady_Set() → PB0 = HIGH                        │    │
│  │   ✓ data_ready_flag = 1                                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   TRUYỀN DỮ LIỆU QUA SPI (DMA)                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ RPi phát hiện PB0 = HIGH → kéo NSS (PB12) xuống LOW         │    │
│  │ RPi gửi 20 byte 0x00 qua MOSI (tạo clock)                   │    │
│  │ DMA tự động đẩy 20 byte từ buffer ra MISO                    │    │
│  │ Sau 20 byte → ngắt DMA, hạ busy flag                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      KẾT THÚC CHU KỲ CAPTURE                         │
│  Main loop phát hiện SPI không busy:                                │
│     ✓ GPIO_DataReady_Clear() → PB0 = LOW                            │
│     ✓ delay 5ms → quay lại đầu vòng lặp                             │
└─────────────────────────────────────────────────────────────────────┘
```

---

📝 Giải thích code chi tiết

5.1. Cấu hình hệ thống (system.c)

```c
void SystemClock_Config(void)
{
    // Enable HSE (8MHz external crystal)
    RCC->CR |= (1 << 16);
    while ((RCC->CR & (1 << 17)) == 0);
    
    // Cấu hình PLL: HSE 8MHz → PLL_M=8 → 1MHz
    //                 PLL_N=336 → 336MHz
    //                 PLL_P=2   → 168MHz (SYSCLK)
    RCC->PLLCFGR = 8 | (336 << 6) | (0 << 16) | (7 << 24) | (1 << 22);
    
    // Enable PLL và chờ lock
    RCC->CR |= (1 << 24);
    while ((RCC->CR & (1 << 25)) == 0);
    
    // Cấu hình prescaler
    // AHB = 168MHz (HCLK)
    // APB1 = 168/4 = 42MHz (TIM2 nằm trên APB1 → được x2 → 84MHz)
    // APB2 = 168/2 = 84MHz (SPI2 dùng APB2)
    RCC->CFGR = (0 << 4) | (5 << 10) | (4 << 13) | (2 << 0);
    
    while ((RCC->CFGR & (3 << 2)) != (2 << 2));
}
```

Giải thích chi tiết:

Thanh ghi Bit Giá trị Ý nghĩa
RCC->CR 16 1 Bật HSE (thạch anh ngoài 8MHz)
RCC->CR 17 kiểm tra Chờ HSE ổn định
RCC->PLLCFGR 5:0 8 PLL_M = 8 (8MHz/8=1MHz)
RCC->PLLCFGR 14:6 336 PLL_N = 336 (1MHz×336=336MHz)
RCC->PLLCFGR 17:16 0 PLL_P = 2 (336MHz/2=168MHz)
RCC->PLLCFGR 22 1 Chọn HSE làm nguồn PLL
RCC->CR 24 1 Bật PLL
RCC->CFGR 7:4 0 AHB prescaler = 1 (168MHz)
RCC->CFGR 12:10 5 APB1 prescaler = 4 (168/4=42MHz)
RCC->CFGR 15:13 4 APB2 prescaler = 2 (168/2=84MHz)
RCC->CFGR 1:0 2 Chọn PLL làm hệ thống clock

---

5.2. Cấu hình GPIO (gpio.c)

```c
void GPIO_Init(void)
{
    // Bật clock cho GPIOA và GPIOB
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN;
    
    // ===== Cấu hình PA0-PA3 (TIM2_CH1-CH4) =====
    // Chế độ: Alternate Function (0b10)
    GPIOA->MODER |= (2 << 0) | (2 << 2) | (2 << 4) | (2 << 6);
    
    // Không pull-up/pull-down
    GPIOA->PUPDR &= ~((3 << 0) | (3 << 2) | (3 << 4) | (3 << 6));
    
    // Chọn Alternate Function 1 (TIM2)
    GPIOA->AFR[0] = (1 << 0) | (1 << 4) | (1 << 8) | (1 << 12);
    
    // ===== Cấu hình PB0 (DATA_READY output) =====
    GPIOB->MODER |= (1 << 0);        // Output mode
    GPIOB->OTYPER &= ~(1 << 0);      // Push-pull
    GPIOB->OSPEEDR |= (2 << 0);      // High speed
    GPIOB->BSRR = (1 << 16);         // Initial LOW (BR0)
    
    // ===== Cấu hình PB12-PB15 (SPI2) =====
    for (int pin = 12; pin <= 15; pin++) {
        GPIOB->MODER |= (2 << (pin * 2));    // Alternate Function
        GPIOB->OSPEEDR |= (3 << (pin * 2));  // Very high speed
    }
    
    // Chọn Alternate Function 5 (SPI2)
    GPIOB->AFR[1] = (5 << ((12-8)*4)) | (5 << ((13-8)*4))
                  | (5 << ((14-8)*4)) | (5 << ((15-8)*4));
}
```

Giải thích các chế độ GPIO:

Chế độ MODER Ý nghĩa
Input 0b00 Đọc giá trị từ chân
Output 0b01 Điều khiển mức HIGH/LOW
Alternate Function 0b10 Chân do ngoại vi điều khiển (TIM2, SPI2)
Analog 0b11 Dùng cho ADC/DAC

AFR (Alternate Function Register):

Giá trị Chức năng
AF1 (1) TIM2 (PA0-PA3)
AF5 (5) SPI2 (PB12-PB15)

---

5.3. Cấu hình TIM2 (timmer.c)

```c
void Timer_Init(void)
{
    // Bật clock TIM2 trên APB1
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
    
    // Reset toàn bộ thanh ghi TIM2
    TIM2->CR1 = TIM2->CR2 = TIM2->SMCR = 0;
    TIM2->DIER = TIM2->SR = 0;
    
    // Cấu hình prescaler: PSC = 0 → 84MHz / (0+1) = 84MHz
    // 1 tick = 11.9 ns
    TIM2->PSC = 0;
    
    // Auto-reload: giá trị lớn nhất (32-bit)
    TIM2->ARR = 0xFFFFFFFFU;
    
    // Cấu hình CCMR1 cho CH1 và CH2 (Input Capture)
    TIM2->CCMR1 = (1 << 0)   // CC1S = 01 (IC1 mapped to TI1)
                | (1 << 8);  // CC2S = 01 (IC2 mapped to TI2)
    
    // Cấu hình CCMR2 cho CH3 và CH4 (Input Capture)
    TIM2->CCMR2 = (1 << 0)   // CC3S = 01 (IC3 mapped to TI3)
                | (1 << 8);  // CC4S = 01 (IC4 mapped to TI4)
    
    // Enable capture trên cả 4 kênh, rising edge
    TIM2->CCER = (1 << 0) | (1 << 4) | (1 << 8) | (1 << 12);
    
    // Enable ngắt cho 4 kênh capture
    TIM2->DIER = (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4);
    
    // Cấu hình NVIC: priority cao nhất
    NVIC_SetPriority(TIM2_IRQn, 0);
    NVIC_EnableIRQ(TIM2_IRQn);
    
    // Update event để load giá trị PSC, ARR
    TIM2->EGR |= (1 << 0);
}
```

Giải thích các thanh ghi TIM2 quan trọng:

Thanh ghi Bit Giá trị Ý nghĩa
PSC 15:0 0 Không chia, tần số = 84MHz
ARR 31:0 0xFFFFFFFF Đếm đến 4.29 tỷ rồi reset về 0
CCMR1 1:0 0b01 CH1 capture trên TI1 (PA0)
CCMR1 9:8 0b01 CH2 capture trên TI2 (PA1)
CCER 0 1 Enable CH1 capture
CCER 1 0 Rising edge (không đảo)
DIER 1-4 1 Enable ngắt cho CC1-CC4
CR1 0 1 CEN = 1 (bắt đầu đếm)

```c
void Timer_Start(void)
{
    // Reset biến toàn cục
    g_capture_flags = 0;
    g_capture_done = 0;
    
    // Reset counter và xóa cờ
    TIM2->CNT = 0;
    TIM2->SR = 0;
    
    // Bắt đầu đếm
    TIM2->CR1 |= (1 << 0);  // CEN = 1
}
```

---

5.4. Cấu hình SPI2 + DMA (spi.c)

```c
void SPI_Init(void)
{
    // Bật clock SPI2 và DMA1
    RCC->APB1ENR |= RCC_APB1ENR_SPI2EN;
    RCC->AHB1ENR |= RCC_AHB1ENR_DMA1EN;
    
    // Reset SPI2
    SPI2->CR1 = 0;
    SPI2->CR2 = 0;
    
    // SPI2 Slave Mode 0 (CPOL=0, CPHA=0)
    SPI2->CR1 = 0;  // MSTR=0, CPOL=0, CPHA=0
    
    // Enable TX DMA và error interrupt
    SPI2->CR2 = (1 << 1) | (1 << 5);  // TXDMAEN | ERRIE
    
    // ===== Cấu hình DMA1 Stream4 Channel0 =====
    // Tắt stream trước khi config
    DMA1_Stream4->CR &= ~(1 << 0);
    while (DMA1_Stream4->CR & (1 << 0));
    
    // Địa chỉ peripheral: SPI2->DR (cố định)
    DMA1_Stream4->PAR = (uint32_t)(&SPI2->DR);
    
    // Địa chỉ memory: buffer (sẽ cập nhật sau)
    DMA1_Stream4->M0AR = (uint32_t)s_tx_buf;
    
    // Số byte truyền
    DMA1_Stream4->NDTR = SPI_TX_BUF_SIZE;
    
    // Cấu hình DMA stream
    DMA1_Stream4->CR = (0 << 25)    // CHSEL = 0 (Channel0)
                     | (1 << 16)    // PL = medium priority
                     | (0 << 13)    // MSIZE = 8-bit
                     | (0 << 11)    // PSIZE = 8-bit
                     | (1 << 10)    // MINC = 1 (tăng địa chỉ memory)
                     | (0 << 9)     // PINC = 0 (periph cố định)
                     | (1 << 6)     // DIR = Mem→Periph
                     | (1 << 4)     // TCIE = 1 (ngắt hoàn thành)
                     | (1 << 2);    // TEIE = 1 (ngắt lỗi)
    
    // Enable NVIC cho DMA
    NVIC_SetPriority(DMA1_Stream4_IRQn, 1);
    NVIC_EnableIRQ(DMA1_Stream4_IRQn);
    
    // Enable SPI2
    SPI2->CR1 |= (1 << 6);  // SPE = 1
}
```

Giải thích DMA config:

Bit Tên Giá trị Ý nghĩa
25-27 CHSEL 000 Channel 0 (SPI2_TX)
16-17 PL 01 Medium priority
13-14 MSIZE 00 Memory data size = 8-bit
11-12 PSIZE 00 Peripheral data size = 8-bit
10 MINC 1 Memory address tăng sau mỗi lần
9 PINC 0 Peripheral address cố định
6-7 DIR 01 Memory → Peripheral
4 TCIE 1 Bật ngắt transfer complete
2 TEIE 1 Bật ngắt transfer error

```c
void SPI_SetTxBuffer(uint8_t *buf, uint16_t size)
{
    // Copy dữ liệu vào buffer của SPI
    memcpy(s_tx_buf, buf, size);
    
    // Tắt DMA stream
    DMA1_Stream4->CR &= ~(1 << 0);
    while (DMA1_Stream4->CR & (1 << 0));
    
    // Cập nhật địa chỉ và số byte
    DMA1_Stream4->M0AR = (uint32_t)s_tx_buf;
    DMA1_Stream4->NDTR = SPI_TX_BUF_SIZE;
    
    // Bật DMA stream (sẵn sàng truyền khi NSS được kéo)
    DMA1_Stream4->CR |= (1 << 0);
}
```

---

5.5. Xử lý ngắt TIM2 (main.c)

```c
void TIM2_IRQHandler(void)
{
    uint32_t sr = TIM2->SR;  // Snapshot trạng thái
    
    // Xử lý từng kênh, chỉ lấy lần capture đầu tiên
    if ((sr & TIM_SR_CC1IF) && !(capture_flags & 0x01)) {
        sensor_data[0].timestamp = TIM2->CCR1;
        sensor_data[0].sensor_id = 'A';
        capture_flags |= 0x01;
    }
    
    if ((sr & TIM_SR_CC2IF) && !(capture_flags & 0x02)) {
        sensor_data[1].timestamp = TIM2->CCR2;
        sensor_data[1].sensor_id = 'B';
        capture_flags |= 0x02;
    }
    
    if ((sr & TIM_SR_CC3IF) && !(capture_flags & 0x04)) {
        sensor_data[2].timestamp = TIM2->CCR3;
        sensor_data[2].sensor_id = 'C';
        capture_flags |= 0x04;
    }
    
    if ((sr & TIM_SR_CC4IF) && !(capture_flags & 0x08)) {
        sensor_data[3].timestamp = TIM2->CCR4;
        sensor_data[3].sensor_id = 'D';
        capture_flags |= 0x08;
    }
    
    // Kiểm tra đã capture đủ 4 sensor chưa
    if (capture_flags == 0x0F) {
        TIM2->CR1 &= ~TIM_CR1_CEN;      // Dừng timer
        
        pack_spi_buffer();               // Đóng gói dữ liệu
        
        SPI_SetTxBuffer(spi_tx_buffer, sizeof(spi_tx_buffer));
        
        GPIO_DataReady_Set();            // PB0 = HIGH
        
        data_ready_flag = 1;             // Báo main loop
    }
    
    // Xóa cờ (ghi 1 vào bit cần xóa)
    TIM2->SR = sr;
}
```

Giải thích logic capture:

```
Thời điểm    Sự kiện                    capture_flags
─────────────────────────────────────────────────────────────
t = 0       Khởi tạo                    0b0000 (0x00)
t = 64,990  Sensor C kích hoạt          0b0100 (0x04)
t = 191,590 Sensor B kích hoạt          0b0110 (0x06)
t = 220,690 Sensor D kích hoạt          0b1110 (0x0E)
t = 284,790 Sensor A kích hoạt          0b1111 (0x0F) → trigger
```

Tại sao dùng bitmask?

· Ngăn chặn một sensor kích hoạt nhiều lần (do nhiễu hoặc phản xạ âm thanh).
· Nhanh hơn dùng mảng boolean.
· Kiểm tra "đủ 4 sensor" chỉ bằng phép so sánh capture_flags == 0x0F.

---

5.6. Đóng gói dữ liệu (main.c)

```c
static void pack_spi_buffer(void)
{
    for (int i = 0; i < 4; i++)
    {
        uint32_t ts = sensor_data[i].timestamp;
        
        // Format: [ID] [byte3] [byte2] [byte1] [byte0]
        // Big-endian: byte cao nhất gửi trước
        spi_tx_buffer[i * 5 + 0] = sensor_data[i].sensor_id;
        spi_tx_buffer[i * 5 + 1] = (ts >> 24) & 0xFF;  // Most significant
        spi_tx_buffer[i * 5 + 2] = (ts >> 16) & 0xFF;
        spi_tx_buffer[i * 5 + 3] = (ts >>  8) & 0xFF;
        spi_tx_buffer[i * 5 + 4] = ts & 0xFF;          // Least significant
    }
}
```

Ví dụ với timestamp của sensor C (64,990 = 0x0000FDDE):

Byte offset Giá trị Mô tả
10 (i=2*5) 'C' (67) ID
11 0x00 Byte cao nhất
12 0x00 
13 0xFD 
14 0xDE Byte thấp nhất

---

5.7. Vòng lặp chính (main.c)

```c
int main(void)
{
    SystemClock_Config();
    GPIO_Init();
    Timer_Init();
    SPI_Init();
    
    GPIO_DataReady_Clear();  // Đảm bảo PB0 = LOW lúc khởi động
    
    while (1)
    {
        // Reset trạng thái
        capture_flags = 0;
        data_ready_flag = 0;
        
        // Bắt đầu capture
        Timer_Start();
        
        // Chờ đủ 4 sensor hoặc timeout (khoảng 250ms)
        uint32_t timeout = 84000000 / 2;  // ~250ms @ 168MHz
        while (!data_ready_flag && timeout > 0) {
            timeout--;
        }
        
        if (!data_ready_flag) {
            // Timeout: không đủ 4 sensor
            Timer_Stop();
            GPIO_DataReady_Clear();
            simple_delay(168000);  // ~1ms
            continue;  // Thử lại
        }
        
        // Dữ liệu đã sẵn sàng, chờ RPi đọc qua SPI
        uint32_t spi_timeout = 84000000 / 5;  // ~200ms
        while (SPI_IsBusy() && spi_timeout > 0) {
            spi_timeout--;
        }
        
        // Kết thúc chu kỳ
        GPIO_DataReady_Clear();
        simple_delay(840000);  // ~5ms nghỉ trước khi capture tiếp
    }
}
```

Giải thích timeout:

Timeout Giá trị Thời gian thực Mục đích
timeout 84.000.000 / 2 = 42.000.000 ~250ms Chờ 4 sensor. Nếu quá lâu → có thể sensor hỏng hoặc không có âm thanh
spi_timeout 84.000.000 / 5 = 16.800.000 ~100ms Chờ RPi đọc dữ liệu. Nếu RPi chậm, vẫn tiếp tục chu kỳ mới
simple_delay(168000) 168.000 ~1ms Nghỉ ngắn trước khi retry
simple_delay(840000) 840.000 ~5ms Nghỉ giữa các chu kỳ capture

---

📦 Dạng dữ liệu gửi qua SPI

Tổng cộng 20 byte được gửi theo thứ tự A → B → C → D:

```
┌────────┬──────────────────────┬─────────────────────────────────────────┐
│ Byte   │ Nội dung             │ Giá trị trong ví dụ                      │
├────────┼──────────────────────┼─────────────────────────────────────────┤
│ 0      │ ID_A                 │ 'A' (0x41)                              │
│ 1-4    │ Timestamp A (BE)     │ 284,790 → 0x00 0x04 0x58 0x76           │
├────────┼──────────────────────┼─────────────────────────────────────────┤
│ 5      │ ID_B                 │ 'B' (0x42)                              │
│ 6-9    │ Timestamp B (BE)     │ 191,590 → 0x00 0x02 0xEC 0x26           │
├────────┼──────────────────────┼─────────────────────────────────────────┤
│ 10     │ ID_C                 │ 'C' (0x43)                              │
│ 11-14  │ Timestamp C (BE)     │ 64,990 → 0x00 0x00 0xFD 0xDE            │
├────────┼──────────────────────┼─────────────────────────────────────────┤
│ 15     │ ID_D                 │ 'D' (0x44)                              │
│ 16-19  │ Timestamp D (BE)     │ 220,690 → 0x00 0x03 0x5D 0x92           │
└────────┴──────────────────────┴─────────────────────────────────────────┘
```

Big-endian (BE) là gì?
Byte quan trọng nhất (MSB) được gửi trước.
Ví dụ: 0x00045876 được gửi thành: 0x00 → 0x04 → 0x58 → 0x76

---

⏱ Timing Diagram

```
TIM2 CNT ───────────────────────────────────────────────────────────────►
         │
292 tick │  Nguồn âm phát (bắt đầu truyền)
         │
64,990   │  █ Sensor C kích hoạt → ghi CCR3 = 64,990
         │
191,590  │      █ Sensor B kích hoạt → ghi CCR2 = 191,590
         │
220,690  │          █ Sensor D kích hoạt → ghi CCR4 = 220,690
         │
284,790  │              █ Sensor A kích hoạt → ghi CCR1 = 284,790
         │              │
         │              ├─ Dừng TIM2
         │              ├─ pack buffer (20 byte)
         │              ├─ Nạp DMA
         │              │
PB0 ─────┼──────────────┼─────────────────────────────────────────────
         │              │██████████████████████████████████████████████
         │              │
         │              ├─ RPi phát hiện PB0=HIGH
         │              ├─ Kéo NSS xuống
NSS ─────┼──────────────┼───────────────────┐
         │              │                   │ LOW
         │              │                   │
SCK ─────┼──────────────┼───────────────────┼─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─┐ ┌─
         │              │                   │ │ │ │ │ │ │ │ │ │ │ │ │
MISO ────┼──────────────┼───────────────────┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─┼─
         │              │                   │ID│ │TS│...│
         │              │                   │  │ │  │   │
PB0 ─────┼──────────────┼───────────────────┘
         │              │
         │              └─ DMA complete → main hạ PB0 xuống LOW
         │
         └────────────────────────────────────────────────────────────►
```

---

⚠ Xử lý lỗi và timeout

Timeout trong main loop

Trường hợp Nguyên nhân Cách xử lý
data_ready_flag = 0 sau timeout Chỉ có 1-3 sensor kích hoạt (nhiễu, âm thanh yếu, sensor hỏng) Dừng TIM2, hạ DATA_READY, delay 1ms rồi retry
SPI_IsBusy() vẫn = 1 sau timeout RPi không kéo NSS hoặc SPI master bị lỗi Vẫn hạ DATA_READY và bắt đầu chu kỳ mới (tránh treo)

Xử lý error trong SPI và DMA

```c
void SPI2_IRQHandler(void)
{
    uint32_t sr = SPI2->SR;
    
    // Overrun error: RPi gửi clock quá nhanh hoặc STM32 không kịp xử lý
    if (sr & (1 << 6)) {
        (void)SPI2->DR;  // Đọc DR để xóa cờ
        (void)SPI2->SR;
    }
    
    // Mode fault: xung đột nhiều master trên bus
    if (sr & (1 << 4)) {
        SPI2->CR1 &= ~(1 << 6);  // Tắt SPI
        SPI2->CR1 |= (1 << 6);   // Bật lại
    }
}
```

```c
void DMA1_Stream4_IRQHandler(void)
{
    uint32_t hisr = DMA1->HISR;
    
    if (hisr & (1 << 5)) {  // TCIF4: transfer complete
        DMA1->HIFCR = (1 << 5);  // Xóa cờ
        s_busy = 0;
    }
    
    if (hisr & (1 << 3)) {  // TEIF4: transfer error
        DMA1->HIFCR = (1 << 3);
        s_busy = 0;
    }
}
```

---

📊 Kết luận

Hệ thống hoạt động theo các bước chính:

1. Khởi tạo clock, GPIO, TIM2, SPI2, DMA.
2. Chờ âm thanh → TIM2 capture timestamp vào 4 sensor.
3. Khi đủ 4 sensor → dừng TIM2, đóng gói 20 byte.
4. Báo RPi qua DATA_READY (PB0 = HIGH).
5. RPi đọc dữ liệu qua SPI2 (DMA tự động truyền).
6. Kết thúc → hạ DATA_READY, reset trạng thái, lặp lại.

Độ chính xác định vị phụ thuộc vào:

· Tần số TIM2 (84 MHz → 11.9 ns/tick → sai số tối đa ±11.9 ns)
· Chất lượng mạch so sánh (tạo xung số)
· Sai số do vận tốc âm thanh thay đổi theo nhiệt độ, độ ẩm

Khả năng mở rộng:

· Có thể dùng 8 cảm biến (TIM3, TIM4, TIM5)
· Tăng tần số TIM2 lên 168MHz (bằng cách gắn TIM2 vào AHB thay vì APB1)
· Dùng giải thuật TDOA phức tạp hơn trên RPi

---

© 2026 - Dự án định vị âm thanh với STM32F407VG