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