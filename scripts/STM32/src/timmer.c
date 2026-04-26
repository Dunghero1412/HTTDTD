/**
 * timmer.c - TIM2 Input Capture 4 kênh (Bare-metal, STM32F407VG)
 * ----------------------------------------------------------------
 * TIM2 là timer 32-bit trên APB1.
 *
 * Clock:
 *   HCLK = 168MHz, APB1 prescaler = 4 → APB1 = 42MHz
 *   Vì APB1 prescaler > 1 → TIM2 clock = 42 × 2 = 84MHz
 *   PSC = 0 → tick = 1/84MHz ≈ 11.9 ns (độ phân giải cao nhất)
 *   Nếu muốn 1 tick = 1µs → PSC = 83
 *
 * Channel mapping (AF01):
 *   TIM2_CH1 → PA0 (Sensor A)
 *   TIM2_CH2 → PA1 (Sensor B)
 *   TIM2_CH3 → PA2 (Sensor C)
 *   TIM2_CH4 → PA3 (Sensor D)
 *
 * Capture: Rising edge, no filter, no prescaler
 *
 * FIX: Thay toàn bộ macro _Pos bằng bit shift trực tiếp,
 *      thay _Msk bằng literal mask, tương thích mọi phiên bản header.
 */

#include "../inc/timmer.h"
#include "../inc/stm32f4xx.h"

/* ------------------------------------------------------------------ */
/* Shared capture data – extern trong main.c                           */
/* ------------------------------------------------------------------ */
volatile uint32_t g_timestamp[4]  = {0U, 0U, 0U, 0U};
volatile uint8_t  g_capture_flags = 0x00U;
volatile uint8_t  g_capture_done  = 0U;

