import numpy as np
from adrc_math_review import *
from adrc_math_review3 import sim_meso, metrics

print("== plain law: step overshoot / rise for flown tunes vs motor time constant (b0 matched = b_acc/tau)")
print(f"{'tune':>12} " + " ".join(f"tau {t*1e3:2.0f}ms" for t in (0.008,0.012,0.02,0.03)))
for (wc,wo) in [(40,70),(70,80),(92,120),(106,120),(99,110),(103,140),(122,128),(60,100)]:
    row=[]
    for tau in (0.008,0.012,0.02,0.03):
        r,o = metrics(sim_meso(wc,wo,2000,2000*tau,tau)); row.append(f"{o:4.1f}%/{r:3.0f}ms")
    print(f"{str((wc,wo)):>12} " + "  ".join(row))

def controller_meso(wc, wo, b0, inv_tau, sigma=0.3, gyro_lpf_hz=150.0, dt=DT):
    kp, kd = wc*wc, 2*wc - inv_tau; b1,b2,b3 = 3*wo, 3*wo**2, wo**3
    om = 2*np.pi*gyro_lpf_hz*CUT_PT2*dt; k = om/(om+1)
    n=6; A=np.zeros((n,n)); B=np.zeros((n,2))
    A[0,0]=1-k; B[0,0]=k; A[1,:]=A[0,:]*k; A[1,1]+=1-k; B[1,:]=B[0,:]*k
    e_x=np.zeros(n); e_x[2]=1; e_x-=A[1,:]; e_u=-B[1,:]
    A[2,:]=-dt*b1*e_x; A[2,2]+=1; A[2,3]+=dt; B[2,:]=-dt*b1*e_u
    A[3,:]=-dt*b2*e_x; A[3,3]+=1-dt*inv_tau; A[3,4]+=dt; A[3,5]+=dt*b0; B[3,:]=-dt*b2*e_u
    A[4,:]=-dt*b3*e_x; A[4,4]+=1-dt*sigma; B[4,:]=-dt*b3*e_u
    Cn=np.zeros(n); Cn[2]=-kp; Cn[3]=-kd; Cn[4]=-1; Cn/=b0; Dr=np.array([0.0,kp/b0])
    C=Cn@A; D=Cn@B+Dr; A[5,:]=C; B[5,:]=D
    return A,B,C,D

w = np.logspace(0, np.log10(np.pi/DT*0.99), 4000); G = pt1_resp(250,w)*pt1_resp(500,w)
def rms(H): return np.sqrt(np.trapezoid(np.abs(H)**2, w)/(np.pi/DT))
print("\n== margins and noise, plain vs motor-pole ESO (tau_model = tau), b0 matched")
print(f"{'tune':>10} {'tau':>5} | {'plain PM':>8} {'GM':>5} {'noise':>6} | {'MESO PM':>8} {'GM':>5} {'noise':>6}")
for (wc,wo) in [(60,100),(99,110),(103,140),(140,150)]:
    for tau in (0.010,0.020,0.030):
        if 1/tau >= 2*wc: continue
        Ad,Bd,Cd,Dd = plant_dss(2000*tau,tau); P = freqresp(Ad,Bd,Cd,Dd,w)[:,0,0]
        A,B,C,D = controller_dss(wc,wo,2000.0); Hp = freqresp(A,B,C,D,w)[:,0]; mp = margins(w,-Hp*G*P)
        A,B,C,D = controller_meso(wc,wo,2000.0,1/tau); Hm = freqresp(A,B,C,D,w)[:,0]; mm = margins(w,-Hm*G*P)
        print(f"{str((wc,wo)):>10} {tau*1e3:4.0f}ms | {mp['PM']:8.1f} {mp['GM_dB']:5.1f} {rms(Hp*G):6.3f} | {mm['PM']:8.1f} {mm['GM_dB']:5.1f} {rms(Hm*G):6.3f}")

print("\n== MESO with b0 mismatch (60/100, tau 20 ms, tau_model exact): overshoot and PM")
for ratio in (0.7,1.0,1.5,2.0):
    r,o = metrics(sim_meso(60,100,2000,40.0*ratio,0.02,0.02))
    Ad,Bd,Cd,Dd = plant_dss(40.0*ratio,0.02); P = freqresp(Ad,Bd,Cd,Dd,w)[:,0,0]
    A,B,C,D = controller_meso(60,100,2000.0,50.0); Hm = freqresp(A,B,C,D,w)[:,0]; mm = margins(w,-Hm*G*P)
    A,B,C,D = controller_dss(60,100,2000.0); Hp = freqresp(A,B,C,D,w)[:,0]; mp = margins(w,-Hp*G*P)
    print(f"  b/b0 {ratio:3.1f}: MESO overshoot {o:5.1f} %, PM {mm['PM']:5.1f} (plain PM {mp['PM']:5.1f})")
