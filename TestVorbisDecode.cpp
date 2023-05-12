#include <WiFi.h>
#include <HTTPClient.h>
#include "driver/i2s.h"

// https://github.com/nothings/stb
// http://nothings.org/stb_vorbis/
#define STB_VORBIS_NO_STDIO
#include "C:\Users\mike\OneDrive\Documents\Arduino\libraries\stb_vorbis.c"

#define SAMPLE_RATE 44100
#define CHANNELS 2

#define I2S_DOUT      17
#define I2S_BCLK      13
#define I2S_LRC       14

uint8_t             m_i2s_num = I2S_NUM_0;          // I2S_NUM_0 or I2S_NUM_1
i2s_config_t        m_i2s_config;                   // stores values for I2S driver
i2s_pin_config_t    m_pin_config;
uint32_t            m_sampleRate=44100;
uint8_t             m_bitsPerSample = 16;           // bitsPerSample
uint8_t             m_vol=64;                       // volume
size_t              m_i2s_bytesWritten = 0;         // set in i2s_write() but not used
uint8_t             m_channels=2;
int16_t             m_outBuff[2048*2];              // Interleaved L/R
int16_t             m_validSamples = 0;
int16_t             m_curSample = 0;
bool                m_f_forceMono = false;
bool                m_f_isPlaying = false;

WiFiClient wifiClient;

esp_err_t I2Sstart(uint8_t i2s_num) 
{
    // It is not necessary to call this function after i2s_driver_install() (it is started automatically),
    // however it is necessary to call it after i2s_stop()
    return i2s_start((i2s_port_t) i2s_num);
}

esp_err_t I2Sstop(uint8_t i2s_num) 
{
    return i2s_stop((i2s_port_t) i2s_num);
}

void setupI2S()
{
    m_i2s_num = I2S_NUM_0; // i2s port number
    m_i2s_config.mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX);
    m_i2s_config.sample_rate          = 44100;
    m_i2s_config.bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT;
    m_i2s_config.channel_format       = I2S_CHANNEL_FMT_RIGHT_LEFT;
    m_i2s_config.communication_format = (i2s_comm_format_t)(I2S_COMM_FORMAT_STAND_I2S);
    m_i2s_config.intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1; // high interrupt priority
    m_i2s_config.dma_buf_count        = 8;      // max buffers
    m_i2s_config.dma_buf_len          = 1024;   // max value
    m_i2s_config.tx_desc_auto_clear   = true;   // new in V1.0.1
    m_i2s_config.fixed_mclk           = I2S_PIN_NO_CHANGE;

    i2s_driver_install((i2s_port_t)m_i2s_num, &m_i2s_config, 0, NULL);
}

bool setPinout(uint8_t BCLK, uint8_t LRC, uint8_t DOUT, int8_t DIN) 
{
    m_pin_config.bck_io_num   = BCLK;
    m_pin_config.ws_io_num    = LRC; //  wclk
    m_pin_config.data_out_num = DOUT;
    m_pin_config.data_in_num  = DIN;
    const esp_err_t result = i2s_set_pin((i2s_port_t) m_i2s_num, &m_pin_config);
    return (result == ESP_OK);
}

bool setSampleRate(uint32_t sampRate) 
{
    i2s_set_sample_rates((i2s_port_t)m_i2s_num, sampRate);
    m_sampleRate = sampRate;
    return true;
}

bool setBitsPerSample(int bits) {
    if((bits != 16) && (bits != 8)) return false;
    m_bitsPerSample = bits;
    return true;
}
uint8_t getBitsPerSample(){
    return m_bitsPerSample;
}

bool setChannels(int ch) {
    if((ch < 1) || (ch > 2)) return false;
    m_channels = ch;
    return true;
}

uint8_t getChannels(){
    return m_channels;
}

//---------------------------------------------------------------------------------------------------------------------

