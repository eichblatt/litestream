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
    marker = FRAME_MARKER
    for i in range(len(data) - 1):
        if ((data[i] << 8) | (data[i + 1])) == marker:
            posns.append(i)
    return posns


def lame_markers(data):
    posns = []
    marker = LAME_MARKER
    for i in range(len(data) - 3):
        if ((data[i] << 24) | (data[i + 1] << 16) | (data[i + 2] << 8) | data[i + 3]) == marker:
            posns.append(i)
    return posns


china_lames = lame_markers(china)
china_frames = frame_markers(china)

china_out = china[china_frames[0] : china_lames[0]]

rider_lames = lame_markers(rider)
rider_frames = frame_markers(rider)
# Ensure that the first frame marker of rider is > the lame_marker (at the beginning of the track).
# rider_frames = [x for x in rider_frames if x > rider_lames[0]]
rider_out = rider[rider_frames[0] :]

out = open("/home/steve/data/joint.mp3", "wb")
out.write(china + rider)
out.close()

joint_out = china_out + rider_out
out2 = open("/home/steve/data/joint2.mp3", "wb")
out2.write(joint_out)
out2.close()

joint_out3 = china + rider_out
out3 = open("/home/steve/data/joint3.mp3", "wb")
out3.write(joint_out3)
out3.close()


china_f = open("/home/steve/data/deadandco2018-07-14.CA14.t02.mp3", "rb")
rider_f = open("/home/steve/data/deadandco2018-07-14.CA14.t03.mp3", "rb")
china = china_f.read()
rider = rider_f.read()
joint_full = china + rider
joint_full_f = open("/home/steve/data/joint_full.mp3", "wb")
joint_full_f.write(joint_full)
joint_full_f.close()

china_f = open("/home/steve/data/deadandco2018-07-14.CA14.t02.ogg", "rb")
rider_f = open("/home/steve/data/deadandco2018-07-14.CA14.t03.ogg", "rb")
china = china_f.read()
rider = rider_f.read()
joint_full = china + rider
joint_full_f = open("/home/steve/data/joint_full.ogg", "wb")
joint_full_f.write(joint_full)
joint_full_f.close()
