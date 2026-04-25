

## **Phần 1: inc/config.h - Cấu Hình Chung**

```c
/**
 * ============================================================================
 * config.h - STM32F407VG Global Configuration
 * ============================================================================
 * 
 * 🎯 MỤC ĐÍCH:
 * Tập trung tất cả macro definitions và configurations
 * Dễ dàng thay đổi cấu hình mà không cần sửa nhiều file
 * 
 * 📍 PIN ASSIGNMENT:
 * PA0-3: TIM2 Input Capture (Sensor A-D)
 * PA4-7: SPI1 (NSS, CLK, MISO, MOSI)
 * PA9-10: USART1 (TX, RX)
 * PB0: GPIO Output (DATA_READY)
 * 
 * ⏱️ TIMING:
 * - System clock: 168MHz
 * - TIM2: 168MHz (5.95ns resolution)
 * - SPI1: 10.5MHz
 * - UART1: 115200 baud
 */

#ifndef __CONFIG_H__
#define __CONFIG_H__

#include <stdint.h>

/* ============================================================================
 * SYSTEM CLOCK CONFIGURATION
 * ============================================================================ */

// ✓ System clock frequency (Hz)
// STM32F407 được cấu hình để chạy ở 168MHz
#define SYSTEM_CLOCK_HZ     168000000UL

// ✓ AHB prescaler: 1 (không chia)
// AHB clock = 168MHz
#define AHB_PRESCALER       1

// ✓ APB1 prescaler: 4 (chia 4)
// APB1 clock = 168MHz / 4 = 42MHz
// Dùng cho Timer, UART, SPI (chế độ slow)
#define APB1_PRESCALER      4

// ✓ APB2 prescaler: 2 (chia 2)
// APB2 clock = 168MHz / 2 = 84MHz
// Dùng cho SPI1 (chế độ fast)
#define APB2_PRESCALER      2

// ✓ Timer clock (dùng cho TIM2)
// TIM2 được gắn vào APB1
// APB1 = 42MHz, nhưng Timer được nhân x2 nếu APB1_PRESCALER > 1
// TIM2_CLK = 42MHz × 2 = 84MHz... KHÔNG ĐÚNG!
// Thực tế: TIM2_CLK = SYSTEM_CLOCK = 168MHz (auto adjust)
#define TIM2_CLOCK_HZ       SYSTEM_CLOCK_HZ

/* ============================================================================
 * GPIO CONFIGURATION
 * ============================================================================ */

// ✓ DATA_READY output pin (PB0)
// Kéo HIGH khi có 4 sensor capture
#define DATA_READY_PORT     GPIOB
#define DATA_READY_PIN      0

// ✓ Sensor A input (PA0)
#define SENSOR_A_PORT       GPIOA
#define SENSOR_A_PIN        0

// ✓ Sensor B input (PA1)
#define SENSOR_B_PORT       GPIOA
#define SENSOR_B_PIN        1

// ✓ Sensor C input (PA2)
#define SENSOR_C_PORT       GPIOA
#define SENSOR_C_PIN        2

// ✓ Sensor D input (PA3)
#define SENSOR_D_PORT       GPIOA
#define SENSOR_D_PIN        3

/* ============================================================================
 * TIMER CONFIGURATION (TIM2 - 32-bit Input Capture)
 * ============================================================================ */

// ✓ Timer số (TIM2 = timer số 2)
#define TIMER_INSTANCE      TIM2

// ✓ Timer clock frequency
// TIM2 chạy ở 168MHz (full system clock)
// Không prescaler, full resolution
#define TIMER_FREQ_HZ       168000000UL

// ✓ Resolution per tick (nanoseconds)
// 1 tick = 1 / 168MHz = 5.952 ns
#define TIMER_NS_PER_TICK   ((1000000000UL) / TIMER_FREQ_HZ)

// ✓ Input Capture channels
// CH1: Sensor A (PA0)
// CH2: Sensor B (PA1)
// CH3: Sensor C (PA2)
// CH4: Sensor D (PA3)
#define TIM_CH_A            TIM_CHANNEL_1
#define TIM_CH_B            TIM_CHANNEL_2
#define TIM_CH_C            TIM_CHANNEL_3
#define TIM_CH_D            TIM_CHANNEL_4

// ✓ Max timer value (32-bit)
#define TIMER_MAX_VALUE     0xFFFFFFFFUL

/* ============================================================================
 * SPI CONFIGURATION (SPI1 - Slave Mode)
 * ============================================================================ */

// ✓ SPI instance
#define SPI_INSTANCE        SPI1

// ✓ SPI pins
// PA4: NSS (Chip Select) từ RPi
// PA5: CLK (Clock) từ RPi
// PA6: MISO (Master In, Slave Out) → data tới RPi
// PA7: MOSI (Master Out, Slave In) → data từ RPi (unused)
#define SPI_NSS_PORT        GPIOA
#define SPI_NSS_PIN         4

#define SPI_CLK_PORT        GPIOA
#define SPI_CLK_PIN         5

#define SPI_MISO_PORT       GPIOA
#define SPI_MISO_PIN        6

#define SPI_MOSI_PORT       GPIOA
#define SPI_MOSI_PIN        7

// ✓ SPI baudrate
// APB2 = 84MHz, prescaler = 8
// SPI_CLK = 84MHz / 8 = 10.5MHz
// Phải khớp với RPi SPI speed (10.5MHz)
#define SPI_BAUDRATE_PRESCALER  SPI_BaudRatePrescaler_8

// ✓ SPI buffer size (20 bytes = 4 sensors × 5 bytes each)
// Format: [ID] [TS_3] [TS_2] [TS_1] [TS_0]
#define SPI_BUFFER_SIZE     20

/* ============================================================================
 * UART CONFIGURATION (USART1 - Debug Logging)
 * ============================================================================ */

// ✓ UART instance
#define UART_INSTANCE       USART1

// ✓ UART pins
// PA9: TX (Transmit) → tới RPi serial
// PA10: RX (Receive) từ RPi serial
#define UART_TX_PORT        GPIOA
#define UART_TX_PIN         9

#define UART_RX_PORT        GPIOA
#define UART_RX_PIN         10

// ✓ UART baud rate
// 115200 bps (standard debug speed)
#define UART_BAUDRATE       115200

// ✓ UART buffer size (debug messages)
#define UART_TX_BUFFER_SIZE 256

/* ============================================================================
 * DATA STRUCTURE
 * ============================================================================ */

// ✓ Cấu trúc lưu timestamp một sensor
typedef struct {
    uint8_t sensor_id;      // 'A', 'B', 'C', 'D'
    uint32_t timestamp;     // 32-bit timer value
} SensorTimestamp_t;

/* ============================================================================
 * FUNCTION PROTOTYPES (Các hàm được define ở file khác)
 * ============================================================================ */

// ✓ System init
void SystemClock_Config(void);
void GPIO_Init(void);
void Timer_Init(void);
void SPI_Init(void);
void UART_Init(void);

// ✓ Interrupt handlers
void TIM2_IRQHandler(void);
void SPI1_IRQHandler(void);
void UART_IRQHandler(void);

// ✓ Callback functions
void OnSensorCapture(uint8_t sensor_id, uint32_t timestamp);
void OnDataReady(void);

// ✓ Utility
void UART_Print(const char *format, ...);

#endif // __CONFIG_H__
```

