/**
 * timer.c - TIM2 Input Capture, 4 channels (Bare-metal, STM32F407VG)
 * --------------------------------------------------------------------
 * TIM2 là timer 32-bit, dùng để capture timestamp chính xác khi
 * tín hiệu từ piezo vượt ngưỡng.
 *
 * Clock: APB1 = 42 MHz → TIM2 clock = 84 MHz (x2 khi APB1 prescaler > 1)
 * Prescaler = 83 → Timer clock = 84MHz / (83+1) = 1 MHz → 1 tick = 1 µs
 *
 * Channel mapping:
 *   CH1 → PA0 (Sensor D) – TIM2_CH1
 *   CH2 → PA1 (Sensor A) – TIM2_CH2
 *   CH3 → PA2 (Sensor B) – TIM2_CH3
 *   CH4 → PA3 (Sensor C) – TIM2_CH4
 *
 * Capture trigger: Rising edge (tín hiệu OPA2134 lên cao = impact)
 * Interrupt: CCxIF set khi capture xảy ra → ISR lưu timestamp
 *
 * Dữ liệu capture được lưu trong:
 *   extern volatile uint32_t g_timestamp[4];
 *   extern volatile uint8_t  g_capture_done;  (= 1 khi đủ 4 kênh)
 */

#include "../inc/timmer.h"
#include "../inc/stm32f4xx.h"

/* ------------------------------------------------------------------ */
/* Shared capture data (dùng trong main.c / tdoa.c)                    */
/* ------------------------------------------------------------------ */
volatile uint32_t g_timestamp[4]  = {0, 0, 0, 0};
volatile uint8_t  g_capture_flags = 0x00;  /* bit0=CH1, bit1=CH2, ... */
volatile uint8_t  g_capture_done  = 0;     /* 1 = đủ 4 kênh */

/* ------------------------------------------------------------------ */
void Timer_Init(void)
{
    /* ── 1. Bật clock TIM2 ───────────────────────────────────────── */
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
    __DSB();

    /* ── 2. Reset TIM2 về trạng thái ban đầu ────────────────────── */
    TIM2->CR1   = 0;
    TIM2->CR2   = 0;
    TIM2->SMCR  = 0;
    TIM2->DIER  = 0;
    TIM2->CCMR1 = 0;
    TIM2->CCMR2 = 0;
    TIM2->CCER  = 0;
    TIM2->CNT   = 0;

    /* ── 3. Prescaler: 84MHz / 84 = 1MHz → 1 tick = 1 µs ────────── */
    TIM2->PSC = 83U;     /* reload value = PSC+1 = 84 */

    /* ── 4. Auto-reload: max 32-bit (TIM2 là 32-bit timer) ──────── */
    TIM2->ARR = 0xFFFFFFFFU;

    /* ── 5. CCMR1: CH1 & CH2 → Input Capture mode ───────────────── */
    /*
     * CCxS = 01 → ICx mapped on TIx (direct)
     * ICxPSC = 00 → no prescaler (capture mỗi edge)
     * ICxF = 0000 → no filter (tín hiệu từ OPA đã qua RC LPF rồi)
     */
    TIM2->CCMR1 = 0;
    TIM2->CCMR1 |= (1U << TIM_CCMR1_CC1S_Pos)   /* CH1: IC1→TI1 */
                 | (0U << TIM_CCMR1_IC1PSC_Pos)
                 | (0U << TIM_CCMR1_IC1F_Pos)
                 | (1U << TIM_CCMR1_CC2S_Pos)    /* CH2: IC2→TI2 */
                 | (0U << TIM_CCMR1_IC2PSC_Pos)
                 | (0U << TIM_CCMR1_IC2F_Pos);

    /* ── 6. CCMR2: CH3 & CH4 → Input Capture mode ───────────────── */
    TIM2->CCMR2 = 0;
    TIM2->CCMR2 |= (1U << TIM_CCMR2_CC3S_Pos)   /* CH3: IC3→TI3 */
                 | (0U << TIM_CCMR2_IC3PSC_Pos)
                 | (0U << TIM_CCMR2_IC3F_Pos)
                 | (1U << TIM_CCMR2_CC4S_Pos)    /* CH4: IC4→TI4 */
                 | (0U << TIM_CCMR2_IC4PSC_Pos)
                 | (0U << TIM_CCMR2_IC4F_Pos);

    /* ── 7. CCER: Enable CH1–CH4, Rising edge ───────────────────── */
    /*
     * CCxP = 0, CCxNP = 0 → Rising edge trigger
     * CCxE = 1 → Enable capture
     */
    TIM2->CCER = TIM_CCER_CC1E   /* CH1 enable */
               | TIM_CCER_CC2E   /* CH2 enable */
               | TIM_CCER_CC3E   /* CH3 enable */
               | TIM_CCER_CC4E;  /* CH4 enable */
    /* CCxP=0 mặc định → rising edge, không cần set thêm */

    /* ── 8. DIER: Enable Capture Compare Interrupt cho cả 4 kênh ── */
    TIM2->DIER = TIM_DIER_CC1IE   /* CH1 capture interrupt */
               | TIM_DIER_CC2IE   /* CH2 capture interrupt */
               | TIM_DIER_CC3IE   /* CH3 capture interrupt */
               | TIM_DIER_CC4IE;  /* CH4 capture interrupt */

    /* ── 9. NVIC: Enable TIM2 interrupt, priority 0 (cao nhất) ─── */
    NVIC_SetPriority(TIM2_IRQn, 0U);
    NVIC_EnableIRQ(TIM2_IRQn);

    /* ── 10. EGR: Generate update event để load PSC/ARR ─────────── */
    TIM2->EGR = TIM_EGR_UG;

    /* Xóa cờ update interrupt (do UG tạo ra) */
    TIM2->SR = 0;
}

