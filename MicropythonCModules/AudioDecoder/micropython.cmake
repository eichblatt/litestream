# Create an INTERFACE library for our C module.
add_library(usermod_Decoder INTERFACE)

# Add our source files to the lib
target_sources(usermod_Decoder INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/vorbis_decoder.cpp
    ${CMAKE_CURRENT_LIST_DIR}/mp3_decoder.cpp
    ${CMAKE_CURRENT_LIST_DIR}/VorbisDecoder.c
    ${CMAKE_CURRENT_LIST_DIR}/MP3Decoder.c
)

# Add the current directory as an include directory.
target_include_directories(usermod_Decoder INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}
)

# Set compiler options for specific source files
set(CXXFLAGS_USERMOD "${CXXFLAGS_USERMOD} -O3")
#set_source_files_properties(${CMAKE_CURRENT_LIST_DIR}/vorbis_decoder.cpp PROPERTIES COMPILE_OPTIONS -O9)
#set_source_files_properties(${CMAKE_CURRENT_LIST_DIR}/VorbisDecoder.c PROPERTIES COMPILE_OPTIONS -O3)
#set_source_files_properties(${CMAKE_CURRENT_LIST_DIR}/mp3_decoder.cpp PROPERTIES COMPILE_OPTIONS -O3)
#set_source_files_properties(${CMAKE_CURRENT_LIST_DIR}/MP3Decoder.c PROPERTIES COMPILE_OPTIONS -O3)

# Link our INTERFACE library to the usermod target.
target_link_libraries(usermod INTERFACE usermod_Decoder)