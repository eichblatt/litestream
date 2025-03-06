// Include MicroPython API.
#include "Decoder.h"

////////////////////////// Vorbis functions //////////////////////////

const mp_obj_type_t Vorbis_Decoder_type;

static void Decoder_Vorbis_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    (void)kind;
    //Vorbis_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    mp_print_str(print, "Vorbis Decoder v");
    mp_obj_print_helper(print, mp_obj_new_int(VorbisMajorVersion), PRINT_REPR);
    mp_print_str(print, ".");
    mp_obj_print_helper(print, mp_obj_new_int(VorbisMinorVersion), PRINT_REPR);
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
    mp_obj_print_helper(print, mp_obj_new_int(MP3MajorVersion), PRINT_REPR);
    mp_print_str(print, ".");
    mp_obj_print_helper(print, mp_obj_new_int(MP3MinorVersion), PRINT_REPR);
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

////////////////////////// AAC functions //////////////////////////

#define InBufferSize 8 * 1024
#define OutBufferSize 4096

const mp_obj_type_t AAC_Decoder_type;

static mp_uint_t mystream_read(mp_obj_t self_in, void *buf, mp_uint_t size, int *errcode) {
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    
    int BytesToReturn = MIN(self->OutputSamples * 2, size);  // Each sample is two bytes

    if (BytesToReturn > 0)
    {
        memcpy(buf, self->OutBuffer + (OutBufferSize - self->OutputSamples * 2), BytesToReturn);
        self->OutputSamples -= BytesToReturn / 2;
    }   
        //printf("%lld\n", esp_timer_get_time() / 1000);
            
            // Write from the output buffer to the output stream
            //mp_uint_t result = 
            
            //stream_out->write(self->OutStream, self->OutBuffer, OutputSamples * 2, &errcode);  // Check later- should it be x4 ?

            //if (errcode != 0)
            //    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Error writing to output stream"));
        
        
        //printf("Readme %lu", size);
        // *errcode = 0;
        
        //if (self->qq)
        //    return 0;
        
        //char source[] = "Hello, World!";
        //memcpy(buf, source, 13);
        //if (self->pos + size > self->buf_len) {
        //    size = self->buf_len - self->pos;
        //}
        //memcpy(buf, self->buffer + self->pos, size);
        //self->pos += size;
        //self->qq = true;

    return BytesToReturn;
    }

static mp_uint_t mystream_write(mp_obj_t self_in, const void *buf, mp_uint_t size, int *errcode) {
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);

    int BytesToWrite = MIN(InBufferSize - self->InputOffset, size);
    memcpy((uint8_t *)(self->InBuffer + self->InputOffset), buf, BytesToWrite);
    self->InputOffset += BytesToWrite;

    /*if (self->pos + size > self->buf_len) {
        size = self->buf_len - self->pos;
    }
    memcpy(self->buffer + self->pos, buf, size);
    self->pos += size;*/
    return BytesToWrite; //size;
}

// Returns the free space left for writing
static mp_obj_t Decoder_AAC_write_free(mp_obj_t self_in)
{
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    
    return mp_obj_new_int(InBufferSize - self->InputOffset);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_write_free_obj, Decoder_AAC_write_free);

// Flushes the input buffer
static mp_obj_t Decoder_AAC_flush(mp_obj_t self_in)
{
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    self->InputOffset = 0;

    return mp_const_none;
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_flush_obj, Decoder_AAC_flush);

// Returns the number of bytes in the input buffer
static mp_obj_t Decoder_AAC_write_used(mp_obj_t self_in)
{
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    
    return mp_obj_new_int(self->InputOffset);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_write_used_obj, Decoder_AAC_write_used);

