dự án nâng cấp node , thay thế MCP3204 đã lỗi thời vì phá nhiều hơn làm, nên tôi quyết định thay thế nó bằng một thứ đắt hơn nhưng hiệu quả hơn.🎖️

Mình sẽ viết:
1. **STM32F407 Firmware** (Chi tiết, full implementation)
2. **Node.py** (Sửa để dùng STM32 thay MCP3204)

---

## **Phần 1: STM32F407 Firmware**

```c
/**
 * ============================================================================
 * STM32F407VG Firmware - Piezoelectric Timestamp Capture System
 * ============================================================================
 * 
 * 🎯 CHỨC NĂNG:
 * 1. Capture timestamp từ 4 Piezo sensors (PA0-PA3) bằng TIM2 (32-bit)
 * 2. Gửi dữ liệu qua SPI Slave (10MHz) khi nhận 4 xung
 * 3. Tín hiệu DATA_READY (PB0) báo RPi có dữ liệu sẵn sàng
 * 4. UART debug (USART1) để log/monitor
 * 
 * 📍 PIN ASSIGNMENT:
 * PA0 → TIM2_CH1 (Sensor A capture)
 * PA1 → TIM2_CH2 (Sensor B capture)
 * PA2 → TIM2_CH3 (Sensor C capture)
 * PA3 → TIM2_CH4 (Sensor D capture)
 * PB0 → GPIO Output (DATA_READY signal)
 * 
 * PA4 → SPI1_NSS (Chip Select from RPi)
 * PA5 → SPI1_CLK (Clock from RPi)
 * PA6 → SPI1_MISO (Data to RPi)
 * PA7 → SPI1_MOSI (Data from RPi, unused)
 * 
 * PA9  → USART1_TX (Debug logging)
 * PA10 → USART1_RX (Debug input, unused)
 * 
 * 🔧 HARDWARE:
 * - STM32F407VG @ 168MHz
 * - TIM2 @ 168MHz (5.95ns resolution)
 * - SPI1 @ 10.5MHz (16MHz max / 2)
 * - USART1 @ 115200 baud
 * ============================================================================
 */

#include "stm32f4xx.h"
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* ============================================================================
 * GLOBAL VARIABLES & STRUCTURES
 * ============================================================================ */

// ✓ Cấu trúc lưu timestamp của một sensor
typedef struct {
    uint8_t sensor_id;      // 'A', 'B', 'C', or 'D'
    uint32_t timestamp;     // 32-bit value từ TIM2
} SensorData_t;

// ✓ Mảng lưu 4 timestamp
SensorData_t sensor_data[4];

// ✓ Counter đếm số sensor đã capture
volatile uint8_t capture_count = 0;

// ✓ Flag báo dữ liệu sẵn sàng
volatile uint8_t data_ready_flag = 0;

// ✓ SPI buffer để gửi về RPi (16 bytes)
// Format: [ID_A][TS_A_3][TS_A_2][TS_A_1][TS_A_0]
//         [ID_B][TS_B_3][TS_B_2][TS_B_1][TS_B_0]
//         [ID_C][TS_C_3][TS_C_2][TS_C_1][TS_C_0]
//         [ID_D][TS_D_3][TS_D_2][TS_D_1][TS_D_0]
uint8_t spi_tx_buffer[20];  // 5 bytes per sensor × 4 sensors

// ✓ UART debug buffer
char uart_buffer[256];

/* ============================================================================
 * FUNCTION PROTOTYPES
 * ============================================================================ */

void system_init(void);
void gpio_init(void);
void timer_init(void);
void spi_init(void);
void uart_init(void);
void exti_init(void);

void tim2_interrupt_handler(void);
void spi_send_data(void);
void data_ready_signal(void);
void uart_print(const char *fmt, ...);

/* ============================================================================
 * INITIALIZATION FUNCTIONS
 * ============================================================================ */

/**
 * @brief System Clock Configuration
 * 
 * 🔧 HOẠT ĐỘNG:
 * - Setup HSE (High Speed External) crystal 8MHz
 * - PLL multiplier để đạt 168MHz
 * - APB1/APB2 prescaler để chia tần số
 */
void system_init(void) {
    // ✓ Enable Power Control clock
    RCC->APB1ENR |= RCC_APB1ENR_PWREN;
    
    // ✓ Set voltage regulator scale (để PLL 168MHz)
    PWR->CR |= PWR_CR_VOS;
    
    // ✓ Enable HSE (8MHz external oscillator)
    RCC->CR |= RCC_CR_HSEON;
    while (!(RCC->CR & RCC_CR_HSERDY));  // Chờ HSE stable
    
    // ✓ Configure PLL
    // PLL_VCO = (HSE_VALUE / PLL_M) × PLL_N
    //         = (8 / 8) × 336 = 336 MHz
    // PLLCLK = PLL_VCO / PLL_P
    //        = 336 / 2 = 168 MHz
    RCC->PLLCFGR = (RCC_PLLCFGR_PLLSRC_HSE |
                    (8 << RCC_PLLCFGR_PLLM_Pos) |      // M = 8
                    (336 << RCC_PLLCFGR_PLLN_Pos) |    // N = 336
                    (0 << RCC_PLLCFGR_PLLP_Pos) |      // P = 2
                    (7 << RCC_PLLCFGR_PLLQ_Pos));      // Q = 7
    
    // ✓ Enable PLL
    RCC->CR |= RCC_CR_PLLON;
    while (!(RCC->CR & RCC_CR_PLLRDY));  // Chờ PLL stable
    
    // ✓ Configure prescalers
    // AHB prescaler = 1 (168MHz)
    RCC->CFGR |= RCC_CFGR_HPRE_DIV1;
    
    // APB1 prescaler = 4 (42MHz) - cho Timer
    RCC->CFGR |= RCC_CFGR_PPRE1_DIV4;
    
    // APB2 prescaler = 2 (84MHz)
    RCC->CFGR |= RCC_CFGR_PPRE2_DIV2;
    
    // ✓ Switch system clock to PLL
    RCC->CFGR |= RCC_CFGR_SW_PLL;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL);
    
    uart_print("[SYS] Clock configured: 168MHz\n");
}

/**
 * @brief GPIO Initialization
 * 
 * 🔧 HOẠT ĐỘNG:
 * - PA0-3: Input (TIM2 capture)
 * - PA4-7: SPI pins
 * - PA9-10: UART pins
 * - PB0: Output (DATA_READY)
 */
void gpio_init(void) {
    // ✓ Enable GPIOA clock
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    
    // ✓ Enable GPIOB clock
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOBEN;
    
    // === CONFIGURE PA0-3 (TIM2 Input Capture) ===
    // PA0, PA1, PA2, PA3 → Mode: Alternate Function
    for (int i = 0; i < 4; i++) {
        // Set to AF mode (10)
        GPIOA->MODER |= (2 << (i * 2));
        // Set AF1 (TIM2)
        if (i < 2) {
            GPIOA->AFR[0] |= (1 << (i * 4));
        } else {
            GPIOA->AFR[1] |= (1 << ((i - 2) * 4));
        }
        // Pull-down resistor
        GPIOA->PUPDR |= (2 << (i * 2));
    }
    
    // === CONFIGURE PA4-7 (SPI1) ===
    // PA4 (NSS), PA5 (CLK), PA6 (MISO), PA7 (MOSI)
    for (int i = 4; i < 8; i++) {
        // Set to AF mode (10)
        GPIOA->MODER |= (2 << (i * 2));
        // Set AF5 (SPI1)
        GPIOA->AFR[1] |= (5 << ((i - 4) * 4));
        // Pull-down for CLK, MOSI
        if (i >= 5) {
            GPIOA->PUPDR |= (2 << (i * 2));
        }
    }
    
    // === CONFIGURE PA9-10 (USART1) ===
    // PA9 (TX), PA10 (RX)
    for (int i = 9; i < 11; i++) {
        // Set to AF mode (10)
        GPIOA->MODER |= (2 << (i * 2));
        // Set AF7 (USART1)
        GPIOA->AFR[1] |= (7 << ((i - 8) * 4));
        // Pull-up for RX
        if (i == 10) {
            GPIOA->PUPDR |= (1 << (i * 2));
        }
    }
    
    // === CONFIGURE PB0 (DATA_READY Output) ===
    // PB0 → Mode: Output (01)
    GPIOB->MODER |= (1 << 0);
    // Speed: High (11)
    GPIOB->OSPEEDR |= (3 << 0);
    // Output type: Push-pull (0)
    // Push-pull là default
    // Initial state: LOW
    GPIOB->ODR &= ~(1 << 0);
    
    uart_print("[GPIO] Initialized\n");
}

/**
 * @brief Timer 2 Initialization (32-bit, 4 Input Capture channels)
 * 
 * 🔧 HOẠT ĐỘNG:
 * - TIM2: 32-bit counter @ 168MHz
 * - CH1-CH4: Input Capture mode (rising edge)
 * - Resolution: 5.95ns per tick
 * 
 * 💡 TIMING:
 * - Prescaler: 0 (no divide, 168MHz)
 * - ARR (Auto-reload): 0xFFFFFFFF (32-bit max)
 * - Max time before overflow: ~25.6 seconds
 * - Per tick: 1/168MHz = 5.95ns
 */
void timer_init(void) {
    // ✓ Enable TIM2 clock
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
    
    // ✓ Set prescaler = 0 (168MHz clock)
    TIM2->PSC = 0;
    
    // ✓ Set auto-reload value (32-bit)
    TIM2->ARR = 0xFFFFFFFF;
    
    // ✓ Configure all 4 channels as Input Capture
    // CCMR1: Channel 1 & 2 configuration
    // CCMR2: Channel 3 & 4 configuration
    
    // Channel 1 (PA0): Input Capture, TI1 input
    TIM2->CCMR1 |= (1 << 0);  // CC1S = 01 (IC1 on TI1)
    // Rising edge
    TIM2->CCER &= ~(3 << 1);  // CC1P = 0, CC1NP = 0
    
    // Channel 2 (PA1): Input Capture, TI2 input
    TIM2->CCMR1 |= (1 << 8);  // CC2S = 01 (IC2 on TI2)
    TIM2->CCER &= ~(3 << 5);  // CC2P = 0, CC2NP = 0
    
    // Channel 3 (PA2): Input Capture, TI3 input
    TIM2->CCMR2 |= (1 << 0);  // CC3S = 01 (IC3 on TI3)
    TIM2->CCER &= ~(3 << 9);  // CC3P = 0, CC3NP = 0
    
    // Channel 4 (PA3): Input Capture, TI4 input
    TIM2->CCMR2 |= (1 << 8);  // CC4S = 01 (IC4 on TI4)
    TIM2->CCER &= ~(3 << 13); // CC4P = 0, CC4NP = 0
    
    // ✓ Enable capture for all channels
    TIM2->CCER |= (1 << 0);   // CC1E
    TIM2->CCER |= (1 << 4);   // CC2E
    TIM2->CCER |= (1 << 8);   // CC3E
    TIM2->CCER |= (1 << 12);  // CC4E
    
    // ✓ Enable interrupts for all channels
    TIM2->DIER |= (1 << 1);   // CC1IE
    TIM2->DIER |= (1 << 2);   // CC2IE
    TIM2->DIER |= (1 << 3);   // CC3IE
    TIM2->DIER |= (1 << 4);   // CC4IE
    
    // ✓ Enable Timer 2
    TIM2->CR1 |= (1 << 0);    // CEN
    
    // ✓ Configure NVIC for TIM2
    // TIM2 interrupt = 28
    NVIC_SetPriority(TIM2_IRQn, 0);  // Highest priority
    NVIC_EnableIRQ(TIM2_IRQn);
    
    uart_print("[TIM2] Initialized (168MHz, 5.95ns/tick)\n");
}

/**
 * @brief SPI1 Initialization (Slave Mode, 10.5MHz)
 * 
 * 🔧 HOẠT ĐỘNG:
 * - SPI1 Slave mode (nhận dữ liệu từ RPi master)
 * - Clock: 10.5MHz (APB2 84MHz / 8)
 * - Data width: 8-bit
 * - CPOL=0, CPHA=0 (Mode 0)
 * 
 * 💡 FLOW:
 * - RPi pull CS (PA4) low
 * - RPi send 20 bytes (đừng care nội dung)
 * - STM32 send 20 bytes từ spi_tx_buffer
 * - Interrupt trigger khi xong
 */
void spi_init(void) {
    // ✓ Enable SPI1 clock
    RCC->APB2ENR |= RCC_APB2ENR_SPI1EN;
    
    // ✓ Disable SPI trước khi config
    SPI1->CR1 &= ~(1 << 6);  // SPE = 0
    
    // === SPI1 Configuration ===
    uint32_t cr1 = 0;
    
    // Slave mode (MSTR = 0)
    cr1 |= (0 << 2);
    
    // Clock divider = 8 (84MHz / 8 = 10.5MHz)
    cr1 |= (3 << 3);  // BR = 011 (div by 8)
    
    // CPOL = 0, CPHA = 0 (Mode 0)
    cr1 |= (0 << 0);  // CPHA
    cr1 |= (0 << 1);  // CPOL
    
    // 8-bit data width (DFF = 0)
    cr1 |= (0 << 11);
    
    // Software NSS management
    cr1 |= (1 << 9);  // SSM = 1
    cr1 |= (1 << 8);  // SSI = 1
    
    // Rx interrupt enable
    cr1 |= (1 << 6);  // RXNEIE
    
    // Tx interrupt enable
    cr1 |= (1 << 7);  // TXEIE
    
    SPI1->CR1 = cr1;
    
    // ✓ Enable SPI1
    SPI1->CR1 |= (1 << 6);  // SPE = 1
    
    // ✓ Configure NVIC
    NVIC_SetPriority(SPI1_IRQn, 1);
    NVIC_EnableIRQ(SPI1_IRQn);
    
    uart_print("[SPI1] Initialized (Slave, 10.5MHz)\n");
}

/**
 * @brief USART1 Initialization (115200 baud)
 * 
 * 🔧 HOẠT ĐỘNG:
 * - USART1: 115200 baud, 8 data bits, 1 stop bit
 * - Dùng cho printf/debug logging
 * - PA9 (TX), PA10 (RX)
 */
void uart_init(void) {
    // ✓ Enable USART1 clock
    RCC->APB2ENR |= RCC_APB2ENR_USART1EN;
    
    // ✓ Set baud rate
    // BRR = fCLK / (16 × baud)
    // BRR = 84MHz / (16 × 115200) = 45.572 ≈ 46
    // Mantissa = 46, Fraction = 9
    uint32_t brr = 46;
    brr |= (9 << 0);  // Fraction = 9
    SPI1->CR1 = brr;
    
    // ✓ Configuration
    uint32_t cr1 = 0;
    cr1 |= (1 << 2);  // RE (Receiver Enable)
    cr1 |= (1 << 3);  // TE (Transmitter Enable)
    cr1 |= (0 << 12); // M = 0 (8 data bits)
    cr1 |= (1 << 13); // UE (UART Enable)
    
    USART1->CR1 = cr1;
    
    uart_print("[UART1] Initialized (115200 baud)\n");
}

/**
 * @brief External Interrupt Initialization (Not used, keep for reference)
 * 
 * 🔧 HOẠT ĐỘNG:
 * - TIM2 capture events don't need EXTI
 * - Timer interrupts handled by TIM2_IRQHandler
 */
void exti_init(void) {
    // Not needed - using TIM2 capture interrupts instead
}

/* ============================================================================
 * INTERRUPT HANDLERS
 * ============================================================================ */

/**
 * @brief TIM2 Interrupt Handler
 * 
 * 🔧 HOẠT ĐỘNG:
 * - Capture events từ TIM2_CH1/2/3/4 (PA0-3)
 * - Lưu timestamp vào sensor_data[] array
 * - Đếm số sensor đã capture (capture_count)
 * - Khi capture_count == 4:
 *   1. Gọi data_ready_signal() để kéo PB0 HIGH
 *   2. Set data_ready_flag = 1
 *   3. Chờ SPI read
 * 
 * 💡 TIMING:
 * - ISR latency: ~10-20 cycles (~60-120ns)
 * - Timestamp accuracy: ±60ns
 * 
 * ⚠️ LƯU Ý:
 * - ISR được gọi 4 lần (1 cho mỗi channel)
 * - Phải clear interrupt flag (SR register)
 * - Phải xử lý fast (< 1μs)
 */
void TIM2_IRQHandler(void) {
    // ✓ Check which channel triggered interrupt
    uint32_t status = TIM2->SR;
    
    // === CHANNEL 1 (Sensor A, PA0) ===
    if (status & TIM_SR_CC1IF) {
        // ✓ Capture value
        uint32_t timestamp = TIM2->CCR1;
        
        // ✓ Store in array
        sensor_data[0].sensor_id = 'A';
        sensor_data[0].timestamp = timestamp;
        
        // ✓ Increment counter
        capture_count++;
        
        // ✓ Clear interrupt flag
        TIM2->SR &= ~TIM_SR_CC1IF;
        
        // uart_print("[CH1] A: %lu\n", timestamp);
    }
    
    // === CHANNEL 2 (Sensor B, PA1) ===
    if (status & TIM_SR_CC2IF) {
        uint32_t timestamp = TIM2->CCR2;
        sensor_data[1].sensor_id = 'B';
        sensor_data[1].timestamp = timestamp;
        capture_count++;
        TIM2->SR &= ~TIM_SR_CC2IF;
        // uart_print("[CH2] B: %lu\n", timestamp);
    }
    
    // === CHANNEL 3 (Sensor C, PA2) ===
    if (status & TIM_SR_CC3IF) {
        uint32_t timestamp = TIM2->CCR3;
        sensor_data[2].sensor_id = 'C';
        sensor_data[2].timestamp = timestamp;
        capture_count++;
        TIM2->SR &= ~TIM_SR_CC3IF;
        // uart_print("[CH3] C: %lu\n", timestamp);
    }
    
    // === CHANNEL 4 (Sensor D, PA3) ===
    if (status & TIM_SR_CC4IF) {
        uint32_t timestamp = TIM2->CCR4;
        sensor_data[3].sensor_id = 'D';
        sensor_data[3].timestamp = timestamp;
        capture_count++;
        TIM2->SR &= ~TIM_SR_CC4IF;
        // uart_print("[CH4] D: %lu\n", timestamp);
    }
    
    // ✓ If all 4 sensors captured
    if (capture_count >= 4) {
        // Signal RPi that data is ready
        data_ready_signal();
        
        // Set flag for main loop
        data_ready_flag = 1;
        
        // Reset counter for next cycle
        capture_count = 0;
    }
}

/**
 * @brief SPI1 Interrupt Handler
 * 
 * 🔧 HOẠT ĐỘNG:
 * - Trigger khi RPi read dữ liệu
 * - Transmit 20 bytes từ spi_tx_buffer
 * - Clear DATA_READY signal sau khi transmit xong
 */
void SPI1_IRQHandler(void) {
    // ✓ Check if transmit complete
    if (SPI1->SR & (1 << 1)) {  // TXE (TX Empty)
        // Do nothing - data will be transmitted automatically
    }
    
    // ✓ Check if receive complete (shouldn't happen in slave Tx mode)
    if (SPI1->SR & (1 << 0)) {  // RXNE
        uint8_t dummy = SPI1->DR;  // Dummy read
    }
}

/* ============================================================================
 * HELPER FUNCTIONS
 * ============================================================================ */

/**
 * @brief Signal DATA_READY to RPi
 * 
 * 🔧 HOẠT ĐỘNG:
 * - Pull PB0 HIGH để báo RPi có dữ liệu
 * - Pack 4 timestamp vào spi_tx_buffer
 * - RPi sẽ trigger SPI read
 */
void data_ready_signal(void) {
    // ✓ Pack timestamps vào SPI buffer
    // Format: [ID_A][TS_A[3]][TS_A[2]][TS_A[1]][TS_A[0]]
    for (int i = 0; i < 4; i++) {
        spi_tx_buffer[i * 5 + 0] = sensor_data[i].sensor_id;
        spi_tx_buffer[i * 5 + 1] = (sensor_data[i].timestamp >> 24) & 0xFF;
        spi_tx_buffer[i * 5 + 2] = (sensor_data[i].timestamp >> 16) & 0xFF;
        spi_tx_buffer[i * 5 + 3] = (sensor_data[i].timestamp >> 8) & 0xFF;
        spi_tx_buffer[i * 5 + 4] = (sensor_data[i].timestamp >> 0) & 0xFF;
    }
    
    // ✓ Pull PB0 HIGH (DATA_READY)
    GPIOB->ODR |= (1 << 0);
    
    uart_print("[DATA] Ready - A:%lu B:%lu C:%lu D:%lu\n",
               sensor_data[0].timestamp,
               sensor_data[1].timestamp,
               sensor_data[2].timestamp,
               sensor_data[3].timestamp);
}

/**
 * @brief Print to UART (debug logging)
 * 
 * 🔧 HOẠT ĐỘNG:
 * - sprintf format string
 * - Gửi từng ký tự qua USART1
 */
void uart_print(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vsnprintf(uart_buffer, sizeof(uart_buffer), fmt, args);
    va_end(args);
    
    // ✓ Send to UART
    for (int i = 0; uart_buffer[i] && i < 255; i++) {
        // Wait for TX empty
        while (!(USART1->SR & (1 << 7)));
        USART1->DR = uart_buffer[i];
    }
}

/* ============================================================================
 * MAIN FUNCTION
 * ============================================================================ */

int main(void) {
    // ✓ System initialization
    system_init();
    
    // ✓ Peripheral initialization
    gpio_init();
    timer_init();
    spi_init();
    uart_init();
    
    uart_print("\n\n");
    uart_print("=====================================\n");
    uart_print("STM32F407VG Piezo Timestamp Capture\n");
    uart_print("=====================================\n");
    uart_print("Ready to capture sensors...\n");
    
    // ✓ Main loop
    while (1) {
        // ✓ Check if data ready
        if (data_ready_flag) {
            // Wait for SPI transmit (pull CS low)
            // Once CS is low, SPI transmission starts automatically
            
            // After SPI transmit complete
            // Pull DATA_READY low
            GPIOB->ODR &= ~(1 << 0);
            
            // Clear flag
            data_ready_flag = 0;
            
            uart_print("[TX] Data sent to RPi\n");
        }
        
        // ✓ Small delay to reduce busy-waiting
        for (volatile int i = 0; i < 1000; i++);
    }
    
    return 0;
}

/* ============================================================================
 * STARTUP CODE & VECTOR TABLE (Already in startup file, keep for reference)
 * ============================================================================ */

// Interrupt vector table will be handled by:
// - startup_stm32f407xx.s (ASM startup file)
// - linker script

```

