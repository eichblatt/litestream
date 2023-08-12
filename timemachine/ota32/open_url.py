import usocket

# open url and return socket
def open_url(url):
    try:
        proto, dummy, host, path = url.split("/", 3)
    except ValueError:
        proto, dummy, host = url.split("/", 2)
        path = ""
    if proto == "http:":
        port = 80
    elif proto == "https:":
        import ussl
        port = 443
    else:
        raise ValueError("Unsupported protocol: " + proto)

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)
        
    ai = usocket.getaddrinfo(host, port, 0, usocket.SOCK_STREAM)
    ai = ai[0]
    
    # s = usocket.socket(ai[0], ai[1], ai[2])
    s = usocket.socket(ai[0], 1, ai[2])
    try:
        s.connect(ai[-1])
        if proto == "https:":
            s = ussl.wrap_socket(s, server_hostname=host)
        s.write(b"%s /%s HTTP/1.0\r\n" % ('GET', path))
        s.write(b"Host: %s\r\n\r\n" % host)

        l = s.readline()
        # print("line 1:", l)
        l = l.split(None, 2)
        status = int(l[1])
        reason = ""
        if len(l) > 2:
            reason = l[2].rstrip()
        while True:
            l = s.readline()
            if not l or l == b"\r\n":
                break
            # print("line 2:", l)
            if l.startswith(b"Transfer-Encoding:"):
                if b"chunked" in l:
                    raise ValueError("Unsupported " + l)
            elif l.startswith(b"Location:") and not 200 <= status <= 299:
                raise NotImplementedError("Redirects not supported")
        if status != 200:
            raise Exception("Download failed, status={} {}".format(status, reason))
    except OSError:
        s.close()
        raise

    return s


def example():
    url = 'https://raw.githubusercontent.com/micropython/micropython-lib/master/LICENSE'
    sock = open_url(url)

    try:
        buffer = bytearray(256)
        while True:
            sz = sock.readinto(buffer)
            if not sz:
                # eof
                break
            print(buffer.decode(), end="")
    finally:
        print("closing socket")
        sock.close()    
