/**
 * gpio.c - GPIO configuration (Bare-metal, STM32F407VG)
 * -------------------------------------------------------
 * PA1  → TIM2_CH2  (Sensor A, AF01, Input)
 * PA2  → TIM2_CH3  (Sensor B, AF01, Input)
 * PA3  → TIM2_CH4  (Sensor C, AF01, Input)
 * PA4  → không dùng TIM2 (PA4 không có TIM2 AF trên F407)
 *         → dùng TIM2_CH1 = PA0 hoặc PA5
 *         *** Xem note bên dưới ***
 *
 * Thực tế TIM2 Input Capture trên STM32F407 (AF01):
 *   TIM2_CH1 → PA0 hoặc PA5  (PA1 = TIM2_CH2 trên một số ref)
 *   TIM2_CH2 → PA1
 *   TIM2_CH3 → PA2
 *   TIM2_CH4 → PA3
 *
 * Theo yêu cầu bạn đặt:
 *   Sensor A → PA1 (TIM2_CH2)
 *   Sensor B → PA2 (TIM2_CH3)
 *   Sensor C → PA3 (TIM2_CH4)
 *   Sensor D → PA0 (TIM2_CH1)  ← dùng PA0 thay PA4 vì PA4 không có TIM2 AF
 *
 * PB0  → DATA_READY output (Push-Pull, no pull)
 *
 * SPI2 pins (Slave):
 *   PB13 → SPI2_SCK  (AF05)
 *   PB14 → SPI2_MISO (AF05)
 *   PB15 → SPI2_MOSI (AF05)
 *   PB12 → SPI2_NSS  (AF05)
 */

#include "gpio.h"
#include "stm32f4xx.h"   /* CMSIS header – đảm bảo include path đúng */

/* ------------------------------------------------------------------ */
/* Macro helpers                                                        */
/* ------------------------------------------------------------------ */
#define AFRL_SET(reg, pin, af)  \
    ((reg) = ((reg) & ~(0xFU << ((pin)*4))) | ((af) << ((pin)*4)))

#define AFRH_SET(reg, pin, af)  \
    ((reg) = ((reg) & ~(0xFU << (((pin)-8)*4))) | ((af) << (((pin)-8)*4)))

