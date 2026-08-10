#!/usr/bin/env python3
"""Side-by-side with ADRC-028, re-derived rather than quoted.

The comparison table in ANALYSIS.md sets this corpus against @dedlike's arm
event. Rather than copy numbers out of that write-up, this recomputes them from
his published log with the same estimators used here, so the two columns are
measured the same way. Craft mass is the one figure that cannot come from a
log; it is his own report and is labelled as such in the text.
"""
import os

import numpy as np

from common import (HERE, headers, load, time_s, gyro, motors, sha256_gz, fs_nominal,
                    pidsum_limits)
from frequency import lomb_peak, welch_peak, peak_spacing

DEDLIKE_DIR = os.path.join(os.path.dirname(HERE), 'pr15400-dedlike-mamba')
DEDLIKE_STEM = 'btfl_003'          # the ADRC arm; 001/002 are the PID references
OURS = ['b8_Airmode_on_ADRC_btfl_001', 'b9_Airmode_on_ADRC_btfl_002']


def describe(stem, basedir=None, label=None):
    h = headers(stem, basedir=basedir)
    d = load(stem, basedir=basedir)
    t = time_s(d)
    fs = fs_nominal(d)
    gu = gyro(d, filtered=False)
    gf = gyro(d)
    m = motors(d)
    peak = np.abs(gf).max(axis=0)

    print(f'\n== {label or stem}')
    print(f'   sha256 {sha256_gz(stem, basedir=basedir)}')
    print(f'   {h.get("Firmware revision", "?")}')
    print(f'   board {h.get("Board information", "?")}, '
          f'pid_type {h.get("pid_type")}, '
          f'wc {h.get("adrcWC")}, wo {h.get("adrcWO")}, b0 {h.get("adrcB0")}')
    lim_rp, lim_y = pidsum_limits(stem, basedir=basedir)
    cellcfg = h.get('vbatcellvoltage', '?').split(',')
    vmax_cell = float(cellcfg[2]) / 100.0
    vref = float(h['vbatref']) / 100.0
    # The same ARITHMETIC as the firmware's autoDetectCellCount()
    # (sensors/battery.c:205-212): integer division by vbatmaxcellvoltage, plus one.
    # It is not a replay of the firmware path, and the difference is worth stating:
    # the firmware divides voltageMeter.displayFiltered, whereas `vbatref` is an
    # unfiltered snapshot taken when logging starts (battery.c:612-615); the firmware
    # then caps at MAX_AUTO_DETECT_CELL_COUNT = 8, which this does not; and a non-zero
    # forceBatteryCellCount would bypass autodetect entirely without appearing in the
    # header. On these three logs none of that changes the answer.
    # Deliberately NOT the maximum decoded sample: on the dedlike log that sample is
    # 18.38 V, which exceeds what four cells can supply at the configured 4.30 V
    # maximum, so it cannot be a valid pack reading. Why it is wrong is not
    # established here - only that it is unusable as an input.
    ncell = int(vref / vmax_cell) + 1
    print(f'   motorOutput {h.get("motorOutput")}, recorded axis limits '
          f'pidsum_limit {lim_rp:.0f} / pidsum_limit_yaw {lim_y:.0f}')
    print(f'   vbatref {vref:.2f} V, vbatcellvoltage {h.get("vbatcellvoltage")}; '
          f'autoDetectCellCount arithmetic int({vref:.2f} / {vmax_cell:.2f}) + 1 '
          f'-> {ncell}S. Three differences from the firmware path: it divides '
          f'voltageMeter.displayFiltered rather than this unfiltered vbatref snapshot, '
          f'and it caps at MAX_AUTO_DETECT_CELL_COUNT = 8 - neither of which changes '
          f'this result; and a non-zero forceBatteryCellCount would bypass autodetect '
          f'entirely, which the header does not record, so that one cannot be checked '
          f'from the log at all.')
    print(f'   {d["_n"]} frames, {t[-1]:.6f} s, mean rate {fs:.2f} Hz, '
          f'vbat {d["vbatLatest (V)"].min():.2f}..{d["vbatLatest (V)"].max():.2f} V')

    # per-axis mixer command and when it first reaches the axis limit
    lim = {0: lim_rp, 1: lim_rp, 2: lim_y}      # recorded, not assumed
    for ax, name in ((0, 'roll'), (1, 'pitch'), (2, 'yaw')):
        keys = [f'axis{k}[{ax}]' for k in 'PIDF' if f'axis{k}[{ax}]' in d]
        missing_d = f'axisD[{ax}]' not in d
        total = sum(d[k] for k in keys)
        hit = np.abs(total) >= lim[ax] - 0.5
        when = f'{t[np.argmax(hit)]*1e3:.3f} ms' if hit.any() else 'never'
        note = ''
        if missing_d:
            note = ('   <-- axisD is ABSENT from this log, so this sum is incomplete and '
                    'the time is not comparable')
        print(f'   {name:5s}: |{"+".join(keys)}| reaches {lim[ax]:.0f} at {when}; '
              f'peak |gyro| {np.abs(gf[ax]).max():.0f} deg/s{note}')

    railed = m.max(axis=0) >= float(h.get('motorOutput', '158,2047').split(',')[1])
    print(f'   first motor at the upper rail: '
          + (f'{t[np.argmax(railed)]*1e3:.3f} ms' if railed.any() else 'never')
          + f' ({int(railed.sum())}/{d["_n"]} frames)')

    idx = np.where(peak > 20)[0]
    win = t >= t[idx[0]] if idx.size else np.ones_like(t, bool)
    if int(win.sum()) >= 64:
        for ax, name in ((0, 'roll'), (1, 'pitch'), (2, 'yaw')):
            x, tw = gu[ax][win], t[win]
            nper = 256 if len(x) >= 256 else 128
            fw, df = welch_peak(tw, x, fs, nper)
            ps = peak_spacing(tw, x)
            print(f'   {name:5s} frequency: Welch/{nper} {fw:.2f} Hz (bin {df:.2f}), '
                  f'Lomb {lomb_peak(tw, x):.2f} Hz, '
                  + (f'peaks {ps[0]:.2f} Hz (n={ps[1]})' if ps else 'peaks inconclusive'))
    else:
        print(f'   frequency: window too short ({int(win.sum())} frames) for these estimators')


def main():
    print('# ADRC-028 (@dedlike) beside this corpus, both measured the same way')
    print('\nMass is not derivable from a log. @dedlike reported 612 g with battery in')
    print('the PR thread on 2026-08-09; that is a report, not a measurement made here.')
    describe(DEDLIKE_STEM, basedir=DEDLIKE_DIR, label=f'@dedlike {DEDLIKE_STEM} (ADRC-028)')
    for stem in OURS:
        describe(stem, label=f'@8ksal8 {stem}')
    print('\nTwo reasons the @dedlike column cannot be compared digit-for-digit:')
    print('  - axisD[2] is absent from his log (blackbox gated it on the legacy D-gain,')
    print('    which the shipped ADRC defaults leave at 0 on yaw), so any yaw command sum')
    print('    computed here is missing its largest term. His write-up reconstructs it;')
    print('    the 87.017 ms figure quoted in ANALYSIS.md comes from there, not from here.')
    print('  - the record is ~0.21 s.')
    print('\nNote the window caveat on the @dedlike side: his record is ~0.21 s, so the')
    print('frequency estimators run on far fewer cycles than ours do and the spread is')
    print('correspondingly wider. Read his figure as the band his write-up gives, not as')
    print('a point estimate comparable digit-for-digit with the 21 Hz here.')


if __name__ == '__main__':
    main()
