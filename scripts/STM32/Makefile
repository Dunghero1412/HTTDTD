# ============================================================================
# STM32F407 Makefile - Build STM32 Firmware
# ============================================================================

# ✓ Compiler
ARM_TOOLCHAIN = arm-none-eabi
CC = $(ARM_TOOLCHAIN)-gcc
AR = $(ARM_TOOLCHAIN)-ar
OBJCOPY = $(ARM_TOOLCHAIN)-objcopy

# ✓ Flags
CFLAGS = -mcpu=cortex-m4 -mfpu=fpv4-sp-d16 -mfloat-abi=hard
CFLAGS += -mthumb -O2 -g
CFLAGS += -Wall -Wextra

# ✓ Include directories
INCLUDES = -I./src -I./lib

# ✓ Source files
SOURCES = src/main.c src/system.c src/gpio.c src/timmer.c src/spi.c src/uart.c
OBJECTS = $(SOURCES:.c=.o)

# ✓ Output
TARGET = stm32_firmware
ELF = $(TARGET).elf
HEX = $(TARGET).hex

# ============================================================================
# RULES
# ============================================================================

# ✓ Default target
all: $(ELF) $(HEX)

# ✓ Link
$(ELF): $(OBJECTS)
	@echo "Linking $@..."
	@$(CC) $(CFLAGS) -nostartfiles -Wl,-Map=$(TARGET).map -o $@ $^

# ✓ Compile
%.o: %.c
	@echo "Compiling $<..."
	@$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

# ✓ Hex file
$(HEX): $(ELF)
	@echo "Creating hex file..."
	@$(OBJCOPY) -O ihex $< $@

# ✓ Clean
clean:
	@echo "Cleaning..."
	@rm -f $(OBJECTS) $(ELF) $(HEX) $(TARGET).map

# ✓ Phony targets
.PHONY: all clean
