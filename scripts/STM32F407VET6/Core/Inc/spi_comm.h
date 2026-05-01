#ifndef SPI_COMM_H
#define SPI_COMM_H

#include <stdint.h>
#include "stm32f407xx.h"
#include "main.h"

#define SPI_TIMEOUT_MS  100U

void     SPI2_Init(void);
void     SPI2_Transmit(const uint8_t *data, uint16_t len);
uint8_t  SPI2_GetStatus(void);

#endif
