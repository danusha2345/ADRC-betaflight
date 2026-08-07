# b8 on a 5" Mamba — first flights, and a gate blind spot found on hardware

**Craft:** Mamba MAMBAF722_I2C (STM32F7X2), 5", 2207/1300 kv, 6S.
**Firmware:** `432d5320a` — `adrc-gate-b7` (`0e34aff0e3`) plus the fork-side `adrc_b0_law`
selector, i.e. exactly what ships as the b8 prebuilt.
**Tune:** `pid_type = ADRC`, `wc 40/40/40`, `wo 120/120/120`, `b0 4000/4000/4000`,
`adrc_liftoff_throttle = 40`, `adrc_hover_throttle = 35`, `debug_mode = ADRC`,
`thrust_linear = 20`.
**Loop:** `looptime 125`, `pid_process_denom 2` (4 kHz), `blackbox_sample_rate 1/2`.

Seven logs, indoors:

| file | what it is | duration |
|---|---|---|
| `handshake_noprops_btfl_000.bbl.gz` | props off, frame shaken by hand, then throttle | 51.4 s |
| `tethered_btfl_001.bbl.gz` | props on, tethered to a weight plate | 36.8 s |
| `freeflight_btfl_002.bbl.gz` | props on, free hover indoors | 89.4 s |
| `loaded_1kg_btfl_003.bbl.gz` | props on, 1 kg payload, hovering just off the floor | 32.5 s |
| `threshold60_btfl_004.bbl.gz` | same, with `adrc_liftoff_throttle = 60` (workaround attempt) | 25.4 s |
| `z3fix_btfl_005/006.bbl.gz` | same, on the fixed firmware `3c85c4b5a` | 21.9 / 31.5 s |

## Tooling note, and a warning about MSP dataflash dumps

The first three logs were pulled over MSP with a script that stripped only 4 bytes of reply
header. The actual reply is `address(u32) + readLen(u16) + compressionMethod(u8)` —
**7 bytes** (`msp.c`, `serializeDataflashReadReply`), so three bytes of framing were written
into the log body every 4096 bytes: 2405 corruptions in one 9.8 MB dump.

That is also what "hangs `blackbox_decode`" looked like: the NUL landing at offset 4096 ends
`parseHeaderLine()`, the parser stays in `PARSER_STATE_HEADER`, and the main loop has no
branch for "header state, byte is not 'H'" — `streamPeekChar()` does not advance, so it
spins forever. Repairing the three bytes makes the stock decoder read the same file in
0.2 s. The logs published here are repaired; the fourth was pulled with the fixed script and
needed no repair.

Two genuine decoder defects surfaced along the way and are worth reporting upstream:
that missing branch (infinite loop instead of an error), and `streamPeekChar()` returning
`*(const char*)`, so a `0xFF` data byte reads as EOF and truncates the log silently.

`iframe_parse.py` here reads I-frames only; it was written while the decoder was unusable.
It produced ~1.2 % false frames (stray `I` bytes inside payload), which is why every number
below comes from the stock decoder on repaired files instead.

## 1. Free flight: the controller is clean

89 s of indoor hover, gate open from 15.08 s:

| metric | value |
|---|---|
| tracking error (roll/pitch), median | **2 °/s** |
| p90 | 3 °/s |
| frames with any motor on a rail | **0.7 %** |
| gate closures after opening | 0 |

With the 1 kg payload (mean collective 36.6 % against ~19 % unloaded), 32.5 s:

| metric | value |
|---|---|
| tracking error, median | **6 °/s** |
| p90 | 16 °/s |
| frames with any motor on a rail | 2.8 % |
| gate closures after opening | 0 |

No limit cycle, no re-latching. These are the first flights on this branch.

## 2. The gate opens through the gyro path; the applied path is still unexercised

| log | gate opens | stick | applied collective | gyro |
|---|---|---|---|---|
| props off | 30.3406 s | 39.0 % | 35.2 % | — |
| free flight | 15.080 s | 21.0 % | 18.7 % | 21 °/s |
| 1 kg payload | 16.986 s | 34.2 % | 31.8 % | 30 °/s |

Only the props-off log opened through the direct throttle test, and only because
`thrust_linear = 20` scales 39 % of stick to 41.6 % of command, past the 40 % threshold. The
two flights opened through the gyro path: stick above the idle floor (half the threshold)
plus sustained rotation.

Across all four logs there is **not one frame** where the applied collective sat above the
threshold while the stick was below 20 %. The applied-collective path added in b7/b8 has
therefore still never been exercised on hardware — not here, not on @8ksal8's ten logs, not
on @bvandevliet's bench. Testing it needs `adrc_liftoff_throttle` set deliberately below the
collective that ground oscillation produces (~25 on this craft).

## 3. Props off, 30 s of shaking, gate stayed shut

