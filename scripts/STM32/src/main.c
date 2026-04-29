/**
 * ============================================================================
 * STM32F407VG Firmware - Piezoelectric Timestamp Capture System
 * ============================================================================
 *
 * CHỨC NĂNG:
 *   1. Capture timestamp từ 4 Piezo sensors qua TIM2 (32-bit, 168MHz)
 *   2. Gửi dữ liệu qua SPI2 Slave (DMA) khi đủ 4 xung
 *   3. PB0 (DATA_READY) báo RPi có dữ liệu sẵn sàng
 *
 * PIN ASSIGNMENT:
 *   PA0 → TIM2_CH1  (Sensor A – AF01)
 *   PA1 → TIM2_CH2  (Sensor B – AF01)
 *   PA2 → TIM2_CH3  (Sensor C – AF01)
 *   PA3 → TIM2_CH4  (Sensor D – AF01)
 *   PB0 → DATA_READY output (GPIO)
 *   PB12 → SPI2_NSS  (AF05)
 *   PB13 → SPI2_SCK  (AF05)
 *   PB14 → SPI2_MISO (AF05)
 *   PB15 → SPI2_MOSI (AF05)
 *
 * TX PACKET FORMAT (20 bytes, big-endian per sensor):
 *   Byte  0     : Sensor ID ('A')
 *   Byte  1– 4  : Timestamp A (uint32_t, big-endian)
 *   Byte  5     : Sensor ID ('B')
 *   Byte  6– 9  : Timestamp B
 *   Byte 10     : Sensor ID ('C')
 *   Byte 11–14  : Timestamp C
 *   Byte 15     : Sensor ID ('D')
 *   Byte 16–19  : Timestamp D
 *
 * HARDWARE:
 *   STM32F407VG @ 168MHz (HCLK)
 *   TIM2 @ 84MHz (APB1×2), PSC=0 → 1 tick = 11.9 ns
 *   SPI2 Slave (DMA1 Stream4 CH0)
 * ============================================================================
 */

#include "../inc/stm32f4xx.h"
#include "../inc/system.h"
#include "../inc/gpio.h"
#include "../inc/timmer.h"
#include "../inc/spi.h"

#include <stdint.h>
#include <string.h>

/* ============================================================================
 * TYPES & GLOBAL VARIABLES
 * ============================================================================ */

/** Cấu trúc lưu timestamp của một sensor (giữ nguyên từ main.c cũ) */
typedef struct {
    uint8_t  sensor_id;    /* 'A', 'B', 'C', 'D' */
    uint32_t timestamp;    /* 32-bit TIM2 capture value (84MHz, PSC=0 → 11.9ns/tick) */
} SensorData_t;

/** Mảng 4 sensor – index 0='A', 1='B', 2='C', 3='D' */
static volatile SensorData_t sensor_data[4];

/**
 * Cờ từng kênh đã capture (bitmask thay vì counter
 * để tránh đếm trùng nếu 2 kênh trigger gần nhau).
 * bit0=CH1(A), bit1=CH2(B), bit2=CH3(C), bit3=CH4(D)
 */
static volatile uint8_t capture_flags = 0x00;

/** 1 khi đủ 4 kênh – main loop xử lý rồi clear về 0 */
static volatile uint8_t data_ready_flag = 0;

/** TX buffer gửi qua SPI2 DMA (20 bytes, 5 bytes/sensor) */
static uint8_t spi_tx_buffer[20];

/* ============================================================================
 * FORWARD DECLARATIONS
 * ============================================================================ */
static void pack_spi_buffer(void);
static void simple_delay(volatile uint32_t count);

/* ============================================================================
 * TIM2 IRQ HANDLER
 * ============================================================================
 *
 * Ghi chú thiết kế:
 *  - Snapshot SR một lần đầu ISR để xử lý nhất quán.
 *  - Dùng bitmask (capture_flags) – không bao giờ đếm trùng một kênh.
 *  - Đọc CCRx để xóa cờ CCxIF (hardware clear on read).
 *  - Khi đủ 4 kênh: dừng TIM2, pack buffer, kích DMA, set DATA_READY.
 *  - Xóa SR bằng ghi 0 trực tiếp vào bit (tránh read-modify-write
 *    có thể xóa nhầm cờ khác đến sau).
 */
