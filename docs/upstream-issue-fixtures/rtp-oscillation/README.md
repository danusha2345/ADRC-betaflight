# Runaway takeoff prevention vs oscillatory ground events — evidence kit

Companion to the betaflight/betaflight issue about `runaway_takeoff_prevention`'s continuous-hold
trigger and oscillatory ground events. `rtp_oscillation_check.py` reconstructs the trigger
condition from decoded blackbox CSVs and prints, per log: the peak reconstructed |Sum|, the
fraction of frames meeting the |Sum| ≥ 600 condition, a conservative upper bound on any
continuous stretch of the full trigger condition (false-neighbour to false-neighbour, so unsaved
PID iterations are inside the bound; runs touching the capture edge are marked censored), the
sample-and-hold total condition-time (the zero-leak accumulator baseline), the largest
inter-frame gap, and a 596/600/604 threshold sweep showing the result does not hinge on per-term
`lrintf` quantisation.

The script's docstring carries the honesty notes: which preconditions of the real check are not
recoverable from a log, and why logs missing `axisD[2]` support no conclusion (a missing *signed*
term bounds nothing).

Requirements: Python 3 with `numpy`; `blackbox_decode` built from
[betaflight/blackbox-tools](https://github.com/betaflight/blackbox-tools) — the numbers below
were produced with commit `f832acf9cd9dbe5ad8220de1a5f4eb4021523d72`.

## Reproduction, from an empty directory

```bash
BASE=https://raw.githubusercontent.com/danusha2345/ADRC-betaflight/master/docs/flight-test-analysis
wget $BASE/pr15400-8ksal8-arming/b8_Airmode_on_ADRC_btfl_001.bbl.gz
wget $BASE/pr15400-8ksal8-arming/b9_Airmode_on_ADRC_btfl_002.bbl.gz
wget $BASE/pr15400-dedlike-groundloop/groundloop_btfl_all.bbl.gz
wget $BASE/pr15400-8ksal8-arming/b9_Airmode_switch_ADRC_btfl_003.bbl.gz   # negative control
gunzip -k *.bbl.gz

blackbox_decode --index 1 b8_Airmode_on_ADRC_btfl_001.bbl
blackbox_decode --index 1 b9_Airmode_on_ADRC_btfl_002.bbl
blackbox_decode --index 2 groundloop_btfl_all.bbl      # log 2 of the file is the event
blackbox_decode --index 1 b9_Airmode_switch_ADRC_btfl_003.bbl

python3 rtp_oscillation_check.py \
    b8_Airmode_on_ADRC_btfl_001.01.csv \
    b9_Airmode_on_ADRC_btfl_002.01.csv \
    groundloop_btfl_all.02.csv \
    b9_Airmode_switch_ADRC_btfl_003.01.csv
```

The fourth log is the 96.506 s flight from the same craft as the first two — a single-flight
negative control: how little condition-time this one flight produced under the same condition.

## Expected output (data rows)

```text
log                                         terms    span  |Sum|max  frames>=600     run<=      accum   maxgap  fires?
b8_Airmode_on_ADRC_btfl_001.01.csv           PIDF   0.71s       838    42 ( 7.3%)    14.5ms     51.9ms    1.3ms      no
b9_Airmode_on_ADRC_btfl_002.01.csv           PIDF   0.68s       896    65 (12.2%)    13.9ms     81.0ms   18.3ms      no
groundloop_btfl_all.02.csv                   PIDF   6.25s      5638   208 ( 3.3%)    15.0ms    208.0ms   19.0ms      no
b9_Airmode_switch_ADRC_btfl_003.01.csv       PIDF  96.51s       665     6 ( 0.0%)     8.9ms      7.6ms   32.3ms      no
```

Full analyses of these logs (frequencies, motor saturation, provenance) are published beside
them: [`pr15400-8ksal8-arming/`](../../flight-test-analysis/pr15400-8ksal8-arming/) and
[`pr15400-dedlike-groundloop/`](../../flight-test-analysis/pr15400-dedlike-groundloop/).

## 2026-09-11 addition: a 14 s ground rock the detector could not catch

Log: `docs/flight-test-analysis/pr15400-8ksal8-airmode-rxsmoothing/b11_tests_20260907/g40_103_140_single_axis.bbl.gz`
(Air65, b11-exp2 `33004f5c`, airmode on, stick at idle, props on, `adrc_ground_wc` 40 on a 103/140 pitch axis;
PR betaflight#15400 comment 5562538603). After a tap the craft rocked at 4 Hz for 14 s at 520–1365 °/s with a motor
at 2047 in every second until the tester disarmed; it walked off the couch. All four terms are logged (PIDF) and the
exact final Sum is logged too (`adrcPidSum`, divide by the `adrc_pid_sum_scale` header) — both give the same answer:

```
blackbox_decode --unit-flags raw g40_103_140_single_axis.bbl
python3 rtp_oscillation_check.py g40_103_140_single_axis.01.csv
log                              terms   span  |Sum|max  frames>=600   run<=     accum   maxgap  fires?
g40_103_140_single_axis.01.csv   PIDF  17.75s     3472  1052 (7.2%)  58.6ms  1281.6ms   1.3ms      no
```

|Sum| reached 3472 (5.8× the threshold) and the full trigger condition was true for 1.28 s in total, but never for
more than 58.6 ms in a row (4 Hz rock: sign crossings every 125 ms), so the 75 ms continuous hold could not be met.
The two companion logs in the same folder (`g20/log2_103-140_single_axis`, `g40_99_110_all`: taps that settled)
give 8.7 ms and 11.2 ms.
