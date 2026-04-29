/**
 * ============================================================================
 * config.h - STM32F407VG Bare Metal Configuration
 * ============================================================================
 *
 * 🎯 MỤC ĐÍCH:
 * Tập trung tất cả macro definitions – không phụ thuộc HAL.
 * Dễ dàng thay đổi cấu hình, phù hợp với ứng dụng bare metal.
 *
 * 📍 PIN ASSIGNMENT:
 * PA0-3 : TIM2_CH1..CH4 (Input Capture – Piezoelectric sensors)
 * PB12-15: SPI2 (NSS, SCK, MISO, MOSI) – Slave mode
 * PB0    : GPIO output (DATA_READY)
 *
 * ⏱️ TIMING:
 * - System clock : 168 MHz (HSE/PLL)
 * - AHB          : 168 MHz
 * - APB1         : 42 MHz  (prescaler = 4)
 * - TIM2 clock   : 84 MHz  (vì APB1 prescaler > 1 → x2)
 * - SPI2 clock   : do master (RPi) cung cấp, STM32 chạy slave
 */

#ifndef __CONFIG_H__
#define __CONFIG_H__

#include <stdint.h>

/* ============================================================================
 * SYSTEM CLOCK CONFIGURATION
 * ============================================================================ */
#define SYSTEM_CLOCK_HZ     168000000UL   // 168 MHz
#define AHB_PRESCALER       1             // AHB = SYSCLK
#define APB1_PRESCALER      4             // APB1 = 168/4 = 42 MHz
#define APB2_PRESCALER      2             // APB2 = 84 MHz (không dùng SPI2)

/* TIM2 được gắn trên APB1.
 * Nếu APB1 prescaler > 1, timer clock = APB1 × 2 = 42 × 2 = 84 MHz.
 */
#define TIM2_CLOCK_HZ       84000000UL    // 84 MHz

/* ============================================================================
 * GPIO CONFIGURATION
 * ============================================================================ */
/* DATA_READY – output, báo hiệu 4 sensor đã capture xong */
#define DATA_READY_PORT     GPIOB
#define DATA_READY_PIN      0

/* Các chân TIM2 input capture */
#define SENSOR_A_PORT       GPIOA
#define SENSOR_A_PIN        0

#define SENSOR_B_PORT       GPIOA
#define SENSOR_B_PIN        1

#define SENSOR_C_PORT       GPIOA
#define SENSOR_C_PIN        2

#define SENSOR_D_PORT       GPIOA
#define SENSOR_D_PIN        3

/* ============================================================================
 * TIM2 – 32-bit INPUT CAPTURE (84 MHz)
 * ============================================================================ */
#define TIMER_INSTANCE      TIM2
#define TIMER_FREQ_HZ       84000000UL

/* Độ phân giải mỗi tick (nanoseconds) : 1/84 MHz ≈ 11.9 ns */
#define TIMER_NS_PER_TICK   (1000000000UL / TIMER_FREQ_HZ)

/* Các kênh capture */
#define TIM_CH_A            TIM_CHANNEL_1
#define TIM_CH_B            TIM_CHANNEL_2
#define TIM_CH_C            TIM_CHANNEL_3
#define TIM_CH_D            TIM_CHANNEL_4

/* Timer 32-bit, giá trị max */
#define TIMER_MAX_VALUE     0xFFFFFFFFUL

/* ============================================================================
 * SPI2 CONFIGURATION – SLAVE MODE
 * ============================================================================ */
#define SPI_INSTANCE        SPI2

/* SPI2 chân trên PORT B:
 * PB12 – NSS   (chip select, từ master)
 * PB13 – SCK   (clock, từ master)
 * PB14 – MISO  (data từ STM32 → master)
 * PB15 – MOSI  (không dùng, có thể bỏ qua)
 */
#define SPI_NSS_PORT        GPIOB
#define SPI_NSS_PIN         12

#define SPI_SCK_PORT        GPIOB
#define SPI_SCK_PIN         13

#define SPI_MISO_PORT       GPIOB
#define SPI_MISO_PIN        14

#define SPI_MOSI_PORT       GPIOB
#define SPI_MOSI_PIN        15

/* SPI buffer: 20 bytes = 4 sensors × (1 ID + 4 timestamp bytes) */
#define SPI_BUFFER_SIZE     20

/* ============================================================================
 * UART (DEBUG) – KHÔNG BẮT BUỘC, tùy chọn
 * ============================================================================ */
/* Giữ lại để tiện debug, có thể bỏ comment nếu dùng */
//#define UART_DEBUG_ENABLE

#ifdef UART_DEBUG_ENABLE
#define UART_INSTANCE       USART1
#define UART_TX_PORT        GPIOA
#define UART_TX_PIN         9
#define UART_RX_PORT        GPIOA
#define UART_RX_PIN         10
#define UART_BAUDRATE       115200
#define UART_TX_BUFFER_SIZE 256
#endif

/* ============================================================================
 * DATA STRUCTURE
 * ============================================================================ */
typedef struct {
    uint8_t sensor_id;      // 'A', 'B', 'C', 'D'
    uint32_t timestamp;     // giá trị TIM2 counter (84 MHz ticks)
} SensorTimestamp_t;

/* ============================================================================
 * FUNCTION PROTOTYPES (các hàm cần định nghĩa trong file .c)
 * ============================================================================ */
void SystemClock_Config(void);
void GPIO_Init(void);
void Timer_Init(void);
void SPI_Init(void);
void UART_Init(void);               // nếu dùng debug

void TIM2_IRQHandler(void);
void SPI2_IRQHandler(void);
void UART_IRQHandler(void);         // nếu dùng debug

void OnSensorCapture(uint8_t sensor_id, uint32_t timestamp);
void OnDataReady(void);

void UART_Print(const char *format, ...);   // nếu dùng debug

#endif /* __CONFIG_H__ */