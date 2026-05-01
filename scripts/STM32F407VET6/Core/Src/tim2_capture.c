#include "tim2_capture.h"
#include "main.h"

volatile CaptureData_t g_capture = {0};

/* ────────────────────────────────────────────────────
 *  TIM2_Capture_Init
 *  PA0→CH1, PA1→CH2, PA2→CH3, PA3→CH4
 *  TIM2: 32-bit, prescaler=0 → tick = HCLK (168 MHz)
 * ──────────────────────────────────────────────────── */
void TIM2_Capture_Init(void) {
    /* ── Enable clocks ──────────────────────────────── */
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN;
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
    __DSB();

    /* ── GPIO PA0–PA3: Alternate Function (AF1 = TIM2) ── */
    for (uint8_t pin = 0; pin < 4; pin++) {
        GPIOA->MODER  &= ~(3U << (pin * 2));
        GPIOA->MODER  |=  (2U << (pin * 2));   // AF mode
        GPIOA->PUPDR  &= ~(3U << (pin * 2));    // No pull
        GPIOA->AFR[0] &= ~(0xFU << (pin * 4));
        GPIOA->AFR[0] |=  (0x1U << (pin * 4)); // AF1 = TIM2
    }

    /* ── TIM2 Base Config ───────────────────────────── */
    TIM2->CR1   = 0;
    TIM2->PSC   = 0;            // Prescaler = 0 → 168 MHz tick
    TIM2->ARR   = 0xFFFFFFFF;   // 32-bit full range
    TIM2->CNT   = 0;

    /* ── Input Capture: CH1–CH4, rising edge ───────── */
    // CCMR1: CH1 (CC1S=01 input TI1), CH2 (CC2S=01 input TI2)
    TIM2->CCMR1 = (1U << TIM_CCMR1_CC1S_Pos)   // CH1 → TI1
                | (1U << TIM_CCMR1_CC2S_Pos);   // CH2 → TI2

    // CCMR2: CH3 (CC3S=01 input TI3), CH4 (CC4S=01 input TI4)
    TIM2->CCMR2 = (1U << TIM_CCMR2_CC3S_Pos)   // CH3 → TI3
                | (1U << TIM_CCMR2_CC4S_Pos);   // CH4 → TI4

    // CCER: Enable CH1–CH4, rising edge (CCxP=0, CCxNP=0)
    TIM2->CCER  = TIM_CCER_CC1E
                | TIM_CCER_CC2E
                | TIM_CCER_CC3E
                | TIM_CCER_CC4E;

    /* ── Enable Capture Interrupts CH1–CH4 ─────────── */
    TIM2->DIER  = TIM_DIER_CC1IE
                | TIM_DIER_CC2IE
                | TIM_DIER_CC3IE
                | TIM_DIER_CC4IE;

    /* ── NVIC ───────────────────────────────────────── */
    NVIC_SetPriority(TIM2_IRQn, 0);  // Priority cao nhất
    NVIC_EnableIRQ(TIM2_IRQn);

    /* Timer chưa start, chờ PB1 High */
    TIM2->CR1 &= ~TIM_CR1_CEN;
}

/* ────────────────────────────────────────────────────
 *  Start: xoá state + bật TIM2
 * ──────────────────────────────────────────────────── */
void TIM2_Capture_Start(void) {
    /* Reset capture data */
    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        g_capture.timestamp[i] = 0;
        g_capture.captured[i]  = false;
    }
    g_capture.count = 0;

    /* Xoá pending flags trước khi start */
    TIM2->SR  = 0;
    TIM2->CNT = 0;
    TIM2->CR1 |= TIM_CR1_CEN;
}

/* ────────────────────────────────────────────────────
 *  Stop: tắt TIM2, xoá hết
 * ──────────────────────────────────────────────────── */
void TIM2_Capture_Stop(void) {
    TIM2->CR1 &= ~TIM_CR1_CEN;
    TIM2->SR   = 0;

    for (uint8_t i = 0; i < NUM_SENSORS; i++) {
        g_capture.timestamp[i] = 0;
        g_capture.captured[i]  = false;
    }
    g_capture.count = 0;
}

bool All_Sensors_Captured(void) {
    return (g_capture.count >= NUM_SENSORS);
}

/* ────────────────────────────────────────────────────
 *  IRQ Handler Implementation
 *  - Mỗi channel chỉ capture 1 lần (cờ captured[i])
 *  - Khi đủ 4 → disable capture, chuyển STATE_PACKAGING
 * ──────────────────────────────────────────────────── */
