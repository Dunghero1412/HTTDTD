/**
 * system.c - System initialization and clock configuration
 * 
 * 🔧 HOẠT ĐỘNG:
 * 1. Khởi tạo HSE (High Speed External) oscillator 8MHz
 * 2. Setup PLL để tăng lên 168MHz
 * 3. Config prescaler cho AHB, APB1, APB2
 * 4. Disable HSI (High Speed Internal) để tiết kiệm power
 */

#include "../inc/stm32f407xx.h"
#include "../inc/config.h"

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
 * Enable interrupts cho đúng các ngoại vi đang dùng:
 *   - TIM2           (IRQn 28)  ← Input Capture 4 kênh
 *   - SPI2           (IRQn 36)  ← SPI Slave error handling
 *   - DMA1_Stream4   (IRQn 15)  ← SPI2 TX DMA transfer complete
 *
 * FIX: Phiên bản cũ enable nhầm SPI1 (IRQn 35) và USART1 (IRQn 37).
 *      Hệ thống dùng SPI2 và không dùng USART → sửa lại cho đúng.
 *      Enable nhầm interrupt có thể trigger Default_Handler nếu
 *      peripheral đó có cờ pending từ trạng thái reset.
 */
void NVIC_Config(void) {
    /* ── TIM2 (IRQn 28) – priority 0 (cao nhất) ─────────────────
     * Capture timestamp phải nhanh nhất, không được trễ            */
    NVIC->ISER[0] |= (1U << 28);   /* ISER0 bit 28 */
    NVIC->IP[28]   = (0U << 4);    /* Priority 0 */

    /* ── SPI2 (IRQn 36) – priority 1 ────────────────────────────
     * Xử lý lỗi OVR / MODF của SPI2 Slave                         */
    NVIC->ISER[1] |= (1U << (36 - 32));  /* ISER1 bit 4 */
    NVIC->IP[36]   = (1U << 4);          /* Priority 1 */

    /* ── DMA1 Stream4 (IRQn 15) – priority 1 ────────────────────
     * Transfer complete / error của SPI2 TX DMA                    */
    NVIC->ISER[0] |= (1U << 15);   /* ISER0 bit 15 */
    NVIC->IP[15]   = (1U << 4);    /* Priority 1 */
}
