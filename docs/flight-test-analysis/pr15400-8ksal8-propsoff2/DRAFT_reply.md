@8ksal8 These 21 arms are the three runs I asked for — the header diffs confirm each run
changes its intended profile variable against your previous set; the CLASSIC run additionally
changes `simplified_pids_mode`, which was needed to make yaw D configurable. Two things rode
along uncontrolled: the measured ELRS link rate differs between some arms, and pack state
differs between groups — both detailed in the write-up. Full analysis, data and scripts:
[`pr15400-8ksal8-propsoff2/`](https://github.com/danusha2345/ADRC-betaflight/tree/master/docs/flight-test-analysis/pr15400-8ksal8-propsoff2).
They kill the two confound explanations for the yaw line, and they also caught me publishing
phase-mixed numbers two days ago — correction below.

## What your three runs established

- **Not the missing yaw D.** Giving CLASSIC a yaw D moves its 30–80 Hz yaw band from 5.98 to
  10.37 deg/s RMS (1.73×) — and the new CLASSIC peak sits at 69–74 Hz, right on top of your
  rotor rates, consistent with rotor vibration through the D term (though proximity alone
  can't rule out a loop contribution). The ADRC gap above it survives: 5.8× in the clean
  feature-on cells.
- **Not dynamic idle.** ADRC moved from 42.68 to 60.26 (1.41×, on a lower pack — not
  attributable), with the peak pinned at 53–54 Hz exactly where it was without dyn idle.
- **The sweep**: amplitude strictly monotonic in yaw wc, 4.8× from wc 80 to wc 120 (3.7×
  within the wc90–120 subset that shares the same measured smoothing config — 62 Hz cutoffs at
  a 166–167 Hz link), while the frequency stays put (47.9–52.0 Hz, not monotonic in wc). And
  in all 13 ADRC arms the liftoff gate never opened and z3 logged exactly zero throughout —
  the disturbance channel never entered the loop, so the oscillation runs through the P/D pair
  (kp = wc², kd = 2wc) acting on the observer's z1/z2 estimates.

What I can NOT claim from this bench: which loop element sets the ~50 Hz. Your rotor rates rise
with wc too (60–68 Hz at wc80 up to 256–275 Hz at wc120 — the oscillation drives the motors),
and a driven motor is itself a vibration source with a path back into the gyro; several higher
rotor orders spend up to ~12 % of some arms within 2 Hz of the line. The mechanical 1× is ruled
out as the carrier, a higher-order contribution is not — and no bench setting can pin the
rotors while the loop is driving them (your earlier dyn-idle-off arms still ran 146–611 Hz),
so this one is on my side to finish with an order-tracking pass over the logs you already
provided, not on yours to fly again.

**One bench run would still add something no analysis can**: a yaw **wo** sweep at fixed wc —
wo was pinned at 125 in this set, so the observer dynamics are the one loop element the sweep
never varied.

## Correction: my "Airmode feature off" numbers were two regimes mixed

Your Airmode switch state is recoverable after all — `blackbox_decode --unit-flags raw` emits
the numeric mode mask, and bit 24 (BOXAIRMODE) is right there; the default rendering just
discards it. Recovered: **in every "switch" arm of both props-off corpora the airmode box went
active mid-arm** (~3–8 s in, several seconds active, off again before disarm — the mask proves
the box state, not what flipped it). So the "feature off = 28.66" I published for ADRC two days
ago mixes a half-authority and a full-authority phase. Split by phase, that cell is **5.20**
airmode-off / **45.53** airmode-on — with airmode genuinely off and static idle, ADRC sat near
the CLASSIC floor. The ratios I published survive (both sides were mixed identically), but the
regime labels were wrong, and the first corpus's ANALYSIS.md now carries a correction note.
This also answers your "mushy at 0 throttle" aside from the other direction: with airmode off
the mixer halves axis authority at zero throttle, and your own arms show the oscillation
needing that authority — 16.70 in the off phases vs 59.77 with the box active, same arms.

The phase split also reconciles the sweep with the dyn-idle cells: those cells' airmode-off
phases ran the same regime as the sweep at yaw wc 96, and their pooled median 16.70 lands
between the wc 90 and wc 100 sweep points.
