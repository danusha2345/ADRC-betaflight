Ready-to-flash Betaflight-ADRC firmware for flight testing — no compiling needed.

## What's new in v0.2.0

This round came out of the first whoop test data and a second independent tester. Four experimental fixes on top of v0.1.0 — full detail in [ADRC_FIXES.md](https://github.com/danusha2345/ADRC-betaflight/blob/master/ADRC_FIXES.md) (`#10`–`#12`):

- **`#10` throttle-scaled b0** — the system gain (D → b0) is now scaled by `(throttle / hover)²` above hover, because motor authority rises with RPM (thrust ≈ throttle²). Keeps the model calibrated across the throttle range; aimed at the whoop takeoff-drift and "floaty" feel. New CLI `adrc_hover_throttle` (%, default 35 — set it near your real hover throttle). The square is deliberately conservative and may feel slightly *soft near full throttle*; raise `adrc_hover_throttle` toward your top throttle if you dislike it.
- **`#10` liftoff-gate re-arm** — the takeoff gate (v0.1.0 fix `#8`) now re-arms after a sustained return to idle **and** stillness, so every ground-test / re-takeoff in one arm is gated, not just the first.
- **`#11` z3 leaky decay** — the observer's disturbance estimate now bleeds a transient bump back to zero (`adrc_sigma_decay`, default 3, mild). Set `0` for the classic pure integrator. Leave `adrc_sigma_decay_sched` at 0 (unvalidated).
- **`#12` blackbox z3 no longer clips** — raw z3 used to saturate the int16 debug field on takeoff ("debug 5/6 go nuts"); it's now logged ÷16 so the trace stays readable. For disturbance *magnitude* the I channel (`−z3/b0`) is the clean signal.

## What helps most — please fly with blackbox logs

The single most useful thing you can send is a **blackbox log with the ADRC observer enabled**:

```
set debug_mode = ADRC
save
```

Then, if you can:
- **A/B the takeoff gate (`#8`/`#10`):** a clean, near-vertical takeoff is what isolates it — indoor bumping into furniture swamps the signal. Fly the tip build, then a build with the gate reverted, same craft/tune.
- **A hard flip or punch-out** with `debug_mode = ADRC` — shows z3 vs the anti-windup clamp under saturation.
- Note your `adrc_b0_scale` and `adrc_hover_throttle` when sharing a tune (the same D means a different b0 at a different scale).

debug layout: roll z1/z2/z3 = debug 0–2, pitch z1/z2/z3 = 3–5, yaw z3 = 6, throttle-scaled b0 ×100 (sign = liftoff latch) = 7. Decode with [blackbox-tools](https://github.com/betaflight/blackbox-tools) and plot with [`adrc_log_plot.py`](https://github.com/danusha2345/ADRC-betaflight/blob/master/docs/flight-test-analysis/adrc_log_plot.py). Post logs in [issue `#1`](https://github.com/danusha2345/ADRC-betaflight/issues/1).

**How to flash:** Betaflight Configurator → Firmware Flasher → *Load Firmware [Local]* → pick the `.hex` for your board → *Flash Firmware* (Full chip erase recommended on the first flash).

**Before the first flight:** read the [README](https://github.com/danusha2345/ADRC-betaflight#where-to-enter-the-values-betaflight-configurator-pid-tuning-tab) — ADRC parameters go into the ordinary P/I/D cells of the PID Tuning tab (P = control bandwidth, I = observer bandwidth, D = system gain), and `set pid_at_min_throttle = off` is strongly recommended. The tuning procedure and example tunes are in the README; what changed vs the original ADRC code is in [ADRC_FIXES.md](https://github.com/danusha2345/ADRC-betaflight/blob/master/ADRC_FIXES.md).

**Your board is not in the named list?** Use the **generic hex for your board's MCU** — e.g. `STM32F7X2` for any F722 board, `STM32F405` for F405 boards, `STM32H743`, `AT32F435M/G`, etc. (this is exactly how official Betaflight releases ship). On first connect the Configurator will offer to *Apply custom defaults* for your board — accept it. If you'd rather have a board-baked build, open an [issue](https://github.com/danusha2345/ADRC-betaflight/issues) and we'll add it to the matrix, or build it yourself with `make <TARGET>`.

⚠️ Experimental flight-controller firmware, so far tested by a handful of pilots. Fly in an open area, keep props away from people, and please report results (good or bad) in [issue `#1`](https://github.com/danusha2345/ADRC-betaflight/issues/1).
