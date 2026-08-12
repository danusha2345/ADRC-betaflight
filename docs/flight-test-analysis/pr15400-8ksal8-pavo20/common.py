"""Shared loading for the @8ksal8 Pavo20 Pro II corpus (2026-08-11).

Three flight logs on the retuned Pavo20 Pro II (F405, 8k gyro / 4k PID,
3S): the finished-tune flight, a GPS-rescue / failsafe flight, and a log
the tester named "wobble". Every number quoted in ANALYSIS.md is produced
by one of the scripts in this directory; none is hand-copied.
"""
import csv
import gzip
import hashlib
import os
import subprocess
import sys

import numpy as np

STEMS = ['Finished_minus_5_percent_btfl_001', 'Return_to_home_btfl_002',
         'wobble_btfl_036']

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


def ensure_csv(stem):
    workdir = os.path.join(HERE, '_decoded')
    os.makedirs(workdir, exist_ok=True)
    csv_path = os.path.join(workdir, f'{stem}.01.csv')
    if os.path.exists(csv_path):
        return csv_path
    bbl = os.path.join(workdir, f'{stem}.bbl')
    if not os.path.exists(bbl):
        with gzip.open(os.path.join(HERE, f'{stem}.bbl.gz'), 'rb') as fi, \
                open(bbl, 'wb') as fo:
            fo.write(fi.read())
    subprocess.run([decoder(), '--index', '1', bbl],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return csv_path


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


def text_column(stem, needle):
    path = ensure_csv(stem)
    with open(path, newline='') as fh:
        rows = list(csv.DictReader(fh, skipinitialspace=True))
    key = next((k for k in rows[0] if needle in k), None)
    return [r[key].strip() for r in rows] if key else None


def time_s(d):
    return (d['time (us)'] - d['time (us)'][0]) / 1e6


def fs_nominal(d):
    t = d['time (us)']
    return (len(t) - 1) / ((t[-1] - t[0]) / 1e6)


def motors(d):
    return np.vstack([d[f'motor[{i}]'] for i in range(4)])
