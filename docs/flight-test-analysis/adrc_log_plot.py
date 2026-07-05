#!/usr/bin/env python3
"""Plot ADRC blackbox logs: tracking error, observer state, motors, liftoff latch.

Companion to adrc_tune_score.py (which ranks tunes as a table) — this one draws
what actually happened. Needs matplotlib (`pip install matplotlib`); everything
else is stdlib.

Usage:
  1. Decode the .bbl with blackbox_decode (https://github.com/betaflight/blackbox-tools):
       blackbox_decode "Take off, 30-100-200.bbl"
  2. Plot:
       python3 adrc_log_plot.py "Take off, 30-100-200.01.csv"          # one PNG per log
       python3 adrc_log_plot.py takeoff/*.csv --overlay                # + I-term comparison
       python3 adrc_log_plot.py log.csv --window -1:5 --out plots/

Per log you get panels for:
  - tracking error (gyro − setpoint), roll & pitch
  - ADRC I-term (= −z3/b0, the observer's disturbance estimate), roll & pitch
  - motor outputs
  - ESO states z1/z2/z3 + the fix #8 liftoff latch — only when the log was
    recorded with `set debug_mode = ADRC`

The dashed vertical line marks spool-up (mean motor output crossing 15% of its
range). Times on the x-axis are seconds relative to it.
"""
import argparse
import csv
import glob
import os
import re
import sys

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except ImportError:
    sys.exit("matplotlib is required: pip install matplotlib")

# palette (light surface)
SURFACE, PAGE = "#fcfcfb", "#f9f9f7"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, BASE = "#e1e0d9", "#c3c2b7"
S1, S2, S3, S4 = "#2a78d6", "#1baf7a", "#eda100", "#008300"

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 9,
    "axes.edgecolor": BASE, "axes.labelcolor": MUTED,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": PAGE, "axes.facecolor": SURFACE,
    "legend.frameon": False,
})

LW = 1.1        # main series
LW_THIN = 0.8   # noisy / secondary series


def read_log(path):
    """Return {column: list[float]} for the columns we use (missing ones absent)."""
    wanted_prefixes = ("time", "gyroADC[", "setpoint[", "axisI[", "motor[",
                       "debug[", "rcCommand[3")
    with open(path) as f:
        reader = csv.reader(f)
        header = [h.strip() for h in next(reader)]
        take = {i: h for i, h in enumerate(header)
                if h.startswith(wanted_prefixes) or h == "time (us)"}
        cols = {h: [] for h in take.values()}
        for row in reader:
            if len(row) != len(header):
                continue
            try:
                vals = {h: float(row[i]) for i, h in take.items()}
            except ValueError:
                continue
            for h, v in vals.items():
                cols[h].append(v)
    return cols


def tune_label(csv_path):
    base = re.sub(r"\.\d+\.csv$", "", csv_path)
    m = re.search(r"\.(\d+)\.csv$", csv_path)
    flight = int(m.group(1)) if m else 1
    bbl = base + ".bbl"
    if os.path.exists(bbl):
        with open(bbl, "rb") as f:
            heads = re.findall(rb"H rollPID:(\d+),(\d+),(\d+)", f.read())
        if heads:
            p, i, d = heads[min(flight, len(heads)) - 1]
            return f"{p.decode()}/{i.decode()}/{d.decode()}"
    return os.path.basename(csv_path)


def spoolup_time(t, cols):
    motors = [cols.get(f"motor[{i}]") for i in range(4)]
    motors = [m for m in motors if m]
    if not motors:
        return t[0]
    avg = [sum(vals) / len(vals) for vals in zip(*motors)]
    lo, hi = min(avg), max(avg)
    thresh = lo + 0.15 * (hi - lo)
    for i, v in enumerate(avg):
        if v > thresh:
            return t[i]
    return t[0]


