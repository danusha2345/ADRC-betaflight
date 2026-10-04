# ADRC math review — the rate loop as implemented (2026-10-01)

Scope: `src/main/flight/adrc.c` / `adrc.h` and the ADRC path of `pid.c` on the PR line
(`adrc-sync-1001` = bvandevliet `adrc-toggle` + master afe6a86dc5, the head of betaflight#15400 after
bvandevliet/betaflight#4). The question asked was not "does it fly" (it does) but "is the math right, and
can it be improved or simplified". Method: a line-by-line read of the controller, then a numerical model of
the loop *exactly as coded* (forward-Euler ESO at 8 kHz, predict-then-correct order, pt2 pre-filter, one-loop
output delay, z3 leak and clamp) against a rate plant with a first-order motor lag,
`ω' = b_acc·T`, `τ·T' = u − T`. Scripts and raw output: `docs/tools/adrc_math_review/`. The discrete model
was cross-checked against a sampling-free RK45 integration (overshoot agrees to 0.1 %).

## 1. What the code does (verified)

Per axis, every PID loop:

```
e      = z1 − pt2(gyro)                              // observer error, pt2 at adrc_gyro_lpf_hz (150)
z1    += dT·(z2 − 3wo·e)
z2    += dT·(z3 + b0·u_prev − 3wo²·e)                // b0·u only while the liftoff gate is open
z3     = z3 − dT·σ·z3 − dT·wo³·e                      // σ = adrc_sigma_decay/10 airborne; growth inhibited while gated / mixer pinned
z3     = clamp(z3, ±pidsum_limit·b0)
u      = ( wc²·(r − z1) − 2wc·z2 − z3 ) / b0           // P, D, I as published in the log
Sum    = u + F + S  →  mixer;  u_prev = clamp(Sum)     // the observer sees what the mixer got
```

with `b0 = adrc_b0 × schedule(throttle)` used consistently in both the observer and the law. This is textbook
bandwidth-parametrised LADRC for a second-order plant (Gao 2003): ESO poles at −wo (triple), virtual PD
critically damped at wc. Checked and found correct: the β gains (3wo, 3wo², wo³); the sign of the D term; the
predict-then-correct ordering (u uses the state already corrected with this loop's gyro sample); the b0·u term
using the previous loop's applied output (consistent with ZOH); the z3 clamp bounding |I| at pidsum_limit;
the leak sitting *inside* the observer loop (see §4); the ground-wc cap formula (`dgain·b0/(2wo)` is
conservative by ~1.4×, since the observer's derivative peak is 0.7·wo, not wo); the z1 estimate never
overshooting the gyro by more than 5 % (so P acting on z1 instead of the filtered gyro is harmless).

Forward Euler is adequate: wo·dT = 0.0125 at wo = 100 / 8 kHz, three orders below where the discretisation
matters. RK4 (suggested in fork issue #1) would change nothing measurable.

## 2. The structural finding: the motor pole lives in z3

The physical plant is first order plus actuator lag. Written in the ESO's form,

```
ω'' = (b_acc/τ)·u − ω'/τ      ⇒   b0 = b_acc/τ ,   f = −ω'/τ
```

so **b0 is not "thrust-to-weight"; it is angular acceleration per unit command divided by the motor time
constant**, and the "disturbance" z3 permanently carries the plant's own term −ω'/τ. The ESO tracks that term
with lag, and during a rate step the lag shows up as overshoot, even with b0 exactly right:

| tune (wc, wo) | τ = 8 ms | 12 ms | 20 ms | 30 ms |
|---|---|---|---|---|
| (40, 70) | 24.7 % / 140 ms | 19.4 % / 125 ms | 13.6 % / 111 ms | 9.9 % / 102 ms |
| (60, 100) default | 20.3 % / 85 ms | 15.5 % / 77 ms | 10.4 % / 69 ms | 7.3 % / 65 ms |
| (99, 110) Air65 | 18.5 % / 56 ms | 14.0 % / 50 ms | 9.5 % / 45 ms | 6.7 % / 42 ms |
| (103, 140) 5" | 16.3 % / 47 ms | 12.1 % / 43 ms | 7.9 % / 39 ms | 5.4 % / 37 ms |
| (122, 128) | 16.7 % / 44 ms | 12.5 % / 39 ms | 8.3 % / 36 ms | 5.8 % / 33 ms |

(overshoot / 10–90 % rise on a 100 °/s step; b0 matched; linear region, no clamp engaged.) The dimensionless
number is wo·τ: 2.4 % overshoot needs wo·τ ≈ 6, i.e. wo ≈ 300 rad/s for a 20 ms motor and ≈ 600 for an 8 ms
whoop motor. Nobody flies there, because wo is also the D-term filter (§3), so the flown tunes sit at
wo·τ ≈ 1–2 and carry 8–18 % overshoot by construction. Faster motors make it *worse*, not better: the term
−ω'/τ the observer must learn grows as 1/τ. Magnitude and direction agree with the 8ksal8 corpus (peak gyro / peak setpoint on steps > 200 °/s:
1.06–1.14 at both 40/70 and 92/120, with the share above 1.2 falling from 20 % to 0 % as wc/wo rose;
`pr15400-8ksal8-airmode-rxsmoothing`, proxy B); it is a model, not a validation.

This is also what the removed per-axis damping ratio (ADRC-032, `adrc_zeta_*`) was compensating by hand.

**Candidate improvement A — put the motor pole in the observer.** Two lines:

```
z2 += dT·(z3 + b0·u_prev − z2/τ − 3wo²·e)
u   = ( wc²·(r − z1) − (2wc − 1/τ)·z2 − z3 ) / b0
```

z3 then holds only what is not in the model; the closed loop is the one the bandwidth design promises.
Modelled effect, same tunes, τ_model = τ:

| | plain | motor pole in ESO |
|---|---|---|
| (60,100), τ 20 ms: rise / overshoot | 69 ms / 10.4 % | 53 ms / 0.0 % |
| (60,100), τ 10 ms | 80 ms / 17.6 % | 52 ms / 0.0 % |
| Air65 (99,110,5378), τ 8 ms | 56 ms / 18.5 % | 30 ms / 0.0 % |
| gyro-noise gain into pidsum, (60,100) τ 20 ms | 0.85 | 0.65 |
| phase margin, (60,100) τ 20 ms | 60° | 45° |
| disturbance step 2000 °/s², peak | 28.1 °/s | 30.8 °/s |

Robust to a wrong τ: τ_model = 2τ still halves the overshoot (4.7 %), 0.7τ gives none. With b0 under-estimated
2× the overshoot stays at zero and the phase margin matches the plain law's (27°). Costs: 8–15° of phase margin
(the plain law was effectively detuned), one more number per craft, and the constraint 1/τ < 2wc (otherwise
the effective D gain goes to zero; with wc = 60 that means τ > 8 ms, so whoops need wc ≥ 100 or a floor on
the D gain). τ is obtainable from the same step-response logs the b0 fitter uses. Field slot: the PG version
is at its 4-bit ceiling, so the field would have to replace one (`adrc_td_hz`, see §5). **Status: model only;
needs a tester A/B on one craft with debug_mode = ADRC before anything else.**

### 2b. Checked against the logs (2026-10-01)

23 tester logs with `debug_mode = ADRC` (Petrel75 ×17, Air65 ×2, THIII+ ×2, AOS 3.5, Pavo20; all 8ksal8's,
b11-exp8…b11), 726 stick moves (setpoint change ≥ 150 °/s within 100 ms, gate open). For every move the loop model
— the law exactly as coded with that log's wc/wo/b0, `adrc_gyro_lpf_hz`, `adrc_sigma_decay` and pidsum limit — is
driven by the logged setpoint from the logged ESO state (z2, z3, u) against the lagged plant, and the plant
(b_acc, τ, delay) is chosen per log and axis to minimise the median RMS error between simulated and logged gyro
(`docs/tools/adrc_math_review/log_check3.py`, output in `logcheck3_out.txt`). Peak ratio = (peak gyro − start) /
(peak setpoint − start) over the move.

| | median | IQR |
|---|---|---|
| logged peak ratio | **1.085** | 1.05–1.12 |
| model as coded, fitted lagged plant | 1.033 | 1.02–1.05 |
| motor-pole variant, same plant and moves | 0.996 | 0.98–1.02 |
| replay error, lagged plant | 5.6 % of peak | 4.7–6.5 % |
| replay error, no-lag plant (gain re-fitted) | 7.0 % | 6.1–8.3 % — lagged better in 45 of 46 log/axis cases |
| fitted τ | 15 ms | 11–36 ms |
| wo·τ at the flown wo | 1.5 | 1.2–3.2 |

Per craft (roll / pitch, logged → coded → motor-pole): Petrel75 1.11/1.07 → 1.03/1.03 → 1.00/0.99;
Air65 1.10/1.12 → 1.05/1.06 → 1.01/1.00; THIII+ 1.11/1.05 → 1.06/1.03 → 1.02/1.00; AOS 3.5 1.07/0.99 → 1.03/1.00 →
1.01/0.98; Pavo20 1.10/1.01 → 1.01/0.98 → 0.99/0.97. Share of moves with more than 10 % overshoot: logged 40–55 %,
coded model 20–30 %, motor-pole variant 10–15 %.

Reading: the flown tunes do carry 5–12 % overshoot on ordinary stick moves (less than the 8–18 % of the ideal step
in §2, as a ramp excites less); a plant with a motor lag explains the logged responses better than one without,
consistently; the model as coded reproduces the shape but under-predicts the overshoot by ~0.05 (the gyro filter
chain, dyn notch, RPM filter and ESC are not in it, and the grid mostly chose zero extra delay); and the motor-pole
law, on the same plant and the same inputs, removes most of what the model does reproduce. What the logs cannot do
is pin τ: stick moves have no energy above ~5 Hz, so b_acc and τ trade off along a ridge (the fitted b_acc/τ runs
0.5–2.4 × the configured b0, often at the grid edge). A Betaflight **chirp** flight (upstream's in-flight system
identification, now also on the angle controller via #15196) on one ADRC craft would give the plant transfer
function directly and settle τ, b0 and the delay in one log. Also worth noting: all 23 logs run
`adrc_gyro_lpf_hz = 0`, and 14 of them `adrc_sigma_decay = 0` — the tester already flies the pure integrator and no
pre-ESO filter.

### 2c. Chirp confirmation (8ksal8, US25 = THIII+ 2.5", 2026-10-01)

8ksal8 had already flown chirps on ADRC and posted two logs in #15400 (comment 5937565409). `US20` decodes to
4.5 s only (75 % of iterations missing in the 16 MiB file) and is unusable; `US25` (wc 81 / wo 90 / b0
6560/3936/2624, FIXED law, `adrc_gyro_lpf_hz` 0, σ 0, pidsum 1000, PID 4 kHz, log 1 kHz) has one 0.2→500 Hz,
16 s sweep per axis. The sweep is exogenous, so H = S_ry/S_ru is an unbiased plant estimate even in closed loop
(`docs/tools/adrc_math_review/chirp_id.py`, output `chirp_out2.txt`).

| | roll | pitch |
|---|---|---|
| coherent band | 1.7–60 Hz | 1.7–66 Hz |
| plant fit `b_acc·e^(−sd)/(s(1+sτ))` | b_acc 135 °/s²/unit, **τ 21.1 ms**, delay 2.2 ms (err 0.085; lag-only 0.24) | b_acc 93, **τ 21.4 ms**, delay 2.3 ms (err 0.060; lag-only 0.26) |
| b_acc/τ vs configured b0 | 6413 vs 6560 (**0.98**) | 4345 vs 3936 (**1.10**) |
| wo·τ, wc·(τ+d) | 1.9, 1.9 | 1.9, 1.9 |
| margins with the *measured* plant | PM 55° at 10.8 Hz, GM 8.0 dB at 29.5 Hz | PM 49° at 13.3 Hz, GM 7.6 dB at 29.5 Hz |
| closed-loop \|T\| measured / model as coded (3, 8, 20, 40 Hz) | 1.11/1.09, 0.43/0.44, 0.23/0.23, 0.086/0.087 | 1.08/1.06, 0.45/0.45, 0.28/0.28, 0.106/0.102 |
| step overshoot on this plant: coded → motor-pole | 11.1 % → 0.2 % (rise 59 → 42 ms; PM 56° → 41°) | 9.6 % → 0.0 % (rise 59 → 43 ms; PM 51° → 39°) |

So, on real hardware: the plant is an integrator plus one 21 ms motor lag and 2 ms of delay; **b0 = b_acc/τ to
within 2–10 %** of what the tester flies; the loop model as coded reproduces the measured closed-loop response
across the band; the margins sit where the wc·τ table of §3 puts them; and the flown wo·τ ≈ 1.9 is the regime
where the plain law carries ~10 % step overshoot that the motor-pole law would remove.

**Yaw is a different plant.** |H|·ω rises from 26 to 70 between 2 and 50 Hz with a positive phase at low
frequency: a zero at ≈ 7.7 rad/s (reaction torque from motor acceleration, fast) ahead of the 26 ms lag and 2.6 ms
delay (lead+lag+delay fit err 0.056; the lag-only model fails at 0.20). The second-order ESO model does not
describe it, "b0 = b_acc/τ" is meaningless there, and the loop as flown (81/90/2624) is close to the edge: PM 11°
at 59.7 Hz, GM 1.2 dB, closed-loop peak 2.8× at 65 Hz — the "60 Hz yaw line" the tester has reported since
September is this resonance. Lower yaw wc/wo (the default yaw wo = 80 exists for a reason) or a yaw-specific
model are the options; the motor-pole variant is not applicable to yaw in this form.

### 2d. Flight A/B of the motor-pole law (ADRC-036, tester builds mp1/mp2)

`adrc_motor_tau_ms` (0 = the plain law, bit-identical) puts the motor pole into the observer on roll and pitch.
Three A/Bs so far, each the same craft and tune with only τ changed (scripts: `docs/tools/adrc_math_review/ab_mp1.py`,
`ab_mp2.py`).

**jmsweng, 2.5", wc 80 / wo 90, b0 4616/3636, τ 0 vs 22 ms, chirp on every axis in both flights (2026-10-04).**
The chirp gives the measured closed-loop response T = S_ry/S_rr directly, same axis, both laws:

| | roll, τ = 0 | roll, τ = 22 | pitch, τ = 0 | pitch, τ = 22 |
|---|---|---|---|---|
| \|T\| peak | 1.09 | 0.98 | 1.09 | 0.99 |
| −3 dB bandwidth | 5.8 Hz | **15.5 Hz** | 6.3 Hz | **20.3 Hz** |
| \|T\| at 8 / 12 Hz | 0.46 / 0.34 | 0.77 / 0.85 | 0.51 / 0.47 | 0.82 / 0.82 |
| phase at 5 Hz | −60° | −35° | −75° | −37° |
| stick moves: peak/setpoint, share > 10 % over | 1.08, 33 % (21) | 1.00, 18 % (17) | 1.09, 43 % (21) | 1.06, 29 % (7) |
| D term RMS | 22.4 | 11.2 | 20.7 | 10.2 |
| plant from the chirp | τ 24.0 ms, d 2.2 ms | τ 21.1 ms, d 3.1 ms | (poor fit) | τ 20.6 ms, d 3.0 ms |
| phase margin, measured H × controller model (plant from the τ = 0 / τ = 22 flight) | 53° / 43° | 40° / 31° | 63° / 33° | 49° / 27° |
| same through the fitted plant | 44° / 36° | 32° / 27° | 42° / 35° | 33° / 27° |
| gain margin, measured H (fitted plant) | 2.4 dB (4.7–6.8) | 4.5 dB (4.8–7.0) | 3.1 dB (3.5–4.4) | 3.7–3.8 dB (3.9–4.6) |

The resonance peak is gone and the tracking bandwidth is 2.7–3.2× wider; the D term does half the work. The loop
model on the plant fitted from these chirps gives the same (−3 dB at 5.3–5.8 Hz plain, 15–20 Hz with the pole;
T peak 1.05–1.11 against the measured 1.09 plain, 0.98–1.00 against 0.98/0.99 with the pole). The price is
**7–14° of phase margin on the same plant** (the two flights' plant estimates differ by more than that, hence
two values per cell) and no gain margin. Yaw, which keeps the plain law, is unchanged (peak 1.19 at 47 Hz in
both). Calm-flight gyro RMS per segment is ~1.3 °/s higher with the pole (median 4.9 → 6.3 roll, 5.5 → 6.7 pitch)
on a day the pilot called extremely windy; yaw, flying the same law in both, rose by the same amount (5.5 → 6.7),
which points at the conditions rather than the pole — a calm-day repeat would settle it.
The tune itself is close to the ceiling with either law: gain margin 2.4–4.5 dB from the measured response
(3.5–7 dB through the fitted plant), phase crossover at 21–27 Hz. wc·τ is 1.7–1.9, and b_acc/τ is 1.07–1.25× the
roll b0 and ~1.3× the pitch b0 (b0 slightly low). b0 × 1.25 gives back ~2 dB and 6–11° with either law
(`ab_mp2_margins.py`, `ab_mp2_margins_out.txt`).

**jmsweng, 5", wc 80 / wo 90, b0 2529/2692, τ 0 vs 23 ms, no chirp.** Pilot: "didn't really notice any differences".
Logs: share of moves > 10 % over 23 → 12 % (roll), 33 → 29 % (pitch); 50 % lag 31 → 28 ms, 17 → 16 ms; D term RMS
33 → 25 and 32 → 21; motor 40+ Hz RMS 19.7 → 17.6. Same direction, smaller.

**jmsweng, 5", suspended weight (a filament spool on a string), τ = 23, same tune.** Not a τ result: the flight
ended on a stopped motor. At 14.9 s, in a low-throttle descent (0.5 g), `motor[1]` stops answering — commanded to
2047, eRPM falls to ~14 and stays there, with a 56 A spike at the stall; the other three keep answering. The craft
flies about 1.6 s on three motors (rates ≤ 371/230/537 °/s up to 16.5 s) and hits the ground at 16.59 s; the 1400–2150 °/s in the
log are that impact. Before the stop the yaw axis was already at its limit (7–13 s: one diagonal pair averaging
1430/1050 against 650/570, a motor at idle half of the time, yaw I touching its 400 bound, yaw rate up to
590 °/s with the stick centred); a motor was at max 8 % of the time (`ab_mp2_weight.py`). An earlier reading of
this log as "past authority, z3 on its clamp" was wrong — it had not looked at eRPM.

**8ksal8, Pavo20 Pro II, 85/100, τ 0 vs 12 ms (2026-10-02)** — τ set below the chirp-measured 33/27 ms: 50 % lag
17 → 6 ms and 25 → 9 ms, typical overshoot no worse, but the 90th-percentile calm-flight segment worse (12.7 →
17.2 °/s); the model puts the phase margin at 45° → 21° for that mismatch. **A τ below the real one costs margin;
measure it (the plant-fit tool reports it) or err high.**

## 3. Stability ceiling and noise: what wc, wo and b0 actually trade

Loop margins (plant as above, gyro lpf1 250 + lpf2 500 + ADRC pt2 150, b0 matched):

| τ | motor pole | max wc for PM ≥ 40°, GM ≥ 6 dB (wo = 1.2 wc) | wc·τ |
|---|---|---|---|
| 5 ms | 200 rad/s | 255 | 1.3 |
| 10 ms | 100 | 175 | 1.75 |
| 15 ms | 67 | 135 | 2.0 |
| 20 ms | 50 | 110 | 2.2 |
| 30 ms | 33 | 85 | 2.55 |
| 40 ms | 25 | 70 | 2.8 |

So **the stability ceiling is wc·τ ≈ 2**, set by motor lag, not by wc alone: a 5" with 20 ms motors tops out
near wc 110, a 7" with 40 ms motors near 70, a whoop with 8 ms motors could in principle run 200. The code
comment "the practical ceiling is noise, not stability" is true for fast motors and false for slow ones.

b0 mismatch at (60,100), τ 20 ms: b/b0 = 0.5 → PM 56°, GM 16 dB (slow, safe); 1.0 → 60°/9.8 dB; 1.5 → 43°/6.3 dB;
2.0 → 27°/3.8 dB; 3.0 → 2°/0.3 dB. **A 2× under-estimate of b0 is the edge; 3× is unstable. Over-estimating only
slows the loop.** This is the quantitative version of the README's "round up if unsure".

Noise. The code comment attributes the noise sensitivity to kp = wc². Per path (RMS pidsum per unit white
gyro noise, default filters, (60,100,2000)): P 0.23, D 0.54, I 0.23, total 0.85; at 50 Hz |D| = 4.1 vs |P| = 1.5.
**The D path (2wc·z2/b0) dominates, and wo sets its bandwidth**: |z2/y| peaks at 0.7·wo (71 at wo = 100) and
falls as 3wo²/ω above it, so any motor line above wo grows with wo². In other words wo *is* ADRC's D-term
filter; the pre-ESO pt2 at 150 Hz is a weak second lever (−11 % noise RMS for −5° phase margin under default
gyro filters; −15 % / −5° with lpf1 off). For comparison, classic BF defaults P45/D30 with dterm lpf1 75 +
lpf2 150 give 1.18 on the same measure, so the ADRC default is the quieter of the two. Suggest correcting
the comment and saying this in the gain guide: raising wo buys disturbance rejection and (per §2) less
overshoot, and pays in D-path noise, exactly like lowering dterm_lpf in classic.

## 4. The leak, once more (fork issue #1)

σ = 0.3/s sits inside the observer loop (`z3 += dT·(−σ·z3 − wo³·e)`), so it only moves where z3 settles, not how
fast it follows: closed loop, z3 holds 99.1 % of a step disturbance at (60,100) and 99.2 % in the Air65 25 %
payload case, leaving 0.3 and 1.1 °/s of steady rate error; peak error unchanged to 0.1 °/s
(`docs/tools/z3_leak_sim.py`). `adrc_sigma_decay = 0` is the pure integrator. Nothing to change.

## 5. Equivalent PID (Carlson 2025 applied to this law)

With u substituted into the ESO, the measurement path u/(−y) is a PID through a second-order filter:

```
Kp = wc·wo²·(3wc + 2wo) / (b0·Δ)      Ki = wc²·wo³ / (b0·Δ)      Kd = wo·(3wc² + 6wc·wo + wo²) / (b0·Δ)
filter: s² + (2wc + 3wo)·s + Δ,   Δ = wc² + 6wc·wo + 3wo²       (σ = 0; with σ > 0 the integrator leaks)
```

| tune | Kp / Ki / Kd | BF-style P / I / D | measurement filter |
|---|---|---|---|
| (60, 100, 2000) default | 1.64 / 25.9 / 0.041 | 51 / 106 / 77 | 42 Hz, ζ 0.80 |
| (99, 110, 5378) Air65 | 1.03 / 21.8 / 0.020 | 32 / 89 / 37 | 53 Hz, ζ 0.79 |
| (103, 140, 3000) 5" | 2.54 / 62.2 / 0.041 | 79 / 255 / 78 | 63 Hz, ζ 0.79 |

(BF numbers via PTERM/ITERM/DTERM_SCALE.) Read: the ADRC default is a classic tune with a high D (77 vs 30)
behind a low (42 Hz) second-order D filter, and the three ADRC numbers pin the five PID+filter numbers to a
family with ζ ≈ 0.8. The setpoint path differs (P on the setpoint, no D on it, plus BF's own F). Useful as a
sanity map for maintainers and pilots; it is not a case for re-implementing ADRC inside the classic path,
because the z3 clamp semantics, the b0 schedule inside the observer and the gate logic have no PID equivalent.

## 6. Simplifications

- `adrc_td_hz`: a PT1 on the setpoint, not a tracking differentiator; off by default, unvalidated, and RC
  smoothing + F already do this job. Drop it (frees the profile slot that §2 would need).
- `adrc_gated_z3_decay`: the inhibit does the real work; the rate only has to be ≥ σ and ≥ 1/s. A constant.
- `adrc_gyro_lpf_hz`: keep, but document it as a weak lever (§3); wo is the filter.
- Comment fixes: the noise attribution (§3); "the practical ceiling is noise, not stability" → wc·τ (§3).
- Log readers: the published I = −z3/b0 carries −ω'/τ during manoeuvres, so it swings with acceleration and is
  not comparable with classic I; "z3 stays high while flying hard" is the model, not a fault.

## 7. What was not found

No sign error, no unit error, no discretisation problem, no clamp that engages in normal flight, no
inconsistency between the b0 used by the observer and by the law, no benefit from a reduced-order ESO
(|z1/y| ≤ 1.05) or from RK4. The feedforward BF adds on top is physically meaningful here too
(u_ff = ṙ/b_acc); with b_acc ≈ 40 °/s² per unit it corresponds to F ≈ 180, close to the default 120.

## 8. Caveats

Everything above assumes a linear first-order motor lag, a matched b0 and 8 kHz loops; real crafts add ESC
and prop dynamics, frame modes and the dyn-notch/RPM-filter delays. The fitter's b0 may already absorb part
of the lag structure, which would move the τ that the model wants. The step-overshoot table and candidate A are
therefore hypotheses with numbers attached, to be checked against logs (step inputs at fixed wc, two wo
values) before any code moves.
