/**
 * spi.c - SPI2 Slave + DMA TX (Bare-metal, STM32F407VG)
 * -------------------------------------------------------
 * STM32 = SPI SLAVE, RPi 5 = SPI MASTER
 *
 * Pins (config trong gpio.c):
 *   PB12 → SPI2_NSS  (AF05) – Hardware NSS từ RPi
 *   PB13 → SPI2_SCK  (AF05) – Clock từ RPi
 *   PB14 → SPI2_MISO (AF05) – STM32 → RPi
 *   PB15 → SPI2_MOSI (AF05) – RPi → STM32 (không dùng)
 *
 * Mode: SPI Mode 0 (CPOL=0, CPHA=0), 8-bit, MSB first
 * DMA:  DMA1 Stream4 Channel0 → SPI2_TX
 *
 * FIX: Thay toàn bộ macro _Pos / _Msk bằng bit shift trực tiếp,
 *      tương thích mọi phiên bản STM32F4 header.
 *
 * -------------------------------------------------------
 * SPI2 CR1 bit layout (dùng trong code này):
 *   bit0  = CPHA     bit1  = CPOL     bit2  = MSTR
 *   bit3  = BR[2:0]  (bit3–5)         bit6  = SPE
 *   bit7  = LSBFIRST bit8  = SSI      bit9  = SSM
 *   bit10 = RXONLY   bit11 = DFF      bit15 = BIDIMODE
 *
 * SPI2 CR2 bit layout:
 *   bit0  = RXDMAEN  bit1  = TXDMAEN  bit2  = SSOE
 *   bit5  = ERRIE    bit6  = RXNEIE   bit7  = TXEIE
 *
 * SPI2 SR bit layout:
 *   bit0  = RXNE     bit1  = TXE      bit6  = OVR
 *   bit4  = MODF     bit7  = BSY
 *
 * DMA1 SxCR bit layout (dùng trong code này):
 *   bit0  = EN       bit1  = DMEIE    bit2  = TEIE
 *   bit3  = HTIE     bit4  = TCIE     bit5  = PFCTRL
 *   bit6–7 = DIR     bit8  = CIRC     bit9  = PINC
 *   bit10 = MINC     bit11–12 = PSIZE bit13–14 = MSIZE
 *   bit16–17 = PL    bit25–27 = CHSEL
 * -------------------------------------------------------
 */

#include "../inc/spi.h"
#include "../inc/stm32f4xx.h"
#include <string.h>

/* ------------------------------------------------------------------ */
/* Internal state                                                       */
/* ------------------------------------------------------------------ */
#define SPI_TX_BUF_SIZE   20U    /* 4 sensor × 5 bytes */

static uint8_t          s_tx_buf[SPI_TX_BUF_SIZE];
static volatile uint8_t s_busy = 0U;

/* ------------------------------------------------------------------ */
void SPI_Init(void)
{
    /* ── 1. Bật clock SPI2 và DMA1 ──────────────────────────────── */
    RCC->APB1ENR |= RCC_APB1ENR_SPI2EN;
    RCC->AHB1ENR |= RCC_AHB1ENR_DMA1EN;
    __DSB();

    /* ── 2. Disable SPI2 trước khi config ───────────────────────── */
    SPI2->CR1 = 0U;
    SPI2->CR2 = 0U;

    /* ── 3. CR1 – SPI2 Slave Mode 0, 8-bit, MSB first ───────────── */
    /*
     * CPHA     = 0 → Capture on first (rising) edge
     * CPOL     = 0 → Clock idle LOW
     * MSTR     = 0 → SLAVE mode
     * BR[2:0]  = 0 → Không quan trọng với slave (clock từ master)
     * SPE      = 0 → Enable sau khi config xong
     * LSBFIRST = 0 → MSB first
     * SSI      = 0 → (không dùng vì SSM=0)
     * SSM      = 0 → Hardware NSS (PB12 điều khiển bởi RPi)
     * RXONLY   = 0 → Full duplex
     * DFF      = 0 → 8-bit data frame
     * BIDIMODE = 0 → 2-line unidirectional
     *
     * → CR1 = 0x0000 (tất cả 0)
     */
    SPI2->CR1 = 0U;

    /* ── 4. CR2 – Enable TX DMA + Error interrupt ────────────────── */
    /*
     * TXDMAEN = bit1 = 1 → DMA request khi TXE set
     * ERRIE   = bit5 = 1 → Interrupt khi OVR/MODF
     */
    SPI2->CR2 = (1U << 1U)    /* TXDMAEN */
              | (1U << 5U);   /* ERRIE   */

    /* ── 5. Cấu hình DMA1 Stream4 Channel0 (SPI2_TX) ────────────── */

    /* Tắt stream trước khi config (EN = bit0) */
    DMA1_Stream4->CR &= ~(1U << 0U);
    while (DMA1_Stream4->CR & (1U << 0U)) {}

    /* Xóa tất cả cờ interrupt của Stream4 trong HIFCR */
    /*
     * HIFCR layout (stream 4–7):
     *   Stream4: bit0=CFEIF4 bit2=CDMEIF4 bit3=CTEIF4
     *            bit4=CHTIF4 bit5=CTCIF4
     */
    DMA1->HIFCR = (1U << 0U)    /* CFEIF4  */
                | (1U << 2U)    /* CDMEIF4 */
                | (1U << 3U)    /* CTEIF4  */
                | (1U << 4U)    /* CHTIF4  */
                | (1U << 5U);   /* CTCIF4  */

    /* PAR: địa chỉ SPI2->DR (peripheral, fixed) */
    DMA1_Stream4->PAR  = (uint32_t)(&SPI2->DR);

    /* M0AR: địa chỉ TX buffer (memory) */
    DMA1_Stream4->M0AR = (uint32_t)s_tx_buf;

    /* NDTR: số byte */
    DMA1_Stream4->NDTR = SPI_TX_BUF_SIZE;

    /* FCR: Direct mode (disable FIFO = bit2 DMDIS = 0) */
    DMA1_Stream4->FCR  = 0U;

    /* SxCR config:
     *   CHSEL[2:0] = 000 → Channel 0      (bit25–27)
     *   PL[1:0]    = 01  → Medium priority (bit16–17)
     *   MSIZE[1:0] = 00  → 8-bit memory   (bit13–14)
     *   PSIZE[1:0] = 00  → 8-bit periph   (bit11–12)
     *   MINC       = 1   → Memory incr    (bit10)
     *   PINC       = 0   → Periph fixed   (bit9)
     *   CIRC       = 0   → No circular    (bit8)
     *   DIR[1:0]   = 01  → Mem→Periph     (bit6–7)
     *   TCIE       = 1   → TC interrupt   (bit4)
     *   TEIE       = 1   → TE interrupt   (bit2)
     *   EN         = 0   → Chưa enable    (bit0)
     */
    DMA1_Stream4->CR = (0U  << 25U)   /* CHSEL = 0 */
                     | (1U  << 16U)   /* PL = medium */
                     | (0U  << 13U)   /* MSIZE = 8-bit */
                     | (0U  << 11U)   /* PSIZE = 8-bit */
                     | (1U  << 10U)   /* MINC = 1 */
                     | (0U  << 9U)    /* PINC = 0 */
                     | (0U  << 8U)    /* CIRC = 0 */
                     | (1U  << 6U)    /* DIR = Mem→Periph */
                     | (1U  << 4U)    /* TCIE = 1 */
                     | (1U  << 2U);   /* TEIE = 1 */

    /* ── 6. NVIC ─────────────────────────────────────────────────── */
    NVIC_SetPriority(DMA1_Stream4_IRQn, 1U);
    NVIC_EnableIRQ(DMA1_Stream4_IRQn);

    NVIC_SetPriority(SPI2_IRQn, 1U);
    NVIC_EnableIRQ(SPI2_IRQn);

    /* ── 7. Enable SPI2 (SPE = bit6 của CR1) ────────────────────── */
    SPI2->CR1 |= (1U << 6U);
}

