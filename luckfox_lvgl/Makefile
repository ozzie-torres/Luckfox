
CC=gcc

SRC=$(shell find src -name '*.c') $(shell find third_party/lvgl/src -name '*.c')

CFLAGS=-I./src -I./third_party/lvgl -I./third_party/lvgl/src -DLV_CONF_INCLUDE_SIMPLE

lvgl_app:
	$(CC) $(SRC) $(CFLAGS) -o lvgl_app

clean:
	rm -f lvgl_app
