CC := /home/rra/OpenCilk-10.0.1-Linux/bin/clang
CFLAGS := -Wall -O3 -g -gdwarf-3 -fopencilk
LDFLAGS := -fopencilk -ldl

TARGET := fib
SRC := fib.c

include ../cilktool/cilkutils.mk

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) -o $@ $(CFLAGS) $^ $(LDFLAGS)



clean::
	rm -f $(TARGET)
