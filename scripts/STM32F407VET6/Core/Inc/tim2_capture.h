#ifndef TIM2_CAPTURE_H
#define TIM2_CAPTURE_H

#include "main.h"
#include <stdint.h>
#include <stdbool.h>
#include "stm32f407xx.h"

/* ── Capture Data Structure ─────────────────────── */
typedef struct {
    uint32_t timestamp[NUM_SENSORS];   // raw tick value
    bool     captured[NUM_SENSORS];    // cờ đã capture chưa
    uint8_t  count;                    // số sensor đã capture
} CaptureData_t;

extern volatile CaptureData_t g_capture;

/* ── API ────────────────────────────────────────── */
void TIM2_Capture_Init(void);   // Cấu hình TIM2 + GPIO PA0-3
void TIM2_Capture_Start(void);  // Enable TIM2, clear flags
void TIM2_Capture_Stop(void);   // Disable TIM2, reset state
void TIM2_IRQHandler_Impl(void);// Gọi từ TIM2_IRQHandler

bool All_Sensors_Captured(void);

#endif
