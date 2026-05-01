# ============================================================================
# STM32F407VET6 Makefile - High-Speed Timestamp Capture
# ============================================================================
# Cấu trúc thư mục:
#   Core/Src/         ← source files (.c)
#   Core/Inc/         ← header files (.h)  [stm32f407xx.h đặt ở đây]
#   startup/          ← startup_stm32f407xx.s
#   Ld/               ← linker_stm32f407xx.ld
# ============================================================================

# ── Toolchain ────────────────────────────────────────────────────────────────
ARM_TOOLCHAIN = arm-none-eabi
CC      = $(ARM_TOOLCHAIN)-gcc
AS      = $(ARM_TOOLCHAIN)-gcc
AR      = $(ARM_TOOLCHAIN)-ar
OBJCOPY = $(ARM_TOOLCHAIN)-objcopy
OBJDUMP = $(ARM_TOOLCHAIN)-objdump
SIZE    = $(ARM_TOOLCHAIN)-size

# ── CPU / FPU flags ──────────────────────────────────────────────────────────
CPU_FLAGS  = -mcpu=cortex-m4
CPU_FLAGS += -mfpu=fpv4-sp-d16
CPU_FLAGS += -mfloat-abi=hard
CPU_FLAGS += -mthumb

# ── Compiler flags ───────────────────────────────────────────────────────────
CFLAGS  = $(CPU_FLAGS)
CFLAGS += -O2 -g
CFLAGS += -Wall -Wextra
CFLAGS += -ffunction-sections       # mỗi function 1 section → linker GC hiệu quả
CFLAGS += -fdata-sections           # mỗi data object 1 section
CFLAGS += -fno-common
CFLAGS += -ffreestanding            # bare-metal: không giả định stdlib đầy đủ
CFLAGS += -DSTM32F407xx             # define MCU cho stm32f407xx.h

# ── Linker script ─────────────────────────────────────────────────────────────
LDSCRIPT = Ld/linker_stm32f407xx.ld

# ── Linker flags ─────────────────────────────────────────────────────────────
LDFLAGS  = $(CPU_FLAGS)
LDFLAGS += --specs=nano.specs       # newlib-nano (nhỏ gọn)
LDFLAGS += --specs=nosys.specs      # stub syscalls → không cần -lc -lnosys
LDFLAGS += -T$(LDSCRIPT)
LDFLAGS += -Wl,--gc-sections        # loại bỏ code/data không dùng
LDFLAGS += -Wl,-Map=$(TARGET).map,--cref
LDFLAGS += -Wl,--print-memory-usage

# ── Include paths ─────────────────────────────────────────────────────────────
INCLUDES  = -I./Core/Inc             # main.h, tim2_capture.h, spi_comm.h ...
INCLUDES += -I./Drivers/CMSIS        # stm32f407xx.h đặt ở đây

# ── Source files ──────────────────────────────────────────────────────────────
C_SOURCES  = Core/Src/main.c         \
             Core/Src/gpio_control.c  \
             Core/Src/tim2_capture.c  \
             Core/Src/spi_comm.c      \
             Core/Src/data_packet.c   \
	     Core/Src/system_stm32f407xx.c

# ── Startup file (assembly) ───────────────────────────────────────────────────
ASM_SOURCES = startup/startup_stm32f407xx.s

# ── Object files ──────────────────────────────────────────────────────────────
# Đặt tất cả .o vào thư mục build/ để giữ source tree sạch
BUILD_DIR = build

C_OBJECTS   = $(patsubst Core/Src/%.c,   $(BUILD_DIR)/%.o, $(C_SOURCES))
ASM_OBJECTS = $(patsubst startup/%.s,    $(BUILD_DIR)/%.o, $(ASM_SOURCES))
OBJECTS     = $(C_OBJECTS) $(ASM_OBJECTS)

# ── Output ────────────────────────────────────────────────────────────────────
TARGET = stm32_timestamp
ELF    = $(TARGET).elf
HEX    = $(TARGET).hex
BIN    = $(TARGET).bin

# ============================================================================
# RULES
# ============================================================================

.PHONY: all clean flash size dump

# Default
all: $(BUILD_DIR) $(ELF) $(HEX) $(BIN) size

# Tạo thư mục build nếu chưa có
$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

# ── Link ──────────────────────────────────────────────────────────────────────
$(ELF): $(OBJECTS) $(LDSCRIPT)
	@echo ""
	@echo ">>> Linking $@..."
	$(CC) $(LDFLAGS) -o $@ $(OBJECTS)
	@echo ">>> Done: $@"
	@echo ""

# ── Compile C ─────────────────────────────────────────────────────────────────
$(BUILD_DIR)/%.o: Core/Src/%.c | $(BUILD_DIR)
	@echo "  CC  $<"
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# ── Assemble startup ──────────────────────────────────────────────────────────
$(BUILD_DIR)/%.o: startup/%.s | $(BUILD_DIR)
	@echo "  AS  $<"
	$(AS) $(CPU_FLAGS) -x assembler-with-cpp -c $< -o $@

# ── HEX / BIN ─────────────────────────────────────────────────────────────────
$(HEX): $(ELF)
	@echo "Creating $@..."
	$(OBJCOPY) -O ihex $< $@

$(BIN): $(ELF)
	@echo "Creating $@..."
	$(OBJCOPY) -O binary -S $< $@

# ── Size report ───────────────────────────────────────────────────────────────
size: $(ELF)
	@echo ""
	@echo "── Memory Usage ──────────────────────────────────"
	$(SIZE) --format=berkeley $<
	@echo "──────────────────────────────────────────────────"

# ── Flash via ST-Link (OpenOCD) ───────────────────────────────────────────────
flash: $(BIN)
	openocd -f interface/stlink.cfg \
	        -f target/stm32f4x.cfg \
	        -c "program $(BIN) 0x08000000 verify reset exit"

# ── Disassembly (debug) ───────────────────────────────────────────────────────
dump: $(ELF)
	$(OBJDUMP) -d -S $< > $(TARGET).dump
	@echo "Disassembly saved to $(TARGET).dump"

# ── Clean ─────────────────────────────────────────────────────────────────────
clean:
	@echo "Cleaning..."
	@rm -rf $(BUILD_DIR) $(ELF) $(HEX) $(BIN) $(TARGET).map $(TARGET).dump
	@echo "Done."