/* ------------------------------------------------------------------ */
void SPI_SetTxBuffer(uint8_t *buf, uint16_t size)
{
    if (size > SPI_TX_BUF_SIZE) size = SPI_TX_BUF_SIZE;

    memcpy(s_tx_buf, buf, size);
    if (size < SPI_TX_BUF_SIZE)
        memset(s_tx_buf + size, 0U, SPI_TX_BUF_SIZE - size);

    s_busy = 1U;

    /* Tắt DMA stream */
    DMA1_Stream4->CR &= ~(1U << 0U);   /* EN = 0 */
    while (DMA1_Stream4->CR & (1U << 0U)) {}

    /* Xóa cờ */
    DMA1->HIFCR = (1U << 0U) | (1U << 2U) | (1U << 3U)
                | (1U << 4U) | (1U << 5U);

    /* Cập nhật địa chỉ và số byte */
    DMA1_Stream4->M0AR = (uint32_t)s_tx_buf;
    DMA1_Stream4->NDTR = SPI_TX_BUF_SIZE;

    /* Xóa SPI OVR flag nếu có */
    (void)SPI2->DR;
    (void)SPI2->SR;

    /* Enable DMA stream → sẵn sàng khi RPi kéo NSS */
    DMA1_Stream4->CR |= (1U << 0U);   /* EN = 1 */
}

/* ------------------------------------------------------------------ */
uint8_t SPI_IsBusy(void)
{
    return s_busy;
}

/* ================================================================== */
/* DMA1 Stream4 IRQ – SPI2 TX Complete                                */
/* ================================================================== */
void DMA1_Stream4_IRQHandler(void)
{
    /*
     * HISR layout stream4:
     *   bit0=FEIF4  bit2=DMEIF4  bit3=TEIF4
     *   bit4=HTIF4  bit5=TCIF4
     */
    uint32_t hisr = DMA1->HISR;

    if (hisr & (1U << 5U))   /* TCIF4: Transfer complete */
    {
        DMA1->HIFCR = (1U << 5U);   /* CTCIF4 */

        /* Chờ SPI TX buffer trống (TXE = bit1 SR) */
        while (!(SPI2->SR & (1U << 1U))) {}
        /* Chờ SPI không còn busy (BSY = bit7 SR) */
        while (SPI2->SR & (1U << 7U)) {}

        s_busy = 0U;
    }

    if (hisr & (1U << 3U))   /* TEIF4: Transfer error */
    {
        DMA1->HIFCR = (1U << 3U);   /* CTEIF4 */
        s_busy = 0U;
    }
}

/* ================================================================== */
/* SPI2 IRQ – Error handling                                           */
/* ================================================================== */
void SPI2_IRQHandler(void)
{
    uint32_t sr = SPI2->SR;

    /* OVR (Overrun) = bit6 */
    if (sr & (1U << 6U))
    {
        (void)SPI2->DR;
        (void)SPI2->SR;
    }

    /* MODF (Mode fault) = bit4 → reset SPE (bit6 CR1) */
    if (sr & (1U << 4U))
    {
        SPI2->CR1 &= ~(1U << 6U);   /* SPE = 0 */
        SPI2->CR1 |=  (1U << 6U);   /* SPE = 1 */
    }
}