---

## **Phần 2: inc/system.h - System Prototypes**

```c
/**
 * system.h - System initialization functions
 */

#ifndef __SYSTEM_H__
#define __SYSTEM_H__

#include <stdint.h>

// ✓ Prototypes
void SystemClock_Config(void);      // Setup system clock to 168MHz
void NVIC_Config(void);              // Configure interrupts

// ✓ Clock frequency (filled by SystemClock_Config)
extern uint32_t SystemCoreClock;

#endif // __SYSTEM_H__
```

---

## **Phần 3: inc/gpio.h - GPIO Prototypes**

```c
/**
 * gpio.h - GPIO configuration functions
 */

#ifndef __GPIO_H__
#define __GPIO_H__

// ✓ Prototypes
void GPIO_Init(void);               // Initialize all GPIO pins
void GPIO_DataReady_Set(void);      // Set DATA_READY (PB0 = HIGH)
void GPIO_DataReady_Clear(void);    // Clear DATA_READY (PB0 = LOW)

#endif // __GPIO_H__
```

---

## **Phần 4: inc/timer.h - Timer Prototypes**

```c
/**
 * timer.h - Timer capture functions
 */

#ifndef __TIMER_H__
#define __TIMER_H__

#include <stdint.h>

// ✓ Prototypes
void Timer_Init(void);              // Initialize TIM2 input capture
uint32_t Timer_GetValue(void);      // Get current timer value
void Timer_Start(void);             // Start timer
void Timer_Stop(void);              // Stop timer

#endif // __TIMER_H__
```

---

## **Phần 5: inc/spi.h - SPI Prototypes**