---

## **Phần 2: Sửa Node.py (Loại Bỏ MCP3204)**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RPi Nano 2W Node - Sử dụng STM32F407 Thay MCP3204

🎯 THAY ĐỔI CHÍNH:
1. Loại bỏ hoàn toàn MCP3204 + SPI 1MHz
2. Thay bằng STM32F407 + SPI 10.5MHz
3. Đợi DATA_READY signal trước khi đọc SPI
4. Parse 20-byte buffer từ STM32

📍 PIN ASSIGNMENT (RPi Nano 2W):
GPIO17 (BCM) → DATA_READY input (từ STM32 PB0)
GPIO10 → MISO (SPI0)
GPIO9 → MOSI (SPI0)
GPIO11 → SCLK (SPI0)
GPIO8 → CE0 (CS)

Chương trình này chạy trên Raspberry Pi Nano 2W để:
1. Chờ DATA_READY signal từ STM32
2. Đọc 20 bytes timestamp từ STM32 qua SPI
3. Parse 4 timestamp từ 4 sensors
4. Tính toán tọa độ viên đạn (Hybrid method)
5. Gửi tọa độ về Controller qua LoRa
"""

# ==================== NHẬP THƯ VIỆN ====================

# ✓ Thư viện điều khiển GPIO trên Raspberry Pi
import RPi.GPIO as GPIO

# ✓ Thư viện làm việc với thời gian
import time

# ✓ Thư viện hệ thống
import sys

# ✓ Thư viện tính toán toán học
import math

# ✓ Thư viện giao tiếp SPI (thay vì spidev)
import spidev

# ✓ Thư viện LoRa để giao tiếp không dây
from rpi_lora import LoRa

# ✓ Cấu hình board cho LoRa module
from rpi_lora.board_config import BOARD

# ✓ Thư viện xử lý ngày giờ
from datetime import datetime

# ✓ Thư viện xử lý mảng số học (cho Hybrid triangulation)
import numpy as np

# ✓ Thư viện giải bài toán tối ưu (Hyperbolic refinement)
from scipy.optimize import least_squares

# ==================== CẤU HÌNH CHUNG ====================

# --- Cấu hình GPIO cho DATA_READY ---
# GPIO17: Input nhận tín hiệu DATA_READY từ STM32 (PB0)
DATA_READY_PIN = 17

# --- Cấu hình GPIO điều khiển motor ---
CONTROL_PIN = 20

# --- Cấu hình LoRa ---
LORA_FREQ = 915

# --- Cấu hình SPI cho STM32 ---
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED = 10500000  # 10.5MHz (STM32 SPI speed)

# --- Tọa độ các cảm biến trên bia ---
SENSOR_POSITIONS = {
    'A': (-50, -50),
    'B': (-50, 50),
    'C': (50, 50),
    'D': (50, -50),
}

# --- Cấu hình ngưỡng phát hiện viên đạn ---
# Không còn dùng nữa (STM32 auto-detect), nhưng giữ cho reference
IMPACT_THRESHOLD = 2000

# --- Cấu hình timing ---
DETECTION_DELAY = 0.01
SENSOR_DETECTION_WINDOW = 0.05
CONTROL_TIMEOUT = 60

# --- Tên Node ---
NODE_NAME = "NODE1A"

# --- Tốc độ âm thanh ---
SOUND_SPEED = 340

# --- Cấu hình STM32 timestamp ---
# TIM2 @ 168MHz → 5.95ns per tick
# 32-bit counter → max 25.6 seconds
STM32_CLK_FREQ = 168e6  # 168MHz
TICK_TO_SECONDS = 1.0 / STM32_CLK_FREQ  # 5.95ns per tick
TICK_TO_CM = SOUND_SPEED * 100 * TICK_TO_SECONDS  # cm per tick

# === CẤU HÌNH HYBRID TRIANGULATION ===
WEIGHTED_AVG_ITERATIONS = 10
WEIGHTED_AVG_LEARNING_RATE = 0.15
ENABLE_HYPERBOLIC = True
HYPERBOLIC_MAX_ITERATIONS = 100
HYPERBOLIC_TOLERANCE = 1e-6

# --- File log ---
LOG_FILE = "score.txt"

# ==================== KHỞI TẠO GPIO ====================

# ✓ Sử dụng chế độ BCM
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# --- Cấu hình DATA_READY pin ---
# GPIO17: Input từ STM32
GPIO.setup(DATA_READY_PIN, GPIO.IN)

# --- Cấu hình CONTROL pin ---
GPIO.setup(CONTROL_PIN, GPIO.OUT)
GPIO.output(CONTROL_PIN, GPIO.LOW)

# ==================== KHỞI TẠO SPI ====================

# ✓ Khởi tạo SPI
spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEVICE)
spi.max_speed_hz = SPI_SPEED

print(f"[INIT] SPI initialized at {SPI_SPEED / 1e6:.1f}MHz")

# ==================== KHỞI TẠO LoRa ====================

lora = LoRa(BOARD.CN1, BOARD.CN1)
lora.set_frequency(LORA_FREQ)

print(f"[INIT] LoRa initialized at {LORA_FREQ}MHz")

# ==================== BIẾN TRẠNG THÁI ====================

control_active = False
control_timeout = None
impact_count = 0
extra_mode_active = False
current_bia_type = "A"

# ==================== HÀM HỖ TRỢ ====================

def log_data(message):
    """
    Ghi dữ liệu vào file log và hiển thị trên console
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] {message}"
    print(log_message)
    
    with open(LOG_FILE, 'a') as f:
        f.write(log_message + "\n")

