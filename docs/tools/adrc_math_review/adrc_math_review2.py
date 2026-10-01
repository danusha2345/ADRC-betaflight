import numpy as np
from adrc_math_review import *

w = np.logspace(0, np.log10(np.pi / DT * 0.99), 4000)
G = pt1_resp(250, w) * pt1_resp(500, w)

print("== max wc with PM >= 40 deg (wo = 1.2 wc, b0 matched, pt2 150 Hz), vs motor time constant tau")
for tau in (0.005, 0.010, 0.015, 0.020, 0.030, 0.040):
    best = None
    for wc in range(20, 301, 5):
        wo = 1.2 * wc
        A, B, C, D = controller_dss(wc, wo, 2000.0)
        Hy = freqresp(A, B, C, D, w)[:, 0]
        Ad, Bd, Cd, Dd = plant_dss(2000.0 * tau, tau)
        P = freqresp(Ad, Bd, Cd, Dd, w)[:, 0, 0]
        m = margins(w, -Hy * G * P)
        if m.get('PM', 0) >= 40 and m.get('GM_dB', 0) >= 6:
            best = (wc, m['PM'], m['GM_dB'])
    print(f"  tau {tau*1e3:4.0f} ms (motor pole {1/tau:5.0f} rad/s): max wc {best[0]:4d}  (wc*tau = {best[0]*tau:.2f}; PM {best[1]:.0f} deg GM {best[2]:.1f} dB)")

print("\n== noise: classic BF defaults P45 D30 with dterm lpf1 75 Hz (dyn min) + lpf2 150 Hz pt1, vs ADRC; RMS per unit white gyro noise")
def rms(H): return np.sqrt(np.trapezoid(np.abs(H)**2, w) / (np.pi / DT))
Dcl = 30*DTERM_SCALE*(1j*w)*pt1_resp(75,w)*pt1_resp(150,w)*G
print(f"  classic: P={rms(45*PTERM_SCALE*G):.3f} D={rms(Dcl):.3f} P+D={rms(45*PTERM_SCALE*G + Dcl):.3f}")
for (wc, wo, b0, name) in [(60,100,2000,'ADRC default'), (99,110,5378,'Air65'), (103,140,3000,'5in 103/140')]:
    A,B,C,D = controller_dss(wc,wo,b0); Hu = freqresp(A,B,C,D,w)[:,0]
    print(f"  {name:13}: total={rms(Hu*G):.3f}")

print("\n== setpoint response vs wo (wc 60, b0 2000, tau 20 ms matched): the ESO must track f = -w'/tau during the step")
for wo in (60, 80, 100, 150, 200, 300):
    h = simulate(60, wo, 2000, 2000*0.02, 0.02)
    y = h[:,2]; t = h[:,0]; i10 = np.argmax(y >= 10); i90 = np.argmax(y >= 90)
    print(f"  wo {wo:3d} (wo*tau {wo*0.02:3.1f}): rise {1e3*(t[i90]-t[i10]):5.1f} ms, overshoot {max(y)-100:5.1f} %")
print("   same at tau 10 ms:")
for wo in (60, 100, 150):
    h = simulate(60, wo, 2000, 2000*0.01, 0.01)
    y = h[:,2]; t = h[:,0]; i10 = np.argmax(y >= 10); i90 = np.argmax(y >= 90)
    print(f"  wo {wo:3d} (wo*tau {wo*0.01:3.1f}): rise {1e3*(t[i90]-t[i10]):5.1f} ms, overshoot {max(y)-100:5.1f} %")

print("\n== feedforward with a realistic stick ramp (0 -> 300 deg/s over 40 ms), default tune, tau 20 ms: lag of rate behind setpoint at end of ramp, overshoot")
def sim_ramp(wc, wo, b0, b_acc, tau, F_bf, ramp=0.04, amp=300.0, T=0.4, sigma=0.3, lpf_hz=150.0, dt=DT):
    kp, kd = wc*wc, 2*wc; b1,b2,b3 = 3*wo, 3*wo**2, wo**3
    om = 2*np.pi*lpf_hz*CUT_PT2*dt; k = om/(om+1); Kf = FF_SCALE*F_bf/100.0
    s1=s=z1=z2=z3=0.0; wr=Tm=0.0; up=0.0; rp=0.0; out=[]
    for n in range(int(T/dt)):
        t=n*dt; r = amp*min(max((t-0.05)/ramp,0),1)
        s1 += k*(wr-s1); s += k*(s1-s); e = z1-s
        z1 += dt*(z2-b1*e); z2 += dt*(z3+b0*up-b2*e); z3 = z3-dt*sigma*z3-dt*b3*e
        u = (kp*(r-z1)-kd*z2-z3)/b0; ff = Kf*(r-rp)/dt; rp=r
        us = max(-500.0,min(500.0,u+ff)); up=us
        Tm += dt*(us-Tm)/tau; wr += dt*b_acc*Tm; out.append((t,r,wr,us))
    return np.array(out)
for F in (0, 60, 120, 200, 300):
    h = sim_ramp(60,100,2000,40.0,0.02,F); t,r,y,u = h.T
    iend = np.argmax(t >= 0.05+0.04); lag = r[iend]-y[iend]
    print(f"  F={F:3d}: rate at end of ramp {y[iend]:6.1f} of 300 (lag {lag:5.1f}), overshoot {max(y)-300:6.1f}, peak |u| {max(abs(u)):5.0f}")

print("\n== disturbance step 2000 deg/s^2 (10 % of authority at b_acc 40) at 0.2 s; peak and 90 % recovery")
for (wc, wo, b0, tau, name) in [(60,100,2000,0.02,'default'), (60,150,2000,0.02,'wo 150'), (99,110,5378,0.01,'Air65')]:
    h = simulate(wc, wo, b0, b0*tau, tau, step=0.0, dist=2000.0, T=0.6)
    y=h[:,2]; t=h[:,0]; i0=np.argmax(t>=0.2); pk=np.max(np.abs(y[i0:])); ipk=i0+np.argmax(np.abs(y[i0:]))
    below = np.where(np.abs(y[ipk:]) < 0.1*pk)[0]; rec = t[ipk+below[0]]-0.2 if len(below) else float('nan')
    print(f"  {name:8}: peak {pk:5.1f} deg/s at {1e3*(t[ipk]-0.2):4.1f} ms, within 10 % of peak after {1e3*rec:5.1f} ms")

print("\n== observer gain |z1/y| peak (P path resonance) and |z2/y| peak")
for wo in (80,100,150):
    A,B,C,D = controller_dss(60,wo,2000.0)
    Hz = freqresp(A,B,A[2:5,:],B[2:5,:],w)[:,:,0]
    i1=np.argmax(abs(Hz[:,0])); i2=np.argmax(abs(Hz[:,1]))
    print(f"  wo {wo}: |z1/y|max={abs(Hz[i1,0]):.2f} at {w[i1]:.0f} rad/s;  |z2/y|max={abs(Hz[i2,1]):.0f} at {w[i2]:.0f} rad/s (= {abs(Hz[i2,1])/wo:.2f} wo)")
