/**
 * startup_stm32f407xx.s
 * Startup file cho STM32F407VG – GNU AS syntax (arm-none-eabi-gcc)
 *
 * Chức năng:
 *   1. Định nghĩa vector table (stack pointer + tất cả IRQ handler)
 *   2. Reset_Handler: copy .data từ Flash→RAM, zero .bss, gọi main()
 *   3. Default_Handler: vòng lặp vô hạn cho mọi IRQ chưa implement
 */
 /* Ghi chú syntax GAS:
 *   @ hoặc   = comment (không dùng ; hay // trong .s) */
/*   .thumb_func   = báo assembler hàm tiếp theo là Thumb
 *   .weak         = có thể bị override bởi định nghĩa mạnh hơn trong .c
 *   .type X, %function = khai báo kiểu symbol
 */

    .syntax unified
    .cpu cortex-m4
    .fpu fpv4-sp-d16
    .thumb

/* ============================================================
 * Stack và Heap size
 * Thay đổi tại đây nếu cần (hoặc override trong linker script)
 * ============================================================ */
    .equ    Stack_Size, 0x400       /* 1 KB stack */
    .equ    Heap_Size,  0x200       /* 512 B heap  */

/* ============================================================
 * Stack section
 * ============================================================ */
    .section .stack, "w", %nobits
    .align  3
__stack_start__:
    .space  Stack_Size
    .global __stack_end__
__stack_end__:

/* ============================================================
 * Heap section
 * ============================================================ */
    .section .heap, "w", %nobits
    .align  3
    .global __heap_start__
__heap_start__:
    .space  Heap_Size
    .global __heap_end__
__heap_end__:

/* ============================================================
 * VECTOR TABLE
 * Phải nằm ở đầu Flash (0x08000000) – linker script đặt
 * section .isr_vector tại địa chỉ đó.
 * ============================================================ */
    .section .isr_vector, "a", %progbits
    .type   g_pfnVectors, %object
    .global g_pfnVectors