/* ------------------------------------------------------------------ */
void Timer_Init(void)
{
    /* ── 1. Bật clock TIM2 (APB1) ───────────────────────────────── */
    RCC->APB1ENR |= RCC_APB1ENR_TIM2EN;
    __DSB();

    /* ── 2. Tắt timer, reset toàn bộ register ───────────────────── */
    TIM2->CR1   = 0U;
    TIM2->CR2   = 0U;
    TIM2->SMCR  = 0U;
    TIM2->DIER  = 0U;
    TIM2->CCMR1 = 0U;
    TIM2->CCMR2 = 0U;
    TIM2->CCER  = 0U;
    TIM2->CNT   = 0U;
    TIM2->SR    = 0U;

    /* ── 3. Prescaler ────────────────────────────────────────────── */
    /*
     * PSC = 83 → TIM2 clock = 84MHz / 84 = 1MHz → 1 tick = 1µs
     * Đủ độ phân giải cho TDOA (tốc độ âm ~0.0343 cm/µs)
     */
    TIM2->PSC = 83U;

    /* ── 4. Auto-reload: max 32-bit ─────────────────────────────── */
    TIM2->ARR = 0xFFFFFFFFU;

    /* ── 5. CCMR1: CH1 và CH2 → Input Capture ───────────────────── */
    /*
     * CCxS[1:0] = 01 → ICx mapped trên TIx (direct input)
     * ICxPSC    = 00 → No prescaler
     * ICxF      = 0000 → No filter
     *
     * CCMR1 layout:
     *   [1:0]   CC1S   [3:2]  IC1PSC  [7:4]  IC1F
     *   [9:8]   CC2S   [11:10]IC2PSC  [15:12]IC2F
     */
    TIM2->CCMR1 = (1U << 0U)    /* CC1S = 01 (IC1→TI1) */
                | (0U << 2U)    /* IC1PSC = 00 */
                | (0U << 4U)    /* IC1F   = 0000 */
                | (1U << 8U)    /* CC2S = 01 (IC2→TI2) */
                | (0U << 10U)   /* IC2PSC = 00 */
                | (0U << 12U);  /* IC2F   = 0000 */

    /* ── 6. CCMR2: CH3 và CH4 → Input Capture ───────────────────── */
    /*
     * CCMR2 layout (sama struktur dengan CCMR1, untuk CH3 dan CH4):
     *   [1:0]   CC3S   [3:2]  IC3PSC  [7:4]  IC3F
     *   [9:8]   CC4S   [11:10]IC4PSC  [15:12]IC4F
     */
    TIM2->CCMR2 = (1U << 0U)    /* CC3S = 01 (IC3→TI3) */
                | (0U << 2U)    /* IC3PSC = 00 */
                | (0U << 4U)    /* IC3F   = 0000 */
                | (1U << 8U)    /* CC4S = 01 (IC4→TI4) */
                | (0U << 10U)   /* IC4PSC = 00 */
                | (0U << 12U);  /* IC4F   = 0000 */

    /* ── 7. CCER: Enable CH1–CH4, Rising edge ───────────────────── */
    /*
     * CCxE  = 1 → Enable capture
     * CCxP  = 0 → Rising edge (bit 1, 5, 9, 13)
     * CCxNP = 0 → (bit 3, 7, 11, 15)
     *
     * CCER layout:
     *   bit0=CC1E  bit1=CC1P  bit3=CC1NP
     *   bit4=CC2E  bit5=CC2P  bit7=CC2NP
     *   bit8=CC3E  bit9=CC3P  bit11=CC3NP
     *   bit12=CC4E bit13=CC4P bit15=CC4NP
     */
    TIM2->CCER = (1U << 0U)    /* CC1E: CH1 enable */
               | (0U << 1U)    /* CC1P: rising edge */
               | (1U << 4U)    /* CC2E: CH2 enable */
               | (0U << 5U)    /* CC2P: rising edge */
               | (1U << 8U)    /* CC3E: CH3 enable */
               | (0U << 9U)    /* CC3P: rising edge */
               | (1U << 12U)   /* CC4E: CH4 enable */
               | (0U << 13U);  /* CC4P: rising edge */

    /* ── 8. DIER: Enable Capture Compare Interrupt CH1–CH4 ──────── */
    /*
     * bit0 = UIE  (update – không dùng)
     * bit1 = CC1IE
     * bit2 = CC2IE
     * bit3 = CC3IE
     * bit4 = CC4IE
     */
    TIM2->DIER = (1U << 1U)    /* CC1IE */
               | (1U << 2U)    /* CC2IE */
               | (1U << 3U)    /* CC3IE */
               | (1U << 4U);   /* CC4IE */

    /* ── 9. NVIC: Enable TIM2_IRQn, priority cao nhất ───────────── */
    NVIC_SetPriority(TIM2_IRQn, 0U);
    NVIC_EnableIRQ(TIM2_IRQn);

    /* ── 10. EGR: Update event để load PSC và ARR ───────────────── */
    TIM2->EGR = (1U << 0U);    /* UG bit */

    /* Xóa cờ update do UG tạo ra */
    TIM2->SR = 0U;
}

/* ------------------------------------------------------------------ */
void Timer_Start(void)
{
    /* Reset capture state */
    g_timestamp[0]  = 0U;
    g_timestamp[1]  = 0U;
    g_timestamp[2]  = 0U;
    g_timestamp[3]  = 0U;
    g_capture_flags = 0x00U;
    g_capture_done  = 0U;

    /* Reset counter và xóa cờ SR */
    TIM2->CNT = 0U;
    TIM2->SR  = 0U;

    /* Start: CEN bit = bit0 của CR1 */
    TIM2->CR1 |= (1U << 0U);
}

/* ------------------------------------------------------------------ */
void Timer_Stop(void)
{
    /* Clear CEN bit */
    TIM2->CR1 &= ~(1U << 0U);
    TIM2->SR   = 0U;
}

/* ------------------------------------------------------------------ */
uint32_t Timer_GetValue(void)
{
    return TIM2->CNT;
}

/*
 * NOTE: TIM2_IRQHandler định nghĩa trong main.c
 * timmer.c chỉ export: Timer_Init, Timer_Start, Timer_Stop, Timer_GetValue
 * và các biến shared: g_timestamp[], g_capture_flags, g_capture_done
 */
