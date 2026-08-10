"""Shared loading for the @8ksal8 arming corpus.

Every number quoted in ANALYSIS.md is produced by one of the scripts in this
directory; none is hand-copied. This module only loads data - it makes no
claims of its own.

Blackbox timestamps in these logs are NOT uniformly spaced: I-frames land on a
different cadence than P-frames, and iterations are dropped. Anything spectral
must either resample onto a uniform grid or work from the real timestamps.
`fs_nominal()` exists for reporting only; do not feed it to a uniform-time
estimator without saying so.
"""
import csv
import gzip
import hashlib
import os
import subprocess
import sys

import numpy as np

LOGS = [
    ('001', 'b8_Airmode_on_ADRC_btfl_001', 'b8', 'feature'),
    ('002', 'b9_Airmode_on_ADRC_btfl_002', 'b9', 'feature'),
    ('004', 'b9_Airmode_on_PID_btfl_004', 'b9', 'feature'),
    ('003', 'b9_Airmode_switch_ADRC_btfl_003', 'b9', 'switch'),
    ('005', 'b9_Airmode_switch_PID_btfl_005', 'b9', 'switch'),
]

HERE = os.path.dirname(os.path.abspath(__file__))
Z3_LOG_SCALE = 16.0          # adrc.c logs lrintf(z3 / ADRC_Z3_LOG_SCALE)
DEBUG_CLIP = 32767           # int16 rail of the blackbox debug field


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


def ensure_csv(stem, workdir=None, basedir=None):
    """Decode <stem>.bbl.gz into <workdir>/<stem>.01.csv if not already there."""
    basedir = basedir or HERE
    workdir = workdir or os.environ.get('ARMING_WORKDIR', os.path.join(HERE, '_decoded'))
    os.makedirs(workdir, exist_ok=True)
    csv_path = os.path.join(workdir, f'{stem}.01.csv')
    if os.path.exists(csv_path):
        return csv_path
    bbl = os.path.join(workdir, f'{stem}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(basedir, f'{stem}.bbl.gz'), 'rb') as fi, open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', bbl],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return csv_path


def sha256_gz(stem, basedir=None):
    """SHA-256 of the *decompressed* .bbl, so it can be compared with the raw file."""
    h = hashlib.sha256()
    with gzip.open(os.path.join(basedir or HERE, f'{stem}.bbl.gz'), 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def headers(stem, basedir=None):
    """All 'H key:value' header lines of the log, as a dict."""
    out = {}
    with gzip.open(os.path.join(basedir or HERE, f'{stem}.bbl.gz'), 'rb') as fh:
        blob = fh.read()
    for line in blob.split(b'\n'):
        if line.startswith(b'H ') and b':' in line:
            k, _, v = line[2:].partition(b':')
            try:
                out[k.decode('ascii')] = v.decode('ascii', 'replace').strip()
            except UnicodeDecodeError:
                pass
    return out


def pidsum_limits(stem, basedir=None):
    """Recorded axis command limits, from the header fields blackbox does write.

    The keys are `pidsum_limit` / `pidsum_limit_yaw` (blackbox.c:1694-1695 via
    parameter_names.h). They are recorded, not assumed - an earlier version of
    these scripts looked for camelCase keys, found nothing, and wrongly said the
    limits were absent.
    """
    h = headers(stem, basedir=basedir)
    return float(h['pidsum_limit']), float(h['pidsum_limit_yaw'])


def acc_1g(stem):
    """acc_1G from the header - do not assume 2048."""
    return float(headers(stem).get('acc_1G', '2048'))


def load(stem, workdir=None, basedir=None):
    """Numeric columns of the decoded CSV, keyed by stripped column name."""
    path = ensure_csv(stem, workdir, basedir)
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


def text_column(stem, needle, workdir=None):
    """A non-numeric CSV column (e.g. the decoded mode field), as a list of strings."""
    path = ensure_csv(stem, workdir)
    with open(path, newline='') as fh:
        rows = list(csv.DictReader(fh, skipinitialspace=True))
    key = next((k for k in rows[0] if needle in k), None)
    return [r[key] for r in rows] if key else None


def time_s(d):
    """Time since the first saved frame, in seconds, from the real timestamps."""
    return (d['time (us)'] - d['time (us)'][0]) / 1e6


def fs_nominal(d):
    """Reporting-only sample rate: (N-1) / span. Not a uniform grid."""
    t = d['time (us)']
    return (len(t) - 1) / ((t[-1] - t[0]) / 1e6)


def gyro(d, filtered=True):
    key = 'gyroADC' if filtered else 'gyroUnfilt'
    return np.vstack([d[f'{key}[{i}]'] for i in range(3)])


def motors(d):
    return np.vstack([d[f'motor[{i}]'] for i in range(4)])


def z3_logged(d):
    """z3 as reconstructed from the debug channels, in z3 units, per axis R/P/Y.

    This is the *logged* estimate: the field is lrintf(z3/16) in an int16, so the
    reconstructed value saturates at |z3| = 32767*16. Use clipped_frames() to
    count how often. Note lrintf() follows the current floating-point rounding
    mode (round-to-nearest, ties-to-even by default) - it is lroundf() that
    rounds halves away from zero - so a logged zero bounds |z3| <= 8.
    """
    return {'R': d['debug[2]'] * Z3_LOG_SCALE,
            'P': d['debug[5]'] * Z3_LOG_SCALE,
            'Y': d['debug[6]'] * Z3_LOG_SCALE}


def clipped_frames(d):
    """Frames where the z3 *debug channel* is at its int16 rail.

    This is a telemetry limit (ADRC-029), NOT the controller's internal z3
    clamp, which sits at the recorded pidsum_limit * b0 and is far higher.
    """
    return {k: int(np.sum(np.abs(d[f'debug[{i}]']) >= DEBUG_CLIP))
            for k, i in (('R', 2), ('P', 5), ('Y', 6))}


def gate_open_state(d):
    """debug[7] carries sign(liftoff)*b0ThrottleScale*100: sign is the gate."""
    return d['debug[7]'] > 0


def resample_uniform(t, x, fs):
    """Linear resampling onto a uniform grid - required before any FFT/Welch.

    Returns (t_uniform, x_uniform). Gaps are interpolated across, which is the
    honest failure mode to state rather than pretending the grid was uniform.
    """
    tu = np.arange(t[0], t[-1], 1.0 / fs)
    return tu, np.interp(tu, t, x)