g_pfnVectors:
    /* Cortex-M4 core exceptions */
    .word   __stack_end__           /* 0x00: Initial Stack Pointer   */
    .word   Reset_Handler           /* 0x04: Reset                   */
    .word   NMI_Handler             /* 0x08: NMI                     */
    .word   HardFault_Handler       /* 0x0C: Hard Fault              */
    .word   MemManage_Handler       /* 0x10: MPU Fault               */
    .word   BusFault_Handler        /* 0x14: Bus Fault               */
    .word   UsageFault_Handler      /* 0x18: Usage Fault             */
    .word   0                       /* 0x1C: Reserved                */
    .word   0                       /* 0x20: Reserved                */
    .word   0                       /* 0x24: Reserved                */
    .word   0                       /* 0x28: Reserved                */
    .word   SVC_Handler             /* 0x2C: SVCall                  */
    .word   DebugMon_Handler        /* 0x30: Debug Monitor           */
    .word   0                       /* 0x34: Reserved                */
    .word   PendSV_Handler          /* 0x38: PendSV                  */
    .word   SysTick_Handler         /* 0x3C: SysTick                 */

    /* STM32F407 peripheral IRQs (position 0–85) */
    .word   WWDG_IRQHandler                 /* 0:  Window Watchdog         */
    .word   PVD_IRQHandler                  /* 1:  PVD via EXTI            */
    .word   TAMP_STAMP_IRQHandler           /* 2:  Tamper/Timestamp        */
    .word   RTC_WKUP_IRQHandler             /* 3:  RTC Wakeup              */
    .word   FLASH_IRQHandler                /* 4:  Flash                   */
    .word   RCC_IRQHandler                  /* 5:  RCC                     */
    .word   EXTI0_IRQHandler                /* 6:  EXTI0                   */
    .word   EXTI1_IRQHandler                /* 7:  EXTI1                   */
    .word   EXTI2_IRQHandler                /* 8:  EXTI2                   */
    .word   EXTI3_IRQHandler                /* 9:  EXTI3                   */
    .word   EXTI4_IRQHandler                /* 10: EXTI4                   */
    .word   DMA1_Stream0_IRQHandler         /* 11: DMA1 Stream0            */
    .word   DMA1_Stream1_IRQHandler         /* 12: DMA1 Stream1            */
    .word   DMA1_Stream2_IRQHandler         /* 13: DMA1 Stream2            */
    .word   DMA1_Stream3_IRQHandler         /* 14: DMA1 Stream3            */
    .word   DMA1_Stream4_IRQHandler         /* 15: DMA1 Stream4 ← SPI2 TX */
    .word   DMA1_Stream5_IRQHandler         /* 16: DMA1 Stream5            */
    .word   DMA1_Stream6_IRQHandler         /* 17: DMA1 Stream6            */
    .word   ADC_IRQHandler                  /* 18: ADC1/2/3                */
    .word   CAN1_TX_IRQHandler              /* 19: CAN1 TX                 */
    .word   CAN1_RX0_IRQHandler             /* 20: CAN1 RX0                */
    .word   CAN1_RX1_IRQHandler             /* 21: CAN1 RX1                */
    .word   CAN1_SCE_IRQHandler             /* 22: CAN1 SCE                */
    .word   EXTI9_5_IRQHandler              /* 23: EXTI9..5                */
    .word   TIM1_BRK_TIM9_IRQHandler        /* 24: TIM1 Break / TIM9       */
    .word   TIM1_UP_TIM10_IRQHandler        /* 25: TIM1 Update / TIM10     */
    .word   TIM1_TRG_COM_TIM11_IRQHandler   /* 26: TIM1 Trigger / TIM11   */
    .word   TIM1_CC_IRQHandler              /* 27: TIM1 Capture Compare    */
    .word   TIM2_IRQHandler                 /* 28: TIM2 ← dùng trong code */
    .word   TIM3_IRQHandler                 /* 29: TIM3                    */
    .word   TIM4_IRQHandler                 /* 30: TIM4                    */
    .word   I2C1_EV_IRQHandler              /* 31: I2C1 Event              */
    .word   I2C1_ER_IRQHandler              /* 32: I2C1 Error              */
    .word   I2C2_EV_IRQHandler              /* 33: I2C2 Event              */
    .word   I2C2_ER_IRQHandler              /* 34: I2C2 Error              */
    .word   SPI1_IRQHandler                 /* 35: SPI1                    */
    .word   SPI2_IRQHandler                 /* 36: SPI2 ← dùng trong code */
    .word   USART1_IRQHandler               /* 37: USART1                  */
    .word   USART2_IRQHandler               /* 38: USART2                  */
    .word   USART3_IRQHandler               /* 39: USART3                  */
    .word   EXTI15_10_IRQHandler            /* 40: EXTI15..10              */
    .word   RTC_Alarm_IRQHandler            /* 41: RTC Alarm               */
    .word   OTG_FS_WKUP_IRQHandler          /* 42: USB OTG FS Wakeup       */
    .word   TIM8_BRK_TIM12_IRQHandler       /* 43: TIM8 Break / TIM12      */
    .word   TIM8_UP_TIM13_IRQHandler        /* 44: TIM8 Update / TIM13     */
    .word   TIM8_TRG_COM_TIM14_IRQHandler   /* 45: TIM8 Trigger / TIM14   */
    .word   TIM8_CC_IRQHandler              /* 46: TIM8 Capture Compare    */
    .word   DMA1_Stream7_IRQHandler         /* 47: DMA1 Stream7            */
    .word   FMC_IRQHandler                  /* 48: FMC                     */
    .word   SDIO_IRQHandler                 /* 49: SDIO                    */
    .word   TIM5_IRQHandler                 /* 50: TIM5                    */
    .word   SPI3_IRQHandler                 /* 51: SPI3                    */
    .word   UART4_IRQHandler                /* 52: UART4                   */
    .word   UART5_IRQHandler                /* 53: UART5                   */
    .word   TIM6_DAC_IRQHandler             /* 54: TIM6 / DAC              */
    .word   TIM7_IRQHandler                 /* 55: TIM7                    */
    .word   DMA2_Stream0_IRQHandler         /* 56: DMA2 Stream0            */
    .word   DMA2_Stream1_IRQHandler         /* 57: DMA2 Stream1            */
    .word   DMA2_Stream2_IRQHandler         /* 58: DMA2 Stream2            */
    .word   DMA2_Stream3_IRQHandler         /* 59: DMA2 Stream3            */
    .word   DMA2_Stream4_IRQHandler         /* 60: DMA2 Stream4            */
    .word   ETH_IRQHandler                  /* 61: Ethernet                */
    .word   ETH_WKUP_IRQHandler             /* 62: Ethernet Wakeup         */
    .word   CAN2_TX_IRQHandler              /* 63: CAN2 TX                 */
    .word   CAN2_RX0_IRQHandler             /* 64: CAN2 RX0                */
    .word   CAN2_RX1_IRQHandler             /* 65: CAN2 RX1                */
    .word   CAN2_SCE_IRQHandler             /* 66: CAN2 SCE                */
    .word   OTG_FS_IRQHandler               /* 67: USB OTG FS              */
    .word   DMA2_Stream5_IRQHandler         /* 68: DMA2 Stream5            */
    .word   DMA2_Stream6_IRQHandler         /* 69: DMA2 Stream6            */
    .word   DMA2_Stream7_IRQHandler         /* 70: DMA2 Stream7            */
    .word   USART6_IRQHandler               /* 71: USART6                  */
    .word   I2C3_EV_IRQHandler              /* 72: I2C3 Event              */
    .word   I2C3_ER_IRQHandler              /* 73: I2C3 Error              */
    .word   OTG_HS_EP1_OUT_IRQHandler       /* 74: USB OTG HS EP1 OUT      */
    .word   OTG_HS_EP1_IN_IRQHandler        /* 75: USB OTG HS EP1 IN       */
    .word   OTG_HS_WKUP_IRQHandler          /* 76: USB OTG HS Wakeup       */
    .word   OTG_HS_IRQHandler               /* 77: USB OTG HS              */
    .word   DCMI_IRQHandler                 /* 78: DCMI                    */
    .word   0                               /* 79: Reserved                */
    .word   HASH_RNG_IRQHandler             /* 80: Hash/RNG                */
    .word   FPU_IRQHandler                  /* 81: FPU                     */