void setup() 
{
    Serial.begin(115200);
    while (!Serial);
  
    Serial.print("Connecting to WiFi");
    WiFi.begin("DODO-31BF", "PU7QUYXQE7");
    
    while (WiFi.status() != WL_CONNECTED) 
    {
      delay(500);
      Serial.print(".");
    }
    
    Serial.println("");
    Serial.println("WiFi connected");
    Serial.println("IP address: ");
    Serial.println(WiFi.localIP());
  
    setupI2S();
    setPinout(I2S_BCLK, I2S_LRC, I2S_DOUT, -1);
    setBitsPerSample(16);
    I2Sstart(m_i2s_num);
  
    // Create a memory block to pass into the Vorbis decoder. It will use this instead of doing its own malloc/malloca
    const stb_vorbis_alloc VorbisBuffer {.alloc_buffer = (char*)malloc(400000), .alloc_buffer_length_in_bytes = 400000};
  
    if (VorbisBuffer.alloc_buffer == NULL)
        Serial.println("Malloc failed");
  
    const char * headerKeys[] = {"Content-Length"} ;
    const size_t numberOfHeaders = 1;
  
    stb_vorbis *v;
    int p, q, len, error, used;
    int bytes_read = 0;
    
    // Make an HTTP request to download the Ogg Vorbis file
    HTTPClient httpClient;
    //httpClient.begin(wifiClient, "http://nothings.org/stb_vorbis/samples/thingy.ogg");
    //httpClient.begin(wifiClient, "192.168.1.123", 1180, "/examplein.ogg");
    httpClient.begin(wifiClient, "http://ia800305.us.archive.org/19/items/gd1980-10-29.beyer.stankiewicz.126919.flac1644/gd1980-10-29s1t02.ogg");
   
    int httpCode = httpClient.GET();
    
    if (httpCode != HTTP_CODE_OK) 
    {
      Serial.printf("Failed to download Ogg Vorbis file: %d\n", httpCode);
  
      if (VorbisBuffer.alloc_buffer)
          free(VorbisBuffer.alloc_buffer);

      httpClient.end();

      return;
    }

    // Get the Content-Length header to see the length of the file
    httpClient.collectHeaders(headerKeys, numberOfHeaders);
    Serial.printf("Length: %s\n", httpClient.header("Content-Length"));
    len = httpClient.header("Content-Length").toInt();
        
    p = 0;

    #define BUFFER_SIZE 8192    // Don't make this (much) smaller as it needs to fit the OGG header and the first frame of the VORBIS data
    
    // Allocate a buffer
    uint8* buffer = (uint8*)malloc(BUFFER_SIZE);

    if (buffer == NULL)
    {
        Serial.println("Buffer malloc failed");
    
        if (VorbisBuffer.alloc_buffer)
            free(VorbisBuffer.alloc_buffer);

        httpClient.end();

        return;
    }
    
    //uint8 buffer[BUFFER_SIZE];

    // Read  data from the HTTP response until the buffer is full
    while (p < BUFFER_SIZE && httpClient.connected())
    {
        bytes_read = httpClient.getStream().read(buffer + p, BUFFER_SIZE - p);
        Serial.printf("Read %d bytes\n", bytes_read);
        p += bytes_read;
    }

    if (p != BUFFER_SIZE)
    {
        Serial.println("Error reading header");
    
        if (buffer)
            free(buffer);
    
        if (VorbisBuffer.alloc_buffer)
            free(VorbisBuffer.alloc_buffer);
    
        httpClient.end();

        return;
    }

    p = 0;
    q = 1;
    used = 0;
          
    // Set up the Ogg Vorbis decoder by passing in a buffer containing the OGG header and the first frame of the VORBIS data
    retry:
    v = stb_vorbis_open_pushdata(buffer, q, &used, &error, &VorbisBuffer);
   
    if (v == NULL) 
    {
        if (error == VORBIS_need_more_data) 
        {
            q += 1;
            Serial.printf("#");
            goto retry;
        }
        else
        {
            Serial.printf("\nError %d\n", error);
            stb_vorbis_close(v);
    
            if (buffer)
                free(buffer);
        
            if (VorbisBuffer.alloc_buffer)
                free(VorbisBuffer.alloc_buffer);
        
            httpClient.end();

            return;
        }
    }
    else
        Serial.printf("\nCreated Ogg Vorbis decoder. Used: %d\n", used);

    //free(buffer);
   
    p = used;                           // p now points to the first byte of audio data

    // Get some info about the stream
    stb_vorbis_info info = stb_vorbis_get_info(v);
    Serial.printf("%d channels, %d samples/sec\n", info.channels, info.sample_rate);
    Serial.printf("Predicted memory needed: %d (%d + %d)\n", info.setup_memory_required + info.temp_memory_required, info.setup_memory_required, info.temp_memory_required);
    Serial.printf("Max frame size: %d\n", info.max_frame_size);

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

    int bytes_in_buffer = BUFFER_SIZE - used;
    int buffer_offset = used;
    int num_outputs;
    float **outputs;
    int num_channels;
    //q = BUFFER_SIZE - p;       // Decode what's left in the buffer after the header has been read
    //int16_t* outbuff = (int16_t*)malloc(1024 * info.channels * 2);
    
    for(;;)
    {
        while (bytes_in_buffer > 0)     // Decode until we have emptied the buffer
        {
            used = stb_vorbis_decode_frame_pushdata(v, buffer + buffer_offset, bytes_in_buffer, &num_channels, &outputs, &num_outputs);
            //Serial.printf("U:%d N:%d, ", used, num_outputs);
            
            buffer_offset += used;
            bytes_in_buffer -= used;
          
            if (num_outputs > 0)   // We have output data
            {
                size_t BytesWritten;
                short outbuff[num_outputs * 2];
                //int16_t* outbuff = (int16_t*)malloc(n * info.channels * 2);
                
                // Convert from float to int
                convert_channels_short_interleaved(2, outbuff, 2, &outputs[0], 0, num_outputs);
             
                // Send converted samples to the DAC      
                i2s_write((i2s_port_t)0, (char*)outbuff, (size_t)num_outputs * info.channels * 2, &BytesWritten, 100);
    
                //free(outbuff);
            }
            
            if (used == 0) // Decoder needs more data. Buffer may still have some data in it, but not enough to decode the next frame. Move the remaining data to the beginning of the buffer and then exit the loop to fill it some more
            {
                Serial.printf("\nDecoder starved. %d bytes left in buffer\n", bytes_in_buffer);
                memcpy(buffer, buffer + buffer_offset, bytes_in_buffer);
                break;
            }
        }
  
        Serial.printf("Get more data. Stack %d\n", uxTaskGetStackHighWaterMark(NULL));
  
        bytes_read = 0;
        
        while (httpClient.connected() && bytes_read == 0)     // Read until we get some data
        {
            Serial.printf("*");
            bytes_read = httpClient.getStream().read(buffer + bytes_in_buffer, BUFFER_SIZE - bytes_in_buffer);
            //Serial.printf("%d ", bytes_read);
        }
  
        Serial.printf("Read %d bytes\n", bytes_read);
        
        bytes_in_buffer += bytes_read;
        buffer_offset = 0;
        
        Serial.printf("Buffer now has %d bytes\n", bytes_in_buffer);
        
        if (!httpClient.connected())
        {
            Serial.printf("EOF");
            break;
        }
    }
        
    stb_vorbis_close(v);
    
    if (buffer)
        free(buffer);
        
    if (VorbisBuffer.alloc_buffer)
        free(VorbisBuffer.alloc_buffer);
        
    httpClient.end();
}

void loop() 
{
}