/*
void TIM2_IRQHandler_Impl(void) {
    uint32_t sr = TIM2->SR;
*/

    /* ── CH1 / Sensor A ─────────────────────────────── */
/*    if ((sr & TIM_SR_CC1IF) && !g_capture.captured[SENSOR_A_CH]) {
        g_capture.timestamp[SENSOR_A_CH] = TIM2->CCR1;  // đọc CCR tự clear flag
        g_capture.captured[SENSOR_A_CH]  = true;
        g_capture.count++;
    } else {
        TIM2->SR &= ~TIM_SR_CC1IF;  // clear nếu đã capture rồi
    }
*/
    /* ── CH2 / Sensor B ─────────────────────────────── */
/*    if ((sr & TIM_SR_CC2IF) && !g_capture.captured[SENSOR_B_CH]) {
        g_capture.timestamp[SENSOR_B_CH] = TIM2->CCR2;
        g_capture.captured[SENSOR_B_CH]  = true;
        g_capture.count++;
    } else {
        TIM2->SR &= ~TIM_SR_CC2IF;
    }
*/
    /* ── CH3 / Sensor C ─────────────────────────────── */
/*    if ((sr & TIM_SR_CC3IF) && !g_capture.captured[SENSOR_C_CH]) {
        g_capture.timestamp[SENSOR_C_CH] = TIM2->CCR3;
        g_capture.captured[SENSOR_C_CH]  = true;
        g_capture.count++;
    } else {
        TIM2->SR &= ~TIM_SR_CC3IF;
    }
*/
    /* ── CH4 / Sensor D ─────────────────────────────── */
/*    if ((sr & TIM_SR_CC4IF) && !g_capture.captured[SENSOR_D_CH]) {
        g_capture.timestamp[SENSOR_D_CH] = TIM2->CCR4;
        g_capture.captured[SENSOR_D_CH]  = true;
        g_capture.count++;
    } else {
        TIM2->SR &= ~TIM_SR_CC4IF;
    }
*/
    /* ── Đủ 4 sensor → dừng capture, báo main loop ─── */
/*    if (g_capture.count >= NUM_SENSORS) {
        TIM2->DIER &= ~(TIM_DIER_CC1IE | TIM_DIER_CC2IE
                      | TIM_DIER_CC3IE | TIM_DIER_CC4IE);
        TIM2->CR1  &= ~TIM_CR1_CEN;
        g_system_state = STATE_PACKAGING;
    }
}
*/

void TIM2_IRQHandler_Impl(void) {
    uint32_t sr = TIM2->SR;

    /* Xử lý từng kênh, chỉ lấy lần đầu */
    if ((sr & TIM_SR_CC1IF) && !g_capture.captured[0]) {
        g_capture.timestamp[0] = TIM2->CCR1;
        g_capture.captured[0] = true;
        g_capture.count++;
    }
    if ((sr & TIM_SR_CC2IF) && !g_capture.captured[1]) {
        g_capture.timestamp[1] = TIM2->CCR2;
        g_capture.captured[1] = true;
        g_capture.count++;
    }
    if ((sr & TIM_SR_CC3IF) && !g_capture.captured[2]) {
        g_capture.timestamp[2] = TIM2->CCR3;
        g_capture.captured[2] = true;
        g_capture.count++;
    }
    if ((sr & TIM_SR_CC4IF) && !g_capture.captured[3]) {
        g_capture.timestamp[3] = TIM2->CCR4;
        g_capture.captured[3] = true;
        g_capture.count++;
    }

    /* Đủ 4 sensor → dừng capture, chuyển trạng thái */
    if (g_capture.count >= NUM_SENSORS) {
        TIM2->DIER &= ~(TIM_DIER_CC1IE | TIM_DIER_CC2IE | TIM_DIER_CC3IE | TIM_DIER_CC4IE);
        TIM2->CR1  &= ~TIM_CR1_CEN;
        g_system_state = STATE_PACKAGING;
    }

    /* Xóa các cờ đã xử lý (chỉ xóa những bit đang set) */
    TIM2->SR = sr;    // ghi 1 vào bit tương ứng để xóa
}
/* ── Vector IRQ (gọi impl) ──────────────────────────── */
void TIM2_IRQHandler(void) {
    TIM2_IRQHandler_Impl();
}
