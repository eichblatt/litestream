Install ESP-IDF
===============
```
: ~ ; cd
: ~ ; mkdir esp
: ~ ; cd esp
: ~/esp ; git clone -b v5.0.2 --recursive https://github.com/espressif/esp-idf.git
: ~/esp ; cd esp-idf/
: ~/esp/esp-idf ; ./install.sh esp32,esp32s3
```
Note: if you get weird errors try rm -rf ~/esp & rm -rf ~/.espressif & PATH=$(getconf PATH) and start again

Flashing the ESP32
=============================
first source the file  $HOME/esp/esp-idf/export.sh
```
: ~ ; source $HOME/esp/esp-idf/export.sh 

: ~ ; cd $HOME/projects/litestream
: ~/projects/litestream ; source /home/steve/.espressif/python_env/idf4.4_py3.10_env/bin/activate
: (idf4.4_py3.10_env) ~/projects/litestream ; pip3 install pyserial   # This only needs to be done once.
: (idf4.4_py3.10_env) ~/projects/litestream ; cd MicropythonFirmware/latest
: (idf4.4_py3.10_env) ~/projects/litestream/MicropythonFirmware/latest ; sudo /home/steve/.espressif/python_env/idf4.4_py3.10_env/bin/python /home/steve/esp/esp-idf/components/esptool_py/esptool/esptool.py -p /dev/ttyACM0 -b 460800 --before default_reset --after no_reset --chip esp32s3  write_flash --flash_mode dio --flash_size detect --flash_freq 80m 0x0 ./bootloader.bin 0x8000 ./partition-table.bin 0x10000 ./micropython.bin
```
Installing the Software
=======================
Log into the device with Jama, and connect to WiFi.
```
import mip

mip.install("github:eichblatt/litestream/timemachine/package.json", version="vs1053", target="test_download")
```
where "version" is the branch or tag, and "target" is the folder to put the code into.

Then, copy the boot.py from the target folder to the root folder, so that it will run when booting up.


Notes:
======
I got errors and had to rm -r ~/.espressif/ and then ./install.sh esp32,esp32s3 again
The ESP-IDF build system does not support spaces in the paths to either ESP-IDF or to projects
Micropython interrupts don't work on ESP32-S3 - see https://github.com/micropython/micropython/issues/8488. Have to run menuconfig and set the single core flag (under ComponentConfig->FreeRTOS->Run FreeRTOS only on first Core) - not sure this is relevant any more
If you get errors about wrong paths for the compiler, you may need to add the correct paths.
```
export PATH=/home/mikealex/.espressif/tools/xtensa-esp32s3-elf/esp-2021r2-patch5-8.4.0/xtensa-esp32s3-elf/bin/xtensa-esp32s3-elf-g++:$PATH
export PATH=/home/mikealex/.espressif/tools/xtensa-esp32s3-elf/esp-2021r2-patch5-8.4.0/xtensa-esp32s3-elf/
bin/xtensa-esp32s3-elf-gcc:$PATH
```
e.g. ESP-IDF v4.4.4 includes "patch5". Then do a "make BOARD=GENERIC_S3_SPIRAM_OCT clean" and build again.

OTA Updates:
===========
1. Remove the contents of the MicropythonFirmware/latest folder, if any.
1. Copy the contents of the folder containing the latest release of micropython.bin to MicropythonFirmware/latest/
: ~/projects/litestream/MicropythonFirmware ; cp v1.20.0-348-g24a6e951e-dirty/* latest/.
2. Compute the sha of the micropython file
    sha256sum micropython.bin > micropython.sha
3. Commit and push this folder contents sha to github.