# ADRC loop gain — what the flight logs of PR betaflight#15400 say (Sept 2026)

One page that replaces eight analysis addenda. Everything below comes from tester Blackbox logs (Air65, TH3+ 2.5",
AOS 3.5, Mamba 5") on the b10.1 → b11-exp5 builds; the per-log tables, logs and scripts are in
`docs/flight-test-analysis/pr15400-8ksal8-airmode-rxsmoothing/ANALYSIS.md` (addenda 3 → 8) and the folders next to it.

## 1. The one number

The ADRC rate loop is a virtual PD on the observer state, divided by the plant-gain estimate:

```
P = wc² · (setpoint − z1) / b0        D = 2 · wc · z2 / b0        I = z3 / b0
```

So every tuning knob acts through two numbers, the **loop gains**

```
G_P = wc² / b0            G_D = 2 · wc · wo / b0   (the D path at the observer's derivative peak, ω = √3·wo)
```

`wc`, `wo`, `b0`, the throttle→b0 schedule, `adrc_hover_throttle`, `thrust_linear` and the per-axis b0 split all
change these two numbers and nothing else that the logs can see. Two tunes with the same G_P/G_D behave the same
even if their `wc/wo/b0` look different.

## 2. The knee (in flight)

Above a craft-specific `wo`, the motors carry a line at **≈ 0.5–0.7 × wo** (Hz per rad/s: 55–61 Hz at wo 100–110 on
the Air65, 61–64 Hz at wo 90 on the TH3+, 65 Hz at wo 100 on the AOS 3.5). Its per-motor RMS grows slowly, then by
×8–10 within ~10 % of `wo`:

| craft / law | quiet | knee |
|---|---|---|
| Air65 SQRT, hover 29 | 88/100: 1.0 % · 97/110: 2 % | 106/120: 16 % |
| Air65 FIXED | 95/106: 1.3 % | 97/108: 3 % · 99/110: 8.7 % |
| AOS 3.5 FIXED, TL 60 | 90/100: 1.0 % | (TL 95 = ×1.9 gain: 9.6 %) |

Tracking (|setpoint − gyro| median 2–5 °/s) does **not** change across the knee — the line is the only warning,
and it is in the motors, not in the gyro (1–3 °/s at the line frequency). Cool motors prove nothing; on the Air65
the same numbers came with hot packs.

**Rule: pick `wo` under the knee for your craft (read the motor spectrum, not the feel), then `wc ≈ 0.9 · wo`.**

## 3. Everything that is secretly a gain multiplier

| knob | what it really does | measured |
|---|---|---|
| `thrust_linear` | multiplies every controller output by the slope of the TL curve at the operating point — hover sits at motor ≈ 0.34 *after* the curve | TL 60: ×1.36 at hover, ×1.6 at 20 % motor · TL 95: ×1.9 / ×2.3 · TL 100: ×2.0 / ×2.4 |
| `adrc_hover_throttle` below the true hover (non-FIXED laws) | the schedule scale at hover is `f(true_hover / setting)`; SQRT with hover 5 on a 36 %-hover craft = ×2.7 on b0 = gain ÷ 2.7 | Air65 144/160 at hover 5 flies like 88/98; at hover 27 (scale 1.15) it is ≈ 134/149 and rings at every zero-stick chop, where the scale clamps at 1 and the raw 144/160 is exposed |
| `adrc_b0_law` above hover | QUADRATIC/LINEAR/SQRT *lower* the gain as throttle rises (b0 × scale); FIXED does not | throttle-pump error: FIXED 30–38 °/s, SQRT 42–46, LINEAR 49–96, QUADRATIC 122–160 (cap) |
| `b0` itself | `b0` and `wc/wo` are one knob: raising b0 lowers G_P and G_D exactly like lowering wc/wo. A b0 *below* the true plant gain is *more* gain (less margin), not a safety margin | doubling b0 at fixed wc/wo halves the gain (AOS 3.5: line 9.6 → 0.7 %, roll overshoot 5 → 19 %) |

Below hover no law scales b0 down (b10.1 clamps the schedule at ≥ 1), so the loop is *under*-gained at low throttle
by roughly the thrust curve (plant gain at 20 % motor ≈ half of hover's). That is the low-throttle wobble testers
cure with TL or with hover 5. **b11-exp5 (`adrc_b0_scale_min`)** lets the schedule go below 1 under hover instead.

**Rules:** set `adrc_hover_throttle` to the *true* hover; fit `b0` with the `thrust_linear` you intend to fly (or
leave TL off); do not use hover 5 as a gain knob — it also removes the schedule (cap reached at 80 % throttle) and
leaves zero-stick moments on the raw gain.

## 4. The ground (arm-time lift, tap test)

With the gate closed the observer is a well-damped linear pair (`s² + 3wo·s + 3wo²`, ζ = 0.87) that cannot ring by
itself; the loop that lifts the craft closes through the airframe and the airmode mixer headroom, and its gain is
`G_D` above. Tap tests (props on, airmode on, stick at idle, three taps) ordered every outcome by `G_D`:

| G_D = 2·wc_ground·wo/b0 | outcome |
|---|---|
| ≥ 4 | self-sustaining rock (4 Hz) or lift |
| 1.6–2.2 | settles in 0.3–0.6 s but rails the motors on every tap |
| ≤ 0.6 | settles clean |

`adrc_ground_wc` (b11-exp2+) lowers `wc` while the gate is closed and ramps it back over `adrc_wc_ramp_ms` after
liftoff; `adrc_ground_dgain` (exp4+, default 1.0) additionally caps the ground `wc` at `dgain · b0 / (2·wo)` so the
default works per tune (b0 differs 2× between two Air65 tunes). **Acceptance test for any tune: three taps, each burst
dead within ~1 s, no motor at 2047.** With airmode the gate does not close on landing — disarm on touchdown.

## 5. Per-axis b0

`b0 = torque authority / inertia`, per axis. The 50/30/20 % split is a whoop rule. Under-gain looks like
bounce-back (roughly: gyro peak / setpoint peak above ~1.2 and error/setpoint ratio above ~0.08 on the active
samples; the well-tuned axes in the same logs sat at 1.08–1.14 and 0.04–0.05). On a squished-X
(AOS 3.5) roll bounced back in every flight and *more* b0 on roll made it worse: roll wants less. Fit per axis
(the fitter does), do not split by percentage.

## 6. Checklist

1. `adrc_hover_throttle` = true hover (read it from a log).
2. Decide `thrust_linear` first, then fit `b0` with it. Treat the fitted b0 and wc/wo as one gain: if you lower
   b0 below the fit you have raised the gain and must lower wc/wo to match (and vice versa).
3. Sweep `wo` up until the motor line appears; stay ~10 % under. `wc ≈ 0.9 · wo`. Same law for the sweep as for
   flying (FIXED vs SQRT move the knee by ~10 wo).
4. Tap test on the ground with airmode on. If it rails, lower `adrc_ground_wc` (or rely on `adrc_ground_dgain`).
5. `adrc_sigma_decay` 0 vs 3 and `adrc_b0_scale_max` 3–5 are not measurable on these craft; leave them.
6. Check the pack before blaming the tune: a pack at 2.5–3.0 V/cell moves every metric.
