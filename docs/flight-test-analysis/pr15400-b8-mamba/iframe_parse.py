#!/usr/bin/env python3
"""Читает только I-кадры blackbox: там все поля абсолютные, предикторы тривиальные.
Этого достаточно, чтобы смотреть состояние гейта, коллектив и стик во времени.
Штатный blackbox_decode на логах этого борта зацикливается.

Использование: iframe_parse.py <лог.bbl>
"""
import sys, re

data = open(sys.argv[1], 'rb').read()
start = data.find(b'H Product')
data = data[start:] if start > 0 else data

hdr_end = data.find(b'\nI')
head = data[:hdr_end if hdr_end > 0 else 8000].decode('latin1', 'replace')


def hfield(name):
    m = re.search(r'^H ' + re.escape(name) + r':(.*)$', head, re.M)
    return m.group(1).strip() if m else None


names = hfield('Field I name').split(',')
signs = [int(x) for x in hfield('Field I signed').split(',')]
preds = [int(x) for x in hfield('Field I predictor').split(',')]
encs = [int(x) for x in hfield('Field I encoding').split(',')]
motor_lo = int(hfield('motorOutput').split(',')[0])
motor_hi = int(hfield('motorOutput').split(',')[1])
vbatref = int(hfield('vbatref') or 0)
idx = {n: i for i, n in enumerate(names)}

pos = hdr_end + 1 if hdr_end > 0 else 0


class Eof(Exception):
    pass


def u32(p):
    """unsigned variable byte"""
    v = 0; shift = 0
    while True:
        if p >= len(data):
            raise Eof
        b = data[p]; p += 1
        v |= (b & 0x7F) << shift
        if not (b & 0x80):
            return v, p
        shift += 7
        if shift > 35:
            raise Eof


def s32(p):
    v, p = u32(p)
    return (v >> 1) ^ -(v & 1), p   # zigzag


def read_field(p, enc):
    if enc == 0:
        return s32(p)
    if enc == 1:
        return u32(p)
    if enc == 3:                      # NEG_14BIT
        v, p = u32(p)
        return -((v >> 1) ^ -(v & 1)), p
    if enc == 9:                      # NULL
        return 0, p
    raise Eof                          # прочие кодировки в I-кадрах этого лога не встречаются


rows = []
while pos < len(data) - 4:
    if data[pos] != ord('I'):
        pos += 1
        continue
    p = pos + 1
    vals = []
    try:
        for i in range(len(names)):
            v, p = read_field(p, encs[i])
            if preds[i] == 11:        # MINTHROTTLE
                v += motor_lo
            elif preds[i] == 5:       # MOTOR_0
                v += vals[idx['motor[0]']]
            elif preds[i] == 9:       # VBATREF
                v += vbatref
            vals.append(v)
    except Eof:
        pos += 1
        continue
    t = vals[idx['time']]
    li = vals[idx['loopIteration']]
    # валидация: время монотонно и растёт разумно, итерации тоже
    if rows and not (rows[-1][0] < t < rows[-1][0] + 5_000_000 and li > rows[-1][1]):
        pos += 1
        continue
    if t <= 0 or li < 0:
        pos += 1
        continue
    rows.append((t, li, vals))
    pos = p

print('I-кадров разобрано:', len(rows))
if not rows:
    sys.exit(1)

t0 = rows[0][0]
print('длительность: %.2f с' % ((rows[-1][0] - t0) / 1e6))
print()
print('  t,с   стик%  коллектив%  d7(гейт)  гиро r/p/y      моторы')
prev_gate = None
for t, li, v in rows:
    ts = (t - t0) / 1e6
    stick = (v[idx['rcCommand[3]']] - 1000) / 10.0
    m = [v[idx['motor[%d]' % k]] for k in range(4)]
    coll = (sum(m) / 4 - motor_lo) / (motor_hi - motor_lo) * 100
    d7 = v[idx['debug[7]']]
    gate = d7 > 0
    mark = ''
    if prev_gate is None or gate != prev_gate:
        mark = '   <<< ГЕЙТ ' + ('ОТКРЫТ' if gate else 'закрыт')
        prev_gate = gate
    if mark or len(rows) < 200 or int(ts * 4) % 4 == 0:
        print('%6.3f %6.1f %8.1f %10d  %5d/%5d/%5d  %s%s' % (
            ts, stick, coll, d7,
            v[idx['gyroADC[0]']], v[idx['gyroADC[1]']], v[idx['gyroADC[2]']],
            m, mark))