/* ============================================================
 * RESET HANDLER
 * Chạy ngay sau khi reset, trước main()
 * ============================================================ */
    .section .text.Reset_Handler, "ax", %progbits
    .global Reset_Handler
    .type   Reset_Handler, %function
    .thumb_func

Reset_Handler:
    /* ── 1. Copy .data section từ Flash → RAM ────────────────── */
    /*
     * Linker script cung cấp:
     *   _sidata = địa chỉ .data trong Flash (Load Memory Address)
     *   _sdata  = địa chỉ đầu .data trong RAM
     *   _edata  = địa chỉ cuối .data trong RAM
     */
    ldr     r0, =_sidata        @ src: .data trong Flash
    ldr     r1, =_sdata         @ dst start: .data trong RAM
    ldr     r2, =_edata         @ dst end

    b       copy_data_check
copy_data_loop:
    ldr     r3, [r0], #4        @ đọc 4 byte từ Flash, tăng r0
    str     r3, [r1], #4        @ ghi 4 byte vào RAM, tăng r1
copy_data_check:
    cmp     r1, r2
    blt     copy_data_loop      @ tiếp tục nếu chưa đến _edata

    /* ── 2. Zero .bss section ────────────────────────────────── */
    /*
     *   _sbss = địa chỉ đầu .bss
     *   _ebss = địa chỉ cuối .bss
     */
    ldr     r0, =_sbss
    ldr     r1, =_ebss
    mov     r2, #0

    b       zero_bss_check
zero_bss_loop:
    str     r2, [r0], #4        @ ghi 0 vào RAM, tăng r0