static mp_obj_t Decoder_AAC_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    mp_arg_check_num(n_args, n_kw, 0, 0, true);

    AAC_Decoder_obj_t *self = m_new_obj(AAC_Decoder_obj_t);
    self->base.type = &AAC_Decoder_type;
    //self->qq = false;

     // Allow for a 16kB input buffer
    self->InBuffer = m_tracked_calloc(1, InBufferSize);
    //m_malloc(InBufferSize);

    if (self->InBuffer == NULL)
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Failed to allocate decoder input buffer"));

    // Decoder returns 2048 16-bit stereo samples
    self->OutBuffer = m_tracked_calloc(1, OutBufferSize);
    //m_malloc(OutBufferSize);
    
    if (self->OutBuffer == NULL)
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Failed to allocate decoder output buffer"));

    self->InputOffset = 0;

    return MP_OBJ_FROM_PTR(self);
}

static void Decoder_AAC_print(const mp_print_t *print, mp_obj_t self_in, mp_print_kind_t kind) {
    (void)kind;
    mp_print_str(print, "AAC Decoder v");
    mp_obj_print_helper(print, mp_obj_new_int(AACMajorVersion), PRINT_REPR);
    mp_print_str(print, ".");
    mp_obj_print_helper(print, mp_obj_new_int(AACMinorVersion), PRINT_REPR);
}

// args[0] = self_in, args[1] = InBuffer, args[2] = OutBuffer
//static mp_obj_t Decoder_AAC_Init(size_t n_args, const mp_obj_t *args)
static mp_obj_t Decoder_AAC_Init(mp_obj_t self_in)
{
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);

    int Result;
    Result = AACDecoder_AllocateBuffers();

    if (!Result)
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Error: AAC Allocate"));

    self->OutputSamples = 0;
    
    // Allocate temporary In and Out buffers for the decoder
    //AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(args[0]);
        
    /*// Ensure the input argument is a ring buffer
    if (!mp_obj_is_type(args[1], &mp_type_ringio))
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Input buffer must be a RingIO object"));

    // Ensure the output argument is a ring buffer
    if (!mp_obj_is_type(args[2], &mp_type_ringio))
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Output buffer must be a RingIO object"));
    
    // Get the stream protocol for the input
    self->InStream = args[1];
    const mp_stream_p_t *stream_in = mp_get_stream(self->InStream);

    if (stream_in == NULL || stream_in->read == NULL)
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Input stream is not readable"));

    // Get the stream protocol for the output
    self->OutStream = args[2];
    const mp_stream_p_t *stream_out = mp_get_stream(self->OutStream);

    if (stream_out == NULL || stream_out->write == NULL)
        mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Output stream is not writable"));*/

    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
//static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(Decoder_AAC_Init_obj, 3, 3, Decoder_AAC_Init);
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_Init_obj, Decoder_AAC_Init);


static mp_obj_t Decoder_AAC_Start(mp_obj_t self_in)
{
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);
    
    //const mp_stream_p_t *stream_in = mp_get_stream(self->InStream);    

    //if (stream_in == NULL)
    //    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("No stream available"));
   

    //int errcode = 0;

    // Read from the input stream into the input buffer
    //self->InputOffset += stream_in->read(self->InStream, (uint8_t *)(self->InBuffer + self->InputOffset), InBufferSize - self->InputOffset, &errcode);
    //mp_buffer_info_t InBufferInfo;
    //mp_get_buffer_raise(InBuffer, &InBufferInfo, MP_BUFFER_READ);
    //byte* InBuf = InBufferInfo.buf;

    //int bytes_in_buffer = mp_obj_get_int(BytesInBuffer);
    //printf("%d bytes in buffer\n", bytes_in_buffer);
    //printf("%c %c %c %c\n", InBuf[0], InBuf[1], InBuf[2], InBuf[3]);

    int Result = AACFindSyncWord((uint8_t *)(self->InBuffer), self->InputOffset);
    
    return mp_obj_new_int(Result);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_Start_obj, Decoder_AAC_Start); 


