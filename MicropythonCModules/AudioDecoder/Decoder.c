// Include MicroPython API.
#include "Decoder.h"

////////////////////////// Vorbis functions //////////////////////////

const mp_obj_type_t Vorbis_Decoder_type;

static void Decoder_Vorbis_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    (void)kind;
    //Vorbis_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    mp_print_str(print, "Vorbis Decoder v");
    mp_obj_print_helper(print, mp_obj_new_int(MajorVersion), PRINT_REPR);
    mp_print_str(print, ".");
    mp_obj_print_helper(print, mp_obj_new_int(MinorVersion), PRINT_REPR);
}

static mp_obj_t Decoder_Vorbis_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 0, 0, true);
    Vorbis_Decoder_obj_t *self = m_new_obj(Vorbis_Decoder_obj_t);
    self->base.type = &Vorbis_Decoder_type;
    //self->a = mp_obj_get_int(args[0]);
    //self->b = mp_obj_get_int(args[1]);
    return MP_OBJ_FROM_PTR(self);
}

// Class methods
/*//STATIC mp_obj_t Decoder_sum(mp_obj_t self_in) {
STATIC mp_obj_t Decoder_sum(size_t n_args, const mp_obj_t *args) {
    //VorbisDecoder1_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    Vorbis_Decoder_obj_t *self = MP_OBJ_TO_PTR(args[0]);
    return mp_obj_new_int(self->a + self->b);
}

//MP_DEFINE_CONST_FUN_OBJ_1(Decoder_sum_obj, Decoder_sum);
MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(Decoder_sum_obj, 4, 4, Decoder_sum);*/

static mp_obj_t Decoder_Vorbis_Init(mp_obj_t self_in)
{
    int Result;
    Result = VORBISDecoder_AllocateBuffers();

    if (!Result)
        mp_raise_msg(&mp_type_ValueError, "Error: Vorbis Allocate");

    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_Vorbis_Init_obj, Decoder_Vorbis_Init);


