# ADRC math review — scripts

- `adrc_math_review.py` … `adrc_math_review4.py`: the loop model (symbolic equivalent PID, discrete frequency
  response of the controller as coded, margins vs motor lag, per-path noise, step/disturbance simulation,
  motor-pole-in-ESO variant). `OUTPUT.txt` is their combined output.
- `log_check3.py`: closed-loop fit of a lagged plant (b_acc, τ, delay) to logged stick moves and replay of the
  moves through the law as coded and through the motor-pole variant. Needs the CSV + `.headers.csv` from
  `blackbox_decode --save-headers` (raw units). `log_check.py` holds the loaders; `nolag_fit.py` is the no-lag
  baseline with its gain re-fitted. `logcheck3_out.txt`, `logcheck3_rows.json`, `nolag_rows.json`: results on
  the 23 logs of 2026-10-01 (8ksal8, Petrel75 / Air65 / THIII+ / AOS 3.5 / Pavo20).
- `chirp_id.py`: plant identification from a Betaflight chirp flight on ADRC (H = S_ry/S_ru, fits: lag+delay,
  lag, two lags, lead+lag+delay), margins and closed-loop T from the measured plant, model comparison and step
  prediction. `chirp_out2.txt`: 8ksal8's `US25` (THIII+ 2.5") chirp of 2026-10-01. (`adrc_math_review4.py`
  updated: the motor-pole controller now handles `adrc_gyro_lpf_hz = 0`.)
- `ab_mp1.py`, `ab_mp2.py`: A/B of `adrc_motor_tau_ms` on the same craft and tune (8ksal8 Pavo20 Pro II τ 0 vs 12;
  jmsweng 2.5" τ 0 vs 22 and 5" τ 0 vs 23, chirps in all four): measured closed-loop T from the chirp, plant fit, stick
  moves, calm segments, noise. Chirp windows come from the flight-mode flags (`blackbox_decode` names the CHIRP bit
  HEADFREE); an earlier setpoint-frequency heuristic missed sweeps that were switched off early. `ab_mp2_margins.py`: loop margins and modelled T for both laws on the plant
  measured in each of jmsweng's flights (raw H and fitted), with the b0 the firmware applied (base × logged schedule). `ab_mp2_weight.py`: timeline of the
  suspended-weight flight (a motor stops at 14.9 s). `*_out.txt`: their outputs.