void TIM2_IRQHandler(void)
{
    uint32_t sr = TIM2->SR;

    /* ── CH1 → Sensor A (PA0 / TIM2_CH1) ────────────────────── */
    if ((sr & TIM_SR_CC1IF) && !(capture_flags & 0x01))
    {
        sensor_data[0].sensor_id = 'A';
        sensor_data[0].timestamp = TIM2->CCR1;  /* đọc CCR → xóa CC1IF */
        capture_flags |= 0x01;
    }
    else if (sr & TIM_SR_CC1IF)
    {
        (void)TIM2->CCR1;   /* bỏ qua lần 2, chỉ xóa cờ */
    }

    /* ── CH2 → Sensor B (PA1 / TIM2_CH2) ────────────────────── */
    if ((sr & TIM_SR_CC2IF) && !(capture_flags & 0x02))
    {
        sensor_data[1].sensor_id = 'B';
        sensor_data[1].timestamp = TIM2->CCR2;
        capture_flags |= 0x02;
    }
    else if (sr & TIM_SR_CC2IF)
    {
        (void)TIM2->CCR2;
    }

    /* ── CH3 → Sensor C (PA2 / TIM2_CH3) ────────────────────── */
    if ((sr & TIM_SR_CC3IF) && !(capture_flags & 0x04))
    {
        sensor_data[2].sensor_id = 'C';
        sensor_data[2].timestamp = TIM2->CCR3;
        capture_flags |= 0x04;
    }
    else if (sr & TIM_SR_CC3IF)
    {
        (void)TIM2->CCR3;
    }

    /* ── CH4 → Sensor D (PA3 / TIM2_CH4) ────────────────────── */
    if ((sr & TIM_SR_CC4IF) && !(capture_flags & 0x08))
    {
        sensor_data[3].sensor_id = 'D';
        sensor_data[3].timestamp = TIM2->CCR4;
        capture_flags |= 0x08;
    }
    else if (sr & TIM_SR_CC4IF)
    {
        (void)TIM2->CCR4;
    }

    /* ── Kiểm tra đủ 4 kênh ──────────────────────────────────── */
    if (capture_flags == 0x0F)
    {
        /* Dừng timer ngay – không capture thêm */
        TIM2->CR1 &= ~TIM_CR1_CEN;

        /* Pack TX buffer (5 bytes/sensor × 4 = 20 bytes) */
        pack_spi_buffer();

        /* Nạp vào SPI DMA – sẵn sàng stream khi RPi kéo NSS */
        SPI_SetTxBuffer(spi_tx_buffer, sizeof(spi_tx_buffer));

        /* PB0 HIGH → báo RPi có dữ liệu */
        GPIO_DataReady_Set();

        /* Báo main loop */
        data_ready_flag = 1;
    }

    /* Xóa toàn bộ cờ SR đã snapshot */
    TIM2->SR = ~sr;
}

/* ============================================================================
 * PACK SPI BUFFER
 * ============================================================================
 * Giữ đúng format 5 bytes/sensor của main.c cũ (big-endian timestamp):
 *   [i*5 + 0] = sensor_id
 *   [i*5 + 1] = timestamp byte cao nhất
 *   [i*5 + 4] = timestamp byte thấp nhất
 */
static void pack_spi_buffer(void)
{
    for (int i = 0; i < 4; i++)
    {
        uint32_t ts = sensor_data[i].timestamp;
        spi_tx_buffer[i * 5 + 0] = sensor_data[i].sensor_id;
        spi_tx_buffer[i * 5 + 1] = (uint8_t)((ts >> 24) & 0xFF);
        spi_tx_buffer[i * 5 + 2] = (uint8_t)((ts >> 16) & 0xFF);
        spi_tx_buffer[i * 5 + 3] = (uint8_t)((ts >>  8) & 0xFF);
        spi_tx_buffer[i * 5 + 4] = (uint8_t)( ts        & 0xFF);
    }
}

