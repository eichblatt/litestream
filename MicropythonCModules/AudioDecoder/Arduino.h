#pragma once

// Dummy file so that the decoder compiles
typedef unsigned char uint8_t;
typedef unsigned short uint16_t;
typedef unsigned long uint32_t;
//typedef char __int8_t;
typedef short int16_t;
typedef long int32_t;
typedef long long int64_t;

//static const char* TAG = "AudioPlayer";
//#include <esp_log.h>
#define log_i(format, ...) void() //TAG, format, ##__VA_ARGS__)
#define log_e(format, ...) void() //TAG, format, ##__VA_ARGS__) //ESP_LOGE
#define log_w(format, ...) void() //TAG, format, ##__VA_ARGS__)

#define PROGMEM
#define pgm_read_word *
#define pgm_read_byte *

#include <esp_heap_caps.h>
#include <string.h>