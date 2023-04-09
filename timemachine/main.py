import network
import time
import urequests

from machine import Pin

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
wifi.scan()  # Scan for available access points
wifi.connect("fiosteve", "Fwest5%maini")  # Connect to an AP
wifi.isconnected()  # Check for successful connection