def read_stm32_timestamps():
    """
    Đọc 4 timestamp từ STM32 qua SPI
    
    🔧 HOẠT ĐỘNG:
    1. Gửi 20 bytes dummy (để STM32 send data)
    2. Nhận 20 bytes: [ID_A][TS_A_3][TS_A_2][TS_A_1][TS_A_0] ...
    3. Parse 4 × (1 + 4) bytes thành sensor data
    4. Chuyển đổi timestamp từ tick → giây
    
    📊 ĐỊNH DẠNG DỮ LIỆU:
    Bytes 0-4:   [ID_A] [TS_A[3]] [TS_A[2]] [TS_A[1]] [TS_A[0]]
    Bytes 5-9:   [ID_B] [TS_B[3]] [TS_B[2]] [TS_B[1]] [TS_B[0]]
    Bytes 10-14: [ID_C] [TS_C[3]] [TS_C[2]] [TS_C[1]] [TS_C[0]]
    Bytes 15-19: [ID_D] [TS_D[3]] [TS_D[2]] [TS_D[1]] [TS_D[0]]
    
    Trả về:
        dict: {'A': time_A, 'B': time_B, 'C': time_C, 'D': time_D}
        (thời gian tính từ khi Sensor A trigger)
    """
    
    try:
        # ✓ Gửi 20 bytes dummy (to trigger STM32 to send)
        # STM32 sẽ ignore input data, chỉ send output từ buffer
        response = spi.xfer2([0x00] * 20)
        
        # ✓ Parse 4 sensors (mỗi sensor 5 bytes)
        timestamps = {}
        
        for i in range(4):
            # Offset: i × 5 bytes
            offset = i * 5
            
            # Byte 0: Sensor ID (A, B, C, D)
            sensor_id = chr(response[offset])  # Convert to char
            
            # Bytes 1-4: 32-bit timestamp (big-endian)
            ts_raw = (response[offset + 1] << 24) | \
                     (response[offset + 2] << 16) | \
                     (response[offset + 3] << 8) | \
                     (response[offset + 4] << 0)
            
            # ✓ Chuyển đổi từ tick → giây
            # 168MHz = 168e6 tick/s
            # 1 tick = 1/168e6 s = 5.95ns
            ts_seconds = ts_raw * TICK_TO_SECONDS
            
            # ✓ Lưu vào dict
            timestamps[sensor_id] = ts_seconds
            
            # ℹ️ Debug log
            print(f"  [CH{i+1}] Sensor {sensor_id}: "
                  f"Raw={ts_raw}, Time={ts_seconds*1e6:.3f}μs")
        
        # ✓ Chuẩn hóa: lấy Sensor A làm tham chiếu (T=0)
        # Vì TDOA method tính từ chênh lệch thời gian
        if 'A' in timestamps:
            t_ref = timestamps['A']
            for key in timestamps:
                timestamps[key] -= t_ref
        
        return timestamps
    
    except Exception as e:
        print(f"[ERROR] Failed to read STM32: {e}")
        return None

