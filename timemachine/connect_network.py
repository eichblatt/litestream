import network

sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
sta_if.scan()  # Scan for available access points
sta_if.connect("fiosteve", "Fwest5%maini")
sta_if.isconnected()  # Check for successful connection
