# Install Jama

Code is at
<https://github.com/jczic/ESP32-MPY-Jama>

## Linux installation

<https://github.com/jczic/ESP32-MPY-Jama#penguin-linux-version-instructions>

```{}
# change to the directory you want to install Jama
: ~ ; cd $HOME/projects
# If the projects directory doesn't exist, make it
: ~ ; mkdir $HOME/projects
: ~ ; cd $HOME/projects
: ~/projects ; 
# clone the repository:
: ~/projects ; git clone https://github.com/jczic/ESP32-MPY-Jama

# install python modules requirements:
: ~/projects ; cd ESP32-MPY-Jama/
: ~/projects/ESP32-MPY-Jama ; sudo apt install libcairo2-dev libgirepository1.0-dev python3-pyqt5 python3-pyqt5.qtwebengine python3-pyqt5.qtwebchannel libqt5webkit5-dev gir1.2-webkit2-4.0

# initialize python venv:
: ~/projects/ESP32-MPY-Jama ; python3 -m venv venv
: ~/projects/ESP32-MPY-Jama ; . venv/bin/activate
: (venv) ~/projects/ESP32-MPY-Jama ; pip3 install wheel setuptools
: (venv) ~/projects/ESP32-MPY-Jama ; pip3 install pyserial pywebview[qt] pycairo PyGObject pyinstaller
```

## Linux dialout group

We also need to set up the port that Jama will use to connect to the device. This port, by default, does not allow users to connect to it.
We only need to change this once.
First, you need to add your user to the `dialout` group, then set the read/write permission for the port, `/dev/ttyACM0`

```{}
: (venv) ~/projects/ESP32-MPY-Jama ; sudo adduser steve dialout
: (venv) ~/projects/ESP32-MPY-Jama ; sudo chmod a+rw /dev/ttyACM0
```

Verify that this worked:

```{}
: (venv) ~/projects/ESP32-MPY-Jama ; ls -ld /dev/ttyACM0
crw-rw---- 1 root dialout 166, 0 Oct 18 17:14 /dev/ttyACM0
: (venv) ~/projects/ESP32-MPY-Jama ; groups
steve adm dialout cdrom sudo dip plugdev lpadmin lxd sambashare
```

The groups output should include `dialout`
Then, you **need to reboot** for this to take effect.

## Running the Program

```{}
: ~ ; cd ~/projects/ESP32-MPY-Jama/
: ~/projects/ESP32-MPY-Jama ; . venv/bin/activate
: (jama_env) ~/ESP32-MPY-Jama ; python3 src/app.py 
```

Starts ESP32 MPY-Jama v1.2.0 on Linux
**NOTE** After flashing an image, you have to press the BOOT and/or the RESET button on the breakout board.

## Install the Software

```{}
import mip
mip.install("github:eichblatt/litestream/timemachine/package.json", version="dev")
copy_file('/lib/boot.py','/boot.py')
```
