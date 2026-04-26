# ============================================================================
# STM32F407VG Makefile - Bare-metal, no OS
# ============================================================================
# Cấu trúc thư mục yêu cầu:
#   src/          ← source files (.c)
#   lib/          ← CMSIS headers, stm32f4xx.h ...
#   lib/startup/  ← startup_stm32f407xx.s
#   lib/ld/       ← stm32f407vg.ld  (linker script)
# ============================================================================

# ── Toolchain ───────────────────────────────────────────────────────────────
ARM_TOOLCHAIN = arm-none-eabi
CC      = $(ARM_TOOLCHAIN)-gcc
AS      = $(ARM_TOOLCHAIN)-gcc   # dùng gcc để assemble (tự nhận -x assembler-with-cpp)
AR      = $(ARM_TOOLCHAIN)-ar
OBJCOPY = $(ARM_TOOLCHAIN)-objcopy
OBJDUMP = $(ARM_TOOLCHAIN)-objdump
SIZE    = $(ARM_TOOLCHAIN)-size

# ── CPU / FPU flags ─────────────────────────────────────────────────────────
CPU_FLAGS  = -mcpu=cortex-m4
CPU_FLAGS += -mfpu=fpv4-sp-d16
CPU_FLAGS += -mfloat-abi=hard
CPU_FLAGS += -mthumb

# ── Compiler flags ──────────────────────────────────────────────────────────
CFLAGS  = $(CPU_FLAGS)
CFLAGS += -O2 -g
CFLAGS += -Wall -Wextra
CFLAGS += -ffunction-sections       # mỗi function 1 section → linker GC hiệu quả
CFLAGS += -fdata-sections           # mỗi data object 1 section
CFLAGS += -fno-common
CFLAGS += -ffreestanding            # bare-metal: không giả định stdlib đầy đủ
CFLAGS += -DSTM32F407xx             # define MCU cho CMSIS header

# ── Linker flags ─────────────────────────────────────────────────────────────
#
#   --specs=nano.specs   → dùng newlib-nano (nhỏ gọn, không cần -lg)
#   --specs=nosys.specs  → stub các syscall (write, read...) → loại bỏ -lg
#   -Wl,--gc-sections    → garbage collect section không dùng
#   -Wl,-Map             → tạo map file để debug linker
#   -T                   → linker script cho STM32F407VG (Flash/RAM layout)
#   -nostartfiles        → KHÔNG dùng (bỏ flag cũ) vì ta cung cấp startup file
#
#LDSCRIPT = lib/ld/stm32f407vg.ld
LDSCRIPT = ld/stm32f407vg_flash.ld

LDFLAGS  = $(CPU_FLAGS)
LDFLAGS += --specs=nano.specs
LDFLAGS += --specs=nosys.specs
LDFLAGS += -T$(LDSCRIPT)
LDFLAGS += -Wl,--gc-sections
LDFLAGS += -Wl,-Map=$(TARGET).map,--cref
LDFLAGS += -Wl,--print-memory-usage

# ── Include paths ────────────────────────────────────────────────────────────
INCLUDES  = -I./src
INCLUDES += -I./lib
INCLUDES += -I./lib/CMSIS/Include          # core_cm4.h, cmsis_gcc.h ...
INCLUDES += -I./lib/CMSIS/Device/ST/STM32F4xx/Include  # stm32f4xx.h
INCLUDE  += -I./inc/
# ── Sources ──────────────────────────────────────────────────────────────────
C_SOURCES = src/main.c    \
            src/system.c  \
            src/gpio.c    \
            src/timmer.c  \
            src/spi.c

# Startup file (assembly) – cung cấp Reset_Handler, vector table
#ASM_SOURCES = lib/startup/startup_stm32f407xx.s
ASM_SOURCES =  startup/startup_stm32f407xx.s

# Object files
C_OBJECTS   = $(C_SOURCES:.c=.o)
ASM_OBJECTS = $(ASM_SOURCES:.s=.o)
OBJECTS     = $(C_OBJECTS) $(ASM_OBJECTS)

# ── Output ───────────────────────────────────────────────────────────────────
TARGET = stm32_firmware
ELF    = $(TARGET).elf
HEX    = $(TARGET).hex
BIN    = $(TARGET).bin

# ============================================================================
# RULES
# ============================================================================

.PHONY: all clean flash size dump

# Default
all: $(ELF) $(HEX) $(BIN) size

# ── Link ─────────────────────────────────────────────────────────────────────
$(ELF): $(OBJECTS) $(LDSCRIPT)
	@echo ""
	@echo "Linking $@..."
	$(CC) $(LDFLAGS) -o $@ $(OBJECTS)
	@echo "Done: $@"

# ── Compile C ────────────────────────────────────────────────────────────────
%.o: %.c
	@echo "  CC  $<"
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# ── Assemble startup ─────────────────────────────────────────────────────────
%.o: %.s
	@echo "  AS  $<"
	$(AS) $(CPU_FLAGS) -c $< -o $@

# ── HEX / BIN ────────────────────────────────────────────────────────────────
$(HEX): $(ELF)
	@echo "Creating $@..."
	$(OBJCOPY) -O ihex $< $@

$(BIN): $(ELF)
	@echo "Creating $@..."
	$(OBJCOPY) -O binary -S $< $@

# ── Size report ──────────────────────────────────────────────────────────────
size: $(ELF)
	@echo ""
	@echo "── Memory Usage ─────────────────────────────"
	$(SIZE) --format=berkeley $<

# ── Flash via ST-Link (cần openocd) ─────────────────────────────────────────
flash: $(BIN)
	openocd -f interface/stlink.cfg \
	        -f target/stm32f4x.cfg \
	        -c "program $(BIN) 0x08000000 verify reset exit"

# ── Disassembly (debug) ──────────────────────────────────────────────────────
dump: $(ELF)
	$(OBJDUMP) -d -S $< > $(TARGET).dump
	@echo "Disassembly saved to $(TARGET).dump"

# ── Clean ────────────────────────────────────────────────────────────────────
clean:
	@echo "Cleaning..."
	@rm -f $(OBJECTS) $(ELF) $(HEX) $(BIN) $(TARGET).map $(TARGET).dump
	@echo "Done."
