def vb(n):
    out = bytearray()
    while n > 127:
        out.append((n & 0x7f) | 0x80); n >>= 7
    out.append(n & 0x7f)
    return bytes(out)

HDR = (b"H Product:Blackbox flight data recorder by Nicholas Sherlock\n"
       b"H Data version:2\n"
       b"H Field I name:loopIteration,time\n"
       b"H Field I signed:0,0\n"
       b"H Field I predictor:0,0\n"
       b"H Field I encoding:1,1\n"
       b"H Field S name:flightModeFlags,stateFlags,failsafePhase\n"
       b"H Field S signed:0,0,0\n"
       b"H Field S predictor:0,0,0\n"
       b"H Field S encoding:1,1,1\n")

iframe = lambda it, t: b"I" + vb(it) + vb(t)
sframe = lambda *v: b"S" + b"".join(vb(x) for x in v)
END = b"E" + bytes([255]) + b"End of log\x00"

# flightModeFlags = 0x01000001: BOXARM (bit 0) + BOXAIRMODE (bit 24)
open("modeflags.bbl","wb").write(
    HDR + iframe(0,1000) + sframe(0x01000001, 0, 0) + iframe(1,2000) + END)
