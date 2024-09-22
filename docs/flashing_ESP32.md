# Flashing ESP 32

- [Flashing ESP 32](#flashing-esp-32)
  - [Install ESP-IDF](#install-esp-idf)
  - [Download the firmware](#download-the-firmware)
  - [Flashing the ESP32](#flashing-the-esp32)
  - [Installing the Software](#installing-the-software)
    - [Notes](#notes)
  - [OTA Updates](#ota-updates)
  - [Getting the Filesystem into File](#getting-the-filesystem-into-file)
    - [Preparing the Filesystem](#preparing-the-filesystem)
    - [Uploading the Filesystem](#uploading-the-filesystem)
  - [Flashing Filesystem](#flashing-filesystem)
    - [Get the Latest Version of the Firmware and Software](#get-the-latest-version-of-the-firmware-and-software)
    - [Flash Everything](#flash-everything)
    - [Rolling Back to a Previous Version of the Firmware](#rolling-back-to-a-previous-version-of-the-firmware)

## Install ESP-IDF

```{}
: ~ ; cd
: ~ ; mkdir esp
: ~ ; cd esp
: ~/esp ; git clone -b v5.2 --recursive https://github.com/espressif/esp-idf.git # This takes several minutes
: ~/esp ; cd esp-idf/
: ~/esp/esp-idf ; ./install.sh esp32,esp32s3
```

Note: if you get weird errors try rm -rf ~/esp & rm -rf ~/.espressif & PATH=$(getconf PATH) and start again

## Download the firmware

clone the litestream repo

```{}
: ~ ; cd ~/projects
: ~/projects ; git clone https://github.com/eichblatt/litestream.git
: ~/projects ; cd litestream
: ~/projects/litestream ; cd MicropythonFirmware/latest
: ~/projects/litestream/MicropythonFirmware/latest ; ls
bootloader.bin  micropython.bin  micropython.sha  partition-table.bin
```

## Flashing the ESP32

first source the file  $HOME/esp/esp-idf/export.sh

```{}
: ~ ; source $HOME/esp/esp-idf/export.sh 

: ~ ; cd $HOME/projects/litestream
: ~ ; IDF_ENV=idf5.2_py3.12_env
: ~/projects/litestream ; source /home/steve/.espressif/python_env/$IDF_ENV/bin/activate
: idf5.2_py3.12_env ~/projects/litestream ; pip3 install pyserial   # No longer required?
: idf5.2_py3.12_env ~/projects/litestream ; cd MicropythonFirmware/latest
: idf5.2_py3.12_env ~/projects/litestream/MicropythonFirmware/latest ; sudo /home/steve/.espressif/python_env/$IDF_ENV/bin/python /home/steve/esp/esp-idf/components/esptool_py/esptool/esptool.py -p /dev/ttyACM0 -b 460800 --before default_reset --after no_reset --chip esp32s3  write_flash --flash_mode dio --flash_size detect --flash_freq 80m 0x0 ./bootloader.bin 0x8000 ./partition-table.bin 0x10000 ./micropython.bin
```

**NOTE**:
For the Serial Board version, I need to replace `/dev/ttyACM0` with `/dev/ttyUSB0`. The command becomes:

```{}
: ~ ; IDF_ENV=idf5.2_py3.12_env
: /home/steve/.espressif/python_env/idf5.2_py3.12_env ~/projects/litestream/MicropythonFirmware/test ; DEVICE=/dev/ttyACM0
: idf5.2_py3.12_env ~/projects/litestream/MicropythonFirmware/latest ; sudo /home/steve/.espressif/python_env/$IDF_ENV/bin/python /home/steve/esp/esp-idf/components/esptool_py/esptool/esptool.py -p $DEVICE -b 460800 --before default_reset --after no_reset --chip esp32s3  write_flash --flash_mode dio --flash_size detect --flash_freq 80m 0x0 ./bootloader.bin 0x8000 ./partition-table.bin 0x10000 ./micropython.bin
```

## Installing the Software

Log into the device with Jama

```{}
: ~ ; cd ~/projects/ESP32-MPY-Jama/
: ~/projects/ESP32-MPY-Jama ; . venv/bin/activate
: jama_env ~/ESP32-MPY-Jama ; python3 src/app.py 
```

Connect to Wifi on the Jama. Then in the REPL, run these commands:

```{}
import mip

mip.install("github:eichblatt/litestream/timemachine/package.json", version="dev")

```

where "version" is the branch or tag, and "target" is the folder to put the code into.

Then, copy the boot.py from the target folder to the root folder, so that it will run when booting up.

```{}
copy_file('/lib/boot.py','/boot.py')
```

### Notes

I got errors and had to rm -r ~/.espressif/ and then ./install.sh esp32,esp32s3 again
The ESP-IDF build system does not support spaces in the paths to either ESP-IDF or to projects
Micropython interrupts don't work on ESP32-S3 - see <https://github.com/micropython/micropython/issues/8488>. Have to run menuconfig and set the single core flag (under ComponentConfig->FreeRTOS->Run FreeRTOS only on first Core) - not sure this is relevant any more
If you get errors about wrong paths for the compiler, you may need to add the correct paths.

```{}
export PATH=/home/mikealex/.espressif/tools/xtensa-esp32s3-elf/esp-2021r2-patch5-8.4.0/xtensa-esp32s3-elf/bin/xtensa-esp32s3-elf-g++:$PATH
export PATH=/home/mikealex/.espressif/tools/xtensa-esp32s3-elf/esp-2021r2-patch5-8.4.0/xtensa-esp32s3-elf/
bin/xtensa-esp32s3-elf-gcc:$PATH
```

e.g. ESP-IDF v4.4.4 includes "patch5". Then do a "make BOARD=GENERIC_S3_SPIRAM_OCT clean" and build again.

## OTA Updates

1. Remove the contents of the MicropythonFirmware/latest folder, if any.
2. Copy the contents of the folder containing the latest release of micropython.bin to MicropythonFirmware/latest/
: ~/projects/litestream/MicropythonFirmware ; cp v1.20.0-348-g24a6e951e-dirty/* latest/.
3. Compute the sha of the micropython file
    sha256sum micropython.bin > micropython.sha
4. Commit and push this folder contents sha to github.

## Getting the Filesystem into File

This procedure gets the filesystem into the file `fsbackup.bin`. See <https://github.com/orgs/micropython/discussions/12223>

### Preparing the Filesystem

The filesystem that we want to flash should not contain files `.knob_sense`, `.screen_type`, `latest_state.json`, and the `wifi_cred.json` should contain the wifi credentials at Joel's home, which are FUCKBITCHE$ and L8erHoes

### Uploading the Filesystem

Disconnect the device from Jama, which will interfere with this process.

```{}
: ~ ; export DEVICE=/dev/ttyACM0 # Note: Old board was /dev/ttyUSB0
: ~ ; source $HOME/esp/esp-idf/export.sh 
: ~ ; cd $HOME/projects/litestream
: ~/projects/litestream ; source /home/steve/.espressif/python_env/$IDF_ENV/bin/activate
: /home/steve/.espressif/python_env/idf5.2_py3.12_env ~/projects/litestream ; cd MicropythonFirmware/latest
: /home/steve/.espressif/python_env/idf5.2_py3.12_env ~/projects/litestream/MicropythonFirmware/latest ; sudo /home/steve/.espressif/python_env/$IDF_ENV/bin/python /home/steve/esp/esp-idf/components/esptool_py/esptool/esptool.py -p $DEVICE -b 460800 --before default_reset --after no_reset --chip esp32s3  read_flash 0x4f0000 0xb10000 fsbackup.bin
```

Note, this takes a few minutes.
Then, push this file `fsbackup.bin` to github, and merge into the main branch.

## Flashing Filesystem

Now, to flash a device with the firmware _and_ software:

### Get the Latest Version of the Firmware and Software

If you have already downloaded the firmware before, then simply get the latest version:

```{}
:  ~ ; cd $HOME/projects/litestream/MicropythonFirmware
:  ~/projects/litestream/MicropythonFirmware ; cd latest
:  ~/projects/litestream/MicropythonFirmware/latest ; git pull
```

If this is the first time, then follow instructions on how to [Download the firmware](#download-the-firmware) above.

### Flash Everything

```{}
: ~ ; export DEVICE=/dev/ttyUSB0 # Note: New serial board is /dev/ttyACM0
: ~ ; source $HOME/esp/esp-idf/export.sh 
: ~ ; cd $HOME/projects/litestream
: ~/projects/litestream ; source /home/steve/.espressif/python_env/$IDF_ENV/bin/activate
: /home/steve/.espressif/python_env/idf5.2_py3.12_env ~/projects/litestream ; cd MicropythonFirmware/latest
: /home/steve/.espressif/python_env/idf5.2_py3.12_env ~/projects/litestream/MicropythonFirmware/latest ; sudo $HOME/.espressif/python_env/$IDF_ENV/bin/python $HOME/esp/esp-idf/components/esptool_py/esptool/esptool.py -p $DEVICE -b 460800 --before default_reset --after no_reset --chip esp32s3  write_flash --flash_mode dio --flash_size detect --flash_freq 80m 0x0 bootloader.bin 0x8000 partition-table.bin 0x10000 micropython.bin 0x4f0000 fsbackup.bin
```

### Rolling Back to a Previous Version of the Firmware

There a few things you need to know when rolling back firmware.

- When writing a different version of the firmware, use the `--erase-all` option in the `esptool.py` command. Otherwise, the filesystem will not be erased, and it will be invalid.
- The file fsbackup.bin is specific to the version of the firmware. You cannot copy it to a different firmware version