/* ============================================================================
 * SIMPLE DELAY
 * ============================================================================
 * Blocking delay đơn giản dùng cho reset cycle và retry.
 * CPU chạy @ 168MHz: ~1ms ≈ 168000 NOP iterations.
 * (TIM2 chạy @ 84MHz nhưng CPU vẫn 168MHz → delay không đổi)
 */
static void simple_delay(volatile uint32_t count)
{
    while (count--) __NOP();
}

/* ============================================================================
 * MAIN
 * ============================================================================ */
int main(void)
{
    /* ── 1. Clock hệ thống → 168MHz ──────────────────────────── */
    SystemClock_Config();

    /* ── 2. NVIC priorities tổng thể ────────────────────────── */
    /*
     * NVIC_Config() trong system.c đã enable IRQ cho TIM2 và SPI2.
     * gpio.c / timer.c / spi.c cũng tự NVIC_EnableIRQ() từng ngoại vi,
     * nên gọi NVIC_Config() ở đây để đảm bảo priorities nhất quán.
     */
    NVIC_Config();

    /* ── 3. Khởi tạo ngoại vi ────────────────────────────────── */
    GPIO_Init();    /* PA0–PA3 AF01(TIM2), PB0 OUT, PB12–15 AF05(SPI2) */
    Timer_Init();   /* TIM2 32-bit, 84MHz, PSC=0 → 11.9ns/tick, IC 4 kênh */
    SPI_Init();     /* SPI2 Slave, DMA1 Stream4 CH0, 8-bit Mode0 */

    /* Đảm bảo DATA_READY LOW khi boot */
    GPIO_DataReady_Clear();

    /* ── 4. Main loop ─────────────────────────────────────────── */
    while (1)
    {
        /* Reset state trước mỗi chu kỳ */
        capture_flags   = 0x00;
        data_ready_flag = 0;

        /* Start TIM2 – Timer_Start() reset CNT, xóa SR, bật CEN */
        Timer_Start();

        /* ── Chờ ISR báo đủ 4 kênh (timeout ~500ms) ─────────── */
        /*
         * 500ms ở 168MHz ≈ 84 000 000 / 2 loop iterations.
         * Mỗi iteration __NOP() ≈ 1 cycle, thực tế loop overhead
         * khoảng 3–5 cycles → timeout thực ~100–170ms, đủ an toàn.
         */
        uint32_t timeout = 84000000UL / 2;
        while (!data_ready_flag && timeout > 0)
        {
            timeout--;
        }

        if (!data_ready_flag)
        {
            /*
             * Timeout: không đủ 4 sensor kích hoạt.
             * Có thể là nhiễu chỉ kích hoạt 1–3 kênh, hoặc bắn trượt.
             * Dừng timer, hạ DATA_READY (phòng trường hợp ISR đã set),
             * nghỉ 1ms rồi retry.
             */
            Timer_Stop();
            GPIO_DataReady_Clear();
            simple_delay(168000UL);   /* ~1ms */
            continue;
        }

        /*
         * Tới đây ISR đã hoàn tất:
         *   ✓ TIM2 đã dừng
         *   ✓ spi_tx_buffer đã packed
         *   ✓ DMA đã được nạp và enable
         *   ✓ PB0 = HIGH (DATA_READY)
         *
         * Main chờ RPi kéo NSS, DMA stream xong.
         */

        /* ── Chờ DMA SPI truyền xong (timeout ~200ms) ───────── */
        uint32_t spi_timeout = 84000000UL / 5;
        while (SPI_IsBusy() && spi_timeout > 0)
        {
            spi_timeout--;
        }

        /* ── Hạ DATA_READY – kết thúc chu kỳ ───────────────── */
        GPIO_DataReady_Clear();

        /* Nghỉ ~5ms cho RPi xử lý TDOA trước khi capture tiếp */
        simple_delay(840000UL);   /* ~5ms @ 168MHz */
    }

    return 0;
}
