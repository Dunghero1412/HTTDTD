/**
 * spi.c - SPI2 Slave mode + DMA TX (Bare-metal, STM32F407VG)
 * ------------------------------------------------------------
 * STM32 là SLAVE, RPi 5 là MASTER.
 *
 * Pins (đã config trong gpio.c):
 *   PB12 → SPI2_NSS  (AF05) – Hardware NSS, slave select từ RPi
 *   PB13 → SPI2_SCK  (AF05) – Clock từ RPi
 *   PB14 → SPI2_MISO (AF05) – STM32 gửi dữ liệu → RPi
 *   PB15 → SPI2_MOSI (AF05) – RPi gửi dữ liệu → STM32 (không dùng)
 *
 * Mode: SPI Mode 0 (CPOL=0, CPHA=0) – phổ biến nhất với RPi
 * Frame: 8-bit, MSB first
 * DMA:   DMA1 Stream 4, Channel 0 → SPI2_TX
 *
 * Luồng hoạt động:
 *   1. main() gọi SPI_SetTxBuffer() với dữ liệu timestamp
 *   2. PB0 (DATA_READY) set HIGH → báo RPi
 *   3. RPi kéo NSS LOW và clock data ra
 *   4. DMA tự động stream TX buffer qua MISO
 *   5. Khi DMA xong → DMA interrupt → SPI_IsBusy() = 0
 *
 * Cấu trúc TX packet (16 bytes):
 *   [0..3]   : timestamp CH1 (uint32_t, little-endian)
 *   [4..7]   : timestamp CH2
 *   [8..11]  : timestamp CH3
 *   [12..15] : timestamp CH4
 */

#include "../inc/spi.h"
#include "../inc/stm32f4xx.h"
#include <string.h>

/* ------------------------------------------------------------------ */
/* Internal state                                                       */
/* ------------------------------------------------------------------ */
#define SPI_TX_BUF_SIZE   16U

static uint8_t  s_tx_buf[SPI_TX_BUF_SIZE];
static volatile uint8_t s_busy = 0;

/* ------------------------------------------------------------------ */
void SPI_Init(void)
{
    /* ── 1. Bật clock SPI2 và DMA1 ──────────────────────────────── */
    RCC->APB1ENR |= RCC_APB1ENR_SPI2EN;
    RCC->AHB1ENR |= RCC_AHB1ENR_DMA1EN;
    __DSB();

    /* ── 2. Reset SPI2 ───────────────────────────────────────────── */
    SPI2->CR1 = 0;
    SPI2->CR2 = 0;

    /* ── 3. Cấu hình SPI2 CR1 ────────────────────────────────────── */
    /*
     * BIDIMODE = 0  → 2-line unidirectional
     * DFF      = 0  → 8-bit data frame
     * RXONLY   = 0  → full duplex
     * SSM      = 0  → Hardware NSS (NSS pin điều khiển bởi RPi)
     * SSI      = 0  → (không dùng khi SSM=0)
     * LSBFIRST = 0  → MSB first
     * SPE      = 0  → chưa enable, enable sau
     * BR       = 0  → không quan trọng với slave (clock từ master)
     * MSTR     = 0  → SLAVE mode
     * CPOL     = 0  → Clock idle LOW  (Mode 0)
     * CPHA     = 0  → Capture on rising edge (Mode 0)
     */
    SPI2->CR1 = 0;  /* Tất cả 0 = slave, mode 0, 8-bit, MSB first */

    /* ── 4. Cấu hình SPI2 CR2 ────────────────────────────────────── */
    /*
     * TXDMAEN = 1 → Enable DMA request khi TX buffer empty
     * SSOE    = 0 → (slave mode, không output NSS)
     * FRF     = 0 → Motorola frame format
     * ERRIE   = 1 → Enable error interrupt (OVR, MODF)
     * RXNEIE  = 0 → Không dùng RX interrupt
     * TXEIE   = 0 → Dùng DMA thay vì interrupt
     */
    SPI2->CR2 = SPI_CR2_TXDMAEN | SPI_CR2_ERRIE;

    /* ── 5. Cấu hình DMA1 Stream4 Channel0 → SPI2_TX ────────────── */
    /*
     * DMA1 Stream4, Channel0 = SPI2_TX (theo DMA request mapping F407)
     */

    /* Tắt stream trước khi config */
    DMA1_Stream4->CR &= ~DMA_SxCR_EN;
    while (DMA1_Stream4->CR & DMA_SxCR_EN) {}  /* chờ disable */

    /* Xóa cờ interrupt của stream 4 */
    DMA1->HIFCR = DMA_HIFCR_CTCIF4 | DMA_HIFCR_CHTIF4
                | DMA_HIFCR_CTEIF4 | DMA_HIFCR_CDMEIF4
                | DMA_HIFCR_CFEIF4;

    /* PAR: địa chỉ SPI2->DR (peripheral) */
    DMA1_Stream4->PAR  = (uint32_t)&SPI2->DR;

    /* MAR: địa chỉ TX buffer (memory) */
    DMA1_Stream4->M0AR = (uint32_t)s_tx_buf;

    /* NDTR: số byte cần truyền */
    DMA1_Stream4->NDTR = SPI_TX_BUF_SIZE;

    /* CR config:
     * CHSEL  = 000  → Channel 0
     * MBURST = 00   → single
     * PBURST = 00   → single
     * CT     = 0    → memory 0
     * DBM    = 0    → no double buffer
     * PL     = 01   → Medium priority
     * MSIZE  = 00   → 8-bit memory
     * PSIZE  = 00   → 8-bit peripheral
     * MINC   = 1    → Memory increment
     * PINC   = 0    → Peripheral fixed
     * CIRC   = 0    → No circular
     * DIR    = 01   → Memory → Peripheral (TX)
     * PFCTRL = 0    → DMA flow control
     * TCIE   = 1    → Transfer complete interrupt
     * HTIE   = 0
     * TEIE   = 1    → Transfer error interrupt
     */
    DMA1_Stream4->CR = (0U  << DMA_SxCR_CHSEL_Pos)  /* Channel 0 */
                     | (1U  << DMA_SxCR_PL_Pos)      /* Priority medium */
                     | (0U  << DMA_SxCR_MSIZE_Pos)   /* 8-bit mem */
                     | (0U  << DMA_SxCR_PSIZE_Pos)   /* 8-bit periph */
                     | DMA_SxCR_MINC                  /* Memory increment */
                     | (1U  << DMA_SxCR_DIR_Pos)     /* Mem→Periph */
                     | DMA_SxCR_TCIE                  /* TC interrupt */
                     | DMA_SxCR_TEIE;                 /* TE interrupt */

    /* FIFO control: disable FIFO (direct mode) */
    DMA1_Stream4->FCR = 0;

    /* ── 6. NVIC: Enable DMA1 Stream4 interrupt ─────────────────── */
    NVIC_SetPriority(DMA1_Stream4_IRQn, 1U);
    NVIC_EnableIRQ(DMA1_Stream4_IRQn);

    /* ── 7. NVIC: Enable SPI2 interrupt (error handling) ────────── */
    NVIC_SetPriority(SPI2_IRQn, 1U);
    NVIC_EnableIRQ(SPI2_IRQn);

    /* ── 8. Enable SPI2 ──────────────────────────────────────────── */
    SPI2->CR1 |= SPI_CR1_SPE;
}

