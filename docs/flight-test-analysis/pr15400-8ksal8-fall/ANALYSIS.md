# @8ksal8's 2026-08-03 flight — the logging stop, and what the record does not contain

Source: PR comment 5172542092, `truncated_log.zip`
(SHA-256 `b23a79ed629752a3ac58087c4175ebd50a75fc34e8cd488945dcce7e57a0f08a`) →
`truncated_log.bbl`, 3 018 752 bytes, SHA-256
`46b24c1702ec3af42cab71f6e76cf62c42d36e3a52c0212e78dfbbc4b9515b01`.

Craft `Pavo20 Pro II`, `BETAFPVF405_ELRS`, firmware `2026.6.0-alpha (543f1a5ff)`
(b5), 3S, 1960 kV, bidirectional DShot, `debug_mode = ADRC`. Tune from the
headers: `adrcWC 120 130 300`, `adrcWO 125 125 150`, `adrcB0 4000 3000 26000`,
`adrc_b0_law 1` (SQRT), `adrc_hover_throttle 29`, `adrc_b0_scale_max 3`,
`adrc_gyro_lpf_hz 150`, `adrc_sigma_decay 3`, `adrc_gated_z3_decay 200`, liftoff
gate `34 / 20 dps / 25 ms` — a different tune from the `wo` pair of the day
before (roll/pitch `wo` now 125, `b0_yaw` now 26000).

**Scope.** The pilot reports that the craft fell later in the same flight and
that logging had already stopped before it. This write-up covers only the log:
where it stops, what state the craft was in at that point, and how its exported
signature differs from his earlier truncations. The fall itself is outside
the record and is not analysed here — nothing available identifies its cause.

## 1. The recorded window ends in an ordinary moment

33.296 s of logging, 65 562 samples at ~2 kHz, ending 33.462 s after the arming
beep (the `Sync beep` event at 30.650 s is written by
`blackboxCheckAndLogArmingBeep()`, i.e. it *is* the arm beep). No `Log clean end`
marker.

State in the last second:

| quantity | value |
|---|---|
| throttle (`rcCommand[3]`) | 1485…1603 while climbing |
| motor commands | 622…1732, no sample at the 2040 rail |
| eRPM | 1232…2703 on all four |
| pack | 11.31…11.60 V, 12.3 A mean (flight max 33.7 A) |
| `\|gyro − setpoint\|` max r/p/y | 30 / 34 / 10 dps |
| `\|I\|` max r/p/y | 59 / 155 / 27 (limits 500 / 500 / 400) |
| b0 throttle scale | 1.26…1.44, liftoff latch airborne throughout |
| GPS | 10 sats, 11 m/s, climbing 1.8 m/s |
| `failsafePhase` | `IDLE` for every sample |
| RX | valid on every sample after the first (row 0 is an init artefact) |

Loop timing is steady into the cut: interval median 0.507 ms, p99 0.510 ms, and
over the last 5 s the maximum is 0.889 ms. The one >1 ms excursion of the flight
(6.09 ms at 16.7 s) is not out of family — 11 unreadable loop iterations in
33.3 s is 0.33/s against 0.03–0.41/s across his other nine logs.

Two decoding notes, because both look alarming and neither is real. The header
gives `I interval 128, P interval 2`, i.e. `blackbox_sample_rate = 1/2` on a
4 kHz PID loop, which is why ~50 % of loop iterations are "missing". And the
CSV's `loopIteration` column is INC-predicted on P frames, so it advances by 1
per logged frame and jumps by 65 at each I frame; those jumps are the predictor
catching up, not lost data.

How much of the record is missing at the stop is only loosely bounded. The
flashfs RAM write buffer is 128 bytes (`FLASHFS_WRITE_BUFFER_SIZE`), and after a
power cycle flashfs re-finds the write head by a binary search over 2 KiB blocks
(`FREE_BLOCK_SIZE = 2048`), which is why the saved length is a multiple of 2048.
The file has no erased-flash (`0xFF`) tail. The chip's own erase-sector size is
not known from the log at all — it depends on the JEDEC ID (a W25Q128 is
256 pages × 256 B = 64 KiB per sector; a GD25Q128 is 4 KiB), which `flash_info`
would print.

## 2. This dump does not carry the signature of his earlier truncations

`corpus_probe.py` over all ten of his logs, decoded with the pinned decoder:

