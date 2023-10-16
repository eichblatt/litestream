# Install Jama
============================================
Code is at
https://github.com/jczic/ESP32-MPY-Jama 

## Linux installation
https://github.com/jczic/ESP32-MPY-Jama#penguin-linux-version-instructions

```
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
: ~/projects/ESP32-MPY-Jama ; pip3 install wheel setuptools
: ~/projects/ESP32-MPY-Jama ; pip3 install pyserial pywebview[qt] pycairo PyGObject pyinstaller
```

# Running the Program
====================
```
: ~ ; cd ~/projects/ESP32-MPY-Jama/
: ~/projects/ESP32-MPY-Jama ; . venv/bin/activate
: (jama_env) ~/ESP32-MPY-Jama ; python3 src/app.py 
```
Starts ESP32 MPY-Jama v1.2.0 on Linux
**NOTE** After flashing an image, you have to press the BOOT and/or the RESET button on the breakout board.
