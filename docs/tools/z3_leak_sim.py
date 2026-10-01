#!/usr/bin/env python3
"""Closed-loop effect of the z3 leak (adrc_sigma_decay) on a step disturbance.

Same discrete equations as src/main/flight/adrc.c: second-order rate plant w'' = d + b*u,
ESO z1/z2/z3 with beta = 3*wo, 3*wo^2, wo^3, the leak inside the z3 update
(z3 += dT*(-sigma*z3 - beta3*e)), control u = (wc^2*(r - z1) - 2*wc*z2 - z3) / b0, 8 kHz Euler.
Prints how much of the step z3 holds, the steady rate error and the peak error.
"""
import math, sys

def run(sigma, wc=60.0, wo=100.0, b=2000.0, b0=2000.0, dt=1/8000, T=12.0, d0=50000.0):
    b1, b2, b3 = 3*wo, 3*wo**2, wo**3
    w = wd = 0.0; z1 = z2 = z3 = 0.0; u = 0.0; out = []
    for k in range(int(T/dt)):
        t = k*dt; d = d0 if t >= 0.5 else 0.0
        e = z1 - w
        z1 += dt*(z2 - b1*e); z2 += dt*(z3 + b0*u - b2*e); z3 += dt*(-sigma*z3 - b3*e)
        u = (wc*wc*(0.0 - z1) - 2*wc*z2 - z3)/b0
        wd += dt*(d + b*u); w += dt*wd
        out.append((t, w, z3))
    return out

def report(label, **kw):
    for s in (0.0, 0.3):
        o = run(s, **kw); d0 = kw.get('d0', 50000.0)
        print(f"{label} sigma={s}: z3 holds {abs(o[-1][2])/d0*100:.2f} % of the step, "
              f"steady rate error {abs(o[-1][1]):.3f} deg/s, peak {max(abs(x[1]) for x in o):.2f} deg/s")

if __name__ == '__main__':
    report("wc 60 / wo 100, d 5e4")
    report("Air65 25 % payload (wc 99 / wo 110, b0 5378, d 4.5e5)", wc=99, wo=110, b=5378, b0=5378, d0=450000, T=8)
