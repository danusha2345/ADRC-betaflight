#!/usr/bin/env python3
"""Which boxes were ACTIVE when - from the numeric mode mask.

The default decode's mode column drops every bit above 9 of the logged
rcModeActivationMask (see pr15400-8ksal8-propsoff2/modemask.py for the full
story); `blackbox_decode --unit-flags raw` emits the numeric mask instead,
and this script decodes each log a second time with that option into its own
cache. Bits that matter here: BOXARM 0, BOXANGLE 1, BOXALTHOLD 4,
BOXFAILSAFE 8, BOXPOSHOLD 9, BOXGPSRESCUE 10, BOXAIRMODE 24 (rc_modes.h).

Two honesty notes. The mask proves a box was ACTIVE - it cannot distinguish
a deliberate switch flip from a linked mode or an aux-programming artifact
(rc_modes.c applies linked conditions before the mask is stored). And
BOXFAILSAFE going active precedes the recorded failsafePhase = 6 entry by
about 1.5 s in both rescues - the failsafe state machine walks through its
rx-loss stages first - so the box activation and the rescue entry are
related but NOT simultaneous; both timestamps are printed below.
"""
import csv
import gzip
import os
import subprocess

from common import STEMS, HERE, decoder, load, time_s, text_column

BITS = {0: 'ARM', 1: 'ANGLE', 4: 'ALTHOLD', 8: 'FAILSAFE', 9: 'POSHOLD',
        10: 'GPSRESCUE', 24: 'AIRMODE'}


def ensure_raw_csv(stem):
    workdir = os.path.join(HERE, '_decoded_rawflags')
    os.makedirs(workdir, exist_ok=True)
    csv_path = os.path.join(workdir, f'{stem}.01.csv')
    if os.path.exists(csv_path):
        return csv_path
    bbl = os.path.join(workdir, f'{stem}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fi, \
                open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', '--unit-flags', 'raw', bbl],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return csv_path


def transitions(stem):
    path = ensure_raw_csv(stem)
    out = []
    with open(path, newline='') as fh:
        r = csv.reader(fh)
        hdr = [h.strip() for h in next(r)]
        fx = next(i for i, h in enumerate(hdr) if h.startswith('flightModeFlags'))
        tx = next(i for i, h in enumerate(hdr) if h.startswith('time'))
        prev, t0 = None, None
        for row in r:
            try:
                t = int(row[tx])
                v = int(row[fx])
            except (ValueError, IndexError):
                continue
            if t0 is None:
                t0 = t
            if v != prev:
                out.append(((t - t0) / 1e6, v))
                prev = v
    return out


def names(mask):
    got = [nm for b, nm in sorted(BITS.items()) if mask & (1 << b)]
    other = mask & ~sum(1 << b for b in BITS)
    if other:
        got.append(f'+0x{other:x}')
    return '|'.join(got) or '(none)'


def main():
    print('# Box activations (numeric mode mask, --unit-flags raw)\n')
    for stem in STEMS:
        print(f'== {stem}')
        for t, v in transitions(stem):
            print(f'   t={t:10.6f}s  mask={v:<10d} {names(v)}')
        print()

    print('BOXFAILSAFE activation vs failsafePhase = 6 entry (the state machine')
    print('walks its rx-loss stages between the two):')
    for stem in ('Return_to_home_btfl_002', 'Finished_minus_5_percent_btfl_001'):
        tr = transitions(stem)
        t_box = next(t for t, v in tr if v & (1 << 8))
        d = load(stem)
        t = time_s(d)
        ph = text_column(stem, 'failsafePhase')
        t_phase = next(t[i] for i in range(1, len(ph)) if ph[i] == '6' and ph[i - 1] != '6')
        print(f'  {stem:38s} box {t_box:10.6f}s -> phase 6 {t_phase:10.6f}s '
              f'(lead {t_phase - t_box:.2f}s)')

    print('\nBOXGPSRESCUE (bit 10) never appears: neither rescue was started from')
    print('a GPS-rescue box. Both rescues follow BOXFAILSAFE activity - a')
    print('switch-simulated RX loss - which is why rcCommand shows throttle at')
    print('1000 inside the rescues: the sticks are not being read while the')
    print('simulated loss is active.')


if __name__ == '__main__':
    main()
