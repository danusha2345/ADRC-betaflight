
<img width="1376" height="768" alt="na" src="https://github.com/user-attachments/assets/eb513be2-56d0-4fa1-88e8-2a53b7f61d74" />


# Betaflight ADRC Controller (Active Disturbance Rejection Control)
[![Boosty](https://img.shields.io/badge/Boosty-Buy_me_a_coffee-FF7143?logo=boosty&logoColor=white&style=for-the-badge)](https://boosty.to/danusha/donate)

**English** | [Русский](README.ru.md)

This repository implements **Active Disturbance Rejection Control (ADRC)** on Betaflight, completely replacing the traditional PID loop. ADRC acts as a "PID Killer"—providing incredible stability, robust wind resistance, and smooth handling even with uncalibrated parameters, changing propeller sizes, or extreme, unbalanced dynamic payloads.

> ⚠️ **Experimental fork with ADRC robustness fixes — more flight testers wanted!**
> This fork carries a series of small, independent ADRC robustness fixes on top of
> `Boyyt357/ADRC-betaflight`: anti-windup on the disturbance estimate, saturation-aware
> observer feedback, ADRC-tuned defaults, zero-throttle observer handling, a liftoff gate
> for the observer, a per-craft System-Gain multiplier, and blackbox logging of the
> observer states. Several are **validated in real flights** (5" and 65 mm whoop, one
> independent pilot — takeoff bounce fixed, leaf-blower/stick-strike/prop-cut survival,
> blackbox-confirmed); hardware diversity is still tiny, so results from other stacks are
> the most valuable thing you can contribute. Each fix is its own commit
> (`git revert <sha>` to A/B). Details and flight evidence in [`ADRC_FIXES.md`](ADRC_FIXES.md).
> **Report in [issue #1 — Call for flight testers](https://github.com/danusha2345/ADRC-betaflight/issues/1).** 🙏

> 📦 **Don't want to compile? [Prebuilt hex files are in Releases](https://github.com/danusha2345/ADRC-betaflight/releases)** — 16 popular boards baked-in plus generic images for every mainstream MCU (F405/F411/F446, F722/F745, G473, H7 series, AT32F435). Flash via Configurator → *Load Firmware [Local]*.

---

## For more Info

[![ADRC Betaflight](https://img.youtube.com/vi/BLTQN-Gw7LE/0.jpg)](https://www.youtube.com/watch?v=BLTQN-Gw7LE)



---

## Key Features
- **No Heavy Tuning Required:** Flies exceptionally well even out of the box with rough, uncalibrated values.
- **Unbalanced Payload Handling:** Actively estimates and cancels external forces dynamically, allowing stable flight even with swinging weights attached to a single motor arm.
- **Propeller Versatility:** Dynamically handles transitions between different prop sizes on the fly without changing parameters.

---

## How it Works: Repurposing the PID Fields
Instead of standard Proportional, Integral, and Derivative gains, this implementation repurposes the Betaflight PID configuration fields to control the ADRC system:

| Field | ADRC Parameter | Description |
| :---: | :--- | :--- |
| **P** | **Control Bandwidth** | Dictates the response speed to errors. Higher values yield faster correction; lower values correct errors more slowly. |
| **I** | **Observer Bandwidth** | Controls the speed of the Extended State Observer (ESO). It dictates how fast the controller estimates and cancels external forces (e.g., wind, prop wash). *Note: Setting this too high can amplify gyro noise and heat up motors.* |
| **D** | **System Gain** | Informs the controller how powerful the motors are based on acceleration and KV rating. Decreasing this increases overall gain (for fast-accelerating motors); increasing it decreases overall gain (for smoother control). |

### Where to enter the values (Betaflight Configurator, PID Tuning tab)

There is no separate "ADRC" screen — you type the ADRC parameters into the **ordinary P / I / D cells** of the PID Tuning tab, per axis, exactly where PID gains normally live:

| Axis | **P** cell → Control Bandwidth (ω_c) | **I** cell → Observer Bandwidth (ω_o) | **D** cell → System Gain (b0 ÷ 10) |
| :--- | :---: | :---: | :---: |
| ROLL | 30 | 100 | 200 |
| PITCH | 30 | 100 | 200 |
| YAW | 30 | 80 | 200 |

*(example values = the community 5" tune below; the firmware defaults are 10 / 110 / 100 for roll & pitch and 10 / 80 / 100 for yaw — yaw runs a slightly lower observer bandwidth by default)*

Two things to know before you hit Save:

1. **Switch the Simplified Tuning sliders OFF first** (PID Tuning tab → slider mode → OFF / expert mode). If the sliders are active, the Configurator recomputes the P/I/D cells from the sliders on save and silently overwrites your ADRC values. For the same reason, don't touch the *Master multiplier* — under ADRC, scaling all cells together is meaningless.
2. The other fields keep (or lose) their meaning as follows:
   - **Feedforward (F)** — unchanged: still the standard Betaflight stick feedforward, applied on top of ADRC. Keep the defaults.
   - **D Max** — ignored (ADRC reads only the D cell, as System Gain).
   - **TPA** — effectively inert (it scales the legacy Kp/Kd coefficients, which ADRC does not use).
   - **Anti-gravity / I-term relax / I-term rotation** — legacy PID helpers; ADRC recomputes its I-term from the observer every loop, so they don't apply (the anti-gravity P-boost is explicitly disabled in this fork — fix #7a).

CLI equivalent, if you prefer it over the GUI: `set p_roll = 30`, `set i_roll = 100`, `set d_roll = 200` (same for `_pitch` / `_yaw`), then `save`.

**If the D cell maxes out** (typical on high thrust/weight builds — tiny whoops): don't chase more D. Set the per-craft System-Gain multiplier once in the CLI — `set adrc_b0_scale = 20` (default 10, range 1–100; b0 = D × scale) — then keep tuning the ordinary D cell in the GUI. The setting lives in the profile and shows up in `diff`/`dump` backups. When sharing your tune, mention the scale: the same D means a different b0 at a different scale.

It is **highly recommended** to disable PID at minimum throttle in case the initial ADRC parameters are incorrect for your drone — otherwise it may behave unpredictably on arm while you adjust parameters. In the Betaflight command line interface (CLI) run:
```
set pid_at_min_throttle = off
```

### Example Parameters
| Drone type | Control Bandwidth (P) | Observer Bandwidth (I) | System Gain (D) |
| :--- | :---: | :---: | :---: |
| 10" drone (author's video) | 10 | 50 | 20 |
| 5" drone (jmsweng, 2300 kV) | 40 | 160 | 200 |
| 5" drone (jmsweng, 1750 kV) | 40 | 160 | 250 |
| 5" drone (jmsweng, 1750 kV, blackbox-refined) | 30 | 100 | 200 |
| 65 mm whoop (jmsweng, Air65 clone, 1S, 30000 kV) | 15 | 65 | 250 (b0-limited — use `adrc_b0_scale`) |

### Tuning procedure (community, from @jmsweng)
A sensible step-by-step instead of guessing, starting from `10 / 50 / 20` (P/I/D):
1. **System Gain (D):** raise until the quad takes off stably (~70 on a 5"), keep raising until it makes a stuttering noise in hover, then back off ~20%. *(Overestimating b0 is fairly harmless; underestimating causes instability.)*
2. **Observer Bandwidth (I):** raise until stuttering/chatter appears in hover, then back off ~20%. *(Too high and the observer starts tracking gyro noise.)*
3. **Control Bandwidth (P):** set to ~¼ of the Observer Bandwidth (the wo ≈ 3–5×wc rule of thumb).

Example end state on a 5" (640 g, DAKEFPVF405, 4S, 2300 kV, Gemfan Hurricane 51433-3): **40 / 160 / 200** — in tests this resisted a leaf-blower and being hit with a stick mid-air, and flew with 20–40% of AUW hung off one motor arm. On faster/lighter setups scale System Gain roughly with kV·mass. The System Gain (D) input maxes out at **255** in this fork (raised from 250); if you genuinely need a larger b0 (high thrust/weight builds), raise `adrc_b0_scale` instead (see above) — but chattering usually means the Observer Bandwidth (I) / gyro filtering needs retuning rather than more gain.

**Refinement (blackbox method):** after swapping to 1750 kV motors jmsweng re-tuned by comparing blackbox traces of the same takeoff+hover under several candidate tunes and picking the one with the least oscillation — ending at **30 / 100 / 200**. Maintainer analysis of those logs confirms the separation is real (takeoff pitch-error RMS differed ~4× between candidate tunes), so a few logged takeoffs are a cheap, quantitative way to choose between tunes that all "feel fine". This method is packaged as a ready-to-run script: [`docs/flight-test-analysis/adrc_tune_score.py`](docs/flight-test-analysis/adrc_tune_score.py) (stdlib-only Python; feed it the CSVs from `blackbox_decode` and it ranks your candidate tunes). Its companion [`adrc_log_plot.py`](docs/flight-test-analysis/adrc_log_plot.py) draws the same logs (tracking error, the observer's disturbance estimate, motors, and — with `set debug_mode = ADRC` — the ESO states and the fix #8 liftoff latch); needs `pip install matplotlib`.

> **Takeoff note:** on the original code, throttle-up shows a brief (sub-second) oscillation/bounce — blackbox analysis traced it to the observer winding up while the craft is still ground-constrained, and fixes **#2** and **#8** in this fork remove it (hardware-confirmed). `set pid_at_min_throttle = off` (above) is still recommended while your tune is unproven. A residual sideways drift right after liftoff with a badly offset CG is the observer honestly *learning* that torque — it shrinks with a healthy Observer Bandwidth.

---

## Prebuilt firmware (no compiling)

Every release on the [**Releases page**](https://github.com/danusha2345/ADRC-betaflight/releases) ships ready-to-flash `.hex` files built by CI from this repo (all fixes included):
- **16 board-specific builds** (config baked in): DAKEFPV F405, BETAFPV G473 V2/V3, CrazyBee F405, Matek F405TE / F722SE, SpeedyBee F405 V3/V4 / F7 V3, Kakute H7, Mamba F722, GEPRC F722, iFlight Blitz F722, T-Motor F7, Foxeer F722 V4, AxisFlying F7 Pro.
- **Generic per-MCU images** for everything else — pick the hex matching your board's MCU (`STM32F7X2` for any F722 board, `STM32F405`, `STM32H743`, `AT32F435M/G`, …), flash it, and accept *Apply custom defaults* when the Configurator offers it (same scheme official Betaflight releases use).

Flash via Configurator → Firmware Flasher → *Load Firmware [Local]* → *Flash Firmware* (full chip erase on the first flash). Want a board added to the baked-in list? Ask in an [issue](https://github.com/danusha2345/ADRC-betaflight/issues).

## Compiling ADRC-Betaflight
Compiles exactly like standard Betaflight (full docs [here](https://betaflight.com/docs/category/building)). On a normal x86_64 Linux / macOS / WSL host:
```
git clone https://github.com/danusha2345/ADRC-betaflight
cd ADRC-betaflight
make arm_sdk_install   # one-time: downloads the pinned arm-none-eabi GCC (13.3.1)
make configs           # one-time: hydrate the board configs submodule
make DAKEFPVF405       # build your target — replace DAKEFPVF405 with your board
```
The `.hex` lands in `obj/`. (Verified: builds clean for `DAKEFPVF405` / STM32F405 with GCC 13.3.1.)

<details>
<summary>Building on an ARM host (e.g. Raspberry Pi)</summary>

The toolchain `make arm_sdk_install` fetches is x86_64-only, so on an ARM host use the system toolchain instead. Tested on a Raspberry Pi 3B running Raspbian Trixie 13.5:

1) Install the toolchain
```
sudo apt update && sudo apt upgrade
sudo apt install gcc-arm-none-eabi libnewlib-arm-none-eabi build-essential
```
2) Clone and enter the repo
```
git clone https://github.com/danusha2345/ADRC-betaflight
cd ADRC-betaflight
```
3) Comment out the `$(error No toolchain URL defined ...)` line in `mk/tools.mk` (line 43) so the build uses the system toolchain instead of downloading one.
4) Point the build at the system compiler version
```
echo "GCC_REQUIRED_VERSION = $(arm-none-eabi-gcc -dumpversion)" >> mk/local.mk
```
5) Hydrate configs and build
```
make configs
make DAKEFPVF405
```
</details>

---

## 🧪 Help test these fixes — testers wanted!

This fork's ADRC robustness fixes (see [`ADRC_FIXES.md`](ADRC_FIXES.md)) have so far been flight-validated by **one independent pilot on two crafts** (5" freestyle quad and a 65 mm whoop) — the results are strong (takeoff bounce fixed, flight with a cut-off prop blade, single-motor balancing), but a sample of one pilot and two FC types proves little. **Different FCs, gyros, sizes and flying styles are exactly what's missing.**

**How to help:**
1. Grab a prebuilt hex from [Releases](https://github.com/danusha2345/ADRC-betaflight/releases) (see above) — or build the fork yourself (*Compiling* above); each fix is a separate commit, so you can `git revert <sha>` to build with or without any one of them.
2. Test safely — **props off first**, then an open area away from people.
3. Report in **[issue #1 — Call for flight testers](https://github.com/danusha2345/ADRC-betaflight/issues/1)**, including:
   - Craft (size, weight, motors/props, FC target) and your ADRC P/I/D (wc/wo/b0).
   - Which commits you built with (or "all").
   - Behavior: arm/spool-up, hover, hard maneuvers, prop wash, wind, recovery after throttle chops, any oscillation or motor heating.
   - A blackbox log if you can grab one.

Even a quick "flew fine on a 5\" with all fixes" or "got oscillation on yaw" is hugely useful. Thank you! 🙏

---

## Hardware Issues

Betaflight does not manufacture or distribute their own hardware. While we are collaborating with and supported by a number of manufacturers, we do not do any kind of hardware support.

If you encounter any hardware issues with your flight controller or another component, please contact the manufacturer or supplier of your hardware, or check [Discord](https://discord.gg/n4E6ak4u3c) to see if others with the same problem have found a solution.

## Releases

**ADRC firmware releases (this fork): [github.com/danusha2345/ADRC-betaflight/releases](https://github.com/danusha2345/ADRC-betaflight/releases).**
Stock (PID) Betaflight releases live [here](https://github.com/betaflight/betaflight/releases), with detailed [release notes](https://www.betaflight.com/docs/category/release-notes) at [betaflight.com](https://www.betaflight.com).

## Open Source / Contributors

Betaflight is software that is **open source** and is available free of charge without warranty to all users.

For a complete list of contributors (past and present) see [Github](https://github.com/betaflight/betaflight/graphs/contributors).
