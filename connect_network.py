import network
import urequests

wifi = network.WLAN(network.STA_IF)
wifi.active(True)
# sta_if.scan()  # Scan for available access points
wifi.connect("fiosteve", "Fwest5%maini")
wifi.isconnected()  # Check for successful connection