static mp_obj_t Decoder_Vorbis_Start(mp_obj_t self_in, mp_obj_t InBuffer, mp_obj_t BytesInBuffer)
{
    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(InBuffer, &InBufferInfo, MP_BUFFER_READ);
    byte* InBuf = InBufferInfo.buf;

    int bytes_in_buffer = mp_obj_get_int(BytesInBuffer);
    //printf("%d bytes in buffer\n", bytes_in_buffer);
    //printf("%c %c %c %c\n", InBuf[0], InBuf[1], InBuf[2], InBuf[3]);

    int Result = VORBISFindSyncWord(InBuf, bytes_in_buffer);

    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_3(Decoder_Vorbis_Start_obj, Decoder_Vorbis_Start);


static mp_obj_t Decoder_Vorbis_GetInfo(mp_obj_t self_in)
{
    // Create a tuple object to return the values - Channels, Sample Rate, Bits per Sample, BitRate
    mp_obj_t tuple[4];
    tuple[0] = mp_obj_new_int(VORBISGetChannels()); //info.channels);
    tuple[1] = mp_obj_new_int(VORBISGetSampRate()); //info.sample_rate);
    tuple[2] = mp_obj_new_int(VORBISGetBitsPerSample()); //info.setup_memory_required);
    tuple[3] = mp_obj_new_int(VORBISGetBitRate()); //info.temp_memory_required);

    return mp_obj_new_tuple(4, tuple);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_Vorbis_GetInfo_obj, Decoder_Vorbis_GetInfo);


// The main function that we call repeatedly to decode the incoming stream into audio samples, which are stored in OutBuffer
// arg[0] = self_in, arg[1] = InBuffer, arg[2] = BytesLeft, arg[3] = OutBuffer
static mp_obj_t Decoder_Vorbis_Decode(size_t n_args, const mp_obj_t *args)
{   
    //gc_lock();
    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(args[1], &InBufferInfo, MP_BUFFER_READ);
    
    mp_buffer_info_t OutBufferInfo;
    mp_get_buffer_raise(args[3], &OutBufferInfo, MP_BUFFER_WRITE);
    
    int BytesLeftInBuffer = mp_obj_get_int(args[2]);

    int OutputSamples = 0;
    //long long t = esp_timer_get_time() / 1000;
    int m_decodeError = VORBISDecode((byte*)InBufferInfo.buf, &BytesLeftInBuffer, (short*)OutBufferInfo.buf);
    //printf("%lld\n", (esp_timer_get_time() / 1000) - t);
    //gc_unlock();
    OutputSamples = VORBISGetOutputSamps();

    mp_obj_t tuple[3];
    tuple[0] = mp_obj_new_int(m_decodeError);
    tuple[1] = mp_obj_new_int(BytesLeftInBuffer);
    tuple[2] = mp_obj_new_int(OutputSamples);
    
    return mp_obj_new_tuple(3, tuple);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(Decoder_Vorbis_Decode_obj, 4, 4, Decoder_Vorbis_Decode);


static mp_obj_t Decoder_Vorbis_Close(mp_obj_t self_in)
{
    VORBISDecoder_FreeBuffers();

    return mp_const_none;
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_Vorbis_Close_obj, Decoder_Vorbis_Close);


// Table entries are key/value pairs of the attribute name (a string) and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be optimized to word-sized integers by the build system (interned strings).
static const mp_rom_map_elem_t Vorbis_Decoder_locals_dict_table[] = {
    //{ MP_ROM_QSTR(MP_QSTR_mysum), MP_ROM_PTR(&Decoder_sum_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Init), MP_ROM_PTR(&Decoder_Vorbis_Init_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Start), MP_ROM_PTR(&Decoder_Vorbis_Start_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_GetInfo), MP_ROM_PTR(&Decoder_Vorbis_GetInfo_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Decode), MP_ROM_PTR(&Decoder_Vorbis_Decode_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Close), MP_ROM_PTR(&Decoder_Vorbis_Close_obj) },
};
static MP_DEFINE_CONST_DICT(Vorbis_Decoder_locals_dict, Vorbis_Decoder_locals_dict_table);


#ifdef MP_OBJ_TYPE_GET_SLOT
MP_DEFINE_CONST_OBJ_TYPE(
    Vorbis_Decoder_type,
    MP_QSTR_VorbisDecoder,
    MP_TYPE_FLAG_NONE,
    print, Decoder_Vorbis_print,
    make_new, Decoder_Vorbis_make_new,
    locals_dict, (mp_obj_dict_t *)&Vorbis_Decoder_locals_dict);
#else
const mp_obj_type_t Vorbis_Decoder_type = {
    {&mp_type_type},
    .name = MP_QSTR_VorbisDecoder,
    .print = Decoder_Vorbis_print,
    .make_new = Decoder_Vorbis_make_new,
    .locals_dict = (mp_obj_dict_t*)&Vorbis_Decoder_locals_dict,
};
#endif


////////////////////////// MP3 functions //////////////////////////

const mp_obj_type_t MP3_Decoder_type;

static void Decoder_MP3_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    (void)kind;
    //MP3_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    mp_print_str(print, "MP3 Decoder v");
    mp_obj_print_helper(print, mp_obj_new_int(MajorVersion), PRINT_REPR);
    mp_print_str(print, ".");
    mp_obj_print_helper(print, mp_obj_new_int(MinorVersion), PRINT_REPR);
}


static mp_obj_t Decoder_MP3_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 0, 0, true);
    MP3_Decoder_obj_t *self = m_new_obj(MP3_Decoder_obj_t);
    self->base.type = &MP3_Decoder_type;
    return MP_OBJ_FROM_PTR(self);
}


static mp_obj_t Decoder_MP3_Init(mp_obj_t self_in)
{
    int Result;
    Result = MP3Decoder_AllocateBuffers();

    if (!Result)
        mp_raise_msg(&mp_type_ValueError, "Error: MP3 Allocate");

    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_MP3_Init_obj, Decoder_MP3_Init);