```c
/**
 * spi.h - SPI slave mode functions
 */

#ifndef __SPI_H__
#define __SPI_H__

#include <stdint.h>

// ✓ Prototypes
void SPI_Init(void);                // Initialize SPI1 slave mode
void SPI_SetTxBuffer(uint8_t *buf, uint16_t size);  // Set TX buffer
uint8_t SPI_IsBusy(void);           // Check if SPI is transmitting

#endif // __SPI_H__
```

---

## **Phần 6: inc/uart.h - UART Prototypes**

```c
/**
 * uart.h - UART debug functions
 */

#ifndef __UART_H__
#define __UART_H__

// ✓ Prototypes
void UART_Init(void);               // Initialize USART1
void UART_Print(const char *fmt, ...);  // Printf-like debug logging
void UART_SendChar(char c);         // Send single character

#endif // __UART_H__
```

---

## **Phần 7: inc/stm32f407xx.h - STM32 Register Definitions**

Đây là file cấu hình register STM32. Vì file quá dài (5000+ dòng), mình sẽ cung cấp **phiên bản rút gọn** chỉ cần thiết cho dự án:

```c
/**
 * stm32f407xx.h - STM32F407 Register Definitions (MINIMAL VERSION)
 * 
 * ⚠️ LƯU Ý: Đây là phiên bản rút gọn chỉ cần thiết
 * Để có đầy đủ, bạn cần lấy file từ:
 * - STM32CubeIDE
 * - GitHub: STMicroelectronics/STM32F4xx_HAL_Driver
 * 
 * File này define tất cả register addresses + bit definitions
 */

#ifndef __STM32F407XX_H__
#define __STM32F407XX_H__

#include <stdint.h>

/* ============================================================================
 * MEMORY MAPPING - Base addresses
 * ============================================================================ */

// ✓ Peripheral base addresses
#define GPIOA_BASE          0x40020000
#define GPIOB_BASE          0x40020400
#define GPIOC_BASE          0x40020800
#define GPIOD_BASE          0x40020C00
#define GPIOE_BASE          0x40021000

#define RCC_BASE            0x40023800
#define NVIC_BASE           0xE000E000

#define TIM2_BASE           0x40000000
#define TIM3_BASE           0x40000400
#define TIM4_BASE           0x40000800
#define TIM5_BASE           0x40000C00

#define SPI1_BASE           0x40013000
#define SPI2_BASE           0x40003800
#define SPI3_BASE           0x40003C00

#define USART1_BASE         0x40011000
#define USART2_BASE         0x40004400
#define USART3_BASE         0x40004800

#define EXTI_BASE           0x40013C00
#define SYSCFG_BASE         0x40013800

/* ============================================================================
 * GPIO REGISTER STRUCTURE
 * ============================================================================ */

typedef struct {
    volatile uint32_t MODER;        // Mode register (offset 0x00)
    volatile uint32_t OTYPER;       // Output type (offset 0x04)
    volatile uint32_t OSPEEDR;      // Output speed (offset 0x08)
    volatile uint32_t PUPDR;        // Pull-up/pull-down (offset 0x0C)
    volatile uint32_t IDR;          // Input data (offset 0x10)
    volatile uint32_t ODR;          // Output data (offset 0x14)
    volatile uint32_t BSRR;         // Bit set/reset (offset 0x18)
    volatile uint32_t LCKR;         // Lock (offset 0x1C)
    volatile uint32_t AFR[2];       // Alternate function (offset 0x20, 0x24)
} GPIO_TypeDef;

// ✓ GPIO instances
#define GPIOA ((GPIO_TypeDef *) GPIOA_BASE)
#define GPIOB ((GPIO_TypeDef *) GPIOB_BASE)
#

typedef struct {
    volatile uint32_t CR;           // Clock control (offset 0x00)
    volatile uint32_t PLLCFGR;      // PLL configuration (offset 0x04)
    volatile uint32_t CFGR;         // Clock configuration (offset 0x08)
    volatile uint32_t CIR;          // Clock interrupt (offset 0x0C)
    volatile uint32_t AHB1RSTR;     // AHB1 reset (offset 0x10)
    volatile uint32_t AHB2RSTR;     // AHB2 reset (offset 0x14)
    volatile uint32_t AHB3RSTR;     // AHB3 reset (offset 0x18)
    uint32_t RESERVED0;
    volatile uint32_t APB1RSTR;     // APB1 reset (offset 0x20)
    volatile uint32_t APB2RSTR;     // APB2 reset (offset 0x24)
    uint32_t RESERVED1[2];
    volatile uint32_t AHB1ENR;      // AHB1 enable (offset 0x30)
    volatile uint32_t AHB2ENR;      // AHB2 enable (offset 0x34)
    volatile uint32_t AHB3ENR;      // AHB3 enable (offset 0x38)
    uint32_t RESERVED2;
    volatile uint32_t APB1ENR;      // APB1 enable (offset 0x40)
    volatile uint32_t APB2ENR;      // APB2 enable (offset 0x44)
} RCC_TypeDef;

#define RCC ((RCC_TypeDef *) RCC_BASE)

// ✓ RCC enable bits
#define RCC_AHB1ENR_GPIOAEN         (1 << 0)
#define RCC_AHB1ENR_GPIOBEN         (1 << 1)
#define RCC_APB1ENR_TIM2EN          (1 << 0)
#define RCC_APB1ENR_USART2EN        (1 << 17)
#define RCC_APB2ENR_SPI1EN          (1 << 12)
#define RCC_APB2ENR_USART1EN        (1 << 4)
#define RCC_APB2ENR_SYSCFGEN        (1 << 14)

/* ============================================================================
 * TIMER REGISTER STRUCTURE
 * ============================================================================ */

typedef struct {
    volatile uint32_t CR1;          // Control 1 (offset 0x00)
    volatile uint32_t CR2;          // Control 2 (offset 0x04)
    volatile uint32_t SMCR;         // Slave mode (offset 0x08)
    volatile uint32_t DIER;         // Interrupt enable (offset 0x0C)
    volatile uint32_t SR;           // Status (offset 0x10)
    volatile uint32_t EGR;          // Event generation (offset 0x14)
    volatile uint32_t CCMR1;        // Capture/compare 1 (offset 0x18)
    volatile uint32_t CCMR2;        // Capture/compare 2 (offset 0x1C)
    volatile uint32_t CCER;         // Capture/compare enable (offset 0x20)
    volatile uint32_t CNT;          // Counter (offset 0x24)
    volatile uint32_t PSC;          // Prescaler (offset 0x28)
    volatile uint32_t ARR;          // Auto-reload (offset 0x2C)
    uint32_t RESERVED0;
    volatile uint32_t CCR1;         // Capture/compare 1 (offset 0x34)
    volatile uint32_t CCR2;         // Capture/compare 2 (offset 0x38)
    volatile uint32_t CCR3;         // Capture/compare 3 (offset 0x3C)
    volatile uint32_t CCR4;         // Capture/compare 4 (offset 0x40)
} TIM_TypeDef;

#define TIM2 ((TIM_TypeDef *) TIM2_BASE)

// ✓ Timer control bits
#define TIM_CR1_CEN         (1 << 0)    // Counter enable
#define TIM_DIER_CC1IE      (1 << 1)    // Capture/compare 1 interrupt
#define TIM_DIER_CC2IE      (1 << 2)
#define TIM_DIER_CC3IE      (1 << 3)
#define TIM_DIER_CC4IE      (1 << 4)
#define TIM_SR_CC1IF        (1 << 1)    // Capture/compare 1 interrupt flag
#define TIM_SR_CC2IF        (1 << 2)
#define TIM_SR_CC3IF        (1 << 3)
#define TIM_SR_CC4IF        (1 << 4)

/* ============================================================================
 * SPI REGISTER STRUCTURE
 * ============================================================================ */

typedef struct {
    volatile uint32_t CR1;          // Control 1 (offset 0x00)
    volatile uint32_t CR2;          // Control 2 (offset 0x04)
    volatile uint32_t SR;           // Status (offset 0x08)
    volatile uint32_t DR;           // Data (offset 0x0C)
    volatile uint32_t CRCPR;        // CRC poly (offset 0x10)
    volatile uint32_t RXCRCR;       // RX CRC (offset 0x14)
    volatile uint32_t TXCRCR;       // TX CRC (offset 0x18)
} SPI_TypeDef;

#define SPI1 ((SPI_TypeDef *) SPI1_BASE)

// ✓ SPI control bits
#define SPI_CR1_CPHA        (1 << 0)    // Clock phase
#define SPI_CR1_CPOL        (1 << 1)    // Clock polarity
#define SPI_CR1_MSTR        (1 << 2)    // Master selection
#define SPI_CR1_BR_Pos      3           // Baud rate position
#define SPI_CR1_BR_Msk      (0x7 << 3)
#define SPI_CR1_SPE         (1 << 6)    // SPI enable
#define SPI_CR1_LSBFIRST    (1 << 7)    // LSB first
#define SPI_CR1_SSI         (1 << 8)    // Internal slave select
#define SPI_CR1_SSM         (1 << 9)    // Software slave select
#define SPI_SR_RXNE         (1 << 0)    // RX not empty
#define SPI_SR_TXE          (1 << 1)    // TX empty
#define SPI_SR_BSY          (1 << 7)    // Busy flag

/* ============================================================================
 * USART REGISTER STRUCTURE
 * ============================================================================ */

typedef struct {
    volatile uint32_t SR;           // Status (offset 0x00)
    volatile uint32_t DR;           // Data (offset 0x04)
    volatile uint32_t BRR;          // Baud rate (offset 0x08)
    volatile uint32_t CR1;          // Control 1 (offset 0x0C)
    volatile uint32_t CR2;          // Control 2 (offset 0x10)
    volatile uint32_t CR3;          // Control 3 (offset 0x14)
} USART_TypeDef;

#define USART1 ((USART_TypeDef *) USART1_BASE)

// ✓ USART control bits
#define USART_SR_RXNE       (1 << 5)    // RX not empty
#define USART_SR_TXE        (1 << 7)    // TX empty
#define USART_CR1_RE        (1 << 2)    // Receiver enable
#define USART_CR1_TE        (1 << 3)    // Transmitter enable
#define USART_CR1_UE        (1 << 13)   // USART enable

/* ============================================================================
 * NVIC (Nested Vectored Interrupt Controller)
 * ============================================================================ */

typedef struct {
    volatile uint32_t ISER[8];      // Interrupt set enable
    uint32_t RESERVED0[24];
    volatile uint32_t ICER[8];      // Interrupt clear enable
    uint32_t RESERVED1[24];
    volatile uint32_t ISPR[8];      // Interrupt set pending
    uint32_t RESERVED2[24];
    volatile uint32_t ICPR[8];      // Interrupt clear pending
    uint32_t RESERVED3[24];
    volatile uint32_t IABR[8];      // Interrupt active bit
    uint32_t RESERVED4[56];
    volatile uint8_t IP[240];       // Interrupt priority
} NVIC_Type;

#define NVIC ((NVIC_Type *) NVIC_BASE)

/* ============================================================================
 * INTERRUPT VECTOR NUMBERS
 * ============================================================================ */

#define TIM2_IRQn           28
#define SPI1_IRQn           35
#define USART1_IRQn         37

#endif // __STM32F407XX_H__
```

