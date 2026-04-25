/**
 * timer.h - Timer capture functions
 */

#ifndef __TIMER_H__
#define __TIMER_H__

#include <stdint.h>

// ✓ Prototypes
void Timer_Init(void);              // Initialize TIM2 input capture
uint32_t Timer_GetValue(void);      // Get current timer value
void Timer_Start(void);             // Start timer
void Timer_Stop(void);              // Stop timer

#endif // __TIMER_H__