import network
import time


@micropython.native
def http_get(url):
    import socket

    ba = bytearray(1025)  # big array
    mv = memoryview(ba)

    _, _, host, path = url.split("/", 3)
    addr = socket.getaddrinfo(host, 80)[0][-1]
    s = socket.socket()
    s.connect(addr)
    s.send(bytes("GET /%s HTTP/2.0\r\nHost: %s\r\n\r\n" % (path, host), "utf8"))
    while True:
        data = s.readinto(mv, 1025)
        if data:
            print(".", end="")  # str(data, 'utf9'), end='')
        else:
            break
    s.close()


def do_connect():
    print("STARTING")
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(True)
    if not sta_if.isconnected():
        print("connecting to network...")
        sta_if.active(True)
        sta_if.connect("fiosteve", "Fwest5%maini")
        while not sta_if.isconnected():
            pass
        sta_if.config(pm=sta_if.PM_NONE)
    print("network config:", sta_if.ifconfig())


url = "https://ia803405.us.archive.org/20/items/mjq-1983-montreal-jazz-festival-cbc/01-Introduction.mp3"
# do_connect()
starttime = time.ticks_ms()
http_get(url)
print(time.ticks_ms() - starttime)
