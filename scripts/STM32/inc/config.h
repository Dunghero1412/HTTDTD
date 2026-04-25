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