def wait_for_data_ready(timeout=2.0):
    """
    Chờ DATA_READY signal từ STM32
    
    🔧 HOẠT ĐỘNG:
    1. Chờ GPIO17 chuyển từ LOW → HIGH
    2. Timeout nếu quá lâu
    3. Trả về True nếu nhận được signal
    
    💡 MỤC ĐÍCH:
    - Tránh polling liên tục
    - Chỉ đọc SPI khi STM32 có dữ liệu sẵn sàng
    - Giảm CPU usage + latency
    
    Tham số:
        timeout (float): Thời gian chờ tối đa (giây)
    
    Trả về:
        bool: True nếu nhận được DATA_READY, False nếu timeout
    """
    
    start_time = time.time()
    
    # ✓ Vòng lặp: chờ GPIO17 = HIGH
    while time.time() - start_time < timeout:
        # ✓ Kiểm tra GPIO17
        if GPIO.input(DATA_READY_PIN) == GPIO.HIGH:
            print(f"[DATA_READY] Signal received")
            
            # ✓ Nhỏ delay để STM32 chuẩn bị dữ liệu
            time.sleep(0.001)  # 1ms
            
            return True
        
        # ✓ Delay nhỏ để tránh busy-waiting
        time.sleep(0.001)  # 1ms polling interval
    
    # ❌ Timeout
    print(f"[ERROR] DATA_READY timeout ({timeout}s)")
    return False

