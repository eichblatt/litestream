from mrequests import mrequests as requests
import time


url = "https://archive.org/download/gd82-08-28.sbd.lai.2333.sbefail.shnf/gd82-08-28d1t101.ogg"

starttime = time.ticks_ms()
print(f"starting to download url. {starttime}")
resp = requests.get(url)
print(f"response status {resp.status_code}")
print(f"response len {resp._content_size}")
print(f"starting to move data. {time.ticks_ms()}")
data = resp.content
print(time.ticks_ms() - starttime)
