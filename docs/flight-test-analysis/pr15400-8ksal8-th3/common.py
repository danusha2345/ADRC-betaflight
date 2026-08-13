"""Shared loading for the @8ksal8 TH3 Freestyle corpus (2026-08-13).

Six flight logs on a rebuilt Emax Tinyhawk III+ Freestyle (2.5", 1204.5
5022KV, F7X2, 8k gyro / 4k PID): a "flight" and an ANGLE-mode "wobble" log
for each of 2s / 3s / 4s packs, all on wo = 150 and per-pack b0 scaled by
the tester's watt-hour rule. The tester's archive also contains eight
tuning arms (btfl_011..018) documenting how he arrived at the tune; they
are not carried here and nothing below is claimed about them.

Every number quoted in ANALYSIS.md is produced by one of the scripts in
this directory; none is hand-copied.
"""
import csv
import gzip
import hashlib
import os
import subprocess
import sys

import numpy as np

# (pack, role, stem)
LOGS = [
    ('2s', 'flight', 'TH3_Freestyle_2s_flight_btfl_001'),
    ('2s', 'wobble', 'TH3_Freestyle_2s_wobble_btfl_019'),
    ('3s', 'flight', 'TH3_Freestyle_3s_flight_btfl_001'),
    ('3s', 'wobble', 'TH3_Freestyle_3s_wobble_btfl_010'),
    ('4s', 'flight', 'TH3_Freestyle_4s_flight_btfl_001'),
    ('4s', 'wobble', 'TH3_Freestyle_4s_wobble_btfl_010'),
]
STEMS = [s for _, _, s in LOGS]

HERE = os.path.dirname(os.path.abspath(__file__))
DEBUG_CLIP = 32767


def decoder():
    p = os.environ.get('BLACKBOX_DECODE')
    if p:
        return p
    from shutil import which
    p = which('blackbox_decode')
    if p:
        return p
    sys.exit('blackbox_decode not found; set BLACKBOX_DECODE=/path/to/blackbox_decode')


def _decode(stem, workdir, extra=()):
    os.makedirs(workdir, exist_ok=True)
    csv_path = os.path.join(workdir, f'{stem}.01.csv')
    if os.path.exists(csv_path):
        return csv_path
    bbl = os.path.join(workdir, f'{stem}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fi, \
                open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', *extra, bbl],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return csv_path


def ensure_csv(stem):
    return _decode(stem, os.path.join(HERE, '_decoded'))


def ensure_raw_csv(stem):
    """Second decode with the numeric mode mask (--unit-flags raw)."""
    return _decode(stem, os.path.join(HERE, '_decoded_rawflags'),
                   extra=('--unit-flags', 'raw'))


def sha256_gz(stem):
    h = hashlib.sha256()
    with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def headers(stem):
    out = {}
    with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fh:
        blob = fh.read()
    for line in blob.split(b'\n'):
        if not line.startswith(b'H '):
            break
        if b':' in line:
            k, _, v = line[2:].partition(b':')
            try:
                out[k.decode('ascii')] = v.decode('ascii', 'replace').strip()
            except UnicodeDecodeError:
                pass
    return out


def load(stem):
    path = ensure_csv(stem)
    with open(path, newline='') as fh:
        rows = list(csv.DictReader(fh, skipinitialspace=True))
    data = {}
    for key in rows[0]:
        name = key.strip()
        try:
            data[name] = np.array([float(r[key]) for r in rows])
        except (ValueError, TypeError):
            continue
    data['_n'] = len(rows)
    return data


def mask_transitions(stem):
    """[(t_s_since_first_frame, mask)] from the numeric mode-mask decode."""
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


def time_s(d):
    return (d['time (us)'] - d['time (us)'][0]) / 1e6


def motors(d):
    return np.vstack([d[f'motor[{i}]'] for i in range(4)])
