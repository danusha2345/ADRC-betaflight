#!/usr/bin/env python3
"""Timeline summary of one decoded Air65 BBL CSV (b10.1 observability fields).

Prints windowed rows: throttle stick, commanded/applied collective, motors, gyro RMS,
dominant roll/pitch frequency, ADRC gate state, z3 (log-scaled) and b0 scale.
"""
import sys
import numpy as np
import csv  # noqa: F401 (used in load)

MOTOR_LO, MOTOR_HI = 48, 2047
CAUSE = {0: "none", 1: "cmd", 2: "gyro", 3: "applied"}


class Frame(dict):
    """Minimal column store: name -> np.ndarray; .t alias; boolean-mask slicing."""
    def __getattr__(self, k):
        return self[k]

    def sel(self, mask):
        f = Frame({k: v[mask] for k, v in self.items()})
        return f


TEXT = {"flightModeFlags", "stateFlags", "failsafePhase"}


def load(path):
    import csv
    with open(path) as fh:
        rd = csv.reader(fh)
        names = [c.strip().split(" ")[0] for c in next(rd)]
        rows = [r for r in rd if len(r) == len(names)]
    cols = list(zip(*rows))
    df = Frame()
    for n, c in zip(names, cols):
        c = [x.strip() for x in c]
        df[n] = np.array(c) if n in TEXT else np.array(c, dtype=float)
    df["t"] = (df["time"] - df["time"][0]) / 1e6
    return df


def state(v):
    v = int(v)
    parts = []
    parts.append("LIFT" if v & 1 else "gate")
    if v & 2:
        parts.append("idle")
    inh = (v >> 2) & 7
    if inh:
        parts.append("inh" + "".join(a for a, b in zip("RPY", (1, 2, 4)) if inh & b))
    parts.append(CAUSE[(v >> 5) & 3])
    return "/".join(parts)


def dom_freq(x, fs):
    x = np.asarray(x, float)
    x = x - x.mean()
    if len(x) < 32 or np.abs(x).max() < 1e-6:
        return 0.0, 0.0
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    m = f >= 3
    i = np.argmax(spec[m])
    return float(f[m][i]), float(spec[m][i] / (spec[m].sum() + 1e-9))


def main(path, win):
    df = load(path)
    dt = np.median(np.diff(df["t"]))
    fs = 1 / dt
    T = df["t"][-1]
    print(f"# {path}\n# samples={len(df["t"])} fs={fs:.0f} Hz duration={T:.2f} s")
    thr_first = df["t"][df["rcCommand[3]"] > 1050]
    print(f"# throttle stick first >1050: {thr_first[0] if len(thr_first) else 'never'}")
    st = df["adrcState"].astype(int)
    lift = np.nonzero((st & 1) == 1)[0]
    if len(lift):
        i0 = lift[0]
        print(f"# gate opened at t={df.t[i0]:.3f} cause={CAUSE[(st[i0] >> 5) & 3]} "
              f"stick={df['rcCommand[3]'][i0]:.0f} cmd={df['adrcCommandedCollective'][i0] / 10:.1f}% "
              f"applied={df['adrcAppliedCollective'][i0] / 10:.1f}%")
    else:
        print("# gate never opened")
    print(f"# gateResetCount min/max {df['adrcGateResetCount'].min()}..{df['adrcGateResetCount'].max()}"
          f"  flightModeFlags uniq {sorted(set(df['flightModeFlags']))[:6]}"
          f"  stateFlags uniq {sorted(set(df['stateFlags']))[:6]}  failsafe uniq {sorted(set(df['failsafePhase']))}")
    print(f"# vbat {df['vbatLatest'].min():.2f}..{df['vbatLatest'].max():.2f} V")
    hdr = ("t0     stick  cmd%  app%  m_mean% m_min% m_max%  gRMS R/P/Y (dps)      |g|max  fR(Hz) fP(Hz)  "
           "z3 R/P/Y     b0sc  state")
    print(hdr)
    edges = np.arange(0, T + win, win)
    for a, b in zip(edges[:-1], edges[1:]):
        w = df.sel((df.t >= a) & (df.t < b))
        if len(w["t"]) < 8:
            continue
        motors = np.column_stack([w[f"motor[{i}]"] for i in range(4)])
        mp = (motors - MOTOR_LO) / (MOTOR_HI - MOTOR_LO) * 100
        g = np.column_stack([w[f"gyroADC[{i}]"] for i in range(3)])
        rms = np.sqrt((g ** 2).mean(axis=0))
        fR, _ = dom_freq(g[:, 0], fs)
        fP, _ = dom_freq(g[:, 1], fs)
        z3 = np.column_stack([w["debug[2]"], w["debug[5]"], w["debug[6]"]])
        z3abs = np.abs(z3).max(axis=0) * np.sign(z3[np.abs(z3).argmax(axis=0), range(3)])
        b0sc = w["debug[7]"]
        stv = w["adrcState"].astype(int)
        s_uniq = "|".join(state(v) for v in sorted(set(stv))[:3])
        print(f"{a:6.2f} {w['rcCommand[3]'].mean():6.0f} {w['adrcCommandedCollective'].mean() / 10:5.1f} "
              f"{w['adrcAppliedCollective'].mean() / 10:5.1f} {mp.mean():7.1f} {mp.min():6.1f} {mp.max():6.1f}  "
              f"{rms[0]:6.1f}/{rms[1]:6.1f}/{rms[2]:6.1f}  {np.abs(g).max():7.0f}  {fR:5.1f}  {fP:5.1f}  "
              f"{z3abs[0]:5.0f}/{z3abs[1]:5.0f}/{z3abs[2]:5.0f}  {b0sc.mean() / 100:5.2f}  {s_uniq}")


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.5)
