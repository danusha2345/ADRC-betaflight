# 8ksal8, 2026-07-30/31 — yaw b0 7k→13k→18k, the hover-anchor test, and why pitch is the twitchy axis

Source: four Blackbox logs attached to PR
[betaflight#15400](https://github.com/betaflight/betaflight/pull/15400) on
2026-07-30 and 2026-07-31. Same craft throughout (F405, 3S, ICM-class IMU,
b5 tag `543f1a5ff`, SQRT b0 law, `debug_mode = ADRC`, ~1972 Hz logging,
`motor_poles = 12`, `motorOutput 198-2047`).

| log | wc R/P/Y | b0 R/P/Y | anchor `adrc_hover_throttle` | vbat med | active |
|---|---|---|---:|---:|---:|
| `Acro_Air_Full_Throttle_Wind_btfl_002` | 125/125/125 | 4000/3000/**7000** | 29 | 10.98 V | 171.0 s |
| `Yawb0_13k` | 125/125/125 | 4000/3000/**13000** | 29 | 11.25 V | 175.0 s |
| `btfl_041` | 125/130/**220** | 4000/3000/**18000** | 29 | 11.89 V | 55.5 s |
| `yaw220wc_18kb0_HoverThrottle35` | 125/130/220 | 4000/3000/18000 | **35** | 10.02 V | 30.1 s |

Reproduce: decode each `.bbl` with the pinned `blackbox_decode`
(`--unit-acceleration g --unit-frame-time us --save-headers`), then
`python3 analyze_round.py <decoded.csv>` and `python3 hover_probe.py <decoded.csv>`.

Metric notes, because two of them are easy to misread:

- **`|I|` is the only b0-comparable view of the observer's disturbance state.**
  The `debug` z3 field is logged as `z3/16` and clips at 32767, i.e. `|z3| ≥ 524k`.
  z3 absorbs the `b0·u` model error, so its magnitude scales with the configured
  b0 — a larger b0 reaches the debug rail on its own, with no change in what the
  controller is doing. `pidData.I = −z3/b0` divides that back out, and the
  anti-windup bound is `|I| ≤ pidSumLimit`. Below, `|I|` is quoted; in every
  log it stays far from that limit (≤ 0.24 % of samples). Two things this does
  **not** say: the debug-field rail (`|z3| ≥ 524k`) is not the internal
  anti-windup rail (`pidSumLimit·b0` = 1.5–7.2 M for these tunes), and motor
  saturation is a separate matter — the two wind flights do rail a motor for
  4.30 % / 0.68 % of samples, and the hover-35 flight for 9.19 %.
- **Collective comes from the motor mean, not the throttle stick**, so it tracks
  what the craft actually needed.

## 1. yaw b0 7k → 13k: an encouraging association — every yaw metric moved the right way, but the flights differ

These two logs differ only in `adrc_b0_yaw` in configuration; same wc, same
filters, same anchor, both flown in wind on the same day. But the flights
themselves are not matched: the 7k flight is much more aggressive (4.30 % of
samples with a motor at the output rail versus 0.68 %, p90 collective 64.7 %
versus 42.9 %), and aggression alone moves every metric below. So this is an
association from two uncontrolled flights, not a controlled A/B — the yaw-only
comparison is the most meaningful part, and even it inherits the aggression
difference.

| metric (airborne, active) | yaw b0 7000 | yaw b0 13000 |
|---|---:|---:|
| yaw `|I|` p95 | 58 | **36** |
| yaw gyro RMS | 32.7 dps | 32.1 dps |
| yaw HF 20–80 Hz | 1.5 dps | **0.9 dps** |
| yaw tracking error RMS (15 Hz LP, commanded segments) | 9.9 dps (13 % of cmd sd) | **8.5 dps (12 %)** |
| yaw z3 at debug rail | 4.02 % | 4.77 % |

Reading: at 7k the yaw axis carried a larger standing correction (`|I|` p95
58 → 36) and more 20–80 Hz activity, and the tracking error did not get worse
when b0 went up (13 % → 12 % — within noise for two different flights). That
direction is *consistent with* 7000 having been low, and it matches the pilot's
"raising yaw b0 helped, and it still feels controllable" — but with the
aggression mismatch above it is support, not proof. A same-pack, similar-flying
repeat would settle it.

`btfl_041` (yaw b0 18000) is **not** a continuation of this A/B: `adrc_wc_yaw`
changed 125 → 220 in the same step, and it is a much calmer flight (p90
collective 29.5 %). Its yaw `|I|` p95 is 106 — three times the 13k value — and
its yaw z3 sits at the debug rail 30.2 % of the time. That could be the b0 step,
the wc step, or the different flight; with two variables moved at once the log
cannot separate them. If the goal is to find the yaw b0 ceiling, the next run
should hold `adrc_wc_yaw = 125` and only change b0.

## 2. The roll-solid / pitch-twitchy asymmetry is real, low-frequency, and physical-looking

The asymmetry the pilot sees in the debug traces is real and reproducible across
all four logs, but it is a **low-frequency** asymmetry, not chatter:

| log | roll `|I|` p95 | pitch `|I|` p95 | yaw `|I|` p95 | roll errRMS | pitch errRMS |
|---|---:|---:|---:|---:|---:|
| yaw 7k (wind) | 64 | **125** | 58 | 8.2 dps (7 %) | **27.7 dps (11 %)** |
| yaw 13k (wind) | 43 | **105** | 36 | 6.0 dps (5 %) | **12.6 dps (7 %)** |
| btfl_041 | 31 | 49 | 106 | 33.0 dps | 28.2 dps |
| hover-35 test | 67 | **148** | 59 | 17.9 dps | 23.5 dps |

Pitch carries a consistently larger standing disturbance estimate than roll —
1.6–2.4× across the four logs (125/64, 105/43, 49/31, 148/67) — and its tracking
error is 1.5–3× roll's in the two wind flights, while its 20–80 Hz content is
*lower* than roll's (3.4 vs 4.5, 2.1 vs 3.2 dps). Chatter-type noise would show
in the HF band; this shows in the standing correction, which is what a
persistent asymmetry (mechanical or tune) looks like. Low HF does not by itself
rule out every sensor or filtering cause, so the candidates below stay
candidates until a discriminating test is flown.

Two candidates, both consistent with the same signature and both testable:

1. **Rear CG.** The pilot has already stated the battery is deliberately set back
   to counter camera weight ("guess it's a little too much" — 2026-07-24 report).
   A static pitch imbalance is exactly a constant disturbance the observer must
   hold, i.e. a raised `|I|` on pitch only.
2. **`adrc_b0_pitch = 3000` against `adrc_b0_roll = 4000`** on a frame whose roll
   and pitch inertias are similar. A too-low b0 raises the effective loop gain on
   that axis, which is the axis-specific "reacts to wind with twitches" the pilot
   describes.

Cheapest discriminator: move the battery forward until the pitch `|I|` p95 drops
toward roll's without touching the tune. If it does, it was CG. If it does not,
set `adrc_b0_pitch = 4000` (matching roll) and re-fly the same conditions.

## 3. The `adrc_hover_throttle = 35` run is a weak control, not a refutation of @jmsweng

@jmsweng reported that setting `adrc_hover_throttle` **above** the craft's real
hover collective produces the inverted "sticking". @8ksal8 set 35 (his usual
value is 29) and saw no sticking. Measured from the logs, that run did not create
the offset the hypothesis needs:

| log | anchor | measured hover collective (calm windows) | offset (anchor − measured) | vbat med |
|---|---:|---:|---:|---:|
| yaw 7k | 29 | 32.4 % (n=518) | **−3.4** | 10.94 V |
| yaw 13k | 29 | 30.9 % (n=972) | **−1.9** | 11.22 V |
| btfl_041 | 29 | 28.6 % (n=76) | **+0.4** | 11.78 V |
| hover-35 test | 35 | 34.6 % (n=24) | **+0.4** | 10.56 V |

The hover-35 flight was flown on a sagging pack (10.02 V median, 10.56 V in the
calm windows, versus 11.78 V in `btfl_041`), and a sagging pack needs more
collective for the same hover. Taken at face value, the anchor of 35 landed
within half a point of the actual hover — i.e. the run most likely tested an
*approximately anchor-matched* configuration rather than the anchor-above-hover
regime the hypothesis needs. But the estimate itself is weak: only 24
heavily-overlapping calm windows survive this aggressive flight (9.19 % of
samples with a motor at the rail; hover spread p10 28.1 %, p90 40.0 %), so
"matched to +0.4" cannot be asserted with confidence. The honest statement:
this run is not a convincing refutation — and not a strong confirmation of
anything either.

To actually discriminate on this craft, make the offset the only variable: two
flights on equally-charged **fresh** packs (measured hover 28–30 %), anchor
**29** in one and **34–35** in the other, everything else unchanged. That
reproduces the same few-points-above offset @jmsweng reported the effect at,
without pack sag re-matching the anchor mid-experiment.

## 4. Ranges the schedule actually visited

For anyone reproducing: the b0 throttle multiplier (debug[7]) stayed modest in
all four logs — median 1.00–1.11, p90 1.01–1.48, max 1.62–1.82 — so none of these
flights probed the `adrc_b0_scale_max = 3` ceiling. The gate was open ≥ 95 % of
each log; no ADRC-026 signature (no zero-throttle motor runaway) appears in any
of them.

## Follow-up (2026-08-01): the ground b0_yaw sweeps — including a logged ADRC-026 false-open — and the first 48k log

Source: `Yaw300wc_b0_36k_Max_sweep.zip` and `Yaw300wc_48kb0.zip` (PR comment
5151289371), same craft (pilot confirms it hovers at ~28–29 %, consistent with
§3's measured 28.6–32.4 %). The pilot's stated procedure: ground, 0 % throttle,
ANGLE on, sweeping yaw b0 to "flatten the saw teeth" PID Toolbox shows in the
yaw response curve, believing wo was maxed out.

**Inventory — the first ZIP holds two `.bbl` files, 14 ground sessions in
total, plus `btfl_045` in the second ZIP.** An earlier revision of this
section analysed only the ascending file and wrongly concluded "no ADRC-026
event"; the descending file contains one.

- `Yaw300wc_b0_36k_20k_sweep.bbl`: five sessions, yaw b0 36k → 32k → 28k →
  24k → 20k;
- `Yaw300wc_b0_36k_Max_sweep.bbl`: nine sessions, yaw b0 36k → 65535;
- all fourteen: `wc 125/130/300`, `wo 160/160/160`, roll/pitch b0 4000/3000.

**What the headers actually changed:** `adrc_wo_yaw` never moved — 160 in
every session (CLI ceiling 600, headroom remains). What hit ceilings is
`adrc_wc_yaw` = 300 (the CLI max) and, in the last ascending session,
`adrc_b0_yaw` = 65535 (the uint16 field max).

**The 20k arm is a logged ADRC-026 false-open at zero throttle.** In
`…20k_sweep.05` (b0_yaw = 20000) the liftoff gate opened **0.775 s after the
log starts, at 0 % stick throttle**, and stayed open for 69.2 % of the record.
After the open: |gyro| reaches 128 dps, a motor is driven to **1122** of the
198–2047 range (≈ 50 % of span), and yaw z3 sits at the debug clip 26.2 % of
the remaining record; the recording ends 1.74 s after the open (disarm). Not a
full runaway to the rail — but a false liftoff detection plus ground-contact
excitation and windup, squarely in the ADRC-026 family, at **wo 160**: the
26 entry recorded so far with the lowest wo. The neighbouring sessions bracket
the trigger: the 32k and 24k arms briefly touch 21 dps (above the 20 dps
threshold, evidently under the 25 ms hold), the ascending nine stay at
≤ 17 dps with the gate closed 100 % of the time. The mechanism is coherent:
the control output scales as 1/b0, so *lowering* b0_yaw raises the grounded
loop gain until the idle excitation crosses the gyro trigger — direct support
for the joint-loop-gain threshold reading in the tracker (wo, wc, b0 jointly,
not a wo-only property).

**Why the closed-gate sessions cannot tune the airborne yaw loop.** With the
gate closed the ESO deliberately runs without the `b0·u` term, and the control
law divides everything by b0 (`P = wc²·err/b0`, `D = 2wc·z2/b0`,
`I = −z3/b0`). On the ground, raising b0_yaw therefore mostly *attenuates* the
yaw output per unit error — a progressively flatter, cleaner-looking idle
response is the expected result of turning the loop gain down, regardless of
the airframe. The "saw teeth going away" measures that attenuation, not the
flight loop; a PID-Toolbox step response taken on the ground with the gate
closed is a different plant from the one that flies. (The one open-gate
session is not usable as tuning data either — it is a safety event.)

**First log at the swept-in tune (`btfl_045`, wc_yaw 300 / b0_yaw 48k,
118 s at hover collective, fresh pack, anchor offset +0.8):** descriptively
the yaw axis is the loosest of the three calm-flight configurations so far —
tracking errRMS 39.3 dps = 27 % of the command sd with σ_gyro/σ_cmd = 1.18
(a std-dev ratio on 15 Hz-lowpassed commanded segments, not a proper
closed-loop gain measurement), lag 9 ms — against 18 % / 1.12 for `btfl_041`
(wc 220 / 18k) and 12 % / 1.04 for the 13k wind flight. Yaw HF is very low
(0.3 dps): quiet but loose. These are different flights, so this is
consistent-with, not proof of, an authority loss. One reading that fits: the
**P-output coefficient** per unit error is `wc²/b0` — 1.20 for 125/13k, 2.69
for 220/18k, **1.88 for 300/48k** — so the final config's direct P path is
weaker than 220/18k's despite both knobs being higher (the closed loop also
involves the ESO, so this is indicative, not the whole stiffness). The yaw
"z3 dbg-rail 43.6 %" here is the §-intro logging-scale effect: at b0 48k the
debug clip corresponds to |I| ≥ 10.9 while actual |I| p95 is 81 (bound 400) —
the channel is clipped telemetry above that level, not evidence of
anti-windup saturation.

## Follow-up 2 (2026-08-02): the "Getting close" set — an in-flight b0_yaw sweep, the remount, and the pilot's report of the 20k arm

Source: PR comment 5157640545 — `Getting_close.zip` (SHA-256
`c23c63454d7e21296fe59f8ec82f7cb55c054033238a2e8bf46ec1c446891e5c`, four
sessions `btfl_052…055`) plus a re-post of `Yaw300wc_48kb0.zip` (SHA-256
`e2650300bf00b776aa08435e4f06bb145bca16d7b152d94819c3fa1e418ef322`), whose
`btfl_045.bbl` is byte-identical to the file analysed above — the re-post adds
the subjective report ("yaw overshooting a little and bouncing side to side a
bit", plus "about an extra minute of flight time"), not new data. The pilot
also reports remounting the frame/prop-guard assembly between the previous
batch and this set, and attaches a PIDtoolbox step-response screenshot over
these same four logs.

**The pilot's report of the 20k arm confirms — and completes — the ADRC-026
record.** His description: "At arm the quad just popped to a hover about an
inch or two … off the ground and stayed there till disarm." The log agrees
with the outcome: after the false open, motors transiently reach 820–1122
with motor-mean collective p90 15 % / max 24 %, and the record ends at the
disarm 1.74 s after the open — for a guarded whoop in strong ground effect,
a real uncommanded lift-off, observed to be **self-limited** (a low hover,
not an escalation to the rail). A plausible mechanism for the self-limiting:
z3 winds up while the grounded plant does not respond, and once the craft
actually lifts the ESO regains a responding plant and the windup stops. That
is a hypothesis — the log records no altitude and the z3 inflection point is
not resolvable from the clipped debug trace — the established part is the
uncommanded lift-off itself. Nor is the self-limited outcome reassurance:
entry into uncommanded flight at 0 % throttle with props on is the hazard,
and the earlier high-wo captures show oscillatory (non-parking) versions of
the same entry.

**The four new sessions are the controlled-direction comparison the ground
sweep could not be: b0_yaw swept in flight at fixed wc_yaw = 300.**

| log | wc R/P/Y | b0 R/P/Y | dur | vbat med | yaw err % / gain | roll / pitch err % | yaw HF 20–80 | `wc²/b0` (yaw) |
|---|---|---|---:|---:|---|---|---:|---:|
| btfl_052 | 125/130/300 | 4000/3000/**32000** | 56 s | 11.20 V | 26 % / 1.16 | 18 % / 17 % | 0.4 | 2.81 |
| btfl_053 | 125/130/300 | 4000/3000/**28000** | 61 s | 11.99 V | 22 % / 1.14 | 16 % / 15 % | 0.4 | 3.21 |
| btfl_054 | 125/130/300 | 4000/3000/**26000** | 81 s | 11.61 V | 20 % / 1.13 | 16 % / 16 % | 0.4 | 3.46 |
| btfl_055 | **120**/130/300 | 4000/3000/**24000** | 97 s | 11.27 V | 19 % / 1.12 | 17 % / 16 % | 0.4 | 3.75 |

(The screening script also emits a cross-correlation lag; it is omitted here
deliberately — it concatenates non-contiguous commanded segments before
correlating, which is not a valid latency estimate on these logs.)

Gate open 89–100 %, saturation 0.00 % in all four; hover collective 27.7–30.2 %
against anchor 29 (matched, multiplier 1.00–1.02). Yaw tracking error falls
monotonically as b0_yaw comes down — err 26 → 19 %, σ-ratio 1.16 → 1.12 —
while the 20–80 Hz band stays flat at 0.4 dps: no chatter cost so far in this
range. This is the direction `wc²/b0` points (2.81 → 3.75; direct P-path
coefficient only — D scales as `2wc/b0` and the ESO participates too). The
pilot's PIDtoolbox screenshot over the same logs agrees at the endpoints
(yaw peak 1.33 at 32k → 1.24 at 24k) but is not strictly monotone in between
(≈1.33/1.28/1.29/1.24), and its yaw latencies are flat (≈19–20.5 ms), so it
adds endpoint support, not an independent monotone confirmation. Verdict:
a consistent one-knob descriptive trend — the cleanest yaw series in this
thread so far — with the usual free-flight caveats (packs differ 11.2–12.0 V
per session; the σ-ratio is not a gain measurement).

**After the remount, roll/pitch tracking is symmetric; attribution is
plausible but not isolated.** The previous batch carried a 1.6–2.4×
pitch-vs-roll tracking asymmetry (errRMS 125/64, 105/43, 49/31, 148/67 dps).
In all four new sessions roll and pitch track symmetrically (15–18 % each,
pitch slightly the better axis) with roll/pitch b0 unchanged at 4000/3000
and wc almost unchanged (125/130, except btfl_055's wc_roll = 120) — which
supports a mechanical contribution from the remount, though nothing here
isolates it causally. Two counterpoints keep it open: pitch |I| p95 is still
1.3–1.7× roll's (49/29, 36/28, 44/31, 40/29) — the integral effort asymmetry
survives even though tracking equalised — and the yaw before/after
comparison is confounded by b0_yaw changing alongside (27 % at 48k before vs
26 % at 32k after), so whether the remount helped yaw cannot be said either
way. The battery-forward CG discriminator is now much less urgent (the
tracking asymmetry it targeted is gone) but the residual |I| asymmetry means
it is not entirely moot.

**Grounded gate margin at the new flying tune (safety note).** In the armed
grounded segments before takeoff (5–7 s each in 053/054/055), the peak
grounded yaw |gyro| was 35 / 38 / 43 dps at b0_yaw 28k / 26k / 24k — one arm
per setting, so a small (and, in these three arms, shrinking) amplitude
margin rather than an established monotone law — with 29–83 separate
>20 dps crossings per arm, every one shorter than 7.6 ms: only the 25 ms
hold kept the gate closed; the 20 dps amplitude threshold is being crossed
routinely. And in btfl_052 the arm transient itself (a 26.4 ms **roll** run
to 56 dps, at b0_yaw 32k) **did** open the gate at 0 % throttle 0.12 s into
the log. It did not develop into a recorded ground incident before the
commanded lift-off ~1.5 s later; the zero-throttle false-open itself was
still unsafe. It is a fifth logged gyro-path open at zero throttle, and a
roll-transient one, so the exposure is not purely a b0_yaw property. Practical consequence: at
these settings the ground margin is hold-limited, not amplitude-limited;
keep the armed-on-ground time short, treat lower b0_yaw as increasing the
false-open risk, and do not resume props-on ANGLE ground sweeps.

The yaw "z3 dbg-rail" column reads 28–39 % across these four sessions — as
before this is the logging clip (at b0_yaw 24–32k the clip corresponds to
|I| ≥ 16–22 while actual |I| p95 is 80–89 against the 400 bound), not
anti-windup saturation.

## Follow-up 3 (2026-08-03): the `wo` pair — a confounded A/B, a tune-identical repeat of `btfl_055`, and a rail/HF association

Source: PR comment 5160697334 — `Yaw300wc_24kb0_160wo.zip` (SHA-256
`f1bcb3ec45cb609f73859f6bdba4db1218750570f2175c8bd1e1818204551088`), two
sessions of ~184 s each, plus the pilot's flight video
(<https://youtu.be/qVvsaoeI-gE>) and his reported tune R 120/150/4000,
P 130/150/3000, Y 300/150/24000. Headers confirm one ADRC change between the
two logs: `adrcWO` 160,160,160 → 150,150,150, i.e. **all three axes at once**.
Everything else is identical (wc 120/130/300, b0 4000/3000/24000,
`adrc_hover_throttle` 29, `adrc_b0_law` 1 = SQRT, `adrc_gyro_lpf_hz` 150,
`vbat_sag_compensation` 0, firmware `543f1a5ff`).

| log | wo | dur | sat | collective med / p90 | b0 scale med / p90 / max | roll / pitch / yaw err % | yaw HF 20–80 | motor HF 20–80 |
|---|---:|---:|---:|---|---|---|---:|---:|
| `…_160wo` | 160 | 184 s | 2.00 % | 32.4 / 54.6 % | 1.06 / 1.36 / 1.81 | 10 / 5 / 6 % | 0.9 | 9.2 |
| `…_150wo` | 150 | 183 s | 2.67 % | 34.1 / 62.6 % | 1.10 / 1.44 / 1.79 | 7 / 9 / 13 % | 1.2 | 12.1 |

**The wo A/B is confounded by how hard each flight was flown.** The second
session carries more collective (p90 62.6 vs 54.6 %), more saturation
(2.67 vs 2.00 %) and markedly more axis activity (roll gyro RMS 89.1 vs
67.2 dps). Every metric that got worse at wo 150 is also a metric that moves
with aggression, so these two logs do not measure `wo`.

**The wo-160 session is a tune-identical repeat of `btfl_055` — in a
completely different envelope.** Same wc, wo, b0, hover anchor and law as the
last log of the Follow-up 2 sweep, yet: collective p90 54.6 % vs 30.6 %,
saturation 2.00 % vs 0.00 %, b0-schedule multiplier reaching 1.81 vs 1.05,
yaw tracking 6 % vs 19 %. Two consequences. (1) These logs **cannot extend
the b0_yaw series** — nothing in them is comparable to it. (2) Checking back,
all four sweep sessions were flown in a tight, matched envelope (collective
p90 30.5 / 28.3 / 29.5 / 30.6 %, zero saturation, multiplier ≤ 1.12), which
*strengthens* the internal validity of that sweep rather than weakening it —
what it measured was small-signal yaw behaviour near hover, and only that.

**Rail contact is strongly associated with the 20–80 Hz motor-command band.**
The pilot's "trilling at high throttle" has no instrumented counterpart — there
is no audio channel — so the nearest measurable quantity is 20–80 Hz content on
the motor mean. Splitting both logs into 0.5 s windows by measured collective
and by whether any motor sat at the configured high rail (2047) inside the
window (`rail_hf_probe.py`, medians, wo-160 / wo-150):

| collective band | HF 20–80, rail < 0.5 % of window | HF 20–80, rail ≥ 2 % of window |
|---|---|---|
| 40–55 % | 1.6 (n=93) / 2.0 (n=108) | 15.7 (n=4) / 10.7 (n=14) |
| 55–70 % | 2.4 (n=18) / 2.3 (n=27) | 9.1 (n=5) / 18.9 (n=20) |
| 70–85 % | 2.9 (n=6) / — | 38.1 (n=6) / 27.0 (n=22) |

At comparable collective, rail-touching windows carry 5–10× the band activity
of non-touching ones; window rail duty correlates with the band at +0.82 /
+0.86 over the collective > 50 % windows. **The causal direction is
unresolved, and so is the relationship to the audible trill.** Both the rail
flag and the HF measure come from the same motor-command signal; matched
collective does not match maneuver, setpoint or cross-axis load; and `b0`
itself sets command gain and therefore rail probability, so it cannot be
excluded as a common cause. The within-flight decline the pilot describes
appears in one log of the two: in wo-160 the high-collective windows go from
rail duty 9.3 % / HF 20.1 in the first half to 0.0 % / 3.0 in the second, while
in wo-150 they are flat (1.1 % / 4.4 → 0.1 % / 4.0). What can be said: nothing
here supports lowering `wo` as the reason for any change, and headroom is the
variable most worth testing next.

**Yaw tracking-error intervals: three descriptive contexts.** Intervals where
`|gyro_yaw − setpoint_yaw|` (both LP 15 Hz) exceeds 40 dps for ≥ 30 ms
(`washout_probe.py`): 5 in the wo-160 log, 12 in the wo-150 log. The detector
groups them by context; it does not identify mechanisms.

1. *With saturation* (wo-160 at 156.1–156.4 s): during a −533 dps roll the
   yaw axis swings −140 → +222 dps against a ±11 dps request, and yaw `|I|`
   touches its 400 bound for 5 ms. **The ordering here is the opposite of
   Pavel's Meteor wc-40 departures**: the error interval starts at 156.0936 s
   and the first rail contact — which then runs continuously for 154 ms — is at
   156.1416 s, i.e. 48 ms *later* (the raw yaw gyro passes 60 dps at a quiet
   stick at 156.1111 s, still 30 ms before the rail). Departure and saturation
   overlap; their causal ordering is unresolved, and it is not the
   saturation-first pattern seen on the Meteor. This is the largest
   uncommanded yaw excursion in the pair, and it does **not** meet the part-3
   event criterion (`excursions.py` reports 0 events in both logs: the 200 dps
   threshold is crossed, the ≥100 ms duration is not).
2. *Large held commands, no saturation* (wo-150 at 103 s and the 118 s
   cluster): requests of +299…+449 dps answered with peaks of +478…+564,
   `|I|` well below bound.
3. *Concurrent with another axis* (44 s, 170 s cluster): yaw errors of
   43–55 dps while pitch runs at 522–622 dps.

The yaw z3 debug field is clipped in 36–100 % of the samples inside every
interval, so the observer state is off-scale exactly where it would be most
interesting — the logging clip, not anti-windup.

**No b0-dependent change in held-command yaw overshoot was resolved.** Peak
`|gyro_yaw|` over a held command (`|setpoint_yaw|` > 150 dps for ≥ 150 ms,
sd/mean < 0.15, peak taken over the hold + 100 ms tail; `yaw_overshoot.py`
defaults):

| log | b0_yaw | holds | overshoot median |
|---|---:|---:|---:|
| btfl_052 | 32000 | 2 | 1.34 |
| btfl_053 | 28000 | 3 | 1.35 |
| btfl_054 | 26000 | 11 | 1.31 |
| btfl_055 | 24000 | 12 | 1.30 |

This is a sparse post-hoc detector on free flight, not a step-response test:
the qualifying-hold count depends on how the pilot happened to fly, and on the
thresholds. `yaw_overshoot.py --sweep` over six threshold/duration settings
returns medians between 1.27 and 1.37 for all four logs with hold counts from
1 to 33 and no b0 ordering — so the honest reading is that **this detector
resolves no b0-dependent change in held-command overshoot**, not that the
quantity is constant. What it does show is that the sweep's improvement lives
in the small-signal tracking metric (26 → 19 %), and that nothing in this
corpus argues that going below b0_yaw 24k would move the large-signal
behaviour the pilot is describing.

**ADRC-026 check: clean in both logs.** The gate opens once per log, at
4.47 s / 4.77 s, on commanded throttle. Grounded `|gyro|` peaks r/p/y are
19/19/27 and 22/13/36 dps; >20 dps runs number 2 and 12 with the longest at
2.5 ms and 6.6 ms against the 25 ms hold. No zero-throttle open — but the
margin is again hold-limited, not amplitude-limited.

Reproduce: `washout_probe.py`, `yaw_overshoot.py` (add `--sweep` for the
threshold sensitivity) and `rail_hf_probe.py` in this directory, plus
`analyze_round.py`, `gate_probe.py` and part-3's `excursions.py`.

## Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| yaw b0 7k → 13k: yaw `|I|`, HF and tracking all moved favourably | POSITIVE (association) | table in §1; flights differ in aggression, not a controlled A/B | medium |
| yaw b0 18k is better still | UNPROVEN | wc_yaw and flight conditions changed with it | high |
| pitch carries a standing asymmetry vs roll (1.6–2.4× `|I|`) | POSITIVE | `|I|` p95 and errRMS across four logs | high |
| that asymmetry is CG rather than tune (or sensor path) | UNTESTED | candidates only, no discriminating run yet | — |
| the hover-35 run refutes @jmsweng | NEGATIVE | offset most likely ≈0; 34.6 % from 24 wide-spread windows | medium-high |
| any ADRC-026 event in the original yaw-7k / yaw-13k / btfl_041 / hover-35 flight set | NEGATIVE | gate open ≥95 %, no zero-throttle runaway | high |
| ADRC-026 false-open in the ground b0_yaw sweeps | **POSITIVE** | `…20k_sweep.05`: gate opens at 0.775 s at 0 % throttle, motor to 1122, z3 clipped 26.2 % after open | high |
| the trigger is bracketed by b0_yaw in that sweep | POSITIVE | 20k opens; 24k/32k touch 21 dps without opening; ascending nine ≤ 17 dps closed | high |
| the closed-gate sessions measured the airborne yaw loop | NEGATIVE | gate closed → no b0·u in the ESO; output ∝ 1/b0 | high |
| wc_yaw 300 / b0_yaw 48k improved flight yaw | NEGATIVE (descriptive, so far) | btfl_045: 27 % err / σ-ratio 1.18 vs 18 % / 1.12 (btfl_041), 12 % / 1.04 (13k); different flights | medium |
| lowering b0_yaw 32k → 24k at wc_yaw 300 improves flight yaw | POSITIVE (descriptive one-knob trend) | Follow-up 2 table: err 26→19 %, σ-ratio 1.16→1.12, HF flat; PIDtoolbox agrees at endpoints (1.33→1.24, non-monotone inside, latency flat); packs differ; lag estimate excluded as invalid | medium |
| the 20k arm reached uncommanded flight (not just windup) | POSITIVE | pilot report ("popped to a hover … stayed till disarm") + collective p90 15 %/max 24 % in ground effect | high |
| the self-limiting was an ESO-regains-the-plant equilibrium | HYPOTHESIS | no altitude channel; z3 inflection not resolvable from clipped trace | — |
| the previous pitch-vs-roll *tracking* asymmetry had a mechanical component | POSITIVE (supported, not isolated) | symmetric 15–18 % post-remount with roll/pitch b0 unchanged (btfl_055 wc_roll 120 the one tune delta); pitch \|I\| still 1.3–1.7× roll | medium |
| the remount's effect on yaw | UNRESOLVED | before/after confounded by b0_yaw 48k → 32k; within the new set yaw moves with b0_yaw | — |
| grounded amplitude margin is small at 24k–28k; the 25 ms hold was the active guard | POSITIVE | grounded yaw peaks 35/38/43 dps (one arm per setting), 29–83 >20 dps crossings per arm, all ≤ 7.6 ms | high |
| a fifth gyro-path open at 0 % throttle (arm transient, btfl_052) | POSITIVE (no recorded incident before lift-off; the false-open itself unsafe; roll-driven, at b0_yaw 32k) | 26.4 ms roll run to 56 dps opens gate at t = 0.12 s; commanded lift-off ~1.5 s later | high |
| lowering wo 160 → 150 improved the craft | UNPROVEN | Follow-up 3: single pair, both flights differ in aggression (collective p90 54.6 vs 62.6 %, roll gyro RMS 67 vs 89 dps); wo changed on all three axes at once | high |
| the wo-160 log extends the b0_yaw sweep (same tune as btfl_055) | NEGATIVE | same tune, incomparable envelope: collective p90 54.6 vs 30.6 %, saturation 2.00 vs 0.00 %, multiplier to 1.81 vs 1.05 | high |
| rail-touching windows carry more 20–80 Hz motor-command activity | POSITIVE (association) | at comparable collective 5–10× higher; rail-duty↔HF correlation +0.82/+0.86 | medium-high |
| that association explains the audible trill | HYPOTHESIS | no audio channel; rail flag and HF share one signal; collective does not match maneuver; `b0` sets both command gain and rail probability | — |
| held-command yaw overshoot responded to b0_yaw 32k → 24k | UNRESOLVED | 1.34/1.35/1.31/1.30 at defaults, but 1–33 holds per log and medians 1.27–1.37 across six threshold settings with no b0 ordering — the detector resolves no change either way | — |
| any ADRC-026 event in the wo pair | NEGATIVE | one commanded gate open per log at 4.47/4.77 s; longest grounded >20 dps run 2.5/6.6 ms vs the 25 ms hold | high |
