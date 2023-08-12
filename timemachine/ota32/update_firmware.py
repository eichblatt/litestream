from ota32 import OTA, open_url
from esp32 import Partition

for p in Partition.find(Partition.TYPE_APP):
    print(p)

print("active partition:", Partition(Partition.RUNNING).info()[4])

# sha_url = "https://raw.githubusercontent.com/eichblatt/litestream/main/MicropythonFirmware/v1.20.0-74-g53cb07357/firmware.sha"
sha_url = (
    "https://raw.githubusercontent.com/eichblatt/litestream/main/MicropythonFirmware/v1.20.0-24-g867e4dd3d/micropython.sha"
)

s = open_url(sha_url)
sha = s.read(1024).split()[0].decode()
s.close()

gc.collect()

# micropy_url = "https://raw.githubusercontent.com/eichblatt/litestream/main/MicropythonFirmware/v1.20.0-74-g53cb07357/firmware.bin"
micropy_url = (
    "https://raw.githubusercontent.com/eichblatt/litestream/main/MicropythonFirmware/v1.20.0-24-g867e4dd3d/micropython.bin"
)

ota = OTA(verbose=True)
ota.ota(micropy_url, sha)