def detect_impact():
    """
    Phát hiện viên đạn tác động vào bia (STM32 version)
    
    🔧 HOẠT ĐỘNG:
    1. Chờ DATA_READY signal từ STM32 (GPIO17)
    2. Khi HIGH, đọc 20 bytes từ SPI
    3. Parse 4 timestamp
    4. Trả về dict với thời gian phát hiện
    
    Trả về:
        dict: Thời gian phát hiện của mỗi sensor (giây)
              {'A': 0.0, 'B': 0.002, 'C': 0.003, 'D': 0.005}
              hoặc None nếu timeout
    """
    
    print("[SENSOR] Waiting for DATA_READY signal...")
    
    # ✓ Chờ DATA_READY từ STM32
    if wait_for_data_ready(timeout=SENSOR_DETECTION_WINDOW * 10):
        # ✓ Đọc dữ liệu từ STM32
        detections = read_stm32_timestamps()
        
        if detections:
            return detections
    
    print("[MISS] No impact detected")
    return None

def triangulation_weighted_average(detections):
    """
    BƯỚC 1: Ước tính nhanh bằng Weighted Average
    (Code giống như NODE-A, copy từ đó)
    """
    
    x = sum(pos[0] for pos in SENSOR_POSITIONS.values()) / 4
    y = sum(pos[1] for pos in SENSOR_POSITIONS.values()) / 4
    
    print(f"[HYBRID-STEP1] Weighted Average - Initial: ({x:.2f}, {y:.2f})")

    for iteration in range(WEIGHTED_AVG_ITERATIONS):
        total_weight = sum(1 / (detections[s] + 0.0001) 
                          for s in SENSOR_POSITIONS.keys())
        
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            weight = (1 / (detections[sensor_name] + 0.0001)) / total_weight
            dx = sx - x
            dy = sy - y
            x += dx * weight * WEIGHTED_AVG_LEARNING_RATE
            y += dy * weight * WEIGHTED_AVG_LEARNING_RATE

    x = max(-50, min(50, x))
    y = max(-50, min(50, y))
    
    print(f"[HYBRID-STEP1] Weighted Average - Final: ({x:.2f}, {y:.2f})")
    
    return x, y

