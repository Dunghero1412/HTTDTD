#include "gpio_control.h"

void GPIO_Control_Init(void) {
    /* ── Enable clocks ──────────────────────────────── */
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOBEN;   // GPIOB cho PB0, PB1
    __DSB();  // đảm bảo clock ổn định trước khi config

    /* ── PB0 → OUTPUT (DATA_READY) ─────────────────── */
    GPIOB->MODER  &= ~(3U << (DATA_READY_PIN * 2));
    GPIOB->MODER  |=  (1U << (DATA_READY_PIN * 2));   // Output push-pull
    GPIOB->OTYPER &= ~(1U << DATA_READY_PIN);          // Push-pull
    GPIOB->OSPEEDR|=  (3U << (DATA_READY_PIN * 2));    // Very high speed
    GPIOB->PUPDR  &= ~(3U << (DATA_READY_PIN * 2));    // No pull
    GPIOB->ODR    &= ~(1U << DATA_READY_PIN);           // Mặc định Low

    /* ── PB1 → INPUT (RUN_TRG) ─────────────────────── */
    GPIOB->MODER  &= ~(3U << (RUN_TRG_PIN * 2));       // Input mode
    GPIOB->PUPDR  &= ~(3U << (RUN_TRG_PIN * 2));
    GPIOB->PUPDR  |=  (2U << (RUN_TRG_PIN * 2));       // Pull-down
    // (công tắc nối 3.3V → High khi bật, pull-down giữ Low khi tắt)
}

void DataReady_Set(void) {
    GPIOB->BSRR = (1U << DATA_READY_PIN);   // Atomic set High
}

void DataReady_Clear(void) {
    GPIOB->BSRR = (1U << (DATA_READY_PIN + 16));  // Atomic set Low
}

bool DataReady_IsHigh(void) {
    return (GPIOB->ODR & (1U << DATA_READY_PIN)) != 0;
}

bool RunTrg_IsHigh(void) {
    return (GPIOB->IDR & (1U << RUN_TRG_PIN)) != 0;
}