zero_bss_check:
    cmp     r0, r1
    blt     zero_bss_loop

    /* ── 3. Gọi SystemInit() nếu có (setup PLL, clock) ──────── */
    /*
     * SystemClock_Config() trong system.c sẽ được gọi từ main().
     * Nếu muốn gọi trước main() thì uncomment dòng dưới:
     */
    @ bl      SystemInit

    /* ── 4. Gọi main() ───────────────────────────────────────── */
    bl      main

    /* ── 5. Nếu main() return (không nên xảy ra) → loop ─────── */
infinite_loop:
    b       infinite_loop

    .size   Reset_Handler, . - Reset_Handler

/* ============================================================
 * DEFAULT HANDLER
 * Tất cả IRQ chưa implement đều nhảy về đây → vòng lặp vô hạn
 * (dễ debug: đặt breakpoint tại Default_Handler)
 * ============================================================ */
    .section .text.Default_Handler, "ax", %progbits
    .global Default_Handler
    .type   Default_Handler, %function
    .thumb_func

Default_Handler:
    b       Default_Handler

    .size   Default_Handler, . - Default_Handler

/* ============================================================
 * WEAK ALIASES
 * Mọi IRQ handler mặc định trỏ về Default_Handler.
 * Để override: định nghĩa hàm cùng tên trong file .c của bạn
 * (ví dụ: void TIM2_IRQHandler(void) { ... } trong main.c)
 * ============================================================ */

    /* Cortex-M4 core */
    .weak   NMI_Handler
    .thumb_set NMI_Handler, Default_Handler

    .weak   HardFault_Handler
    .thumb_set HardFault_Handler, Default_Handler

    .weak   MemManage_Handler
    .thumb_set MemManage_Handler, Default_Handler

    .weak   BusFault_Handler
    .thumb_set BusFault_Handler, Default_Handler

    .weak   UsageFault_Handler
    .thumb_set UsageFault_Handler, Default_Handler

    .weak   SVC_Handler
    .thumb_set SVC_Handler, Default_Handler

    .weak   DebugMon_Handler
    .thumb_set DebugMon_Handler, Default_Handler

    .weak   PendSV_Handler
    .thumb_set PendSV_Handler, Default_Handler

    .weak   SysTick_Handler
    .thumb_set SysTick_Handler, Default_Handler

    /* STM32F407 peripherals */
    .weak   WWDG_IRQHandler
    .thumb_set WWDG_IRQHandler, Default_Handler

    .weak   PVD_IRQHandler
    .thumb_set PVD_IRQHandler, Default_Handler

    .weak   TAMP_STAMP_IRQHandler
    .thumb_set TAMP_STAMP_IRQHandler, Default_Handler

    .weak   RTC_WKUP_IRQHandler
    .thumb_set RTC_WKUP_IRQHandler, Default_Handler

    .weak   FLASH_IRQHandler
    .thumb_set FLASH_IRQHandler, Default_Handler

    .weak   RCC_IRQHandler
    .thumb_set RCC_IRQHandler, Default_Handler

    .weak   EXTI0_IRQHandler
    .thumb_set EXTI0_IRQHandler, Default_Handler

    .weak   EXTI1_IRQHandler
    .thumb_set EXTI1_IRQHandler, Default_Handler

    .weak   EXTI2_IRQHandler
    .thumb_set EXTI2_IRQHandler, Default_Handler

    .weak   EXTI3_IRQHandler
    .thumb_set EXTI3_IRQHandler, Default_Handler

    .weak   EXTI4_IRQHandler
    .thumb_set EXTI4_IRQHandler, Default_Handler

    .weak   DMA1_Stream0_IRQHandler
    .thumb_set DMA1_Stream0_IRQHandler, Default_Handler

    .weak   DMA1_Stream1_IRQHandler
    .thumb_set DMA1_Stream1_IRQHandler, Default_Handler

    .weak   DMA1_Stream2_IRQHandler
    .thumb_set DMA1_Stream2_IRQHandler, Default_Handler

    .weak   DMA1_Stream3_IRQHandler
    .thumb_set DMA1_Stream3_IRQHandler, Default_Handler

    .weak   DMA1_Stream4_IRQHandler
    .thumb_set DMA1_Stream4_IRQHandler, Default_Handler

    .weak   DMA1_Stream5_IRQHandler
    .thumb_set DMA1_Stream5_IRQHandler, Default_Handler

    .weak   DMA1_Stream6_IRQHandler
    .thumb_set DMA1_Stream6_IRQHandler, Default_Handler

    .weak   ADC_IRQHandler
    .thumb_set ADC_IRQHandler, Default_Handler

    .weak   CAN1_TX_IRQHandler
    .thumb_set CAN1_TX_IRQHandler, Default_Handler

    .weak   CAN1_RX0_IRQHandler
    .thumb_set CAN1_RX0_IRQHandler, Default_Handler

    .weak   CAN1_RX1_IRQHandler
    .thumb_set CAN1_RX1_IRQHandler, Default_Handler

    .weak   CAN1_SCE_IRQHandler
    .thumb_set CAN1_SCE_IRQHandler, Default_Handler

    .weak   EXTI9_5_IRQHandler
    .thumb_set EXTI9_5_IRQHandler, Default_Handler

    .weak   TIM1_BRK_TIM9_IRQHandler
    .thumb_set TIM1_BRK_TIM9_IRQHandler, Default_Handler

    .weak   TIM1_UP_TIM10_IRQHandler
    .thumb_set TIM1_UP_TIM10_IRQHandler, Default_Handler

    .weak   TIM1_TRG_COM_TIM11_IRQHandler
    .thumb_set TIM1_TRG_COM_TIM11_IRQHandler, Default_Handler

    .weak   TIM1_CC_IRQHandler
    .thumb_set TIM1_CC_IRQHandler, Default_Handler

    .weak   TIM2_IRQHandler
    .thumb_set TIM2_IRQHandler, Default_Handler

    .weak   TIM3_IRQHandler
    .thumb_set TIM3_IRQHandler, Default_Handler

    .weak   TIM4_IRQHandler
    .thumb_set TIM4_IRQHandler, Default_Handler

    .weak   I2C1_EV_IRQHandler
    .thumb_set I2C1_EV_IRQHandler, Default_Handler

    .weak   I2C1_ER_IRQHandler
    .thumb_set I2C1_ER_IRQHandler, Default_Handler

    .weak   I2C2_EV_IRQHandler
    .thumb_set I2C2_EV_IRQHandler, Default_Handler

    .weak   I2C2_ER_IRQHandler
    .thumb_set I2C2_ER_IRQHandler, Default_Handler

    .weak   SPI1_IRQHandler
    .thumb_set SPI1_IRQHandler, Default_Handler

    .weak   SPI2_IRQHandler
    .thumb_set SPI2_IRQHandler, Default_Handler

    .weak   USART1_IRQHandler
    .thumb_set USART1_IRQHandler, Default_Handler

    .weak   USART2_IRQHandler
    .thumb_set USART2_IRQHandler, Default_Handler

    .weak   USART3_IRQHandler
    .thumb_set USART3_IRQHandler, Default_Handler

    .weak   EXTI15_10_IRQHandler
    .thumb_set EXTI15_10_IRQHandler, Default_Handler

    .weak   RTC_Alarm_IRQHandler
    .thumb_set RTC_Alarm_IRQHandler, Default_Handler

    .weak   OTG_FS_WKUP_IRQHandler
    .thumb_set OTG_FS_WKUP_IRQHandler, Default_Handler

    .weak   TIM8_BRK_TIM12_IRQHandler
    .thumb_set TIM8_BRK_TIM12_IRQHandler, Default_Handler

    .weak   TIM8_UP_TIM13_IRQHandler
    .thumb_set TIM8_UP_TIM13_IRQHandler, Default_Handler

    .weak   TIM8_TRG_COM_TIM14_IRQHandler
    .thumb_set TIM8_TRG_COM_TIM14_IRQHandler, Default_Handler

    .weak   TIM8_CC_IRQHandler
    .thumb_set TIM8_CC_IRQHandler, Default_Handler

    .weak   DMA1_Stream7_IRQHandler
    .thumb_set DMA1_Stream7_IRQHandler, Default_Handler

    .weak   FMC_IRQHandler
    .thumb_set FMC_IRQHandler, Default_Handler

    .weak   SDIO_IRQHandler
    .thumb_set SDIO_IRQHandler, Default_Handler

    .weak   TIM5_IRQHandler
    .thumb_set TIM5_IRQHandler, Default_Handler

    .weak   SPI3_IRQHandler
    .thumb_set SPI3_IRQHandler, Default_Handler

    .weak   UART4_IRQHandler
    .thumb_set UART4_IRQHandler, Default_Handler

    .weak   UART5_IRQHandler
    .thumb_set UART5_IRQHandler, Default_Handler

    .weak   TIM6_DAC_IRQHandler
    .thumb_set TIM6_DAC_IRQHandler, Default_Handler

    .weak   TIM7_IRQHandler
    .thumb_set TIM7_IRQHandler, Default_Handler

    .weak   DMA2_Stream0_IRQHandler
    .thumb_set DMA2_Stream0_IRQHandler, Default_Handler

    .weak   DMA2_Stream1_IRQHandler
    .thumb_set DMA2_Stream1_IRQHandler, Default_Handler

    .weak   DMA2_Stream2_IRQHandler
    .thumb_set DMA2_Stream2_IRQHandler, Default_Handler

    .weak   DMA2_Stream3_IRQHandler
    .thumb_set DMA2_Stream3_IRQHandler, Default_Handler

    .weak   DMA2_Stream4_IRQHandler
    .thumb_set DMA2_Stream4_IRQHandler, Default_Handler

    .weak   ETH_IRQHandler
    .thumb_set ETH_IRQHandler, Default_Handler

    .weak   ETH_WKUP_IRQHandler
    .thumb_set ETH_WKUP_IRQHandler, Default_Handler

    .weak   CAN2_TX_IRQHandler
    .thumb_set CAN2_TX_IRQHandler, Default_Handler

    .weak   CAN2_RX0_IRQHandler
    .thumb_set CAN2_RX0_IRQHandler, Default_Handler

    .weak   CAN2_RX1_IRQHandler
    .thumb_set CAN2_RX1_IRQHandler, Default_Handler

    .weak   CAN2_SCE_IRQHandler
    .thumb_set CAN2_SCE_IRQHandler, Default_Handler

    .weak   OTG_FS_IRQHandler
    .thumb_set OTG_FS_IRQHandler, Default_Handler

    .weak   DMA2_Stream5_IRQHandler
    .thumb_set DMA2_Stream5_IRQHandler, Default_Handler

    .weak   DMA2_Stream6_IRQHandler
    .thumb_set DMA2_Stream6_IRQHandler, Default_Handler

    .weak   DMA2_Stream7_IRQHandler
    .thumb_set DMA2_Stream7_IRQHandler, Default_Handler

    .weak   USART6_IRQHandler
    .thumb_set USART6_IRQHandler, Default_Handler

    .weak   I2C3_EV_IRQHandler
    .thumb_set I2C3_EV_IRQHandler, Default_Handler

    .weak   I2C3_ER_IRQHandler
    .thumb_set I2C3_ER_IRQHandler, Default_Handler

    .weak   OTG_HS_EP1_OUT_IRQHandler
    .thumb_set OTG_HS_EP1_OUT_IRQHandler, Default_Handler

    .weak   OTG_HS_EP1_IN_IRQHandler
    .thumb_set OTG_HS_EP1_IN_IRQHandler, Default_Handler

    .weak   OTG_HS_WKUP_IRQHandler
    .thumb_set OTG_HS_WKUP_IRQHandler, Default_Handler

    .weak   OTG_HS_IRQHandler
    .thumb_set OTG_HS_IRQHandler, Default_Handler

    .weak   DCMI_IRQHandler
    .thumb_set DCMI_IRQHandler, Default_Handler

    .weak   HASH_RNG_IRQHandler
    .thumb_set HASH_RNG_IRQHandler, Default_Handler

    .weak   FPU_IRQHandler
    .thumb_set FPU_IRQHandler, Default_Handler

/* end of file */
