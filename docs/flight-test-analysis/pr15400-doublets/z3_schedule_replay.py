#!/usr/bin/env python3
"""ADRC-025 state-frame replay for the saved 2026-07-15 punch/chop corpus.

This is deliberately not a closed-loop flight replay.  It freezes the last
pre-chop z3 sample and asks what the I-equivalent correction -z3/(b0*scale)
does while the logged schedule moves to its settled post-chop scale:

  current  keep z3 absolute (shipping behavior)
  rescale  z3 *= scale_new/scale_old (bumpless I-equivalent correction)
  reset    z3 = 0 (discard the learned disturbance state)

The result isolates the state-frame discontinuity.  It cannot predict the
subsequent gyro trajectory because the log lacks an exact counterfactual
applied motor command and the real craft is closed-loop.
"""
import argparse
import csv
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
LOGS = [
    ('btfl_003_p1_throttle_punch_rebound.01.csv', 'p1', 2000.0),
    ('btfl_006_p1_chops_and_playing.01.csv', 'p1', 2000.0),
    ('btfl_010_p1_playing.01.csv', 'p1', 2000.0),
    ('btfl_009_p2_stock_tune_rolls_n_punches.01.csv', 'p2', 2252.0),
]
FIELDS = [
    'time (us)', 'rcCommand[3]', 'gyroADC[0]', 'gyroADC[1]',
    'debug[5]', 'debug[7]', 'setpoint[0]', 'setpoint[1]',
]


def load(path):
    with open(path, newline='') as fh:
        header = [name.strip() for name in next(csv.reader(fh))]
    index = {name: i for i, name in enumerate(header)}
    missing = [name for name in FIELDS if name not in index]
    if missing:
        raise ValueError(f'{path}: missing {missing}')
    values = np.genfromtxt(
        path, delimiter=',', skip_header=1,
        usecols=[index[name] for name in FIELDS], invalid_raise=False,
    )
    return {name: values[:, i] for i, name in enumerate(FIELDS)}


def event_rows(data, label, b0_pitch):
    t = data['time (us)'] * 1e-6
    t -= t[0]
    fs = 1.0 / np.median(np.diff(t))
    throttle = (data['rcCommand[3]'] - 1000.0) / 10.0
    scale_signed = data['debug[7]'] / 100.0
    z3_pitch = data['debug[5]'] * 16.0
    n = len(t)
    rows = []
    i = 0
    while i < n - int(fs):
        if throttle[i] > 40.0 and scale_signed[i] > 0.0:
            chop = i
            while chop < n - 1 and throttle[chop] >= 15.0:
                chop += 1
            if t[chop] - t[i] < 4.0 and throttle[chop] < 15.0:
                end = min(n, chop + int(0.6 * fs))
                stick = max(
                    np.max(np.abs(data['setpoint[0]'][chop:end])),
                    np.max(np.abs(data['setpoint[1]'][chop:end])),
                )
                if stick < 60.0 and end - chop >= int(0.55 * fs):
                    pre0 = max(i, chop - int(0.03 * fs))
                    pre_scale = float(np.median(scale_signed[pre0:chop]))
                    # Some saved punch trains start the next pulse inside the
                    # 0.6 s rebound window.  The minimum is the actual logged
                    # low point of this release; an end-window median would
                    # silently measure the following punch instead.
                    post_scale = float(np.min(scale_signed[chop:end]))
                    z3_pre = float(np.median(z3_pitch[pre0:chop]))
                    if (pre_scale <= 0.0 or post_scale <= 0.0
                            or pre_scale < 1.2 * post_scale):
                        i = end
                        continue

                    i_pre = -z3_pre / (b0_pitch * pre_scale)
                    i_current = -z3_pre / (b0_pitch * post_scale)
                    i_rescaled = -(z3_pre * post_scale / pre_scale) / (
                        b0_pitch * post_scale)
                    i_reset = 0.0
                    rows.append(dict(
                        profile=label,
                        time_s=float(t[chop]),
                        throttle_max=float(np.max(throttle[i:chop])),
                        scale_pre=pre_scale,
                        scale_post=post_scale,
                        z3_pre=z3_pre,
                        i_pre=i_pre,
                        current_delta=abs(i_current - i_pre),
                        rescale_delta=abs(i_rescaled - i_pre),
                        reset_delta=abs(i_reset - i_pre),
                        rebound_pitch=float(np.max(np.abs(data['gyroADC[1]'][chop:end]))),
                        clipped=bool(np.max(np.abs(data['debug[5]'][pre0:end])) >= 32767),
                    ))
                    i = end
                    continue
            i = chop
        i += 1
    return rows


def summary(rows, label):
    subset = [row for row in rows if label == 'all' or row['profile'] == label]
    print(f'{label}: n={len(subset)}')
    for key in ('scale_pre', 'scale_post', 'current_delta',
                'rescale_delta', 'reset_delta', 'rebound_pitch'):
        values = np.array([row[key] for row in subset])
        print(f'  {key:15s} median={np.median(values):8.3f} max={np.max(values):8.3f}')
    print(f"  clipped events  {sum(row['clipped'] for row in subset)}/{len(subset)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rows = []
    for filename, label, b0_pitch in LOGS:
        rows.extend(event_rows(load(HERE / filename), label, b0_pitch))
    for label in ('p1', 'p2', 'all'):
        summary(rows, label)

    if args.check:
        assert len(rows) == 20, len(rows)
        assert sum(row['profile'] == 'p1' for row in rows) == 16
        assert max(row['rescale_delta'] for row in rows) < 1e-12
        # Guards against silently changing the event/state snapshot contract.
        current = np.median([row['current_delta'] for row in rows])
        reset = np.median([row['reset_delta'] for row in rows])
        assert np.isclose(current, 65.80759322033897, atol=1e-9), current
        assert np.isclose(reset, 34.25308940201303, atol=1e-9), reset
        print('CHECK: PASS')


if __name__ == '__main__':
    main()
