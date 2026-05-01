#include "spi_comm.h"

/* Định nghĩa chân PB12 là NSS (hardware, do master kéo) */
void SPI2_Init(void) {
    /* Clock GPIOB, SPI2 */
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOBEN;
    RCC->APB1ENR |= RCC_APB1ENR_SPI2EN;
    __DSB();

    /* Cấu hình chân SPI2: PB12(NSS), PB13(SCK), PB14(MISO), PB15(MOSI) tất cả AF5 */
    for (int pin = 12; pin <= 15; pin++) {
        GPIOB->MODER &= ~(3U << (pin * 2));
        GPIOB->MODER |=  (2U << (pin * 2));          // Alternate function
        GPIOB->OSPEEDR |= (3U << (pin * 2));         // High speed
        GPIOB->PUPDR   &= ~(3U << (pin * 2));        // No pull
        /* AFRH cho pin 8-15 */
        GPIOB->AFR[1] &= ~(0xFU << ((pin - 8) * 4));
        GPIOB->AFR[1] |=  (5U << ((pin - 8) * 4));   // AF5 = SPI2
    }
    /* Riêng PB12 NSS: cấu hình hardware NSS (không phải output) */
    GPIOB->MODER &= ~(3U << (12 * 2));               // vẫn là AF

    /* Cấu hình SPI2 ở chế độ Slave, mode 0, 8-bit */
    SPI2->CR1 = 0;                    // CPOL=0, CPHA=0, MSTR=0
    SPI2->CR2 = 0;
    SPI2->CR1 |= SPI_CR1_SPE;         // Enable SPI
}

/* Hàm truyền dữ liệu (blocking) – chờ master kéo CS và cấp clock */
void SPI2_Transmit(const uint8_t *data, uint16_t len) {
    for (uint16_t i = 0; i < len; i++) {
        /* Chờ TXE (master bắt đầu giao dịch) */
        while (!(SPI2->SR & SPI_SR_TXE));
        *(__IO uint8_t *)&SPI2->DR = data[i];
        /* Chờ RXNE để đọc byte rác (do master gửi 0x00) */
        while (!(SPI2->SR & SPI_SR_RXNE));
        (void)SPI2->DR;   // bỏ qua
    }
    /* Chờ đến khi BUSY = 0 (kết thúc giao dịch) */
    while (SPI2->SR & SPI_SR_BSY);
}
