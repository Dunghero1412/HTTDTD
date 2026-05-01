#include "stm32f407xx.h"

/**
 * SystemInit - Gọi bởi startup trước main()
 * Bare-metal tối giản: không cấu hình PLL ở đây,
 * chỉ đảm bảo FPU được bật (Cortex-M4 hard-float).
 */
void SystemInit(void) {
    /* ── Bật FPU (CP10, CP11 full access) ──────────── */
    SCB->CPACR |= (0xFU << 20);
    __DSB();
    __ISB();

    /* ── Tắt tất cả interrupt ngoại vi (an toàn khi reset) ── */
    RCC->CIR = 0x00000000;
}
void SystemClock_Config(void) {
    /* Enable HSE */
    RCC->CR |= RCC_CR_HSEON;
    while (!(RCC->CR & RCC_CR_HSERDY));

    /* Cấu hình PLL: HSE 8MHz -> M=8 -> 1MHz, N=336 -> 336MHz, P=2 -> 168MHz */
    RCC->PLLCFGR = (8 << RCC_PLLCFGR_PLLM_Pos)
                 | (336 << RCC_PLLCFGR_PLLN_Pos)
                 | (0 << RCC_PLLCFGR_PLLP_Pos)   // PLLP = 2
                 | (7 << RCC_PLLCFGR_PLLQ_Pos)
                 | RCC_PLLCFGR_PLLSRC_HSE;

    /* Enable PLL */
    RCC->CR |= RCC_CR_PLLON;
    while (!(RCC->CR & RCC_CR_PLLRDY));

    /* Chọn PLL làm clock hệ thống, AHB prescaler = 1, APB1 = /4, APB2 = /2 */
    RCC->CFGR = RCC_CFGR_SW_PLL
              | RCC_CFGR_HPRE_DIV1
              | RCC_CFGR_PPRE1_DIV4
              | RCC_CFGR_PPRE2_DIV2;
    while ((RCC->CFGR & RCC_CFGR_SWS) != RCC_CFGR_SWS_PLL);
}
