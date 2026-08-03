#!/usr/bin/env python3
"""Turn a manufacturer thrust-vs-throttle table into a schedule-shape proxy.

The mixer adds a command differential to each motor, so the static torque per
unit control follows the LOCAL SLOPE of the thrust curve, not the thrust. That
makes dT/dthrottle a static roll/pitch proxy for the *shape* of a b0 schedule.
It is not a measurement of this implementation's b0: the ESO models
omega_ddot = z3 + b0*u (b0 in deg/s^3 per PID output), so b0 also absorbs the
ESC/motor/prop dynamics, and the yaw axis needs the reaction-torque slope
dQ/dcmd rather than thrust at all.

Data: Gemfan 1219s-3 / 0702-27000kv sheet at 4.2 V, per motor, as attached to
PR 15400 comment 5161126252.  The hover point of the craft it is mounted on is
NOT known, so the normalisation is swept.

Usage: python3 thrust_slope.py [hover_percent ...]
"""

import sys

import numpy as np

THROTTLE = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 100], float)
THRUST_G = np.array([0.1, 1.8, 5.5, 9.6, 13.9, 18.1, 22.8, 25.9, 31.6, 34.7], float)

slope = np.gradient(THRUST_G, THROTTLE)
hovers = [float(a) for a in sys.argv[1:]] or [25.0, 29.0, 31.0, 35.0]

print("raw sheet and its local slope (vendor data, single voltage, 10-point grid)")
print("thr%   T(g)   dT/dthr(g/%)")
for x, y, dy in zip(THROTTLE, THRUST_G, slope):
    print(f"{x:4.0f} {y:6.1f} {dy:12.3f}")

for hover in hovers:
    slope_hover = np.interp(hover, THROTTLE, slope)
    print(f"\nnormalised to hover = {hover:.0f} % (slope there {slope_hover:.3f} g/%)")
    print("thr%   slope ratio    FIXED   SQRT  LINEAR   QUAD  QUAD capped@3")
    for x, dy in zip(THROTTLE, slope):
        if x < hover:
            continue
        r = x / hover
        q = max(1.0, r * r)
        print(f"{x:4.0f} {dy/slope_hover:12.2f} {1.0:8.2f} {max(1.0, np.sqrt(r)):6.2f} "
              f"{max(1.0, r):7.2f} {q:6.2f} {min(q, 3.0):13.2f}")

# above ~30 % the sheet is close to a straight line with a negative intercept,
# i.e. roughly constant slope. Report the fit so the claim is checkable.
above = THROTTLE >= 30
a, b = np.polyfit(THROTTLE[above], THRUST_G[above], 1)
resid = THRUST_G[above] - (a * THROTTLE[above] + b)
print(f"\nstraight-line fit above 30 %: T = {a:.3f}*thr {b:+.1f} g, "
      f"max residual {np.abs(resid).max():.1f} g")
print(f"slope over 30-100 %: min {slope[above].min():.3f}, max {slope[above].max():.3f} g/% "
      f"(spread {slope[above].max()/slope[above].min():.2f}x on a 10-point vendor grid)")
