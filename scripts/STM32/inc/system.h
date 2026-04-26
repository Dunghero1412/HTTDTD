/**
 * system.h - System initialization functions
 */

#ifndef __SYSTEM_H__
#define __SYSTEM_H__

#include <stdint.h>

// ✓ Prototypes
void SystemClock_Config(void);      // Setup system clock to 168MHz
void NVIC_Config(void);              // Configure interrupts

// ✓ Clock frequency (filled by SystemClock_Config)
extern uint32_t SystemCoreClock;

#endif // __SYSTEM_H__