# @8ksal8's props-off arms: the runaway did not reproduce; a yaw line did

> **Correction, 2026-08-12.** The four "Airmode feature off" cells here are not one regime per
> arm: the numeric mode mask (`blackbox_decode --unit-flags raw`; the default flag rendering
> discards bit 24) shows the BOXAIRMODE box became active for a mid-arm stretch in every one of
> them. The whole-arm medians below therefore mix a ×0.5-authority and a ×1.0-authority phase —
> the "ADRC, feature off" 28.66 deg/s is mostly its airmode-on phase; the airmode-off phases
> alone sit at 5.20 deg/s. The ADRC/CLASSIC ratios survive (both sides were mixed the same
> way), the regime labels do not. Recovery tool, phase-split numbers and the follow-up corpus:
> [`../pr15400-8ksal8-propsoff2/`](../pr15400-8ksal8-propsoff2/) (`modemask.py`, `spectra.py`).

**Reporter:** @8ksal8, PR #15400 comment of 2026-08-10, four archives, **props off**, four arms in
each of {ADRC, CLASSIC} × {Airmode feature on, off}.
**Craft and firmware:** the same Air65 and the same b9 build `919116fed` as the props-on set
analysed in [`pr15400-8ksal8-arming/`](../pr15400-8ksal8-arming/).
**Why it was asked for:** with props fitted, two arms of five ran to the motor rail in under
200 ms. Removing the props removes prop-generated thrust and its reaction against the ground;
it does not remove motor reaction torque, frame and ground coupling, motor-order vibration or
electrical paths into the gyro. What it separates is narrower than an earlier draft of this file
claimed, and the conclusions below are bounded accordingly.

**This time the controller labels are real.** The four `PID` archives carry `pid_type:0`, and
`axisD[2]` is absent from them exactly as a CLASSIC profile with `yawPID` D = 0 implies. The
previous set's `PID` logs did not; that is fixed.

Every number measured from this corpus is printed by one of the four scripts here; figures quoted
from the props-on set or from ADRC-028 are labelled as such where they appear. `summaries.py` generates
the rounded phrases with their derivations, and `summaries.py --check` is a regression guard (not
a proof — its blind spots are listed in the script).

---

## 1. What differs besides the controller

`provenance.py` prints the header diff between one representative arm of each profile — not a
"full" diff: the Field table rows are elided (they differ only through `axisD[2]`) and the
per-arm-variable keys (`vbatref`, `rc_smoothing_*`) are listed separately. It is still long:
besides the controller it includes `d_max`, `ff_weight`, `throttle_boost`, `anti_gravity_gain`,
`angle_limit`, TPA and the simplified-tuning settings, most of which plausibly do nothing at zero
stick input — but "plausibly" is not "checked". The differences judged material, **at least**
these four:

1. **Dynamic idle is on in the CLASSIC runs and off in the ADRC runs.** Directly:
   `dyn_idle_min_rpm` is 0 in the ADRC headers and 30 in the CLASSIC ones; consistently,
   `motorOutput` is `48,2047` under CLASSIC against `158,2047` under ADRC
   (`mixer_init.c:360-362` sets `motorOutputLow` to `DSHOT_MIN_THROTTLE` when dynamic idle is
   active).
2. **The CLASSIC profile has no yaw D at all** — `yawPID 38,54,0`. Under ADRC a D-equivalent term
   is always present, `kd = 2·wc`. Any yaw difference below is therefore *a D term on yaw against
   none*, not only *ADRC against CLASSIC*.
3. **The gains are different objects**: `38,54,26 / 39,57,28 / 38,54,0` against `wc 80,80,96`,
   `wo 103,103,125`, `b0 7007,4312,5848`.
4. **The pack**: the ADRC arms start at 3.92–4.21 V and sag as far as 3.67 V; the CLASSIC arms
   sit at 4.21–4.29 V nearly flat. Cause and effect run both ways here — the ADRC arms draw more
   — but the starting voltages differ too.

The first difference is measurable and large:

| group | rotor | motor median | peak current |
|---|---:|---:|---:|
| ADRC, Airmode feature on | 510 Hz | 253 | 8.64 A |
| ADRC, Airmode feature off | 156 Hz | 190 | 8.85 A |
| CLASSIC, Airmode feature on | 63 Hz | 102 | 0.89 A |
| CLASSIC, Airmode feature off | 60 Hz | 101 | 1.02 A |