---

## **Phần 8: src/system.c - System Clock & Init**

```c
/**
 * system.c - System initialization and clock configuration
 * 
 * 🔧 HOẠT ĐỘNG:
 * 1. Khởi tạo HSE (High Speed External) oscillator 8MHz
 * 2. Setup PLL để tăng lên 168MHz
 * 3. Config prescaler cho AHB, APB1, APB2
 * 4. Disable HSI (High Speed Internal) để tiết kiệm power
 */

#include "stm32f407xx.h"
#include "config.h"

// ✓ System core clock (được fill bởi SystemClock_Config)
uint32_t SystemCoreClock = SYSTEM_CLOCK_HZ;

/**
 * SystemClock_Config - Configure system clock to 168MHz
 * 
 * 🔧 QUY TRÌNH:
 * 1. Enable HSE (8MHz external crystal)
 * 2. Setup PLL:
 *    - Input: 8MHz HSE
 *    - M (prescaler): 8 → 1MHz
 *    - N (multiplier): 336 → 336MHz
 *    - P (main prescaler): 2 → 168MHz
 *    - Q (USB prescaler): 7 → 48MHz
 * 3. Enable PLL
 * 4. Switch system clock to PLL
 * 5. Setup prescaler (AHB, APB1, APB2)
 */
void SystemClock_Config(void) {
    // ✓ Enable Power Control Clock
    // RCC_APB1ENR bit 28 = Power control clock enable
    RCC->APB1ENR |= (1 << 28);
    
    // ✓ Set voltage regulator scale
    // Cần VOS (voltage output scale) = 11 để hỗ trợ 168MHz
    // Đây là register trong PWR (Power control)
    // Bước này không essential nếu không stress test
    
    // === STEP 1: Enable HSE (High Speed External) ===
    // RCC_CR bit 16 = HSEON (HSE oscillator enable)
    RCC->CR |= (1 << 16);
    
    // ✓ Wait for HSE to stabilize
    // RCC_CR bit 17 = HSERDY (HSE ready)
    while ((RCC->CR & (1 << 17)) == 0);  // Chờ HSE stable
    
    // === STEP 2: Configure PLL ===
    // RCC_PLLCFGR: (offset 0x04)
    // Bits [27:24] PLLQ = Q divider for USB/SDIO
    // Bits [16:0]  PLLP = P divider (main output)
    // Bits [14:6]  PLLN = N multiplier
    // Bits [5:0]   PLLM = M prescaler
    
    uint32_t pllcfgr = 0;
    
    // PLLM = 8 (bits 5:0)
    // HSE / PLLM = 8MHz / 8 = 1MHz
    pllcfgr |= 8;
    
    // PLLN = 336 (bits 14:6)
    // 1MHz × 336 = 336MHz
    pllcfgr |= (336 << 6);
    
    // PLLP = 2 (bits 17:16)
    // 336MHz / 2 = 168MHz (main output)
    // Note: PLLP value = (N+1), so we want 2 = 0 in register
    pllcfgr |= (0 << 16);  // PLLP = 2
    
    // PLLQ = 7 (bits 27:24)
    // 336MHz / 7 = 48MHz (for USB)
    pllcfgr |= (7 << 24);
    
    // PLLSRC = 1 (bit 22) - select HSE as PLL input
    pllcfgr |= (1 << 22);
    
    // ✓ Write PLL config
    RCC->PLLCFGR = pllcfgr;
    
    // === STEP 3: Enable PLL ===
    // RCC_CR bit 24 = PLLON (PLL enable)
    RCC->CR |= (1 << 24);
    
    // ✓ Wait for PLL to lock
    // RCC_CR bit 25 = PLLRDY (PLL ready)
    while ((RCC->CR & (1 << 25)) == 0);  // Chờ PLL lock
    
    // === STEP 4: Configure prescaler ===
    uint32_t cfgr = 0;
    
    // AHB prescaler = 1 (HPRE bits 7:4)
    // SYSCLK / 1 = 168MHz
    cfgr |= (0 << 4);  // HPRE = 0 (prescaler 1)
    
    // APB1 prescaler = 4 (PPRE1 bits 12:10)
    // AHB / 4 = 168 / 4 = 42MHz
    cfgr |= (5 << 10);  // PPRE1 = 101 (prescaler 4)
    
    // APB2 prescaler = 2 (PPRE2 bits 15:13)
    // AHB / 2 = 168 / 2 = 84MHz
    cfgr |= (4 << 13);  // PPRE2 = 100 (prescaler 2)
    
    // ✓ Switch system clock to PLL (SW bits 1:0)
    // SW = 10 means select PLL as system clock
    cfgr |= (2 << 0);  // SW = 10
    
    // ✓ Write config
    RCC->CFGR = cfgr;
    
    // ✓ Wait for clock switch to complete
    // SWS bits 3:2 should show current clock source
    while ((RCC->CFGR & (3 << 2)) != (2 << 2));
    
    // === STEP 5: Update SystemCoreClock ===
    SystemCoreClock = SYSTEM_CLOCK_HZ;
}

/**
 * NVIC_Config - Configure Nested Vectored Interrupt Controller
 * 
 * 🔧 HOẠT ĐỘNG:
 * Enable interrupts cho:
 * - TIM2 (IRQn 28)
 * - SPI1 (IRQn 35)
 * - USART1 (IRQn 37)
 */
void NVIC_Config(void) {
    // ✓ Enable TIM2 interrupt (IRQn 28)
    // ISER0 = bit 28 (vì IRQn < 32)
    NVIC->ISER[0] |= (1 << 28);
    
    // ✓ Enable SPI1 interrupt (IRQn 35)
    // ISER1 = bit (35 - 32) = bit 3
    NVIC->ISER[1] |= (1 << 3);
    
    // ✓ Enable USART1 interrupt (IRQn 37)
    // ISER1 = bit (37 - 32) = bit 5
    NVIC->ISER[1] |= (1 << 5);
    
    // ✓ Set interrupt priorities (optional)
    // IP register stores priority for each interrupt
    // Lower number = higher priority
    // Each interrupt has 4 bits (0-15)
    
    // TIM2 priority = 0 (highest, capture must be fast)
    NVIC->IP[28] = 0 << 4;
    
    // SPI1 priority = 1
    NVIC->IP[35] = 1 << 4;
    
    // USART1 priority = 2
    NVIC->IP[37] = 2 << 4;
}
```

