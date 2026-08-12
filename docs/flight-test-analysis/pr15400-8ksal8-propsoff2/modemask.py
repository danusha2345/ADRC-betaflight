#!/usr/bin/env python3
"""Recover the BOXAIRMODE switch state that the default decode throws away.

The blackbox slow frame's `flightModeFlags` field is not runtime flight-mode
flags: the firmware memcpy()s the low 32 bits of `rcModeActivationMask` into
it (blackbox.c, writeSlowFrame path). In that mask BOXARM is bit 0 and
BOXAIRMODE is bit 24 (rc_modes.h). blackbox_decode's default flag rendering
knows only bits 0-9 and silently discards bit 24 - both 1 and 16777217
(0x01000001) print as "ANGLE_MODE", so the default CSV cannot distinguish
airmode-switch on from off.

The same decoder CAN emit the numeric mask: `--unit-flags raw`. This script
decodes each log a second time with that option (into its own cache, so the
default-decode CSVs the other scripts use are never mixed up with these) and
prints the mask transitions on the decoded time base (seconds since the
first saved data frame). get_phases() is imported by spectra.py to split the
switch-cell arms into airmode-off / airmode-on segments.

An earlier version of this script used a hand-written frame parser instead
of the pinned decoder; it mishandled GPS frames and reported phase
boundaries up to tens of milliseconds off, which moved five of the eight
published phase medians at their quoted precision. Everything here now
comes from the same pinned blackbox_decode as the rest of the analysis.

It runs over BOTH corpora. That matters beyond this analysis: the first
props-off corpus (../pr15400-8ksal8-propsoff) was published with its four
"Airmode feature off" cells treated as one regime per arm, BOXAIRMODE being
unrecoverable from the default decode. Recovered here: the BOXAIRMODE box
became active mid-arm in every switch cell of both corpora (the mask proves
the box state, not who or what flipped it - a linked mode or aux programming
would look identical), so those per-arm medians mix a low-authority and a
full-authority phase.
"""
import csv
import glob
import gzip
import os
import subprocess

from common import HERE, OLD, decoder

AIR_BIT = 1 << 24
_CACHE = {}


def ensure_raw_csv(stem, basedir=None):
    """Decode <stem>.bbl.gz with --unit-flags raw into _decoded_rawflags/."""
    basedir = basedir or HERE
    workdir = os.path.join(basedir, '_decoded_rawflags')
    os.makedirs(workdir, exist_ok=True)
    csv_path = os.path.join(workdir, f'{stem}.01.csv')
    if os.path.exists(csv_path):
        return csv_path
    bbl = os.path.join(workdir, f'{stem}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(basedir, f'{stem}.bbl.gz'), 'rb') as fi, \
                open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', '--unit-flags', 'raw', bbl],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return csv_path


def transitions(stem, basedir=None):
    """[(t_seconds_since_first_data_frame, mask)] for each mask change."""
    key = (stem, basedir or HERE)
    if key in _CACHE:
        return _CACHE[key]
    path = ensure_raw_csv(stem, basedir)
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
    _CACHE[key] = out
    return out


def get_phases(stem, span_s, basedir=None):
    """[(t_start, t_end, airmode_bool)] covering [0, span_s]."""
    trans = transitions(stem, basedir)
    phases = []
    cur_t, cur_air = 0.0, bool(trans[0][1] & AIR_BIT) if trans else False
    for t, v in trans:
        air = bool(v & AIR_BIT)
        if air != cur_air and t > cur_t:
            phases.append((cur_t, min(t, span_s), cur_air))
            cur_t, cur_air = t, air
    if cur_t < span_s:
        phases.append((cur_t, span_s, cur_air))
    return phases


def main():
    for title, basedir in [('this corpus', HERE),
                           ('first props-off corpus (../pr15400-8ksal8-propsoff)', OLD)]:
        print(f'== {title}')
        for gz in sorted(glob.glob(os.path.join(basedir, '*.bbl.gz'))):
            stem = os.path.basename(gz)[:-len('.bbl.gz')]
            tr = transitions(stem, basedir)
            txt = ';  '.join(
                f'{t:9.6f}s -> {v}' + (' (+BOXAIRMODE)' if v & AIR_BIT else '')
                for t, v in tr)
            print(f'  {stem:36s} {txt}')
        print()
    print('Times are seconds since the first saved data frame (the decoded CSV\'s')
    print('own zero). mask bit 0 = BOXARM, bit 24 = BOXAIRMODE; 16777217 = both.')
    print('A trailing ...-> 1 -> 0 pair is the airmode box deactivating and the')
    print('arm switch releasing. Logs with no 16777217 entry never had the box')
    print('active: the "on" cells carry FEATURE_AIRMODE in the header feature')
    print('mask instead, and the wc-sweep arms ran with airmode fully off.')


if __name__ == '__main__':
    main()
