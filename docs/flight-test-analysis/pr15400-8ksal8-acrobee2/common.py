"""Shared loading for the @8ksal8 AcroBee75 filter-ladder corpus (2026-08-15).

Seven short test arms on the same AcroBee75 and the same ADRC tune as the
neighbouring pr15400-8ksal8-acrobee campaign (wc 100/100/50 over
wo 120/120/80, b0 3923/2353/1569): the gyro filter stages toggled one at a
time and in combination. Exactly three intended profile keys change across
the ladder (overview.py checks the union): gyro_lpf1_dyn_hz (250,500 when
on), gyro_lpf2_static_hz (500 when on) and rpm_filter_harmonics (1 when
on); the remaining per-arm differences are measurement/runtime keys
(vbatref and the two rc_smoothing_* values, printed per arm by
overview.py - the LP2 arm ran at a different measured link rate). No
dynamic notch, no yaw_lowpass and no dterm filters are configured in any
of them - fewer stages in play than in the first pair.
Each arm contains one BOXAIRMODE activation on a fresh-ish pack - the
regime the first pair's report was about.

Every AcroBee-derived number quoted in ANALYSIS.md is produced by one of
the scripts in this directory; cross-campaign quotes are marked as such in
ANALYSIS.md and are not re-derived here.
"""
import csv
import gzip
import hashlib
import os
import subprocess
import sys

import numpy as np

# (label: which stages are on, stem)
LOGS = [
    ('off',         'All_Filters_off_btfl_009'),
    ('LP1',         'LowPass1_on_btfl_001'),
    ('LP2',         'LowPass2_on_btfl_002'),
    ('RPM',         'RPM_on_btfl_003'),
    ('LP1+RPM',     'LowPass1_RPM_on_btfl_004'),
    ('LP2+RPM',     'LowPass2_RPM_on_btfl_007'),
    ('LP1+LP2+RPM', 'LowPass1_2_RPM_on_btfl_008'),
]
STEMS = [s for _, s in LOGS]

HERE = os.path.dirname(os.path.abspath(__file__))
DEBUG_CLIP = 32767
AIR_BIT = 1 << 24


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


def airmode_windows(stem, span_s):
    """[(t_start, t_end)] where the BOXAIRMODE box was active."""
    out = []
    cur = None
    for t, v in mask_transitions(stem):
        if (v & AIR_BIT) and cur is None:
            cur = t
        elif not (v & AIR_BIT) and cur is not None:
            out.append((cur, t))
            cur = None
    if cur is not None:
        out.append((cur, span_s))
    return out


def time_s(d):
    return (d['time (us)'] - d['time (us)'][0]) / 1e6


def motors(d):
    return np.vstack([d[f'motor[{i}]'] for i in range(4)])