| log | bytes | MiB | duration | kB/s | logs | clean end |
|---|---:|---:|---:|---:|:--:|:--:|
| `truncated_log` | 3 018 752 | 2.879 | 33.296 s | 90.66 | 1/1 | **no** |
| `btfl_052` | 5 062 656 | 4.828 | 56.418 s | 89.73 | 1/1 | yes |
| `btfl_041` | 5 314 560 | 5.068 | 58.635 s | 90.64 | 1/1 | yes |
| `btfl_053` | 5 486 592 | 5.232 | 61.065 s | 89.85 | 1/1 | yes |
| `btfl_054` | 7 356 416 | 7.016 | 81.379 s | 90.40 | 1/1 | yes |
| `btfl_055` | 8 736 768 | 8.332 | 97.270 s | 89.82 | 1/1 | yes |
| `btfl_045` | 10 659 840 | 10.166 | 118.263 s | 90.14 | 1/1 | yes |
| `Yaw300wc_24kb0_160wo` | **16 777 216** | 16.000 | 184.231 s | 91.07 | 1/1 | **no** |
| `Yaw300wc_24kbo_150wo` | **16 777 216** | 16.000 | 183.132 s | 91.61 | 1/1 | **no** |
| `Yawb0_13k` | **16 777 216** | 16.000 | 184.273 s | 91.05 | 1/1 | **no** |

All ten carry the same `DeviceUID 004400513034510733373636`, the same craft name
and the same firmware, so this is one physical flight controller throughout: the
16 MiB figure is his chip, measured three times. Write rate is a tight
89.7–91.6 kB/s across every log.

The three earlier "cut short" logs are the dataflash written to its last byte.
The firmware path matches: when `isBlackboxDeviceFull()` trips, `blackboxUpdate()`
sets `BLACKBOX_STATE_STOPPED` directly, *without* `blackboxFinish()`, so a full
chip stops logging with no end marker. An ordinary disarm takes the other path
(`disarm()` → `blackboxFinish()` → `FLIGHT_LOG_EVENT_LOG_END`) whenever
`blackbox_mode` is not `ALWAYS_ON`, and his six clean logs show his logger does
write that marker.

This log stops at 3 018 752 bytes = 2.88 MiB and is `Log 1 of 1`, so no second
log was opened afterwards either. The exported dump is 2.88 MiB from a nominal
16 MiB device; the incident-time used offset and the actual free space were never
captured. What *is* measured is the dump's length, which comes from the FlashFS
free-space search performed at the next boot, plus a partition size inferred from
the three full dumps rather than read from the device. `flash_info` reports both
directly and would settle it.

Why the logger stopped is **not established**. The full-device path is the only
silent stop this firmware has been shown to take, and this dump does not carry
its signature. `isBlackboxDeviceFull()` is `flashfsIsEOF()`, which is only
`tailAddress >= flashfsSize` (`flashfs.c:638`), so an ordinary failed write does
not by itself move the logger into that path, and the explicit erase states are
excluded from it anyway (`blackbox.c`). A flash-subsystem fault remains a
candidate; no mechanism has been traced.

## 3. What the recorded window does and does not say about the motors

It says the obvious failure modes are absent *in it*: eRPM is non-zero on all
four motors in 100 % of samples, and a desync screen — command ≥ 900, steady
within 60 counts over the trailing 30 ms, eRPM below 70 % of that motor's own
command→eRPM fit, for ≥ 5 ms — returns zero hits. The RPM shortfalls a naive
static model flags (nine, 10–33 ms) all sit inside commanded spool-ups from
idle, which is rotor inertia.

It does not say the motors were "healthy". `eRPM/command` is not efficiency —
it moves with pack voltage, aerodynamic load and manoeuvre — and the ~4 % offset
between diagonals is stable but unexplained; attributing it to the CW/CCW prop
pair would need a bench test. The defensible statement is: *in the recorded
window this detector found no sustained desync signature*. The state of the motor
path later in the flight is not in the record.

Same for the controller: tracking error ≤ 34 dps, `|I|` ≤ 191 of 500 across the
whole flight, no rail contact in the last second, liftoff latch airborne — no
ADRC anomaly in the recorded window, and nothing about the unrecorded part.

And the same caveat applies to `failsafePhase = IDLE` and RX validity: those
cover the recorded window only. Because the absence of an end marker means the
logger stopped before any later disarm could be written, it does not exclude a
disarm or a failsafe after the cut — only during the record.

## 4. What is worth doing next

- **`flash_info` before anything else touches the chip.** It prints the JEDEC ID,
  the geometry and `FlashFS size=`/`usedSize=`, which pins the device type and
  the actual used offset. `flash_scan` tests the chip for write errors, but it
  **erases the flash first**, so it comes only after everything is saved. General
  order: pull the data, read `flash_info`, erase only when you have to.
- **The fall is not diagnosable from what exists.** The hardware is worth going
  over, but nothing in the record narrows it, and the record that would is the
  one that stopped earlier in the flight.
- **The two failures should be investigated separately.** Nothing found so far
  links them — which is not the same as knowing they are unrelated.
- **The logging failure is itself the thing to track.** It costs the evidence for
  everything else; whether it recurs, and under what conditions, is worth
  recording each time.

## 5. Claim ledger

