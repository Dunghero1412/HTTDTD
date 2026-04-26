/**
 * gpio.c - GPIO configuration (Bare-metal, STM32F407VG)
 * -------------------------------------------------------
 * PA0  → TIM2_CH1 (Sensor A, AF01)
 * PA1  → TIM2_CH2 (Sensor B, AF01)
 * PA2  → TIM2_CH3 (Sensor C, AF01)
 * PA3  → TIM2_CH4 (Sensor D, AF01)
 * PB0  → DATA_READY output (Push-Pull)
 * PB12 → SPI2_NSS  (AF05)
 * PB13 → SPI2_SCK  (AF05)
 * PB14 → SPI2_MISO (AF05)
 * PB15 → SPI2_MOSI (AF05)
 *
 * FIX: Dùng đúng macro names theo STM32F4 header (phiên bản cũ):
 *   GPIO_MODER_MODERx_Pos  → pin * 2
 *   GPIO_PUPDR_PUPDx       → GPIO_PUPDR_PUPDRx
 *   GPIO_OTYPER_OTx        → GPIO_OTYPER_OT_x
 *   GPIO_OSPEEDR_OSPEEDx   → GPIO_OSPEEDER_OSPEEDRx
 *   GPIO_BSRR_BSx / BRx   → GPIO_BSRR_BS_x / BR_x
 */

#include "../inc/gpio.h"
#include "../inc/stm32f4xx.h"

/* ------------------------------------------------------------------ */
/* Helper macro: set AFR (Alternate Function Register)                 */
/* AFR[0] = AFRL (pin 0–7), AFR[1] = AFRH (pin 8–15)                 */
/* ------------------------------------------------------------------ */
#define AFRL_SET(gpio, pin, af) \
    ((gpio)->AFR[0] = ((gpio)->AFR[0] & ~(0xFU << ((pin) * 4U))) \
                    | ((af) << ((pin) * 4U)))

#define AFRH_SET(gpio, pin, af) \
    ((gpio)->AFR[1] = ((gpio)->AFR[1] & ~(0xFU << (((pin) - 8U) * 4U))) \
                    | ((af) << (((pin) - 8U) * 4U)))

/* ------------------------------------------------------------------ */
void GPIO_Init(void)
{
    /* ── 1. Bật clock GPIOA và GPIOB ─────────────────────────────── */
    RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN;
    __DSB();

    /* ================================================================
     * GPIOA – PA0–PA3: TIM2 Input Capture (AF01)
     * Mode = 10 (Alternate Function)
     * ================================================================ */

    /* MODER: clear rồi set AF mode (0b10) cho PA0–PA3 */
    GPIOA->MODER &= ~( (3U << (0U * 2U))   /* PA0 */
                     | (3U << (1U * 2U))   /* PA1 */
                     | (3U << (2U * 2U))   /* PA2 */
                     | (3U << (3U * 2U))); /* PA3 */
    GPIOA->MODER |=  ( (2U << (0U * 2U))
                     | (2U << (1U * 2U))
                     | (2U << (2U * 2U))
                     | (2U << (3U * 2U)));

    /* PUPDR: No pull (0b00) cho PA0–PA3
     * Tín hiệu từ OPA2134 đủ drive, không cần pull */
    GPIOA->PUPDR &= ~( (3U << (0U * 2U))
                     | (3U << (1U * 2U))
                     | (3U << (2U * 2U))
                     | (3U << (3U * 2U)));

    /* AFRL: PA0–PA3 → AF01 (TIM2) */
    AFRL_SET(GPIOA, 0U, 1U);
    AFRL_SET(GPIOA, 1U, 1U);
    AFRL_SET(GPIOA, 2U, 1U);
    AFRL_SET(GPIOA, 3U, 1U);

    /* ================================================================
     * GPIOB – PB0: DATA_READY Output Push-Pull
     * ================================================================ */

    /* MODER: Output (0b01) */
    GPIOB->MODER &= ~(3U << (0U * 2U));
    GPIOB->MODER |=  (1U << (0U * 2U));

    /* OTYPER: Push-pull (bit = 0) */
    GPIOB->OTYPER &= ~GPIO_OTYPER_OT_0;

    /* OSPEEDR: High speed (0b10) */
    GPIOB->OSPEEDR &= ~(3U << (0U * 2U));
    GPIOB->OSPEEDR |=  (2U << (0U * 2U));

    /* PUPDR: No pull */
    GPIOB->PUPDR &= ~(3U << (0U * 2U));

    /* BSRR: Default LOW (BR0) */
    GPIOB->BSRR = GPIO_BSRR_BR_0;

    /* ================================================================
     * GPIOB – PB12–PB15: SPI2 Alternate Function (AF05)
     * ================================================================ */

    /* MODER: AF mode (0b10) cho PB12–PB15 */
    GPIOB->MODER &= ~( (3U << (12U * 2U))
                     | (3U << (13U * 2U))
                     | (3U << (14U * 2U))
                     | (3U << (15U * 2U)));
    GPIOB->MODER |=  ( (2U << (12U * 2U))
                     | (2U << (13U * 2U))
                     | (2U << (14U * 2U))
                     | (2U << (15U * 2U)));

    /* OTYPER: Push-pull cho PB12–PB15 */
    GPIOB->OTYPER &= ~( GPIO_OTYPER_OT_12
                      | GPIO_OTYPER_OT_13
                      | GPIO_OTYPER_OT_14
                      | GPIO_OTYPER_OT_15);

    /* OSPEEDR: Very high speed (0b11) cho SPI */
    GPIOB->OSPEEDR &= ~( (3U << (12U * 2U))
                       | (3U << (13U * 2U))
                       | (3U << (14U * 2U))
                       | (3U << (15U * 2U)));
    GPIOB->OSPEEDR |=  ( (3U << (12U * 2U))
                       | (3U << (13U * 2U))
                       | (3U << (14U * 2U))
                       | (3U << (15U * 2U)));

    /* PUPDR: No pull cho PB12–PB15 */
    GPIOB->PUPDR &= ~( (3U << (12U * 2U))
                     | (3U << (13U * 2U))
                     | (3U << (14U * 2U))
                     | (3U << (15U * 2U)));

    /* AFRH: PB12–PB15 → AF05 (SPI2) */
    AFRH_SET(GPIOB, 12U, 5U);
    AFRH_SET(GPIOB, 13U, 5U);
    AFRH_SET(GPIOB, 14U, 5U);
    AFRH_SET(GPIOB, 15U, 5U);
}

/* ------------------------------------------------------------------ */
void GPIO_DataReady_Set(void)
{
    GPIOB->BSRR = GPIO_BSRR_BS_0;   /* PB0 = HIGH (atomic set) */
}

void GPIO_DataReady_Clear(void)
{
    GPIOB->BSRR = GPIO_BSRR_BR_0;   /* PB0 = LOW  (atomic reset) */
}