def triangulation_hyperbolic_refinement(detections, x_init, y_init):
    """
    BƯỚC 2: Tinh chỉnh chính xác bằng Hyperbolic Least Squares
    (Code giống như NODE-A, copy từ đó)
    """
    
    print(f"[HYBRID-STEP2] Hyperbolic Refinement - Starting from ({x_init:.2f}, {y_init:.2f})")
    
    SOUND_SPEED_CMS = SOUND_SPEED * 100
    
    def residuals(pos):
        x_est, y_est = pos
        
        distances = {}
        for sensor_name, (sx, sy) in SENSOR_POSITIONS.items():
            distances[sensor_name] = np.sqrt((x_est - sx)**2 + (y_est - sy)**2)
        
        distance_diffs_measured = {}
        for sensor_name in SENSOR_POSITIONS.keys():
            time_diff = detections[sensor_name] - detections['A']
            distance_diffs_measured[sensor_name] = time_diff * SOUND_SPEED_CMS
        
        errors = []
        for sensor_name in ['B', 'C', 'D']:
            d_A = distances['A']
            d_sensor = distances[sensor_name]
            diff_theoretical = d_A - d_sensor
            diff_measured = distance_diffs_measured[sensor_name]
            error = diff_theoretical - diff_measured
            errors.append(error)
        
        return errors
    
    try:
        initial_guess = [x_init, y_init]
        
        result = least_squares(
            residuals,
            initial_guess,
            bounds=([-50, -50], [50, 50]),
            max_nfev=HYPERBOLIC_MAX_ITERATIONS,
            ftol=HYPERBOLIC_TOLERANCE,
            verbose=0
        )
        
        x_refined, y_refined = result.x
        
        print(f"[HYBRID-STEP2] Hyperbolic Refinement - Success!")
        print(f"[HYBRID-STEP2] Refined position: ({x_refined:.2f}, {y_refined:.2f})")
        
        return x_refined, y_refined
    
    except Exception as e:
        print(f"[HYBRID-STEP2] Hyperbolic Refinement failed: {e}")
        return x_init, y_init