static mp_obj_t Decoder_AAC_GetInfo(mp_obj_t self_in)
{
    // Create a tuple object to return the values - Channels, Sample Rate, Bits per Sample, BitRate
    mp_obj_t tuple[4];
    tuple[0] = mp_obj_new_int(AACGetChannels());
    tuple[1] = mp_obj_new_int(AACGetSampRate());
    tuple[2] = mp_obj_new_int(AACGetBitsPerSample());
    tuple[3] = mp_obj_new_int(AACGetBitrate());

    return mp_obj_new_tuple(4, tuple);
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_GetInfo_obj, Decoder_AAC_GetInfo);


// The main function that we call repeatedly to decode the incoming stream into audio samples, which are stored in OutBuffer
// args[0] = self_in, args[1] = InBuffer, args[2] = OutBuffer
static mp_obj_t Decoder_AAC_Decode(mp_obj_t self_in)
{
    //mp_buffer_info_t InBufferInfo;
    //mp_get_buffer_raise(args[1], &InBufferInfo, MP_BUFFER_READ);
    
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);

    // Check that we have our input and output buffers and input and outpus streams
    //if (self->InBuffer == NULL || self->OutBuffer == NULL || self->InStream == NULL || self->OutStream == NULL)
    //    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Run AAC_Init first."));

    int BytesDecoded = 0;
    self->OutputSamples = 0;
    //int errcode = 0;

    //const mp_stream_p_t *stream_in = mp_get_stream(self->InStream);    
    //const mp_stream_p_t *stream_out = mp_get_stream(self->OutStream); 

    //if (stream_in == NULL || stream_out == NULL)
    //    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("No stream available"));
   

    // Read from the input stream into the input buffer
    //self->InputOffset += stream_in->read(self->InStream, (uint8_t *)(self->InBuffer + self->InputOffset), InBufferSize - self->InputOffset, &errcode);

    //if (errcode != 0)
    //    mp_raise_msg(&mp_type_RuntimeError, MP_ERROR_TEXT("Error reading from input stream"));

    int m_decodeError = 0;
    int BytesInBuffer = self->InputOffset;

    // We will only decode if we have input data (obviously) AND all the output samples have been read from previous decodes as they will get overwritten
    if (BytesInBuffer > 0 && self->OutputSamples == 0)
    {
        //printf("%lld ", esp_timer_get_time() / 1000);
        m_decodeError = AACDecode(self->InBuffer, &BytesInBuffer, self->OutBuffer, 0);
        BytesDecoded = self->InputOffset - BytesInBuffer;
        self->OutputSamples = AACGetOutputSamps();  // Each sample is two bytes
        
        // Move the left over bytes back to the beginning of the input buffer
        memcpy(self->InBuffer, self->InBuffer + BytesDecoded, BytesInBuffer);
        self->InputOffset = BytesInBuffer;
    }
    else
    {
        m_decodeError = -1;
    }

    mp_obj_t tuple[4];
    tuple[0] = mp_obj_new_int(m_decodeError);
    tuple[1] = mp_obj_new_int(BytesDecoded);
    tuple[2] = mp_obj_new_int(self->OutputSamples);
    tuple[3] = mp_obj_new_int(BytesInBuffer);
    
    return mp_obj_new_tuple(4, tuple);
}
// Define a Python reference to the function above.
//static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(Decoder_AAC_Decode2_obj, 3, 3, Decoder_AAC_Decode2);
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_Decode_obj, Decoder_AAC_Decode);

static mp_obj_t Decoder_AAC_Close(mp_obj_t self_in)
{
    // Free the memory used by the decoder
    AACDecoder_FreeBuffers();

    return mp_const_none;
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_Close_obj, Decoder_AAC_Close);

static mp_obj_t Decoder_AAC_Cleanup(mp_obj_t self_in)
{
    // Free the temporary buffers
    AAC_Decoder_obj_t *self = MP_OBJ_TO_PTR(self_in);

    if (self->InBuffer != NULL)
    {
        m_free(self->InBuffer);
        self->InBuffer = NULL;
    }

    if (self->OutBuffer != NULL)
    {
        m_free(self->OutBuffer);
        self->OutBuffer = NULL;
    }

    self->InputOffset = 0;

    return mp_const_none;
}
// Define a Python reference to the function above.
static MP_DEFINE_CONST_FUN_OBJ_1(Decoder_AAC_Cleanup_obj, Decoder_AAC_Cleanup);

