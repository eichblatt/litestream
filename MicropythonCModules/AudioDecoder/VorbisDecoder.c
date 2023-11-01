// Include MicroPython API.
#include "py/runtime.h"
//#include "esp_timer.h"
#include "stdint.h"
#include "vorbis_decoder.h" // Modified from https://github.com/schreibfaul1/ESP32-audioI2S/tree/master/src/vorbis_decoder

STATIC mp_obj_t Vorbis_Init(void)
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
    Result = VORBISDecoder_AllocateBuffers();

    if (!Result)
    {
        mp_raise_msg(&mp_type_ValueError, "Error: Vorbis Allocate");
    }

    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(Vorbis_Init_obj, Vorbis_Init);


STATIC mp_obj_t Vorbis_Start(mp_obj_t InBuffer, mp_obj_t BytesInBuffer)
{
    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(InBuffer, &InBufferInfo, MP_BUFFER_READ);
    byte* bb = InBufferInfo.buf;

    int bytes_in_buffer = mp_obj_get_int(BytesInBuffer);
    //printf("%d bytes in buffer\n", bytes_in_buffer);
    //printf("%c %c %c %c\n", bb[0], bb[1], bb[2], bb[3]);

    int retn = VORBISFindSyncWord(bb, bytes_in_buffer);

    return mp_obj_new_int(retn);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_2(Vorbis_Start_obj, Vorbis_Start);


STATIC mp_obj_t Vorbis_GetInfo(void)
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
    tuple[0] = mp_obj_new_int(VORBISGetChannels()); //info.channels);
    tuple[1] = mp_obj_new_int(VORBISGetSampRate()); //info.sample_rate);
    tuple[2] = mp_obj_new_int(VORBISGetBitsPerSample()); //info.setup_memory_required);
    tuple[3] = mp_obj_new_int(VORBISGetBitRate()); //info.temp_memory_required);

    return mp_obj_new_tuple(4, tuple);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(Vorbis_GetInfo_obj, Vorbis_GetInfo);

// The main function that we call repeatedly to decode the incoming stream into audio samples, which are stored in OutBuffer
STATIC mp_obj_t Vorbis_Decode(mp_obj_t InBuffer, mp_obj_t BytesLeft, mp_obj_t OutBuffer)
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
    //long long t = esp_timer_get_time() / 1000;
    int m_decodeError = VORBISDecode((byte*)InBufferInfo.buf, &BytesLeftInBuffer, (short*)OutBufferInfo.buf);
    //printf("%lld\n", (esp_timer_get_time() / 1000) - t);

    //if (m_decodeError != -1)
    OutputSamples = VORBISGetOutputSamps();

    mp_obj_t tuple[3];
    tuple[0] = mp_obj_new_int(m_decodeError);
    tuple[1] = mp_obj_new_int(BytesLeftInBuffer);
    tuple[2] = mp_obj_new_int(OutputSamples);
    
    return mp_obj_new_tuple(3, tuple);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_3(Vorbis_Decode_obj, Vorbis_Decode);

STATIC mp_obj_t Vorbis_Close(void)
{
    //if (Decoder == NULL)
    //    mp_raise_msg(&mp_type_ValueError, "Vorbis Decoder not initalised");

    VORBISDecoder_FreeBuffers();

    return mp_const_none;
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(Vorbis_Close_obj, Vorbis_Close);


// Define all properties of the module.
// Table entries are key/value pairs of the attribute name (a string)
// and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be
// optimized to word-sized integers by the build system (interned strings).
STATIC const mp_rom_map_elem_t module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_VorbisDecoder) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Init), MP_ROM_PTR(&Vorbis_Init_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Start), MP_ROM_PTR(&Vorbis_Start_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_GetInfo), MP_ROM_PTR(&Vorbis_GetInfo_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Decode), MP_ROM_PTR(&Vorbis_Decode_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Close), MP_ROM_PTR(&Vorbis_Close_obj) },
};
STATIC MP_DEFINE_CONST_DICT(module_globals, module_globals_table);

// Define module object.
const mp_obj_module_t user_cmoduleVorbis = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&module_globals,
};

// Register the module to make it available in Python.
MP_REGISTER_MODULE(MP_QSTR_VorbisDecoder, user_cmoduleVorbis);