static mp_obj_t Decoder_MP3_Start(mp_obj_t self_in, mp_obj_t InBuffer, mp_obj_t BytesInBuffer)
{
    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(InBuffer, &InBufferInfo, MP_BUFFER_READ);
    byte* InBuf = InBufferInfo.buf;

    int bytes_in_buffer = mp_obj_get_int(BytesInBuffer);
    //printf("%d bytes in buffer\n", bytes_in_buffer);
    //printf("%c %c %c %c\n", InBuf[0], InBuf[1], InBuf[2], InBuf[3]);

    int Result = MP3FindSyncWord(InBuf, bytes_in_buffer);

    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_3(Decoder_MP3_Start_obj, Decoder_MP3_Start);


static mp_obj_t Decoder_MP3_GetInfo(mp_obj_t self_in)
{
    // Create a tuple object to return the values - Channels, Sample Rate, Bits per Sample, BitRate
    mp_obj_t tuple[4];
    tuple[0] = mp_obj_new_int(MP3GetChannels());
    tuple[1] = mp_obj_new_int(MP3GetSampRate());
    tuple[2] = mp_obj_new_int(MP3GetBitsPerSample());
    tuple[3] = mp_obj_new_int(MP3GetBitrate());

    return mp_obj_new_tuple(4, tuple);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_MP3_GetInfo_obj, Decoder_MP3_GetInfo);

// The main function that we call repeatedly to decode the incoming stream into audio samples, which are stored in OutBuffer
// arg[0] = self_in, arg[1] = InBuffer, arg[2] = BytesLeft, arg[3] = OutBuffer
static mp_obj_t Decoder_MP3_Decode(size_t n_args, const mp_obj_t *args)
{
    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(args[1], &InBufferInfo, MP_BUFFER_READ);
    
    mp_buffer_info_t OutBufferInfo;
    mp_get_buffer_raise(args[3], &OutBufferInfo, MP_BUFFER_WRITE);
    
    int BytesLeftInBuffer = mp_obj_get_int(args[2]);

    int OutputSamples = 0;
     
    MP3GetNextFrameInfo((byte*)InBufferInfo.buf);
    //printf("%lld ", esp_timer_get_time() / 1000);
    int m_decodeError = MP3Decode((byte*)InBufferInfo.buf, &BytesLeftInBuffer, (short*)OutBufferInfo.buf, 0);
    //printf("%lld\n", esp_timer_get_time() / 1000);
    MP3GetLastFrameInfo();
    
    OutputSamples = MP3GetOutputSamps();

    mp_obj_t tuple[3];
    tuple[0] = mp_obj_new_int(m_decodeError);
    tuple[1] = mp_obj_new_int(BytesLeftInBuffer);
    tuple[2] = mp_obj_new_int(OutputSamples);
    
    return mp_obj_new_tuple(3, tuple);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(Decoder_MP3_Decode_obj, 4, 4, Decoder_MP3_Decode);

static mp_obj_t Decoder_MP3_Close(mp_obj_t self_in)
{
    MP3Decoder_FreeBuffers();

    return mp_const_none;
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_MP3_Close_obj, Decoder_MP3_Close);

// Table entries are key/value pairs of the attribute name (a string) and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be optimized to word-sized integers by the build system (interned strings).
static const mp_rom_map_elem_t MP3_Decoder_locals_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_MP3_Init), MP_ROM_PTR(&Decoder_MP3_Init_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_Start), MP_ROM_PTR(&Decoder_MP3_Start_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_GetInfo), MP_ROM_PTR(&Decoder_MP3_GetInfo_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_Decode), MP_ROM_PTR(&Decoder_MP3_Decode_obj) },
    { MP_ROM_QSTR(MP_QSTR_MP3_Close), MP_ROM_PTR(&Decoder_MP3_Close_obj) },
};
static MP_DEFINE_CONST_DICT(MP3_Decoder_locals_dict, MP3_Decoder_locals_dict_table);

#ifdef MP_OBJ_TYPE_GET_SLOT
MP_DEFINE_CONST_OBJ_TYPE(
    MP3_Decoder_type,
    MP_QSTR_MP3Decoder,
    MP_TYPE_FLAG_NONE,
    print, Decoder_MP3_print,
    make_new, Decoder_MP3_make_new,
    locals_dict, (mp_obj_dict_t *)&MP3_Decoder_locals_dict);
#else
const mp_obj_type_t MP3_Decoder_type = {
    {&mp_type_type},
    .name = MP_QSTR_MP3Decoder,
    .print = Decoder_MP3_print,
    .make_new = Decoder_MP3_make_new,
    .locals_dict = (mp_obj_dict_t*)&MP3_Decoder_locals_dict,
};
#endif


////////////////////////// Module functions //////////////////////////

static const mp_map_elem_t AudioDecoder_globals_table[] = {
    {MP_OBJ_NEW_QSTR(MP_QSTR___name__), MP_OBJ_NEW_QSTR(MP_QSTR_AudioDecoder)},
    {MP_OBJ_NEW_QSTR(MP_QSTR_VorbisDecoder), (mp_obj_t)&Vorbis_Decoder_type},	
    {MP_OBJ_NEW_QSTR(MP_QSTR_MP3Decoder), (mp_obj_t)&MP3_Decoder_type},	
};

static MP_DEFINE_CONST_DICT (
    mp_module_AudioDecoder_globals,
    AudioDecoder_globals_table
);

const mp_obj_module_t AudioDecoder_user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t*)&mp_module_AudioDecoder_globals,
};

MP_REGISTER_MODULE(MP_QSTR_AudioDecoder, AudioDecoder_user_cmodule);