Rotor rate is the median of the four per-motor medians, from the logged `eRPM` (`eRPM/100`
electrical, `blackbox.c:292`, converted with the header's `motor_poles`). The motors in the ADRC
arms turn several times faster and draw roughly nine times the current with nothing on the
shafts. Peak-current frames have near-zero setpoints and strongly differential motor commands
(printed per arm by `arms.py`; the first ADRC arm peaks at 9.41 A with motors
1565/237/158/1418), so this is the control-and-mixer path working, not a
static idle floor — though a peak is not a sustained figure, and "working" does not by itself
establish self-excitation.

## 2. The runaway did not reproduce in eight props-off arms

| group | span | gyro median | gyro max | frames at rail | peak current |
|---|---:|---:|---:|---:|---:|
| ADRC, Airmode feature on | 7.17 s | 42.0 | 88 | 0 | 8.64 A |
| ADRC, Airmode feature off | 14.49 s | 7.0 | 87 | 0 | 8.85 A |
| CLASSIC, Airmode feature on | 8.12 s | 4.0 | 16 | 0 | 0.89 A |
| CLASSIC, Airmode feature off | 12.37 s | 4.0 | 15 | 0 | 1.02 A |

Gyro figures are deg/s, max over the three axes per frame, median over four arms.

**Frames at the motor rail across all sixteen arms: 0.** With props fitted, two arms of five
reached it, at 176.480 and 182.802 ms; here eight ADRC arms run for 5.9 to 18.7 s without getting
there.

What that does and does not establish. A one-sided Fisher exact test on 2-of-5 against 0-of-8
gives p = 0.13, and 0-of-8 alone leaves a one-sided 95 % upper bound of 0.31 on the per-arm event probability
(treating the eight consecutive arms of one craft as independent trials, which they need not be) —
the props-on event was itself intermittent, so eight quiet arms cannot prove the
event impossible without props. The two corpora are also not matched (the props-on set mixes b8
and b9 and both Airmode states). The defensible statement is: **the runaway did not reproduce in
eight props-off ADRC arms; on the same metric the props-on events are 32–48× the worst props-off
group median; this is consistent with a prop-dependent aerodynamic or ground-reaction
contribution and makes this props-off protocol a weak reproducer — it does not prove the event
cannot occur without props.**

Measured with the same estimator on both corpora (an earlier draft compared a filtered-gyro peak
against a band RMS, which are different quantities): the 8–30 Hz roll/pitch RMS in the two railed
props-on logs is 153.2/102.4 and 123.1/107.6 deg/s, against at most 3.16 deg/s RMS among the
eight props-off group medians.

**`z3` and the gate are inert in all eight ADRC arms here** — gate open in 0 frames of all eight,
logged `z3` zero throughout — and all eight are b9, where the growth inhibit keys on the gate
alone, so the internal `z3` is exactly zero by the source state machine with no assumption about
unlogged intervals. That statement does **not** retroactively cover the b8 log in the props-on
set: there the inhibit also required `throttleAtIdle` and the first 167.5 ms are unrecorded, so
that log keeps its original proviso (section 5 of the props-on analysis).

## 3. Something is very much still happening, and it is yaw

Splitting by axis and by band, with the band edges fixed in advance:

| group | axis | 0–8 Hz | 8–30 Hz | 30–80 Hz | 80–400 Hz | peak |
|---|---|---:|---:|---:|---:|---:|
| ADRC, Airmode on | roll | 0.23 | 1.05 | 4.82 | 4.71 | 53.9 |
| | pitch | 0.18 | 0.31 | 1.99 | 4.50 | 53.9 |
| | **yaw** | 0.44 | 0.57 | **42.68** | 3.58 | 53.9 |
| ADRC, Airmode off | roll | 0.59 | 3.16 | 2.77 | 7.52 | 53.4 |
| | pitch | 0.20 | 0.80 | 1.54 | 9.52 | 153.5 |
| | **yaw** | 0.52 | 0.99 | **28.66** | 4.51 | 53.4 |
| CLASSIC, Airmode on | roll | 0.08 | 0.29 | 0.81 | 2.26 | 223.4 |
| | pitch | 0.07 | 0.13 | 1.21 | 1.64 | 55.9 |
| | **yaw** | 0.13 | 0.19 | **5.98** | 0.93 | 55.9 |
| CLASSIC, Airmode off | roll | 0.09 | 0.18 | 1.13 | 2.37 | 217.4 |
| | pitch | 0.08 | 0.13 | 1.62 | 1.44 | 55.4 |
| | **yaw** | 0.18 | 0.24 | **4.51** | 0.96 | 55.4 |

RMS in deg/s inside each band, median over the four arms of each group.

Almost all of the props-off motion is **yaw, in a band around 50 Hz**, and in the ADRC cells it
is **7.1× the CLASSIC level with the Airmode feature on** and **6.4× the CLASSIC level with it
off**. Roll and pitch stay in single digits everywhere. Given section 1, the defensible
attribution is that **the ADRC-labelled cells carry the larger amplitude under these confounded
profiles** — not that the controller alone drives it.

**What the yaw line is remains open, and an earlier version of this file got the rotor-order test
wrong.** It pooled all four motors into one median (60–63 Hz in the CLASSIC cells) and declared
the 55 Hz line unrelated. Per motor, the picture is different: in **every CLASSIC arm, motor 2
sits within 0.3–1.7 Hz of the yaw peak** — a near-coincidence the pooled median hid. And in the
ADRC-feature-on arms every shaft rate (457–611 Hz) is above the ~402 Hz Nyquist of the saved
stream, so those orders reach the spectrum only as aliases, which the old test did not consider
at all. `spectra.py` now prints per-motor rates with 1×-aliases folded at the arm-average frame
rate — an approximation itself, since the frame intervals are irregular. What holds: the pooled
rotor rate spans 60 to 510 Hz across the groups while the group-median yaw peak moves only between
53.4 and 55.9 Hz; per-motor **median** 1× orders reproduce the CLASSIC near-coincidence; no ADRC
per-motor **median** 1×, folded at the arm-average frame rate, is closer than 92.1 Hz to the line;
and the shaft rates of the four feature-on ADRC arms (457–611 Hz) exceed the ~402 Hz Nyquist while
the feature-off ones (146–171 Hz) do not. What the medians hide, and `spectra.py` now prints: the
**time-varying** 1× brushes the yaw line briefly in every ADRC arm (minimum distance 0.02–0.60 Hz,
0.08–5.07 % of frames within 2 Hz), and in the CLASSIC arms 42–61 % of frames have a 1× within
2 Hz of the line. So this corpus does not rule out a 1× contribution in the ADRC cells — nor establish
one; in the CLASSIC cells the line most plausibly *is* motor 2's 1×. Separating these needs an
order tracker on the real timestamps (integrate motor phase from `eRPM(t)`, estimate 1× amplitude
and coherence), not a comparison of medians.

## 4. What the two corpora together do and do not say

- **The 8–30 Hz roll/pitch runaway did not reproduce without props** (bounded as in section 2).
- **A yaw oscillation in a band around 50 Hz is present without props**, at 28.66–42.68 deg/s
  RMS in the ADRC cells. Yaw is also the axis that failed on @dedlike's craft in ADRC-028 and
  the axis carrying a weaker component near 46 Hz in the props-on set — three yaw observations
  on two craft, between roughly 34 and 56 Hz. Whether they share a mechanism is **not
  established**; in the CLASSIC cells here the line may simply be motor 2's rotation frequency.
- **The 6.4–7.1× ADRC-to-CLASSIC ratio is real but not attributable to the controller alone**
  (section 1: no yaw D in the CLASSIC profile, dynamic idle, different gains, different pack
  state).
- **Nothing in this corpus involves the disturbance estimate or the liftoff gate**; the b8
  props-on log keeps its separate proviso.

## 5. What would separate the remaining possibilities

Props-off, low-risk, in rough order of value:

1. **CLASSIC with a non-zero yaw D**, everything else unchanged. If the yaw line's amplitude
   follows the D term rather than the controller, that settles the largest confound in one run.
2. **ADRC with dynamic idle enabled**, matching the CLASSIC runs, so the motors turn at a
   comparable rate — this also moves the motor orders, and a motor-order line would expose
   itself by tracking them.
3. **A `wc` sweep on yaw alone** with `wo` and `b0` fixed. `kd = 2·wc`, so if the line scales
   with `wc` the D path is the drive.

Separately, and **not** low-risk: repeating the four cells **with props on** would show whether
the yaw line seeds the roll/pitch runaway. After an event that reached the motor rail in under
200 ms, that is not a hand-held bench test — it needs a restraint or an automatic cutoff, and it
is listed here as a distinct protocol, not as part of the props-off set.

## Reproduction

```bash
export BLACKBOX_DECODE=/path/to/blackbox_decode
python3 provenance.py   # headers, full profile diff, the four material differences
python3 arms.py         # per-arm rates, motor saturation, gate and z3 (with the b8 proviso)
python3 spectra.py      # band decomposition, same-metric props-on comparison, per-motor rotor test
python3 summaries.py    # the rounded phrases used in prose, with their derivation
ARMING_REPLY=<reply.md> JM_REPLY=<jm.md> python3 summaries.py --check
```

Scripts decode the `.bbl.gz` into `_decoded/` on first run; the props-on comparison uses a
separate cache because one log stem exists in both corpora. `summaries.py --check` is a guard,
not a proof; its blind spots are listed in the script.
