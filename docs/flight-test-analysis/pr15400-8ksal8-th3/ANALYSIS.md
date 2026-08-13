# TH3 Freestyle: one tune, three packs, b0 scaled by a watt-hour rule

**Data**: six flight logs by @8ksal8 on a rebuilt Emax Tinyhawk III+ Freestyle (2.5",
1204.5 5022KV, F7X2, 8k gyro / 4k PID, b9 firmware `919116fed`), posted 2026-08-13 in
PR #15400. One craft flown on 2s, 3s and 4s packs with `wc/wo` fixed at 110/110/120 over
150/150/150 and per-pack `b0` produced by the tester's rule — multiply by the percentage change
in pack watt-hours:

| pack | b0 (R/P/Y) | flight log | ANGLE-mode "wobble" log |
|---|---|---|---|
| 2s | 5610/4080/12500 | 177.6 s | 91.0 s |
| 3s | 7773/5653/17319 | 175.1 s | 106.3 s |
| 4s | 9896/7197/22050 | 174.6 s | 97.8 s |

The tester's archive also contains eight tuning arms documenting how he reached the tune; they
are not carried in this directory and nothing here is claimed about them. The per-pack
comparison is **not** single-variable — most plainly because pack, day and stick input change
together with b0. Two header keys also differ between packs (`overview.py` prints the full
diff): `angle_limit` (40 → 60), which shapes the ANGLE-mode wobble logs' setpoint and is a real
confound for those rows, and the `dterm_*` filter settings — which on this firmware do **not**
touch the ADRC D path (classic D is filtered through the dterm chain and then overwritten by
`applyAdrcControl()`, whose D is −kd·z2/b0 from the observer's own dedicated gyro filter), so
they are flagged but not load-bearing. Every number below is printed by `overview.py`; none is
hand-copied.

## The tune tracks on all three packs

Acro-flight tracking error medians are 2/2/4, 2/2/3 and 2/2/3 deg/s (p90 9/8/13, 8/8/12,
7/8/11) for 2s/3s/4s — similar across a doubling of pack voltage. Motor-rail samples fall as
pack headroom grows: 8346 → 1759 → 765. The "wobble" logs are the tester's ANGLE-mode
stick-rocking procedure (numeric mode mask: ANGLE throughout, airmode never active — the same
procedure and the same instrument caveat as on the Pavo20: their logged setpoint is the
self-level loop's output, and their error numbers measure a different control chain than the
acro flights).

## The watt-hour rule vs the measured voltage

His multipliers: 3s/2s = 1.386, 4s/3s = 1.273 (with a self-reported extra margin on the 4s
step). The measured flight-median pack voltages give ratios 1.526 and 1.359 — each measured voltage
step sits above the b0 step (by 10.2 % and 6.7 %), and over the full 2s→4s range the
voltage-proportional endpoint (2.074) sits 17.6 % above the configured b0 scale (1.764). All three
configurations nevertheless flew with similar rounded tracking metrics. That is an observed
coincidence of metrics across three different flights, not a controlled test: nothing here
identifies what absorbed the difference (the observer is one candidate; the actual
thrust-per-command law, which is not exactly proportional to voltage, is another), and which
scaling rule is "right" is not decidable from these flights.

Note the starting-point heuristic the tester described (pick wo under the craft's noise
ceiling, then shape b0/wc) is his procedure, reported here, not something these logs test.

## The yaw z3 telemetry rail, again

With yaw `b0` = 12500–22050, the yaw z3 debug channel saturates its b9 int16 rail
(32767·16 = 524272) in **3.4–10.7 %** of frames in the acro flights and **21.1–26.6 %** in the
wobble logs, while the controller's own yaw clamp sits at 5000000–8820000 (`overview.py`).
This craft joins the Pavo20 as a live case for ADRC-029's per-profile `adrc_z3_log_scale`
header line (in b10): on b9, most of the yaw disturbance-estimate range is invisible.

## Reproduction

```bash
pip install numpy scipy
export BLACKBOX_DECODE=/path/to/blackbox_decode   # betaflight/blackbox-tools, commit f832acf9cd
python3 overview.py
python3 summaries.py --check
```