/* ------------------------------------------------------------------ */
void Timer_Start(void)
{
    /* Reset state */
    g_timestamp[0]  = 0;
    g_timestamp[1]  = 0;
    g_timestamp[2]  = 0;
    g_timestamp[3]  = 0;
    g_capture_flags = 0x00;
    g_capture_done  = 0;

    TIM2->CNT = 0;           /* Reset counter */
    TIM2->SR  = 0;           /* Xóa tất cả cờ */
    TIM2->CR1 |= TIM_CR1_CEN; /* Start */
}

/* ------------------------------------------------------------------ */
void Timer_Stop(void)
{
    TIM2->CR1 &= ~TIM_CR1_CEN;  /* Stop counter */
    TIM2->SR   = 0;
}

/* ------------------------------------------------------------------ */
uint32_t Timer_GetValue(void)
{
    return TIM2->CNT;
}

/* ================================================================== */
/* TIM2 IRQ Handler                                                    */
/* ================================================================== */
void TIM2_IRQHandler(void)
{
    uint32_t sr = TIM2->SR;

    /* ── CH1 capture (PA0 – Sensor D) ──────────────────────────── */
    if ((sr & TIM_SR_CC1IF) && !(g_capture_flags & 0x01))
    {
        g_timestamp[0]   = TIM2->CCR1;   /* đọc CCR tự xóa CC1IF */
        g_capture_flags |= 0x01;
    }
    else if (sr & TIM_SR_CC1IF)
    {
        (void)TIM2->CCR1;                /* đọc để xóa cờ, bỏ qua giá trị */
    }

    /* ── CH2 capture (PA1 – Sensor A) ──────────────────────────── */
    if ((sr & TIM_SR_CC2IF) && !(g_capture_flags & 0x02))
    {
        g_timestamp[1]   = TIM2->CCR2;
        g_capture_flags |= 0x02;
    }
    else if (sr & TIM_SR_CC2IF)
    {
        (void)TIM2->CCR2;
    }

    /* ── CH3 capture (PA2 – Sensor B) ──────────────────────────── */
    if ((sr & TIM_SR_CC3IF) && !(g_capture_flags & 0x04))
    {
        g_timestamp[2]   = TIM2->CCR3;
        g_capture_flags |= 0x04;
    }
    else if (sr & TIM_SR_CC3IF)
    {
        (void)TIM2->CCR3;
    }

    /* ── CH4 capture (PA3 – Sensor C) ──────────────────────────── */
    if ((sr & TIM_SR_CC4IF) && !(g_capture_flags & 0x08))
    {
        g_timestamp[3]   = TIM2->CCR4;
        g_capture_flags |= 0x08;
    }
    else if (sr & TIM_SR_CC4IF)
    {
        (void)TIM2->CCR4;
    }

    /* ── Kiểm tra đủ 4 kênh ─────────────────────────────────────── */
    if (g_capture_flags == 0x0F)
    {
        g_capture_done = 1;
        Timer_Stop();   /* Dừng timer, chờ main xử lý */
    }

    /* Xóa tất cả cờ SR đã xử lý */
    TIM2->SR = ~sr;
}
