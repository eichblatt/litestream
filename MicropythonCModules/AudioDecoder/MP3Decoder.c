// Include MicroPython API.
#include "py/runtime.h"
#include "stdint.h"
//#include "esp_timer.h"
#include "mp3_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/mp3_decoder

STATIC mp_obj_t MP3_Init(void)
{
    // Get a memory block from the calling MicroPython code to use as a Ring Buffer.
    //mp_buffer_info_t RingBufferInfo;
    //mp_get_buffer_raise(Buffer, &RingBufferInfo, MP_BUFFER_READ | MP_BUFFER_WRITE);
    //RingBuffer = (char*)RingBufferInfo.buf;
    //RingBufferLen = RingBufferInfo.len;

   // This is the buffer containing encoded streaming data from Python code
   // mp_buffer_info_t StreamBufferInfo;
   // mp_get_buffer_raise(StreamBuffer, &StreamBufferInfo, MP_BUFFER_READ);

    int Result;
    Result = MP3Decoder_AllocateBuffers();

    if (!Result)
    {
        mp_raise_msg(&mp_type_ValueError, "Error: MP3 Allocate");
    }

    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(MP3_Init_obj, MP3_Init);


STATIC mp_obj_t MP3_Start(mp_obj_t InBuffer, mp_obj_t BytesInBuffer)
{
    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(InBuffer, &InBufferInfo, MP_BUFFER_READ);
    byte* bb = InBufferInfo.buf;

    int bytes_in_buffer = mp_obj_get_int(BytesInBuffer);
    //printf("%d bytes in buffer\n", bytes_in_buffer);
    //printf("%c %c %c %c\n", bb[0], bb[1], bb[2], bb[3]);

    int retn = MP3FindSyncWord(bb, bytes_in_buffer);

    return mp_obj_new_int(retn);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_2(MP3_Start_obj, MP3_Start);


STATIC mp_obj_t MP3_GetInfo(void)
{
 /*   stb_vorbis_info info;

    if (Decoder != NULL)
        info = stb_vorbis_get_info(Decoder);
    else
    {
        mp_raise_msg(&mp_type_ValueError, "Vorbis Decoder not initalised");
        return mp_obj_new_int(-1);
    }
*/
    // Create a tuple object to return the values - Channels, Sample Rate, Bits per Sample, BitRate
    mp_obj_t tuple[4];
    tuple[0] = mp_obj_new_int(MP3GetChannels()); //info.channels);
    tuple[1] = mp_obj_new_int(MP3GetSampRate()); //info.sample_rate);
    tuple[2] = mp_obj_new_int(MP3GetBitsPerSample()); //info.setup_memory_required);
    tuple[3] = mp_obj_new_int(MP3GetBitrate()); //info.temp_memory_required);

    return mp_obj_new_tuple(4, tuple);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(MP3_GetInfo_obj, MP3_GetInfo);

// The main function that we call repeatedly to decode the incoming stream into audio samples, which are stored in OutBuffer
STATIC mp_obj_t MP3_Decode(mp_obj_t InBuffer, mp_obj_t BytesLeft, mp_obj_t OutBuffer)
{
    //if (Decoder == NULL)
    //    mp_raise_msg(&mp_type_ValueError, "Vorbis Decoder not initalised");

    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(InBuffer, &InBufferInfo, MP_BUFFER_READ);
    
    mp_buffer_info_t OutBufferInfo;
    mp_get_buffer_raise(OutBuffer, &OutBufferInfo, MP_BUFFER_WRITE);
    
    int BytesLeftInBuffer = mp_obj_get_int(BytesLeft);

    int OutputSamples = 0;
    //printf("====");
    
    MP3GetNextFrameInfo((byte*)InBufferInfo.buf);
    //printf("%lld ", esp_timer_get_time() / 1000);
    int m_decodeError = MP3Decode((byte*)InBufferInfo.buf, &BytesLeftInBuffer, (short*)OutBufferInfo.buf, 0);
    //printf("%lld\n", esp_timer_get_time() / 1000);
    MP3GetLastFrameInfo();
    

    //if (m_decodeError != -1)
    OutputSamples = MP3GetOutputSamps();

    mp_obj_t tuple[3];
    tuple[0] = mp_obj_new_int(m_decodeError);
    tuple[1] = mp_obj_new_int(BytesLeftInBuffer);
    tuple[2] = mp_obj_new_int(OutputSamples);
    
    return mp_obj_new_tuple(3, tuple);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_3(MP3_Decode_obj, MP3_Decode);

STATIC mp_obj_t MP3_Close(void)
{
    //if (Decoder == NULL)
    //    mp_raise_msg(&mp_type_ValueError, "Vorbis Decoder not initalised");

    MP3Decoder_FreeBuffers();

    return mp_const_none;
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(MP3_Close_obj, MP3_Close);


// Define all properties of the module.
// Table entries are key/value pairs of the attribute name (a string)
// and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be
// optimized to word-sized integers by the build system (interned strings).
STATIC const mp_rom_map_elem_t module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_MP3Decoder) },
    { MP_ROM_QSTR(MP_QSTR_MP3_Init), MP_ROM_PTR(&MP3_Init_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_Start), MP_ROM_PTR(&MP3_Start_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_GetInfo), MP_ROM_PTR(&MP3_GetInfo_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_Decode), MP_ROM_PTR(&MP3_Decode_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_Close), MP_ROM_PTR(&MP3_Close_obj) },
};
STATIC MP_DEFINE_CONST_DICT(module_globals, module_globals_table);

// Define module object.
const mp_obj_module_t user_cmoduleMP3 = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&module_globals,
};

// Register the module to make it available in Python.
MP_REGISTER_MODULE(MP_QSTR_MP3Decoder, user_cmoduleMP3);