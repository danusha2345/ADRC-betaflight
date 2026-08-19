# Yaw wc / wc=wo / b0-redistribution sweeps (Air65, 11 flights)

**Data**: eleven acro flights by @8ksal8 on the Air65 R (b9 firmware `919116fed`), posted
2026-08-19 in PR #15400 (comment id 5337016044) as four zips: a yaw `wc` sweep 50–80 at fixed
yaw `wo = 80`; a matching `wc = wo` sweep 50–80; two flights with yaw b0 lowered 2340 → 878
while roll/pitch b0 rose to keep the three-axis sum unchanged (his description); and one
flight with yaw `wc = wo = 88` above lowered roll/pitch. All logs share the b0calc filter
state: main Betaflight gyro/dterm stages disabled, the ADRC observer's own input PT2 active at
`adrc_gyro_lpf_hz = 185`. One flight per cell — every number is a single observation printed
by `analysis.py`; the tester reports flying the same track each time (his report, not a log
fact). Per-log SHA-256 and the full metric grid are printed by the script.

**Known confounds**: this is not a single-knob controlled comparison — the full header-union
diff (printed by the script) covers the swept tune axes and their legacy PID mirrors, plus
`rc_smoothing_*` and `vbatref`. The rx link rate is not constant across cells —
`rc_smoothing_rx_smoothed` clusters at ~166 Hz and ~332–339 Hz (per-cell values printed).
Link-rate-matched contrasts (matched in this confound only; battery, inputs and conditions
stay uncontrolled): the wc=50 pair (wo 80 vs 50, both 166 Hz), the wc=wo 50/60/70 run (all
166 Hz), and the 80/80 repeated cell (332 vs 333 Hz). The wc=60 and wc=70 same-wc pairs cross
clusters, and so does the stock-vs-adjusted b0 pair at wc=wo=60 (166 vs 333 Hz). Battery
state also differs between cells (vbat minima span 3.14–3.61 V).

## The 30–80 Hz yaw peak tracks wo more closely than wc in this set

With `wo` held at 80 the band peak stays in a 47.0–53.5 Hz range for every `wc` in 50–80.
When `wo` moves down together with `wc`, the peak moves down with it: wo=50 → 34.43 Hz,
wo=60 → 40.73 Hz, wo=70 → 50.95 Hz, wo=80 → 55.09 Hz. The cleanest same-link-rate contrast is
the wc=50 pair (both 166 Hz): wo 80 → 47.01 Hz vs wo 50 → 34.43 Hz with `wc` identical — the
one pair where `wc` and the link rate both hold still; in the wc=wo sweep both parameters move
together. The peak is not `wc`-invariant — it spans 47.0–53.5 Hz across the wc sweep — but the
excursion when `wo` moves (34.4–55.1 Hz) is larger. In these cells the peak frequency tracks
the observer bandwidth more closely than the controller bandwidth; no claim of a null `wc`
effect is made. Observed association; one flight per cell; no mechanism is established. This addresses the question the filter campaigns left open — there, `wo` was
never varied.

The 80/80 tune appears in both sweeps — the only repeated cell in this set (matching wc/wo/b0;
headers not fully identical — rx_smoothed 332 vs 333, vbatref 430 vs 433): 53.50 vs 55.09 Hz,
prominence 9.6 vs 6.3, band RMS 1.56 vs 1.49 deg/s. One repeat shows one realised
between-flight difference; it is not a variance estimate for the other cells.

## Lowering yaw b0 (2340 → 878, sum-preserving)

At `wc = wo = 50` the flight completes (80.3 s) with the band elevated: RMS 1.06 → 2.25 deg/s,
prominence 2.2 → 24.1 against the same-tune stock-b0 cell (a same-link-rate pair, both
166 Hz). At `wc = wo = 60` the log shows a sustained large-amplitude yaw error component at
46.24 Hz (prominence 77210.8, band RMS 55.53 deg/s, yaw error median 48.0 deg/s vs 18.0
stock) and ends after 12.8 s; the vbat floor is 3.61 V (reached at 1.1 s) and the final vbat
sample is 3.95 V; the log does not record why it ended. This stock-vs-
adjusted pair crosses link-rate clusters (166 vs 333 Hz), so the b0 change is not isolated in
it. In ADRC terms a lower b0 scales the P/D output up, which raises small-signal loop gain —
the direction consistent with a reduced oscillation margin — but one flight does not establish
the mechanism, and no threshold between wo 50 and 60 is inferred.

## The raised-yaw cell (a whole-tune change, not one knob)

The `lower_RP_raise_Y` cell moves yaw to `wc = wo = 88` and simultaneously lowers roll/pitch
to `wc 76 / wo 126` from 84/140 (yaw b0 stock) — a whole-tune cell. It shows the band peak at
58.03 Hz with prominence 2667.9 and band RMS 7.68 deg/s — the largest band RMS among the 10
logs with duration ≥ 30 s (the "full-length" criterion; the 12.8-s log is excluded), in the
cell with the highest yaw `wo`. Its yaw tracking median is 19.0 deg/s against 11.0 deg/s in
the 80/80 cell of the same sweep set. Nothing attributes these differences to the yaw change
alone.

## Caveats

- One flight per cell, uncontrolled inputs and conditions; the repeated 80/80 cell is the
  only repeat. Track similarity is the tester's report.
- The link-rate and battery confounds above apply to all cross-cluster comparisons.
- Prominence (band max PSD / band median PSD) is a descriptor with no validated threshold.
- Nothing here attributes the band to a component; the wo-association is a frequency
  observation, not a mechanism.

## Reproduction

```bash
pip install numpy scipy
export BLACKBOX_DECODE=/path/to/blackbox_decode   # betaflight/blackbox-tools, commit f832acf9cd
python3 analysis.py
YAWSWEEP_REPLY=DRAFT_reply.md python3 summaries.py --check
```
