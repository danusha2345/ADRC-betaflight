
<img width="1376" height="768" alt="na" src="https://github.com/user-attachments/assets/eb513be2-56d0-4fa1-88e8-2a53b7f61d74" />


# Betaflight ADRC Controller (Active Disturbance Rejection Control)

**English** | [Русский](README.ru.md)

This repository implements **Active Disturbance Rejection Control (ADRC)** on Betaflight, completely replacing the traditional PID loop. ADRC acts as a "PID Killer"—providing incredible stability, robust wind resistance, and smooth handling even with uncalibrated parameters, changing propeller sizes, or extreme, unbalanced dynamic payloads.

> ⚠️ **Experimental robustness fixes on this fork — flight testers wanted!**
> This fork carries a series of small, independent ADRC robustness fixes on top of
> `Boyyt357/ADRC-betaflight` (anti-windup on the disturbance estimate, saturation-aware
> observer feedback, ADRC-tuned defaults, zero-throttle observer handling, plus one
> experimental change). **They are UNTESTED on real hardware.** Each fix is its own commit so
> you can build with or without any of them (`git revert <sha>`). Details and rationale in
> [`ADRC_FIXES.md`](ADRC_FIXES.md). If you fly it, **please report in
> [issue #1 — Call for flight testers](https://github.com/danusha2345/ADRC-betaflight/issues/1)** —
> what you flew, which commits, and how it behaved. 🙏

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

### Tuning procedure (community, from @jmsweng)
A sensible step-by-step instead of guessing, starting from `10 / 50 / 20` (P/I/D):
1. **System Gain (D):** raise until the quad takes off stably (~70 on a 5"), keep raising until it makes a stuttering noise in hover, then back off ~20%. *(Overestimating b0 is fairly harmless; underestimating causes instability.)*
2. **Observer Bandwidth (I):** raise until stuttering/chatter appears in hover, then back off ~20%. *(Too high and the observer starts tracking gyro noise.)*
3. **Control Bandwidth (P):** set to ~¼ of the Observer Bandwidth (the wo ≈ 3–5×wc rule of thumb).

Example end state on a 5" (640 g, DAKEFPVF405, 4S, 2300 kV, Gemfan Hurricane 51433-3): **40 / 160 / 200** — in tests this resisted a leaf-blower and being hit with a stick mid-air, and flew with 20–40% of AUW hung off one motor arm. On faster/lighter setups scale System Gain roughly with kV·mass. The System Gain (D) input maxes out at **255** in this fork (raised from 250); if you need more, chattering usually means the Observer Bandwidth (I) / gyro filtering needs retuning rather than more gain.

> **Takeoff note:** the rate ESO doesn't model gravity, so on throttle-up there's often a brief (sub-second) oscillation/bounce before it settles — some pilots report this as "unpredictable on arm". `set pid_at_min_throttle = off` (above) helps, and a firm toss-launch avoids it.

---

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

This fork's ADRC robustness fixes (see [`ADRC_FIXES.md`](ADRC_FIXES.md)) are **UNTESTED on real hardware** — the code builds clean but has never flown. If you have a craft you can safely test on, please help validate them.

**How to help:**
1. Build the fork (see *Compiling* above). Each fix is a separate commit, so you can `git revert <sha>` to build with or without any one of them.
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

## Betaflight Releases

You can find our release [here](https://github.com/betaflight/betaflight/releases) on Github and we also have more detailed [release notes](https://www.betaflight.com/docs/category/release-notes) at [betaflight.com](https://www.betaflight.com).

## Open Source / Contributors

Betaflight is software that is **open source** and is available free of charge without warranty to all users.

For a complete list of contributors (past and present) see [Github](https://github.com/betaflight/betaflight/graphs/contributors).