def triangulation(detections):
    """
    Tính tọa độ viên đạn bằng phương pháp HYBRID
    (Code giống như NODE-A, copy từ đó)
    """
    
    try:
        print("[HYBRID] Starting triangulation (Hybrid method)...")
        
        x_weighted, y_weighted = triangulation_weighted_average(detections)
        
        if ENABLE_HYPERBOLIC:
            x_refined, y_refined = triangulation_hyperbolic_refinement(
                detections, 
                x_weighted, 
                y_weighted
            )
            x_final = x_refined
            y_final = y_refined
        else:
            print("[HYBRID] Hyperbolic refinement disabled, using Weighted Average")
            x_final = x_weighted
            y_final = y_weighted
        
        x_final = max(-50, min(50, x_final))
        y_final = max(-50, min(50, y_final))
        
        print(f"[HYBRID] Final result: ({x_final:.2f}, {y_final:.2f})")
        print("="*60)
        
        return round(x_final, 1), round(y_final, 1)

    except Exception as e:
        print(f"[ERROR] Triangulation failed: {e}")
        return None, None

# ==================== HÀM GỬIDỮ LIỆU ====================

def send_command(node_name, command):
    """
    Gửi lệnh điều khiển đến một Node qua LoRa
    """
    try:
        message = f"{node_name} {command}"
        lora.send(message.encode())
        log_data(f"[TX] Sent: {message}")
    except Exception as e:
        log_data(f"[ERROR] Failed to send: {e}")

def receive_data():
    """
    Nhận dữ liệu từ các Node qua LoRa
    """
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

def send_coordinates(x, y):
    """
    Gửi tọa độ viên đạn về Controller qua LoRa
    """
    try:
        message = f"{NODE_NAME}, {x}, {y}"
        lora.send(message.encode())
        print(f"[TX] Sent: {message}")
    except Exception as e:
        print(f"[ERROR] Failed to send: {e}")

# ==================== HÀM NHẬN LỆNH ====================

