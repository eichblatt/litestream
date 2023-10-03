# Splice together 2 mp3 files, and also removing tags, etc.
china_f = open("/home/steve/data/deadandco2018-07-14.CA14.t02.mp3", "rb")
rider_f = open("/home/steve/data/deadandco2018-07-14.CA14.t03.mp3", "rb")

china_f.seek(-3 * 15188433 // 100, 2)  # last 3% of china
china = china_f.read()

rider = rider_f.read(520876)


FRAME_MARKER = 0xFFFB
LAME_MARKER = 0x4C414D45


def frame_markers(data):
    posns = []
    marker = 0xFFBB
    for i in range(len(data) - 1):
        if data[i] << 8 | data[i + 1] == marker:
            posns.append(i)
    return posns


def lame_markers(data):
    posns = []
    marker = 0x4C414D45
    for i in range(len(data) - 3):
        if data[i] << 24 | data[i + 1] << 16 | data[i + 2] << 8 | data[i + 3] == marker:
            posns.append(i)
    return posns


china_out = china[frame_markers(china)[0] : lame_markers(china)[0]]

# I have ensured that the first frame marker of rider is > the lame_marker (at the beginning of the track).
rider_out = rider[frame_markers(rider)[0] :]

out = open("/home/steve/data/joint.mp3", "wb")
out.write(china + rider)
out.close()

joint_out = china[:402436] + rider_out
out2 = open("/home/steve/data/joint2.mp3", "wb")
out2.write(joint_out)
out2.close()
