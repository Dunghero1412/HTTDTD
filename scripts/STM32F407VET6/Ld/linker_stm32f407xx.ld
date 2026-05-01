ENTRY(Reset_Handler)        /* Entry point of program, stored in ELF header. */

/* ── Stack top: cuối SRAM (0x20000000 + 128K) ──────────────────────────────
 * startup file cần symbol _estack để khởi tạo SP.                          */
_estack = ORIGIN(SRAM) + LENGTH(SRAM);   /* = 0x20020000 */

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08000000, LENGTH = 512K   /* STM32F407VET6: 512KB Flash */
    SRAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 128K   /* STM32F407VET6: 128KB SRAM  */
}

SECTIONS
{
    /* ── .text: code + read-only data → FLASH ──────────────────────────── */
    .text :
    {
        *(.isr_vector)      /* Vector table phải đứng đầu FLASH */
        *(.text)
        *(.text.*)
        *(.init)
        *(.fini)
        *(.rodata)
        *(.rodata.*)
        . = ALIGN(4);
        _end_of_text = .;
    }> FLASH

    /* ── .data: biến khởi tạo → LMA=FLASH, VMA=SRAM ───────────────────── */
    _load_data = LOADADDR(.data);   /* LMA của .data trong FLASH  */
    _sidata    = _load_data;        /* Alias startup cần           */

    .data :
    {
        _start_of_data = .;
        _sdata         = .;         /* Alias startup cần           */
        *(.data)
        *(.data.*)
        . = ALIGN(4);
        _end_of_data = .;
        _edata       = .;           /* Alias startup cần           */
    }> SRAM AT> FLASH

    /* ── .bss: biến chưa khởi tạo → SRAM (zeroed at startup) ──────────── */
    .bss :
    {
        _start_of_bss = .;
        _sbss         = .;          /* Alias startup cần           */
        __bss_start__ = .;          /* Alias newlib nano.specs     */
        *(.bss)
        *(.bss.*)
        *(COMMON)
        . = ALIGN(4);
        _end_of_bss = .;
        _ebss       = .;            /* Alias startup cần           */
        __bss_end__ = .;            /* Alias newlib nano.specs     */
        . = ALIGN(4);
        end    = .;                 /* Heap start cho _sbrk()      */
        __end__ = .;
    }> SRAM
}
