#ifndef MAIN_H
#define MAIN_H

#include "stm32f407xx.h"
#include <stdint.h>
#include <stdbool.h>

/* ── Pin Definitions ───────────────────────────── */
#define RUN_TRG_PIN     1U   // PB1 - INPUT  (switch → 3.3V)
#define DATA_READY_PIN  0U   // PB0 - OUTPUT (→ RPi)

/* ── Sensor Channel Mapping (TIM2 CH1–CH4) ─────── */
#define SENSOR_A_CH     0U   // PA0 → TIM2_CH1
#define SENSOR_B_CH     1U   // PA1 → TIM2_CH2
#define SENSOR_C_CH     2U   // PA2 → TIM2_CH3
#define SENSOR_D_CH     3U   // PA3 → TIM2_CH4

#define NUM_SENSORS     4U

/* ── System States ──────────────────────────────── */
typedef enum {
    STATE_IDLE      = 0,  // PB1 Low  - chờ
    STATE_CAPTURING = 1,  // PB1 High - đang capture
    STATE_PACKAGING = 2,  // Đủ 4 timestamp - đóng gói
    STATE_WAITING   = 3,  // Chờ RPi đọc xong (DATA_READY High)
} SystemState_t;

extern volatile SystemState_t g_system_state;
extern volatile uint32_t g_wait_timeout;

void SystemClock_Config(void);
#endif