// Table entries are key/value pairs of the attribute name (a string) and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be optimized to word-sized integers by the build system (interned strings).
static const mp_rom_map_elem_t AAC_Decoder_locals_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_AAC_Init), MP_ROM_PTR(&Decoder_AAC_Init_obj) },
    { MP_ROM_QSTR(MP_QSTR_AAC_Start), MP_ROM_PTR(&Decoder_AAC_Start_obj) },
    { MP_ROM_QSTR(MP_QSTR_AAC_GetInfo), MP_ROM_PTR(&Decoder_AAC_GetInfo_obj) },
    { MP_ROM_QSTR(MP_QSTR_AAC_Decode), MP_ROM_PTR(&Decoder_AAC_Decode_obj) },
    { MP_ROM_QSTR(MP_QSTR_AAC_Close), MP_ROM_PTR(&Decoder_AAC_Close_obj) },
    { MP_ROM_QSTR(MP_QSTR_AAC_Cleanup), MP_ROM_PTR(&Decoder_AAC_Cleanup_obj) },
    { MP_ROM_QSTR(MP_QSTR_write_free), MP_ROM_PTR(&Decoder_AAC_write_free_obj) },
    { MP_ROM_QSTR(MP_QSTR_write_used), MP_ROM_PTR(&Decoder_AAC_write_used_obj) },
    { MP_ROM_QSTR(MP_QSTR_flush), MP_ROM_PTR(&Decoder_AAC_flush_obj) },
    { MP_ROM_QSTR(MP_QSTR_read), MP_ROM_PTR(&mp_stream_read_obj) },
    { MP_ROM_QSTR(MP_QSTR_readinto), MP_ROM_PTR(&mp_stream_readinto_obj) },
    { MP_ROM_QSTR(MP_QSTR_write), MP_ROM_PTR(&mp_stream_write_obj) },
};
static MP_DEFINE_CONST_DICT(AAC_Decoder_locals_dict, AAC_Decoder_locals_dict_table);

// Define the stream protocol
static const mp_stream_p_t AAC_Decoder_stream_p = {
    .read = mystream_read,
    .write = mystream_write,
    .is_text = false,
};

#ifdef MP_OBJ_TYPE_GET_SLOT
MP_DEFINE_CONST_OBJ_TYPE(
    AAC_Decoder_type,
    MP_QSTR_AACDecoder,
    MP_TYPE_FLAG_NONE,
    print, Decoder_AAC_print,
    make_new, Decoder_AAC_make_new,
    protocol, &AAC_Decoder_stream_p,
    locals_dict, (mp_obj_dict_t *)&AAC_Decoder_locals_dict);
#else
const mp_obj_type_t AAC_Decoder_type = {
    {&mp_type_type},
    .name = MP_QSTR_AACDecoder,
    .print = Decoder_AAC_print,
    .make_new = Decoder_AAC_make_new,
    .protocol = &AAC_Decoder_stream_p,
    .locals_dict = (mp_obj_dict_t*)&AAC_Decoder_locals_dict,
};
#endif

////////////////////////// Module functions //////////////////////////

static const mp_map_elem_t AudioDecoder_globals_table[] = {
    {MP_OBJ_NEW_QSTR(MP_QSTR___name__), MP_OBJ_NEW_QSTR(MP_QSTR_AudioDecoder)},
    {MP_OBJ_NEW_QSTR(MP_QSTR_VorbisDecoder), (mp_obj_t)&Vorbis_Decoder_type},	
    {MP_OBJ_NEW_QSTR(MP_QSTR_MP3Decoder), (mp_obj_t)&MP3_Decoder_type},
    {MP_OBJ_NEW_QSTR(MP_QSTR_AAC_Decoder), (mp_obj_t)&AAC_Decoder_type},	
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
