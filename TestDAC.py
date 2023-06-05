from machine import Pin, I2S
import io

sck_pin = Pin(13)   # Serial clock output
ws_pin = Pin(14)    # Word clock output
sd_pin = Pin(17)    # Serial data output

buf = bytearray(1024)

print("Starting") 
audio_out = I2S(1, sck=sck_pin, ws=ws_pin, sd=sd_pin, mode=I2S.TX, bits=16, format=I2S.STEREO, rate=44100, ibuf=1024)
print(audio_out)

with io.open("GDCDQualityTrim.wav", 'rb') as fp:
    size = fp.readinto(buf)
        
    while (size > 0):
        print('.', end='')
        audio_out.write(buf)
        size = fp.readinto(buf)
        
print("Finished") 
fp.close()

audio_out.deinit()
