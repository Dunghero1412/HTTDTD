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