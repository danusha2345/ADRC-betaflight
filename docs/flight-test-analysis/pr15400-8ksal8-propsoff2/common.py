"""Shared loading for the second @8ksal8 props-off corpus (2026-08-11).

Twenty-one bench arms in three requested runs, each a paired PROFILE change
against the first props-off corpus (../pr15400-8ksal8-propsoff, 2026-08-10,
same firmware 919116fed, same craft):

  - CLASSIC with yaw D = 26 where the old CLASSIC cells had yaw D = 0
    (plus simplified_pids_mode 2 -> 1, needed to set it);
  - the flown ADRC tune with dyn_idle_min_rpm = 30 where the old ADRC cells
    had 0;
  - a yaw-only wc sweep, 80/90/100/110/120, at fixed wo = 125 and
    b0 = 5848 (dyn idle 30, Airmode feature off) - the sweep's only profile
    variable is yaw wc.

Profile-identical is not runtime-identical: the measured RC-smoothing state
follows the ELRS link rate and differs between arms, and pack state differs
between groups - provenance.py prints both per arm/group.

Every number quoted in ANALYSIS.md is produced by one of the scripts in this
directory; none is hand-copied. This module only loads data - it makes no
claims of its own.

Blackbox timestamps are NOT uniformly spaced; anything spectral must resample
onto a uniform grid or work from the real timestamps. `fs_nominal()` exists
for reporting only.
"""
import csv
import gzip
import hashlib
import os
import subprocess
import sys

import numpy as np

# (group label, controller, Airmode feature, stem prefix, log stems)
GROUPS = [
    ('CLASSIC yawD=26, Airmode on',  'CLASSIC', 'on',  'classicYD_on',
     ['btfl_001', 'btfl_002', 'btfl_003', 'btfl_004']),
    ('CLASSIC yawD=26, Airmode off', 'CLASSIC', 'off', 'classicYD_sw',
     ['btfl_005', 'btfl_006', 'btfl_007', 'btfl_008']),
    ('ADRC dynIdle=30, Airmode on',  'ADRC',    'on',  'dynidle_on',
     ['btfl_009', 'btfl_010', 'btfl_011', 'btfl_012']),
    ('ADRC dynIdle=30, Airmode off', 'ADRC',    'off', 'dynidle_sw',
     ['btfl_013', 'btfl_014', 'btfl_015', 'btfl_016']),
]
LOGS = [(g, f'{sub}_{stem}', ctrl, air)
        for g, ctrl, air, sub, stems in GROUPS for stem in stems]

# yaw wc sweep: (yaw wc from the header, stem). dyn idle 30, Airmode feature
# off, wo/b0 fixed - so the only within-sweep variable is yaw wc.
SWEEP = [(80,  'sweep_yaw_wc80_btfl_001'),
         (90,  'sweep_yaw_wc90_btfl_002'),
         (100, 'sweep_yaw_wc100_btfl_003'),
         (110, 'sweep_yaw_wc110_btfl_004'),
         (120, 'sweep_yaw_wc120_btfl_005')]

ALL_STEMS = [stem for _, stem, _, _ in LOGS] + [s for _, s in SWEEP]

ERPM_SCALE = 100.0        # blackbox logs eRPM/100 (blackbox.c:292)
DEBUG_CLIP = 32767        # int16 rail of the blackbox debug field

HERE = os.path.dirname(os.path.abspath(__file__))
# The first props-off corpus, for the paired comparisons. A separate decode
# cache per corpus is essential: a shared cache once served the wrong log for
# a stem that existed in two corpora.
OLD = os.path.join(os.path.dirname(HERE), 'pr15400-8ksal8-propsoff')


def decoder():
    """Path to blackbox_decode; override with BLACKBOX_DECODE."""
    p = os.environ.get('BLACKBOX_DECODE')
    if p:
        return p
    from shutil import which
    p = which('blackbox_decode')
    if p:
        return p
    sys.exit('blackbox_decode not found; set BLACKBOX_DECODE=/path/to/blackbox_decode')


def ensure_csv(stem, basedir=None):
    """Decode <basedir>/<stem>.bbl.gz into <basedir>/_decoded/<stem>.01.csv."""
    basedir = basedir or HERE
    workdir = os.path.join(basedir, '_decoded')
    os.makedirs(workdir, exist_ok=True)
    csv_path = os.path.join(workdir, f'{stem}.01.csv')
    if os.path.exists(csv_path):
        return csv_path
    bbl = os.path.join(workdir, f'{stem}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(basedir, f'{stem}.bbl.gz'), 'rb') as fi, \
                open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', bbl],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return csv_path


def sha256_gz(stem, basedir=None):
    """SHA-256 of the *decompressed* .bbl, comparable with the raw file."""
    h = hashlib.sha256()
    with gzip.open(os.path.join(basedir or HERE, f'{stem}.bbl.gz'), 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def headers(stem, basedir=None):
    """All 'H key:value' header lines of the log, as a dict.

    Only the contiguous H-block at the start is scanned; searching the whole
    binary once fabricated keys out of frame data in an earlier corpus.
    """
    out = {}
    with gzip.open(os.path.join(basedir or HERE, f'{stem}.bbl.gz'), 'rb') as fh:
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


def z3_scale(stem, basedir=None):
    """z3 debug divisor: the adrc_z3_log_scale header line if present (b10+),
    else the legacy fixed 16 (ADRC-029). Every log here is b9, so 16 - but
    read it anyway so the script survives a b10 re-run."""
    return float(headers(stem, basedir=basedir).get('adrc_z3_log_scale', '16'))


def load(stem, basedir=None):
    """Numeric columns of the decoded CSV, keyed by stripped column name."""
    path = ensure_csv(stem, basedir)
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


def time_s(d):
    """Time since the first saved frame, in seconds, from the real timestamps."""
    return (d['time (us)'] - d['time (us)'][0]) / 1e6


def fs_nominal(d):
    """Reporting-only sample rate: (N-1) / span. Not a uniform grid."""
    t = d['time (us)']
    return (len(t) - 1) / ((t[-1] - t[0]) / 1e6)


def resample_uniform(t, x, fs):
    """Linear resampling onto a uniform grid - required before any FFT/Welch.
    Gaps are interpolated across; that is the honest failure mode to state."""
    tu = np.arange(t[0], t[-1], 1.0 / fs)
    return tu, np.interp(tu, t, x)


def gyro(d, filtered=True):
    key = 'gyroADC' if filtered else 'gyroUnfilt'
    return np.vstack([d[f'{key}[{i}]'] for i in range(3)])


def motors(d):
    return np.vstack([d[f'motor[{i}]'] for i in range(4)])


def rotor_hz_per_motor(d, stem, basedir=None):
    """Median mechanical rotor frequency of EACH motor, Hz, from logged eRPM.
    Pooling four motors into one median hid a near-coincidence once."""
    poles = float(headers(stem, basedir=basedir).get('motor_poles', '12'))
    e = np.vstack([d[f'eRPM[{i}]'] for i in range(4)]) * ERPM_SCALE
    return [float(np.median(e[i]) / (poles / 2.0) / 60.0) for i in range(4)]


def alias_of(freq, fs):
    """Where a real frequency lands in a spectrum sampled at fs (folded)."""
    f = freq % fs
    return fs - f if f > fs / 2.0 else f
