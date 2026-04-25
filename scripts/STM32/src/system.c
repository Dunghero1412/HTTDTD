/**
 * system.c - System initialization and clock configuration
 * 
 * 🔧 HOẠT ĐỘNG:
 * 1. Khởi tạo HSE (High Speed External) oscillator 8MHz
 * 2. Setup PLL để tăng lên 168MHz
 * 3. Config prescaler cho AHB, APB1, APB2
 * 4. Disable HSI (High Speed Internal) để tiết kiệm power
 */

#include "stm32f407xx.h"
#include "config.h"

// ✓ System core clock (được fill bởi SystemClock_Config)
uint32_t SystemCoreClock = SYSTEM_CLOCK_HZ;

/**
 * SystemClock_Config - Configure system clock to 168MHz
 * 
 * 🔧 QUY TRÌNH:
 * 1. Enable HSE (8MHz external crystal)
 * 2. Setup PLL:
 *    - Input: 8MHz HSE
 *    - M (prescaler): 8 → 1MHz
 *    - N (multiplier): 336 → 336MHz
 *    - P (main prescaler): 2 → 168MHz
 *    - Q (USB prescaler): 7 → 48MHz
 * 3. Enable PLL
 * 4. Switch system clock to PLL
 * 5. Setup prescaler (AHB, APB1, APB2)
 */
void SystemClock_Config(void) {
    // ✓ Enable Power Control Clock
    // RCC_APB1ENR bit 28 = Power control clock enable
    RCC->APB1ENR |= (1 << 28);
    
    // ✓ Set voltage regulator scale
    // Cần VOS (voltage output scale) = 11 để hỗ trợ 168MHz
    // Đây là register trong PWR (Power control)
    // Bước này không essential nếu không stress test
    
    // === STEP 1: Enable HSE (High Speed External) ===
    // RCC_CR bit 16 = HSEON (HSE oscillator enable)
    RCC->CR |= (1 << 16);
    
    // ✓ Wait for HSE to stabilize
    // RCC_CR bit 17 = HSERDY (HSE ready)
    while ((RCC->CR & (1 << 17)) == 0);  // Chờ HSE stable
    
    // === STEP 2: Configure PLL ===
    // RCC_PLLCFGR: (offset 0x04)
    // Bits [27:24] PLLQ = Q divider for USB/SDIO
    // Bits [16:0]  PLLP = P divider (main output)
    // Bits [14:6]  PLLN = N multiplier
    // Bits [5:0]   PLLM = M prescaler
    
    uint32_t pllcfgr = 0;
    
    // PLLM = 8 (bits 5:0)
    // HSE / PLLM = 8MHz / 8 = 1MHz
    pllcfgr |= 8;
    
    // PLLN = 336 (bits 14:6)
    // 1MHz × 336 = 336MHz
    pllcfgr |= (336 << 6);
    
    // PLLP = 2 (bits 17:16)
    // 336MHz / 2 = 168MHz (main output)
    // Note: PLLP value = (N+1), so we want 2 = 0 in register
    pllcfgr |= (0 << 16);  // PLLP = 2
    
    // PLLQ = 7 (bits 27:24)
    // 336MHz / 7 = 48MHz (for USB)
    pllcfgr |= (7 << 24);
    
    // PLLSRC = 1 (bit 22) - select HSE as PLL input
    pllcfgr |= (1 << 22);
    
    // ✓ Write PLL config
    RCC->PLLCFGR = pllcfgr;
    
    // === STEP 3: Enable PLL ===
    // RCC_CR bit 24 = PLLON (PLL enable)
    RCC->CR |= (1 << 24);
    
    // ✓ Wait for PLL to lock
    // RCC_CR bit 25 = PLLRDY (PLL ready)
    while ((RCC->CR & (1 << 25)) == 0);  // Chờ PLL lock
    
    // === STEP 4: Configure prescaler ===
    uint32_t cfgr = 0;
    
    // AHB prescaler = 1 (HPRE bits 7:4)
    // SYSCLK / 1 = 168MHz
    cfgr |= (0 << 4);  // HPRE = 0 (prescaler 1)
    
    // APB1 prescaler = 4 (PPRE1 bits 12:10)
    // AHB / 4 = 168 / 4 = 42MHz
    cfgr |= (5 << 10);  // PPRE1 = 101 (prescaler 4)
    
    // APB2 prescaler = 2 (PPRE2 bits 15:13)
    // AHB / 2 = 168 / 2 = 84MHz
    cfgr |= (4 << 13);  // PPRE2 = 100 (prescaler 2)
    
    // ✓ Switch system clock to PLL (SW bits 1:0)
    // SW = 10 means select PLL as system clock
    cfgr |= (2 << 0);  // SW = 10
    
    // ✓ Write config
    RCC->CFGR = cfgr;
    
    // ✓ Wait for clock switch to complete
    // SWS bits 3:2 should show current clock source
    while ((RCC->CFGR & (3 << 2)) != (2 << 2));
    
    // === STEP 5: Update SystemCoreClock ===
    SystemCoreClock = SYSTEM_CLOCK_HZ;
}

/**
 * NVIC_Config - Configure Nested Vectored Interrupt Controller
 * 
 * 🔧 HOẠT ĐỘNG:
 * Enable interrupts cho:
 * - TIM2 (IRQn 28)
 * - SPI1 (IRQn 35)
 * - USART1 (IRQn 37)
 */
void NVIC_Config(void) {
    // ✓ Enable TIM2 interrupt (IRQn 28)
    // ISER0 = bit 28 (vì IRQn < 32)
    NVIC->ISER[0] |= (1 << 28);
    
    // ✓ Enable SPI1 interrupt (IRQn 35)
    // ISER1 = bit (35 - 32) = bit 3
    NVIC->ISER[1] |= (1 << 3);
    
    // ✓ Enable USART1 interrupt (IRQn 37)
    // ISER1 = bit (37 - 32) = bit 5
    NVIC->ISER[1] |= (1 << 5);
    
    // ✓ Set interrupt priorities (optional)
    // IP register stores priority for each interrupt
    // Lower number = higher priority
    // Each interrupt has 4 bits (0-15)
    
    // TIM2 priority = 0 (highest, capture must be fast)
    NVIC->IP[28] = 0 << 4;
    
    // SPI1 priority = 1
    NVIC->IP[35] = 1 << 4;
    
    // USART1 priority = 2
    NVIC->IP[37] = 2 << 4;
}