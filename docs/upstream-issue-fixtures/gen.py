import sys

def vb(n):
    out = bytearray()
    while n > 127:
        out.append((n & 0x7f) | 0x80)
        n >>= 7
    out.append(n & 0x7f)
    return bytes(out)

HDR = (b"H Product:Blackbox flight data recorder by Nicholas Sherlock\n"
       b"H Data version:2\n"
       b"H Field I name:loopIteration,time\n"
       b"H Field I signed:0,0\n"
       b"H Field I predictor:0,0\n"
       b"H Field I encoding:1,1\n")

def iframe(it, t):
    return b"I" + vb(it) + vb(t)

def eframe(eid, *vals):
    return b"E" + bytes([eid]) + b"".join(vb(v) for v in vals)

END = b"E" + bytes([255]) + b"End of log\x00"

open("plain.bbl","wb").write(HDR + iframe(0,1000) + iframe(1,2000) + END)

# event 15 (DISARM), reason=2, then a valid I frame
open("event15_disarm.bbl","wb").write(
    HDR + iframe(0,1000) + eframe(15, 2) + iframe(1,2000) + END)

# event 30 (FLIGHTMODE), flags=0x01000001, lastFlags=1, then a valid I frame
open("event30_flightmode.bbl","wb").write(
    HDR + iframe(0,1000) + eframe(30, 0x01000001, 1) + iframe(1,2000) + END)

# event 30 whose payload's first VB byte is 0x49 == 'I': flags=73, lastFlags=1
open("event30_desync.bbl","wb").write(
    HDR + iframe(0,1000) + eframe(30, 73, 1) + iframe(1,2000) + END)

# event 30 whose payload's first VB byte is 0xFF: flags=255 -> "ff 01", lastFlags=1
open("event30_eoftrunc.bbl","wb").write(
    HDR + iframe(0,1000) + eframe(30, 255, 1) + iframe(1,2000) + END)
