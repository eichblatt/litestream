// Include MicroPython API.
#include "py/runtime.h"

#define STB_VORBIS_NO_STDIO
#include "stb_vorbis.c"

// Used to get the time in the Timer class example.
#include "py/mphal.h"

stb_vorbis *v;

int x;

STATIC mp_obj_t Vorbis_Start(mp_obj_t VorbisBuffer, mp_obj_t VorbisBufferSize, mp_obj_t StreamBuffer)
{
    //#define BUFFER_SIZE 8192    // Don't make this (much) smaller as it needs to fit the OGG header and the first frame of the VORBIS data
    //mp_raise_msg(&mp_type_ValueError, "We are here");
    
    // Create a memory block to pass into the Vorbis decoder. It will use this instead of doing its own malloc/malloca
    //const stb_vorbis_alloc VBuffer = {.alloc_buffer = (char*)MP_OBJ_TO_PTR(VorbisBuffer), .alloc_buffer_length_in_bytes = mp_obj_get_int(VorbisBufferSize)};
    mp_buffer_info_t VorbisBufferInfo;
    mp_get_buffer_raise(VorbisBuffer, &VorbisBufferInfo, MP_BUFFER_READ | MP_BUFFER_WRITE);
    const stb_vorbis_alloc VBuffer = {.alloc_buffer = (char*)VorbisBufferInfo.buf, .alloc_buffer_length_in_bytes = VorbisBufferInfo.len};

    // This is the buffer containing encoded streaming data from Python code
    mp_buffer_info_t StreamBufferInfo;
    mp_get_buffer_raise(StreamBuffer, &StreamBufferInfo, MP_BUFFER_READ);

    //uint8* buffer = (uint8*)MP_OBJ_TO_PTR(StreamBuffer);
    printf("Buffer Data: %x %x\n", ((uint8*)StreamBufferInfo.buf)[0], ((uint8*)StreamBufferInfo.buf)[1]);


    int header_pos = 8192;
    int used, error;

    v = stb_vorbis_open_pushdata((uint8*)StreamBufferInfo.buf, header_pos, &used, &error, &VBuffer);

    if (error == VORBIS_need_more_data)
    {
        mp_raise_msg(&mp_type_ValueError, "Need more data");
    }

    if (v == NULL || error != 0)
    {
        if (v == NULL)
            printf("V is NULL\n");

        printf("Error: %d", error);

        //mp_raise_msg(&mp_type_ValueError, "Error");

        if (v != NULL)
            stb_vorbis_close(v);

        return mp_obj_new_int(-1);
    }

    return mp_obj_new_int(used);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_3(Vorbis_Start_obj, Vorbis_Start);

STATIC mp_obj_t Vorbis_GetInfo(void)
{
    stb_vorbis_info info;

    if (v != NULL)
        info = stb_vorbis_get_info(v);
    else
    {
        mp_raise_msg(&mp_type_ValueError, "Vorbis Decoder not initalised");
        return mp_obj_new_int(-1);
    }

    printf("%d channels, %d samples/sec\n", info.channels, info.sample_rate);
    printf("Predicted memory needed: %d (%d + %d)\n", info.setup_memory_required + info.temp_memory_required, info.setup_memory_required, info.temp_memory_required);
    printf("Max frame size: %d\n", info.max_frame_size);

    return mp_obj_new_int(info.max_frame_size);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(Vorbis_GetInfo_obj, Vorbis_GetInfo);


// Info on calling stb_vorbis_decode_frame_pushdata:
// stb_vorbis *f,                   // the file we're decoding
// const unsigned char *datablock,  // The buffer containing data
// int datablock_length_in_bytes,   // Length of the buffer
// int *channels,                   // place to write number of float * buffers
// float ***output,                 // place to write float ** array of float * buffers
// int *samples                     // place to write number of output samples
// return value: number of bytes we used from datablock
//
// Possible cases:
//     0 bytes used, 0 samples output (need more data)
//     N bytes used, 0 samples output (resynching the stream, keep going)
//     N bytes used, M samples output (one frame of data)
// Note that after opening a file, you will ALWAYS get one N-bytes,0-sample
// frame, because Vorbis always "discards" the first frame.
STATIC mp_obj_t Vorbis_Decode(mp_obj_t InBuffer, mp_obj_t BufferOffset, mp_obj_t OutBuffer)
{
    if (v == NULL)
        mp_raise_msg(&mp_type_ValueError, "Vorbis Decoder not initalised");

    int used = 0;
    int num_outputs, num_channels;
    float **outputs;

    mp_buffer_info_t InBufferInfo;
    mp_get_buffer_raise(InBuffer, &InBufferInfo, MP_BUFFER_READ);
    mp_buffer_info_t OutBufferInfo;
    mp_get_buffer_raise(OutBuffer, &OutBufferInfo, MP_BUFFER_WRITE);
    int offset = mp_obj_get_int(BufferOffset);

    used = stb_vorbis_decode_frame_pushdata(v, (uint8*)InBufferInfo.buf, offset, &num_channels, &outputs, &num_outputs);

    if (num_outputs > 0)            // We got some decoded data
        convert_channels_short_interleaved(2, (short*)OutBufferInfo.buf, 2, &outputs[0], 0, num_outputs); // Convert from float to int

    // Create a tuple object to return two value - bytes used from the buffer and number of decoded output samples
    mp_obj_t tuple[2];
    tuple[0] = mp_obj_new_int(used);
    tuple[1] = mp_obj_new_int(num_outputs);

    return mp_obj_new_tuple(2, tuple);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_3(Vorbis_Decode_obj, Vorbis_Decode);

STATIC mp_obj_t Vorbis_Close(void)
{
    if (v == NULL)
        mp_raise_msg(&mp_type_ValueError, "Vorbis Decoder not initalised");

    stb_vorbis_close(v);

    return mp_const_none;
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_0(Vorbis_Close_obj, Vorbis_Close);
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////



// This is the function which will be called from Python as cexample.add_ints(a, b).
STATIC mp_obj_t example_add_ints(mp_obj_t a_obj, mp_obj_t b_obj) {
    // Extract the ints from the micropython input objects.
    int a = mp_obj_get_int(a_obj);  
    int b = mp_obj_get_int(b_obj);

    // Calculate the addition and convert to MicroPython object.
    return mp_obj_new_int(a + b);
}
// Define a Python reference to the function above.
STATIC MP_DEFINE_CONST_FUN_OBJ_2(example_add_ints_obj, example_add_ints);





// This structure represents Timer instance objects.
typedef struct _example_Timer_obj_t {
    // All objects start with the base.
    mp_obj_base_t base;
    // Everything below can be thought of as instance attributes, but they
    // cannot be accessed by MicroPython code directly. In this example we
    // store the time at which the object was created.
    mp_uint_t start_time;
} example_Timer_obj_t;

// This is the Timer.time() method. After creating a Timer object, this
// can be called to get the time elapsed since creating the Timer.
STATIC mp_obj_t example_Timer_time(mp_obj_t self_in) {
    // The first argument is self. It is cast to the *example_Timer_obj_t
    // type so we can read its attributes.
    example_Timer_obj_t *self = MP_OBJ_TO_PTR(self_in);

    // Get the elapsed time and return it as a MicroPython integer.
    mp_uint_t elapsed = mp_hal_ticks_ms() - self->start_time;
    return mp_obj_new_int_from_uint(elapsed);
}
STATIC MP_DEFINE_CONST_FUN_OBJ_1(example_Timer_time_obj, example_Timer_time);

// This represents Timer.__new__ and Timer.__init__, which is called when
// the user instantiates a Timer object.
STATIC mp_obj_t example_Timer_make_new(const mp_obj_type_t *type, size_t n_args, size_t n_kw, const mp_obj_t *args) {
    // Allocates the new object and sets the type.
    example_Timer_obj_t *self = mp_obj_malloc(example_Timer_obj_t, type);

    // Initializes the time for this Timer instance.
    self->start_time = mp_hal_ticks_ms();

    // The make_new function always returns self.
    return MP_OBJ_FROM_PTR(self);
}

// This collects all methods and other static class attributes of the Timer.
// The table structure is similar to the module table, as detailed below.
STATIC const mp_rom_map_elem_t example_Timer_locals_dict_table[] = {
    { MP_ROM_QSTR(MP_QSTR_time), MP_ROM_PTR(&example_Timer_time_obj) },
};
STATIC MP_DEFINE_CONST_DICT(example_Timer_locals_dict, example_Timer_locals_dict_table);

// This defines the type(Timer) object.
MP_DEFINE_CONST_OBJ_TYPE(
    example_type_Timer,
    MP_QSTR_Timer,
    MP_TYPE_FLAG_NONE,
    make_new, example_Timer_make_new,
    locals_dict, &example_Timer_locals_dict
    );

// Define all properties of the module.
// Table entries are key/value pairs of the attribute name (a string)
// and the MicroPython object reference.
// All identifiers and strings are written as MP_QSTR_xxx and will be
// optimized to word-sized integers by the build system (interned strings).
STATIC const mp_rom_map_elem_t module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_Player) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Start), MP_ROM_PTR(&Vorbis_Start_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_GetInfo), MP_ROM_PTR(&Vorbis_GetInfo_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Decode), MP_ROM_PTR(&Vorbis_Decode_obj) },
    { MP_ROM_QSTR(MP_QSTR_Vorbis_Close), MP_ROM_PTR(&Vorbis_Close_obj) },
    { MP_ROM_QSTR(MP_QSTR_add_ints), MP_ROM_PTR(&example_add_ints_obj) },
    { MP_ROM_QSTR(MP_QSTR_Timer), MP_ROM_PTR(&example_type_Timer) },
};
STATIC MP_DEFINE_CONST_DICT(module_globals, module_globals_table);

// Define module object.
const mp_obj_module_t user_cmodule = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&module_globals,
};

// Register the module to make it available in Python.
MP_REGISTER_MODULE(MP_QSTR_Player, user_cmodule);