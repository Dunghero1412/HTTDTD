#ifndef GPIO_CONTROL_H
#define GPIO_CONTROL_H

#include "main.h"
#include <stdbool.h>

void GPIO_Control_Init(void);

/* PB0 - DATA_READY output */
void DataReady_Set(void);    // → High: báo RPi
void DataReady_Clear(void);  // → Low:  RPi đã nhận xong
bool DataReady_IsHigh(void);

/* PB1 - RUN_TRG input */
bool RunTrg_IsHigh(void);

#endif
