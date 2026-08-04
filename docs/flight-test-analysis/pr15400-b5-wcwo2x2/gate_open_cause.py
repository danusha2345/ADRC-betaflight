#!/usr/bin/env python3
"""Which branch opened the ADRC liftoff gate in the wo=150 arms?

debug[7] = (liftoff ? +1 : -1) * b0ThrottleScale * 100, so its sign is the gate
state. The direct branch fires on the published collective >= adrc_liftoff_throttle
(30% in these logs); the gyro branch fires on peak |gyro| > 20 dps sustained 25 ms.

The collective itself is not logged. mean(motor), normalised over the logged
motorOutput range, is its closest available proxy: the symmetric mix cancels in
the mean, leaving collective plus whatever the mixer's own constrain added.
Report both, plus the gyro condition, around the sign flip.

The gyro condition is checked against the blackbox gyroADC[] columns: the
detector reads gyro.gyroADCf (the filtered rate), and blackbox.c logs exactly
that as gyroADC[] (gyroUnfilt[] is the raw pre-filter signal, a different
series).
"""
import csv
import sys

MOTOR_LOW, MOTOR_HIGH = 48.0, 2047.0
LIFTOFF_THROTTLE = 0.30
GYRO_DPS = 20.0
HOLD_S = 0.025
# The detector runs once per PID iteration, while blackbox here saved every second one. Runs are
# therefore reported in saved samples AND converted to iterations, which is what the hold counts.
LOOPTIME_S = 312e-6

COLS = ["time (us)", "rcCommand[3]", "debug[7]",
        "gyroADC[0]", "gyroADC[1]", "gyroADC[2]",
        "motor[0]", "motor[1]", "motor[2]", "motor[3]"]


def load(fname):
    with open(fname) as f:
        r = csv.reader(f)
        hdr = [h.strip() for h in next(r)]
        idx = [hdr.index(c) for c in COLS]
        out = []
        for row in r:
            try:
                out.append([float(row[i]) for i in idx])
            except (ValueError, IndexError):
                continue
    return out


def longest_gyro_run(rows, upto):
    """Longest run of consecutive samples with peak |gyro| above GYRO_DPS, before index `upto`.

    This is the quantity the gyro branch actually needs to satisfy: its hold is continuous, so a
    run shorter than adrc_liftoff_hold_ms cannot open the gate no matter how many such runs occur.
    """
    run = best = 0
    for r in rows[:upto]:
        peak = max(abs(r[3]), abs(r[4]), abs(r[5]))
        run = run + 1 if peak > GYRO_DPS else 0
        best = max(best, run)
    return best


def main(fname):
    rows = load(fname)
    if not rows:
        print(f"{fname}: no rows")
        return
    dt = (rows[1][0] - rows[0][0]) / 1e6
    import math
    need = math.ceil(HOLD_S / dt)                  # in saved samples
    need_iters = math.ceil(HOLD_S / LOOPTIME_S)    # in PID iterations - what the gate actually counts
    stride = max(1, int(round(dt / LOOPTIME_S)))   # iterations per saved sample
    # First sample with the gate open.
    open_i = next((i for i, r in enumerate(rows) if r[2] > 0), None)
    if open_i is None:
        best = longest_gyro_run(rows, len(rows))
        print(f"\n=== {fname}: gate never opens in the saved record ({len(rows)} samples)")
        print(f"  longest gyro>{GYRO_DPS:.0f} dps run over the whole record: {best} samples "
              f"({best*dt*1000:.1f} ms) = at most {best*stride + (stride-1)} consecutive PID "
              f"iterations even crediting every unsaved neighbour, against the {need_iters} the "
              f"hold needs")
        return
    t0 = rows[open_i][0]
    print(f"\n=== {fname}: gate opens at sample {open_i}, t = {t0/1e6:.3f} s "
          f"(record starts {rows[0][0]/1e6:.3f} s, {len(rows)} samples)")
    if open_i == 0:
        print("  !! the record's FIRST sample already has the gate open - "
              "the opening itself is outside the log")

    lo = max(0, open_i - 12)
    print("  idx    dt_ms  rc[3]   mean_motor%  peak|gyro|  gate")
    for i in range(lo, min(len(rows), open_i + 4)):
        r = rows[i]
        mean_motor = sum(r[6:10]) / 4.0
        pct = 100.0 * (mean_motor - MOTOR_LOW) / (MOTOR_HIGH - MOTOR_LOW)
        peak = max(abs(r[3]), abs(r[4]), abs(r[5]))
        mark = "<== OPEN" if i == open_i else ""
        print(f"  {i:5d} {(r[0]-t0)/1000.0:8.2f} {r[1]:7.0f} "
              f"{pct:11.1f} {peak:11.1f}   {'OPEN' if r[2] > 0 else 'shut'} {mark}")

    # Could the gyro branch have opened it? Two readings: the hold window immediately before the
    # open, and the longest continuous run anywhere before it (the published table's column).
    best = longest_gyro_run(rows, open_i)
    print(f"  longest gyro>{GYRO_DPS:.0f} dps run before the open: {best} samples "
          f"({best*dt*1000:.1f} ms) = at most {best*stride + (stride-1)} consecutive PID "
          f"iterations even crediting every unsaved neighbour, against the {need_iters} the hold "
          f"needs => gyro path "
          f"{'COULD fire' if best*stride + (stride-1) >= need_iters else 'DID NOT fire'}")
    window = rows[max(0, open_i - need):open_i]
    if window:
        sustained = all(max(abs(r[3]), abs(r[4]), abs(r[5])) > GYRO_DPS for r in window)
        peaks = [max(abs(r[3]), abs(r[4]), abs(r[5])) for r in window]
        print(f"  gyro hold: needs {need} samples > {GYRO_DPS} dps "
              f"({HOLD_S*1000:.0f} ms at {dt*1e6:.0f} us); "
              f"satisfied={sustained}, min peak in window {min(peaks):.1f} dps")
    prev = rows[open_i - 1] if open_i else None
    if prev is not None:
        pm = 100.0 * (sum(prev[6:10]) / 4.0 - MOTOR_LOW) / (MOTOR_HIGH - MOTOR_LOW)
        cm = 100.0 * (sum(rows[open_i][6:10]) / 4.0 - MOTOR_LOW) / (MOTOR_HIGH - MOTOR_LOW)
        print(f"  collective proxy: {pm:.1f}% -> {cm:.1f}% "
              f"(threshold {LIFTOFF_THROTTLE*100:.0f}%) => direct branch "
              f"{'CANNOT be excluded' if cm >= LIFTOFF_THROTTLE*100 or pm >= LIFTOFF_THROTTLE*100 else 'excluded at these samples'}")


if __name__ == "__main__":
    for f in sys.argv[1:]:
        main(f)