/* ------------------------------------------------------------------ */
void GPIO_Init(void)
{
    /* ── 1. Bật clock GPIOA và GPIOB ─────────────────────────────── */
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN;
    __DSB();   /* đảm bảo clock ổn định trước khi truy cập register */

    /* ================================================================
     * GPIOA – TIM2 Input Capture pins
     * PA0 = TIM2_CH1 (Sensor D)
     * PA1 = TIM2_CH2 (Sensor A)
     * PA2 = TIM2_CH3 (Sensor B)
     * PA3 = TIM2_CH4 (Sensor C)
     * Mode: Alternate Function (10)
     * ================================================================ */

    /* MODER: set PA0, PA1, PA2, PA3 → AF mode (0b10) */
    GPIOA->MODER &= ~( GPIO_MODER_MODER0 | GPIO_MODER_MODER1
                     | GPIO_MODER_MODER2 | GPIO_MODER_MODER3);
    GPIOA->MODER |=  ( (2U << GPIO_MODER_MODER0_Pos)
                     | (2U << GPIO_MODER_MODER1_Pos)
                     | (2U << GPIO_MODER_MODER2_Pos)
                     | (2U << GPIO_MODER_MODER3_Pos));

    /* OTYPER: Push-pull (default = 0, không cần set) */

    /* OSPEEDR: không quan trọng với input, để default */

    /* PUPDR: No pull (floating – tín hiệu từ OPA2134 đủ drive) */
    GPIOA->PUPDR &= ~( GPIO_PUPDR_PUPD0 | GPIO_PUPDR_PUPD1
                     | GPIO_PUPDR_PUPD2 | GPIO_PUPDR_PUPD3);

    /* AFRL: PA0–PA3 → AF01 (TIM2) */
    AFRL_SET(GPIOA->AFR[0], 0, 1U);   /* PA0 → AF01 */
    AFRL_SET(GPIOA->AFR[0], 1, 1U);   /* PA1 → AF01 */
    AFRL_SET(GPIOA->AFR[0], 2, 1U);   /* PA2 → AF01 */
    AFRL_SET(GPIOA->AFR[0], 3, 1U);   /* PA3 → AF01 */

    /* ================================================================
     * GPIOB – PB0  : DATA_READY output
     *         PB12 : SPI2_NSS  (AF05)
     *         PB13 : SPI2_SCK  (AF05)
     *         PB14 : SPI2_MISO (AF05)
     *         PB15 : SPI2_MOSI (AF05)
     * ================================================================ */

    /* ── PB0: Output Push-Pull ──────────────────────────────────── */
    GPIOB->MODER &= ~GPIO_MODER_MODER0;
    GPIOB->MODER |=  (1U << GPIO_MODER_MODER0_Pos);   /* Output */
    GPIOB->OTYPER  &= ~GPIO_OTYPER_OT0;               /* Push-pull */
    GPIOB->OSPEEDR &= ~GPIO_OSPEEDR_OSPEED0;
    GPIOB->OSPEEDR |=  (2U << GPIO_OSPEEDR_OSPEED0_Pos); /* High speed */
    GPIOB->PUPDR   &= ~GPIO_PUPDR_PUPD0;              /* No pull */
    GPIOB->BSRR     =  GPIO_BSRR_BR0;                 /* Default LOW */

    /* ── PB12–PB15: SPI2 Alternate Function AF05 ────────────────── */
    /* MODER: AF mode (0b10) */
    GPIOB->MODER &= ~( GPIO_MODER_MODER12 | GPIO_MODER_MODER13
                     | GPIO_MODER_MODER14 | GPIO_MODER_MODER15);
    GPIOB->MODER |=  ( (2U << GPIO_MODER_MODER12_Pos)
                     | (2U << GPIO_MODER_MODER13_Pos)
                     | (2U << GPIO_MODER_MODER14_Pos)
                     | (2U << GPIO_MODER_MODER15_Pos));

    /* OTYPER: Push-pull cho tất cả */
    GPIOB->OTYPER &= ~( GPIO_OTYPER_OT12 | GPIO_OTYPER_OT13
                      | GPIO_OTYPER_OT14 | GPIO_OTYPER_OT15);

    /* OSPEEDR: Very high speed cho SPI */
    GPIOB->OSPEEDR &= ~( GPIO_OSPEEDR_OSPEED12 | GPIO_OSPEEDR_OSPEED13
                       | GPIO_OSPEEDR_OSPEED14 | GPIO_OSPEEDR_OSPEED15);
    GPIOB->OSPEEDR |=  ( (3U << GPIO_OSPEEDR_OSPEED12_Pos)
                       | (3U << GPIO_OSPEEDR_OSPEED13_Pos)
                       | (3U << GPIO_OSPEEDR_OSPEED14_Pos)
                       | (3U << GPIO_OSPEEDR_OSPEED15_Pos));

    /* PUPDR: No pull */
    GPIOB->PUPDR &= ~( GPIO_PUPDR_PUPD12 | GPIO_PUPDR_PUPD13
                     | GPIO_PUPDR_PUPD14 | GPIO_PUPDR_PUPD15);

    /* AFRH: PB12–PB15 → AF05 (SPI2) */
    AFRH_SET(GPIOB->AFR[1], 12, 5U);
    AFRH_SET(GPIOB->AFR[1], 13, 5U);
    AFRH_SET(GPIOB->AFR[1], 14, 5U);
    AFRH_SET(GPIOB->AFR[1], 15, 5U);
}

/* ------------------------------------------------------------------ */
/* DATA_READY helpers                                                   */
/* ------------------------------------------------------------------ */

void GPIO_DataReady_Set(void)
{
    GPIOB->BSRR = GPIO_BSRR_BS0;   /* PB0 = HIGH */
}

void GPIO_DataReady_Clear(void)
{
    GPIOB->BSRR = GPIO_BSRR_BR0;   /* PB0 = LOW */
}
