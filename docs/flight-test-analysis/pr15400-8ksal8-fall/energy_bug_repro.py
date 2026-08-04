#!/usr/bin/env python3
"""Reproduce blackbox-tools' wrong `energyCumulative` column arithmetic.

Decoder under test: blackbox-tools f832acf9cd. Log: Betaflight 543f1a5ff,
header `currentSensor "-300,457"`, `amperageLatest` present.

The script (a) integrates the amperage column the decoder itself prints, and
(b) re-implements what the decoder does internally, so the printed
`energyCumulative` can be reconstructed exactly and attributed to specific
defects.

Usage: python3 energy_bug_repro.py <decoded.csv>
"""

import sys

import numpy as np

ADCVREF = 33          # parser.c:852
DEF_OFFSET = 0        # parser.c:1289 - used because `currentSensor` is not parsed
DEF_SCALE = 400       # parser.c:1290
US_PER_HOUR = 3.6e9   # battery.c


def load(path):
    with open(path) as f:
        names = [c.strip() for c in f.readline().split(",")]
    cols = [i for i, n in enumerate(names) if "(flags)" not in n]
    d = np.genfromtxt(path, delimiter=",", skip_header=1, usecols=cols, invalid_raise=False)
    idx = {names[c]: k for k, c in enumerate(cols)}
    return (d[:, idx["time (us)"]].astype(np.int64),
            d[:, idx["amperageLatest (A)"]],
            d[:, idx["energyCumulative (mAh)"]])


def decoder_energy(t_us, amps, seed_bug=True, adc_bug=True, int16_bug=True):
    """Re-implementation of currentMeterUpdateMeasured() as the decoder drives it."""
    raw = np.rint(amps * 100).astype(np.int64)                    # centiamps, as logged
    if adc_bug:                                                   # parser.c:860
        mv = (raw * ADCVREF * 100) // 4095
        ma = ((mv - DEF_OFFSET) * 10000) // DEF_SCALE
    else:
        ma = raw * 10                                             # what it should be
    if int16_bug:                                                 # battery.c:48 parameter
        ma = ((ma + 32768) % 65536) - 32768
    energy, last = 0.0, None
    for k in range(len(t_us)):
        # blackbox_decode.c:762 passes the *previous* frame time; it starts at -1
        ct = int(t_us[k - 1]) if k > 0 else (-1 if seed_bug else int(t_us[0]))
        ct32 = ct & 0xFFFFFFFF
        if last is not None and last != 0:                        # battery.c guard
            energy += ma[k] * ((ct32 - last) & 0xFFFFFFFF) / US_PER_HOUR
        last = ct32
    return energy


def main(path):
    t, a, e = load(path)
    truth = float(np.trapezoid(a, t)) / 3_600_000                 # A·us -> mAh
    print(f"{len(t)} samples, {(t[-1]-t[0])/1e6:.3f} s, mean {a.mean():.3f} A")
    print(f"decoder column: first two rows {e[0]:.0f}, {e[1]:.0f} mAh; final {e[-1]:.0f} mAh")
    print(f"integral of the printed amperage column: {truth:.2f} mAh\n")

    print(f"{'variant':46s} {'mAh':>9s}")
    for label, kw in [
        ("full re-implementation (all three defects)", {}),
        ("without the lastFrameTime=-1 seed", dict(seed_bug=False)),
        ("without the legacy ADC conversion", dict(adc_bug=False)),
        ("without the int16_t parameter truncation", dict(int16_bug=False)),
        ("with none of them", dict(seed_bug=False, adc_bug=False, int16_bug=False)),
    ]:
        print(f"{label:46s} {decoder_energy(t, a, **kw):9.1f}")

    raw = np.rint(a * 100).astype(np.int64)
    mv = (raw * ADCVREF * 100) // 4095
    ma = ((mv - DEF_OFFSET) * 10000) // DEF_SCALE
    over = ma > 32767
    print(f"\nworked example, one sample: {a[1]:.2f} A logged as {raw[1]} cA -> "
          f"{mv[1]} mV -> {ma[1]} mA ({ma[1]/(raw[1]*10):.3f}x the true value)")
    print(f"samples whose mis-scaled value overflows int16_t: {over.sum()} "
          f"({100*over.mean():.1f} %), peak {ma.max()} mA -> "
          f"{((ma.max()+32768)%65536)-32768} mA after truncation")
    with_log_consts = ((mv[1] - (-300)) * 10000) // 457
    print(f"using the log's own currentSensor constants (-300, 457) instead of the "
          f"defaults would give {with_log_consts} mA for that sample")


main(sys.argv[1] if len(sys.argv) > 1 else "truncated_log.01.csv")