| claim | verdict | basis | confidence |
|---|---|---|---|
| the log ends with the craft flying normally | POSITIVE | last second nominal on throttle, motors, eRPM, pack, tracking, ADRC state; loop timing steady to the last sample | high |
| the fall is inside the recorded window | NEGATIVE | pilot's own report, and the record ends in ordinary climbing flight with no precursor | high |
| this truncation has the same exported signature as his earlier ones | NEGATIVE | the three earlier ones are exactly 16.00 MiB — the full-device signature, same FC UID; this dump is 2.88 MiB | high |
| the cause of the logging stop is identified | NEGATIVE | the full-device path is the only silent-stop mechanism shown in this firmware, and the exported signature does not match it | high |
| free space at the moment of the stop is known | NEGATIVE | only the post-flight dump length is measured; the incident-time used offset was never captured | high |
| a sustained desync signature is present before the cut | NEGATIVE (recorded window only) | zero hits on the steady-command RPM-collapse screen | medium-high |
| the motors were "healthy" for the whole flight | NOT SUPPORTED | `eRPM/command` is not efficiency, and the record ends well before the event | — |
| an ADRC malfunction is visible before the cut | NEGATIVE (recorded window only) | tracking ≤34 dps, `\|I\|` ≤191 of 500, no rail, liftoff latch airborne | medium-high |
| RX loss / failsafe was involved | NEGATIVE (recorded window only) | `failsafePhase = IDLE`, RX valid; after the cut the log proves nothing | medium |
| the 6 ms mid-flight discontinuity is a precursor | NEGATIVE | 0.33 unreadable loop iterations per second here vs 0.03–0.41/s across his other nine logs | medium-high |

## 6. Reproduction

```bash
# from this directory; REPO is the checkout root, LOGS holds all ten .bbl files
DEC=$REPO/.scratch/tools/blackbox-tools/obj/blackbox_decode   # pinned build
"$DEC" --unit-acceleration g --unit-frame-time us --save-headers truncated_log.bbl
python3 fall_probe.py truncated_log.01.csv 30.650492          # sections 1, 3
python3 corpus_probe.py "$DEC" "$LOGS"                        # section 2
python3 energy_bug_repro.py truncated_log.01.csv              # decoder notes
```

## Decoder notes

`blackbox_decode` renders `flightModeFlags` with the old flight-mode table, but
the firmware logs `rcModeActivationMask` (`blackbox.c:1010`), so the column
labelled `ANGLE_MODE` is box bit 0 = `BOXARM` (`rc_modes.h`): the craft was armed
for the whole log and flying acro. Likewise `CALIBRATE_MAG` in `stateFlags` is
`GPS_FIX_EVER` in current firmware. This build of the decoder also has no
`DISARM` event type at all, so the absence of a disarm entry in the `.event`
sidecar carries no information.

`energyCumulative` is not a logged field either — the S-frame carries only
`flightModeFlags, stateFlags, failsafePhase, rxSignalReceived,
rxFlightChannelsValid` — and the column the decoder synthesises is wrong on this
log: 115 mAh against 51.18 mAh for the trapezoidal integral of the
`amperageLatest` column in the same CSV. `energy_bug_repro.py` re-implements the
decoder's arithmetic and lands on 115.3 mAh, so the mechanism is settled. Three
defects compound (raised separately against blackbox-tools, decoder
`f832acf9cd`):

1. **Seed.** `lastFrameTime` starts at `-1` (`blackbox_decode.c:1081`) and the
   `'P'`/`'I'` branch calls `updateSimulations(log, frame, lastFrameTime)` before
   assigning it (`:762` vs `:765`). That `-1` truncates to `0xFFFFFFFF` in the
   `uint32_t time` parameter; `battery.c`'s `lastTime != 0` guard skips the first
   call but stores it, so the *next* call computes `t₀ − 0xFFFFFFFF` with unsigned
   wrap ≈ 30.8 s. That is the 0 → 32 mAh step on CSV row 1. The merge branch uses
   the current frame time instead (`:707–709`), so the two paths disagree.
2. **Unit category error.** `amperageLatest` is centiamps (`current.h`), but the
   decoder pushes it through `flightLogAmperageADCToMilliamps()` (`:406`,
   `parser.c:860`), which treats it as a 12-bit ADC count: 1.84 A logged as
   184 cA becomes 148 mV and then 3700 mA — 2.011× the true value.
3. **`int16_t` parameter.** `currentMeterUpdateMeasured()` takes the milliamp
   value as `int16_t` (`battery.c:48`), so the mis-scaled peak of 67 850 mA wraps
   to 2314 mA. 3.2 % of samples in this log overflow — all the high-current ones,
   which is why the total lands at 2.25× rather than the ~2.7× the scaling alone
   would give.

The unparsed `currentSensor` header (`parser.c:439` knows only `currentMeter`) is
a separate compatibility observation rather than a fourth cause: it means the
defaults `offset 0, scale 400` are applied. Feeding the log's own `-300, 457`
through the same path would give 9803 mA for that 1.84 A sample — worse — which
is itself evidence that the conversion, not its constants, is the wrong
operation. Where the header renamed has not been traced.