The cleanest negative control we have: **60 595 consecutive frames** with the gate closed,
stick at 0.0 %, and the gyro **above the 20 °/s gate threshold 64.8 % of the time**
(median 41 °/s, p90 169, peak 306). Before the idle interlock that rotation would have
opened the gate in 25 ms. Not one sample had `|gyro| > 20 °/s` while the stick was above the
idle floor, which is exactly what the interlock is meant to guarantee.

## 4. ADRC-026 nearly reproduced on a third craft

Tethered log, t = 26.313 s: applied collective **39.6 %** with the throttle stick at
**0.0 %** and gyro 466 °/s, against a 40 % threshold. It missed by 0.4 percentage points.

Third independent measurement of the mechanism, after @8ksal8's ten arms (where it did open
the gate) and @bvandevliet's bench (24.1 % against 30 %). The gate correctly did not open —
because the threshold was not reached, not because a guard fired.

The tethered log is not usable for anything else: after the gate opened, 97 % of frames have
a motor on a rail and gyro reaches 1049 °/s. The tether pins the craft and it fights it.

## 5. Finding: the z3 growth inhibit has a blind spot before liftoff

Reported symptom: *the craft tips over on takeoff and has to be corrected with the stick.*
Part of that is expected — this is a rate controller, so a craft that leaves the ground
tilted keeps its tilt. But the logs show a real contributor.

`inhibitZ3Growth = !liftoff && throttleAtIdle`, and `throttleAtIdle` is
`commanded < 0.5 * liftoffThrottlePercent` — the same signal that unblocks the gyro gate
path. So the moment the stick passes half the liftoff threshold, the inhibit is lifted while
the craft is still on the ground and the gate is still shut.

Measured on two flights:

| log | inhibit released at | gate opened at | **blind window** | peak z3 (logged, ×16 for real) | motor spread |
|---|---|---|---|---|---|
| free flight | 14.50 s, stick 20.1 % | 15.08 s | **0.6 s** | 2401 | 7 → 183 |
| 1 kg payload | 11.40 s, stick 20.0 % | 16.99 s | **5.6 s** | 1312 | → 129 |

The heavier and smoother the takeoff, the longer the observer charges its disturbance
estimate against a plant the ground is holding — with the payload it ran for nearly six
seconds. Whatever it accumulates is carried into the first airborne loop. The inhibit exists
precisely to prevent this; it is defeated because it keys on throttle rather than on the
gate itself.

## 6. The configuration workaround does not work — measured, then retracted

Before touching code we tried the obvious thing: raise `adrc_liftoff_throttle` from 40 to
60, so the idle floor moves from 20 % to 30 % and the blind window shrinks.
`threshold60_btfl_004.bbl.gz`, same craft, same payload, same flying:

| | threshold 40 | threshold 60 |
|---|---|---|
| inhibit released at stick | 20.0 % | 30.0 % |
| blind window | 5.58 s | **0.86 s** |
| peak \|z3\| inside the window | 1312 | **1491** |
| \|z3\| at gate open | 411 | **1054** |
| \|z3\| 0.5 s after gate open | 3063 | **7277** |
| tracking error, median | 6 °/s | 8 °/s |

The window shrank 6.5×, exactly as predicted — and it made no difference, because the
estimate plateaus fast: within the first **0.25 s** after the inhibit releases, `|z3|`
already reaches 887 at threshold 60, against 997 accumulated over the whole 5.58 s at
threshold 40. Worse, the higher threshold opens the gate later, so the craft meets liftoff
with more windup, not less (1054 vs 411). The pilot reported no perceptible difference,
which matches.

So the duration of the window is not the variable that matters. Only the code fix is.

## 7. Fix verified in flight

`inhibitZ3Growth` now keys on the gate alone (`!liftoff`), dropping the `throttleAtIdle`
term that created the blind spot. Dropping it does not reintroduce ADRC-020: the gate
latches for the rest of the arm cycle, so airborne `liftoff` is true and the inhibit cannot
engage whatever the stick does.

Two short flights on the fixed firmware (`3c85c4b5a`), same craft, same 1 kg payload —
`z3fix_btfl_005.bbl.gz` and `z3fix_btfl_006.bbl.gz`:

| | flight 1 | flight 2 |
|---|---|---|
| gate opened | 9.12 s, stick 32.7 % | 5.75 s, stick 33.1 % |
| max stick before the gate | 32.7 % | 33.2 % |
| **max \|z3\| before the gate** | **0** | **0** |
| \|z3\| 0.5 s after the gate | 3678 | 5019 |
| tracking error, median / p90 | 6 / 14 °/s | 6 / 15 °/s |
| frames with a motor on a rail | 0.2 % | 0.0 % |
| gate closures after opening | 0 | 0 |

`z3` is **exactly zero** until the gate opens in both flights, with the stick well past the
old idle floor of 20 %. The observer then charges normally once airborne, so the ADRC-020
behaviour is intact. Tracking is unchanged from before the fix (6 °/s median), and rail
contact dropped from 2.8 % to 0.2 % and 0.0 %.

This is the first change in this series verified by flight before publication rather than
after.
