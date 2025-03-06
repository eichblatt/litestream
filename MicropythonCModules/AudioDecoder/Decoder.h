#pragma once
#include "py/runtime.h"
#include "py/gc.h"
#include "py/obj.h"
#include "py/stream.h"
#include "stdint.h"
#include <string.h>

//#include "vorbis_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/vorbis_decoder
//#include "mp3_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/mp3_decoder
//#include "esp_timer.h"

const int VorbisMajorVersion = 1;
const int VorbisMinorVersion = 4;
const int MP3MajorVersion = 1;
const int MP3MinorVersion = 4;
const int AACMajorVersion = 2;
const int AACMinorVersion = 0;

typedef struct _Vorbis_Decoder_obj_t {
    mp_obj_base_t base;
    //int16_t a;
    //int16_t b;
} Vorbis_Decoder_obj_t;

typedef struct _MP3_Decoder_obj_t {
    mp_obj_base_t base;
} MP3_Decoder_obj_t;

typedef struct _AAC_Decoder_obj_t {
    mp_obj_base_t base;
    void *InBuffer;
    void *OutBuffer;
    int InputOffset;
    //mp_obj_t *InStream;
    //mp_obj_t *OutStream;
    int OutputSamples;
} AAC_Decoder_obj_t;

#ifdef __cplusplus
extern "C" {
#endif

// Vorbis functions that we call in C++ code
extern bool VORBISDecoder_AllocateBuffers();
extern int VORBISDecode(uint8_t *inbuf, int *bytesLeft, short *outbuf);
extern void VORBISDecoder_FreeBuffers();
extern uint16_t VORBISGetOutputSamps();
extern uint8_t VORBISGetChannels();
extern uint32_t VORBISGetSampRate();
extern uint8_t VORBISGetBitsPerSample();
extern uint32_t VORBISGetBitRate();
extern int VORBISFindSyncWord(unsigned char *buf, int nBytes);

// MP3 functions that we call in C++ code
extern bool MP3Decoder_AllocateBuffers(void);
extern int MP3Decode( unsigned char *inbuf, int *bytesLeft, short *outbuf, int useSize);
extern void MP3Decoder_FreeBuffers();
extern int MP3GetOutputSamps();
extern int MP3GetChannels();
extern int MP3GetSampRate();
extern int MP3GetBitsPerSample();
extern int MP3GetBitrate();
extern int MP3FindSyncWord(unsigned char *buf, int nBytes);
extern int MP3GetNextFrameInfo(unsigned char *buf);
extern void MP3GetLastFrameInfo();

// AAC functions that we call in C++ code
extern bool AACDecoder_AllocateBuffers(void);
extern int AACDecode(unsigned char *inbuf, int *bytesLeft, short *outbuf, int useSize);
extern void AACDecoder_FreeBuffers();
extern int AACGetOutputSamps();
extern int AACGetChannels();
extern int AACGetSampRate();
extern int AACGetBitsPerSample();
extern int AACGetBitrate();
extern int AACFindSyncWord(unsigned char *buf, int nBytes);

#ifdef __cplusplus
}
#endif
