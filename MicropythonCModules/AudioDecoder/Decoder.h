#pragma once
#include "py/runtime.h"
#include "py/gc.h"
#include "py/obj.h"
#include "stdint.h"
#include "vorbis_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/vorbis_decoder
#include "mp3_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/mp3_decoder
//#include "esp_timer.h"

const int MajorVersion = 1;
const int MinorVersion = 0;

typedef struct _Vorbis_Decoder_obj_t {
    mp_obj_base_t base;
    //int16_t a;
    //int16_t b;

    // Vorbis Decoder Globals. All of these have mallocs/callocs done against them in vorbis_decoder.cpp, so must be members here to avoid the MicroPython GC collecting them
    uint8_t *s_lastSegmentTable;
    uint16_t *s_vorbisSegmentTable;
    char* s_vorbisChbuf;
    struct _vorbis_info_mapping *s_map_param;
    struct _vorbis_info_mode *s_mode_param;
    struct _vorbis_info_floor **s_floor_param;
    struct _vorbis_info_residue *s_residue_param;
    struct _codebook *s_codebooks;
    int8_t *s_floor_type;
    struct _vorbis_dsp_state *s_dsp_state;
} Vorbis_Decoder_obj_t;

typedef struct _MP3_Decoder_obj_t {
    mp_obj_base_t base;

    // MP3 Decoder Globals. All of these have mallocs/callocs done against them in mp3_decoder.cpp, so must be members here to avoid the MicroPython GC collecting them
    struct MP3DecInfo *m_MP3DecInfo;
    struct FrameHeader *m_FrameHeader;
    struct SideInfo *m_SideInfo;
    struct ScaleFactorJS *m_ScaleFactorJS;
    struct HuffmanInfo *m_HuffmanInfo;
    struct DequantInfo *m_DequantInfo;
    struct IMDCTInfo *m_IMDCTInfo;
    struct SubbandInfo *m_SubbandInfo;
    struct MP3FrameInfo *m_MP3FrameInfo;
} MP3_Decoder_obj_t;

extern Vorbis_Decoder_obj_t *mpVorbis;
extern MP3_Decoder_obj_t *mpMP3;