/* ------------------------------------------------------------------ */
void SPI_SetTxBuffer(uint8_t *buf, uint16_t size)
{
    if (size > SPI_TX_BUF_SIZE) size = SPI_TX_BUF_SIZE;

    /* Copy dữ liệu vào TX buffer nội */
    memcpy(s_tx_buf, buf, size);

    /* Padding nếu size < 16 */
    if (size < SPI_TX_BUF_SIZE)
        memset(s_tx_buf + size, 0, SPI_TX_BUF_SIZE - size);

    /* ── Khởi động lại DMA ─────────────────────────────────────── */
    s_busy = 1;

    /* Tắt DMA stream */
    DMA1_Stream4->CR &= ~DMA_SxCR_EN;
    while (DMA1_Stream4->CR & DMA_SxCR_EN) {}

    /* Xóa cờ */
    DMA1->HIFCR = DMA_HIFCR_CTCIF4 | DMA_HIFCR_CHTIF4
                | DMA_HIFCR_CTEIF4 | DMA_HIFCR_CDMEIF4
                | DMA_HIFCR_CFEIF4;

    /* Cập nhật địa chỉ và số byte */
    DMA1_Stream4->M0AR = (uint32_t)s_tx_buf;
    DMA1_Stream4->NDTR = SPI_TX_BUF_SIZE;

    /* Xóa SPI OVR nếu có */
    (void)SPI2->DR;
    (void)SPI2->SR;

    /* Enable DMA stream → sẵn sàng truyền khi RPi kéo NSS */
    DMA1_Stream4->CR |= DMA_SxCR_EN;
}

/* ------------------------------------------------------------------ */
uint8_t SPI_IsBusy(void)
{
    return s_busy;
}

/* ================================================================== */
/* DMA1 Stream4 IRQ Handler – SPI2 TX Complete                        */
/* ================================================================== */
void DMA1_Stream4_IRQHandler(void)
{
    uint32_t hisr = DMA1->HISR;

    if (hisr & DMA_HISR_TCIF4)
    {
        /* Transfer complete */
        DMA1->HIFCR = DMA_HIFCR_CTCIF4;

        /* Chờ SPI TX buffer trống và SPI không busy */
        while (!(SPI2->SR & SPI_SR_TXE)) {}
        while (SPI2->SR & SPI_SR_BSY)   {}

        s_busy = 0;
    }

    if (hisr & DMA_HISR_TEIF4)
    {
        /* Transfer error – xóa cờ, reset busy */
        DMA1->HIFCR = DMA_HIFCR_CTEIF4;
        s_busy = 0;
    }
}

/* ================================================================== */
/* SPI2 IRQ Handler – Error handling                                   */
/* ================================================================== */
void SPI2_IRQHandler(void)
{
    uint32_t sr = SPI2->SR;

    /* OVR (Overrun): đọc DR và SR để xóa */
    if (sr & SPI_SR_OVR)
    {
        (void)SPI2->DR;
        (void)SPI2->SR;
    }

    /* MODF (Mode fault): reset SPE */
    if (sr & SPI_SR_MODF)
    {
        SPI2->CR1 &= ~SPI_CR1_SPE;
        SPI2->CR1 |=  SPI_CR1_SPE;
    }
}
