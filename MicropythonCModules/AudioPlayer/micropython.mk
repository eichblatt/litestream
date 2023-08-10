EXAMPLE_MOD_DIR := $(USERMOD_DIR)

# Add all C files to SRC_USERMOD.
SRC_USERMOD_LIB_CXX += $(EXAMPLE_MOD_DIR)/vorbis_decoder.cpp
SRC_USERMOD_C += $(EXAMPLE_MOD_DIR)/Player.c

# We can add our module folder to include paths if needed
# This is not actually needed in this example.
CFLAGS_USERMOD += -I$(EXAMPLE_MOD_DIR)
CXXFLAGS_USERMOD += -I$(EXAMPLE_MOD_DIR) -std=c++11

# We use C++ features so have to link against the standard library.
LDFLAGS_USERMOD += -lstdc++

CEXAMPLE_MOD_DIR := $(USERMOD_DIR)
