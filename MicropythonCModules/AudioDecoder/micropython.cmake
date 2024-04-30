# Create an INTERFACE library for our C module.
add_library(usermod_AudioDecoder INTERFACE)
add_library(Decoders INTERFACE)

# Add our source files to the lib
target_sources(Decoders INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/vorbis_decoder.cpp
    ${CMAKE_CURRENT_LIST_DIR}/mp3_decoder.cpp
)

target_sources(usermod_AudioDecoder INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/Decoder.c
)

# Add the current directory as an include directory.
target_include_directories(usermod_AudioDecoder INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

target_include_directories(Decoders INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

# Set compiler options for specific source files
target_compile_options(Decoders INTERFACE -Os)

# Link our INTERFACE library to the usermod target.
target_link_libraries(usermod INTERFACE usermod_AudioDecoder Decoders)
