#pragma once
#include "py/runtime.h"
#include "py/gc.h"
#include "py/obj.h"
#include "stdint.h"
#include "vorbis_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/vorbis_decoder
#include "mp3_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/mp3_decoder
//#include "esp_timer.h"

const int MajorVersion = 1;
const int MinorVersion = 2;

typedef struct _Vorbis_Decoder_obj_t {
    mp_obj_base_t base;
    //int16_t a;
    //int16_t b;
} Vorbis_Decoder_obj_t;

typedef struct _MP3_Decoder_obj_t {
    mp_obj_base_t base;
} MP3_Decoder_obj_t;