def decimate(x, y, max_points=4000):
    step = max(1, len(x) // max_points)
    return x[::step], y[::step]


def has_adrc_debug(cols):
    dbg = cols.get("debug[7]")
    return bool(dbg) and any(v != 0 for v in dbg)


def plot_log(path, out_dir, window):
    cols = read_log(path)
    if "time (us)" not in cols or not cols["time (us)"]:
        print(f"skip {path}: no data")
        return None
    t = [x / 1e6 for x in cols["time (us)"]]
    t0 = spoolup_time(t, cols)
    rel = [x - t0 for x in t]
    lo, hi = window
    sel = [i for i, x in enumerate(rel) if lo <= x <= hi]
    if len(sel) < 50:
        sel = range(len(rel))
    rel = [rel[i] for i in sel]

    def series(name):
        c = cols.get(name)
        return [c[i] for i in sel] if c else None

    debug = has_adrc_debug(cols)
    n_panels = 3 + (1 if debug else 0)
    fig, axes = plt.subplots(n_panels, 1, figsize=(9, 2.1 * n_panels),
                             dpi=150, sharex=True)
    label = tune_label(path)
    fig.suptitle(f"{os.path.basename(path)}   —   tune {label}",
                 color=INK, fontsize=11, x=0.02, ha="left")

    # 1: tracking error
    ax = axes[0]
    for axis_i, (name, c) in enumerate((("roll", S1), ("pitch", S2))):
        g, s = series(f"gyroADC[{axis_i}]"), series(f"setpoint[{axis_i}]")
        if g and s:
            err = [a - b for a, b in zip(g, s)]
            ax.plot(*decimate(rel, err), color=c, lw=LW_THIN, label=name)
    ax.set_ylabel("gyro − setpoint, deg/s")
    ax.legend(labelcolor=INK2, loc="upper right", ncols=2)

    # 2: I-term (−z3/b0)
    ax = axes[1]
    for axis_i, (name, c) in enumerate((("roll", S1), ("pitch", S2))):
        it = series(f"axisI[{axis_i}]")
        if it:
            ax.plot(*decimate(rel, it), color=c, lw=LW, label=name)
    ax.set_ylabel("I-term (−z3/b0)")
    ax.legend(labelcolor=INK2, loc="upper right", ncols=2)

    # 3: motors
    ax = axes[2]
    for m_i, c in enumerate((S1, S2, S3, S4)):
        mv = series(f"motor[{m_i}]")
        if mv:
            ax.plot(*decimate(rel, mv), color=c, lw=LW_THIN, label=f"motor {m_i + 1}")
    ax.set_ylabel("motor output")
    ax.legend(labelcolor=INK2, loc="lower right", ncols=4)

    # 4: ESO states (debug_mode = ADRC only)
    if debug:
        ax = axes[3]
        # z3 (debug[5]) is logged /16 on recent firmware (fix #12) so it doesn't clip int16 —
        # multiply back to put it on the same scale as z1/z2. Harmless x16 on older raw-z3 logs.
        Z3_SCALE = 16
        for idx, name, c, lw, scale in ((3, "pitch z1 (rate)", S1, LW_THIN, 1),
                                        (4, "pitch z2 (accel)", S3, LW_THIN, 1),
                                        (5, "pitch z3 (disturbance)", S2, LW, Z3_SCALE)):
            d = series(f"debug[{idx}]")
            if d:
                if scale != 1:
                    d = [v * scale for v in d]
                ax.plot(*decimate(rel, d), color=c, lw=lw, label=name)
        d7 = series("debug[7]")
        if d7:
            # debug[7] sign is the fix #8 liftoff latch (magnitude = throttle-scaled b0
            # multiplier x100 on recent firmware, fix #10; older logs store ±b0).
            latched = [1.0 if v > 0 else 0.0 for v in d7]
            ax2 = ax.twinx()
            ax2.plot(*decimate(rel, latched), color=INK2, lw=LW_THIN, ls="--",
                     label="liftoff latch")
            ax2.set_ylim(-0.05, 1.4)
            ax2.set_yticks([0, 1])
            ax2.set_yticklabels(["gated", "air"], color=INK2)
            ax2.grid(False)
        ax.set_ylabel("ESO states (pitch)")  # z3 logged /16 on recent fw (fix #12)
        ax.legend(labelcolor=INK2, loc="upper right", ncols=3)

    for ax in axes:
        ax.axvline(0, color=BASE, lw=0.8, ls="--")
    axes[-1].set_xlabel("seconds after spool-up")

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(out_dir,
                       re.sub(r"\.csv$", "", os.path.basename(path)) + ".png")
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")
    return path


def plot_overlay(paths, out_dir, window):
    """Overlay the pitch I-term of several logs — the takeoff-windup comparison."""
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=150)
    palette = [S1, S2, S3, S4, "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
    for n, path in enumerate(paths):
        cols = read_log(path)
        if "time (us)" not in cols or not cols["time (us)"]:
            continue
        t = [x / 1e6 for x in cols["time (us)"]]
        t0 = spoolup_time(t, cols)
        it = cols.get("axisI[1]")
        if not it:
            continue
        rel, vals = zip(*[(x - t0, v) for x, v in zip(t, it)
                          if window[0] <= x - t0 <= window[1]])
        ax.plot(*decimate(list(rel), list(vals)),
                color=palette[n % len(palette)], lw=LW, label=tune_label(path))
    ax.axvline(0, color=BASE, lw=0.8, ls="--")
    ax.set_xlabel("seconds after spool-up")
    ax.set_ylabel("pitch I-term (−z3/b0)")
    ax.set_title("Observer disturbance estimate around takeoff, per log",
                 color=INK, fontsize=11, loc="left")
    ax.legend(labelcolor=INK2, title="tune (wc/wo/D)",
              title_fontproperties={"size": 8})
    fig.tight_layout()
    out = os.path.join(out_dir, "overlay_iterm.png")
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", help="decoded blackbox CSV file(s) or globs")
    ap.add_argument("--out", default=".", help="output directory (default: cwd)")
    ap.add_argument("--window", default="-1:6", metavar="LO:HI",
                    help="time window in seconds relative to spool-up (default -1:6)")
    ap.add_argument("--overlay", action="store_true",
                    help="also draw one figure overlaying the pitch I-term of all logs")
    args = ap.parse_args()

    lo, hi = (float(x) for x in args.window.split(":"))
    paths = sorted({p for pat in args.csv for p in glob.glob(pat)
                    if p.endswith(".csv")})
    if not paths:
        ap.error("no CSV files matched")
    os.makedirs(args.out, exist_ok=True)

    done = [p for p in (plot_log(p, args.out, (lo, hi)) for p in paths) if p]
    if args.overlay and len(done) > 1:
        plot_overlay(done, args.out, (lo, hi))


if __name__ == "__main__":
    main()