def receive_command():
    """
    Nhận lệnh từ Controller qua LoRa
    (Code giống như NODE-A, copy từ đó)
    """
    
    global control_active, control_timeout, impact_count, extra_mode_active, current_bia_type

    try:
        if lora.is_rx_busy():
            return None

        payload = lora.read()

        if payload:
            command = payload.decode().strip()
            print(f"[RX] Received: {command}")

            parts = command.split()

            if len(parts) >= 2:
                node_command = parts[0].upper()
                action = parts[1].upper()

                is_broadcast_extra = (node_command == "EXTRA")
                
                if is_broadcast_extra:
                    if action == "UP":
                        extra_mode_active = True
                        control_active = False
                        print(f"[EXTRA] Mode ON - GPIO {CONTROL_PIN} is HIGH")
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        return "EXTRA_ON"
                    
                    elif action == "DOWN":
                        extra_mode_active = False
                        control_active = False
                        print(f"[EXTRA] Mode OFF - GPIO {CONTROL_PIN} is LOW")
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        return "EXTRA_OFF"

                is_broadcast_a = (node_command == "A")
                
                if is_broadcast_a and not extra_mode_active:
                    current_bia_type = "A"
                    
                    if action == "UP":
                        control_active = True
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        impact_count = 0
                        print(f"[CONTROL] BROADCAST A UP - Activated")
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        control_active = False
                        print(f"[CONTROL] BROADCAST A DOWN - Deactivated")
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        return "DEACTIVATED"

                is_for_this_node = (node_command == NODE_NAME)
                
                if is_for_this_node and not extra_mode_active:
                    if action == "UP":
                        control_active = True
                        control_timeout = time.time() + CONTROL_TIMEOUT
                        impact_count = 0
                        print(f"[CONTROL] {node_command} UP - Activated")
                        GPIO.output(CONTROL_PIN, GPIO.HIGH)
                        return "ACTIVATED"
                    
                    elif action == "DOWN":
                        control_active = False
                        print(f"[CONTROL] {node_command} DOWN - Deactivated")
                        GPIO.output(CONTROL_PIN, GPIO.LOW)
                        return "DEACTIVATED"

    except Exception as e:
        print(f"[ERROR] Failed to receive command: {e}")

    return None

# ==================== VÒNG LẶP CHÍNH ====================

def main():
    """
    Vòng lặp chính của Node
    
    🔧 HOẠT ĐỘNG:
    1. Liên tục kiểm tra LoRa nhận lệnh
    2. Khi lệnh UP: bật GPIO 20, chờ DATA_READY từ STM32
    3. Khi DATA_READY: đọc timestamp từ STM32 qua SPI
    4. Tính toán tọa độ bằng Hybrid method
    5. Gửi tọa độ về Controller
    """
    
    global control_active, control_timeout, impact_count, extra_mode_active

    try:
        print("="*60)
        print(f"NODE STARTED - {NODE_NAME}")
        print("="*60)
        
        while True:
            # ✓ Nhận lệnh từ Controller
            receive_command()

            # ✓ Nếu điều khiển đang active
            if control_active and not extra_mode_active:
                
                # ✓ Kiểm tra timeout
                if time.time() > control_timeout:
                    control_active = False
                    GPIO.output(CONTROL_PIN, GPIO.LOW)
                    print("[TIMEOUT] Control timeout after 60s")
                
                else:
                    # ✓ Phát hiện viên đạn (chờ DATA_READY từ STM32)
                    detections = detect_impact()

                    if detections:
                        impact_count += 1
                        print(f"[IMPACT] Detection #{impact_count}")

                        # ✓ Tính toán tọa độ
                        x, y = triangulation(detections)

                        if x is not None and y is not None:
                            print(f"[RESULT] Position: x={x}, y={y}")
                            send_coordinates(x, y)

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

# ==================== CHẠY CHƯƠNG TRÌNH ====================

if __name__ == "__main__":
    main()
```

---

## **📋 SETUP GUIDE**

### **Phần Cứng**

```
STM32F407 ↔ RPi Nano 2W Connection:

STM32                RPi
──────────────────────────
PA0 (TIM2_CH1) → Sensor A
PA1 (TIM2_CH2) → Sensor B
PA2 (TIM2_CH3) → Sensor C
PA3 (TIM2_CH4) → Sensor D

PA4 (SPI1_NSS) → GPIO8 (CE0)
PA5 (SPI1_CLK) → GPIO11 (SCLK)
PA6 (SPI1_MISO) → GPIO9 (MISO)
PA7 (SPI1_MOSI) → GPIO10 (MOSI)

PB0 (DATA_READY) → GPIO17 (BCM)

GND ↔ GND (common)
VCC (3.3V) ← RPi 3.3V (hoặc power supply)
```

### **Lập Trình STM32**

```bash
# 1. Download STM32CubeIDE
wget https://www.st.com/en/development-tools/stm32cubeide.html

# 2. Tạo project mới
New → STM32 Project
Select: STM32F407VG
Board: STM32F407G Discovery

# 3. Copy code STM32 vào main.c

# 4. Build
Project → Build Project

# 5. Flash vào STM32
Run → Debug (hoặc Use ST-Link)
```

### **Cài Node.py**

```bash
# 1. Copy Node.py vào /opt
sudo cp node.py /opt/

# 2. Test
python3 /opt/node.py
```

---

## **🧪 TESTING CHECKLIST**

```
☑️ STM32 khởi động
☑️ UART debug: "Clock configured: 168MHz" ✓
☑️ TIM2: "Initialized (168MHz, 5.95ns/tick)" ✓
☑️ SPI1: "Initialized (Slave, 10.5MHz)" ✓

☑️ Trigger Sensor A
   - STM32 log: "[CH1] A: xxxx" ✓
   
☑️ Trigger Sensor B
   - STM32 log: "[CH2] B: xxxx" ✓
   
☑️ Trigger Sensor C
   - STM32 log: "[CH3] C: xxxx" ✓
   
☑️ Trigger Sensor D
   - STM32 log: "[CH4] D: xxxx" ✓

☑️ Tất cả 4 sensor trigger
   - STM32 log: "[DATA] Ready - A:xxx B:xxx C:xxx D:xxx" ✓
   - PB0 (DATA_READY) = HIGH ✓

☑️ RPi Node.py đang chạy
   - Nhận DATA_READY signal (GPIO17) ✓
   - Đọc SPI (20 bytes) ✓
   - Parse timestamp ✓
   
☑️ Tính toán TDOA
   - Triangulation (Hybrid) ✓
   - Kết quả tọa độ ✓
   
☑️ Gửi LoRa
   - Message đến Controller ✓
```

