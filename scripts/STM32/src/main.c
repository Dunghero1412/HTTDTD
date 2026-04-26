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

#include "../inc/stm32f4xx.h"
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
