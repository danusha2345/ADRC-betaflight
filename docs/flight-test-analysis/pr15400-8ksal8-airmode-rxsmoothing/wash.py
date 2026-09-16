import sys, numpy as np
class DF:
    def __init__(s,f):
        hdr=open(f).readline().strip().split(',')
        s.cols=[c.strip() for c in hdr]
        s.a=np.genfromtxt(f,delimiter=',',skip_header=1,usecols=range(len(s.cols)),filling_values=0,invalid_raise=False)
    def __getitem__(s,k):
        if isinstance(k,list): return s.a[:,[s.cols.index(x) for x in k]]
        return s.a[:,s.cols.index(k)]
    def __len__(s): return s.a.shape[0]
f=sys.argv[1]
d=DF(f)
t=(d['time (us)']-d['time (us)'][0])/1e6
g=d[['gyroADC[0]','gyroADC[1]','gyroADC[2]']]
sp=d[['setpoint[0]','setpoint[1]','setpoint[2]']]
err=g-sp
m=d[['motor[0]','motor[1]','motor[2]','motor[3]']]
I=d[['axisI[0]','axisI[1]','axisI[2]']]
P=d[['axisP[0]','axisP[1]','axisP[2]']]
D=d[['axisD[0]','axisD[1]','axisD[2]']]
ps=d[['adrcPidSum[0]','adrcPidSum[1]','adrcPidSum[2]']]
vb=d['vbatLatest (V)']; amp=d['amperageLatest (A)']
st=d['adrcState']; thr=d['rcCommand[3]']
lift=(st.astype(int)&1)>0
print(f"{f}: {t[-1]:.1f}s, n={len(d)}, vbat {vb[:500].mean():.2f}->{vb[-500:].mean():.2f} V, amps median {np.median(amp[lift]) if lift.any() else 0:.1f}, liftoff {lift.mean()*100:.0f}%")
# saturation: min motor < 200 and max > 1900 simultaneously
sat=(m.min(1)<300)&(m.max(1)>1900)&lift
print(f"  mixer sat (min<300&max>1900): {sat.mean()*100:.2f}% of samples")
# events: |roll or pitch err| > 350 sustained ~ 30ms, in air
big=(np.abs(err[:,:2]).max(1)>350)&lift
ev=[]; i=0; n=len(d)
while i<n:
    if big[i]:
        j=i
        while j<n and (big[j] or (j-i<50)): j+=1
        if (big[i:j].sum())>15: ev.append((i,j))
        i=j
    else: i+=1
print(f"  events(|rp err|>350 sustained): {len(ev)}")
for a,b in ev[:12]:
    w=slice(max(a-300,0),min(b+100,n))
    k=np.argmax(np.abs(err[w,:2]).max(1))+w.start
    pre=slice(max(k-400,0),k)
    print(f"  t={t[k]:.2f}s dur={t[b-1]-t[a]:.2f}s peak err r/p={err[k,0]:.0f}/{err[k,1]:.0f} gyro={g[k].round()} sp={sp[k].round()} thr={thr[k]:.0f}")
    print(f"     at peak: P={P[k].round()} I={I[k].round()} D={D[k].round()} pidSum={ps[k].round()} motors={m[k]} vbat={vb[k]:.2f} A={amp[k]:.0f}")
    print(f"     pre-400ms: max|yawI|={np.abs(I[pre,2]).max():.0f} max|yawPS|={np.abs(ps[pre,2]).max():.0f} yawerr max={np.abs(err[pre,2]).max():.0f} sat%={sat[pre].mean()*100:.0f} minmotor={m[pre].min()} maxmotor={m[pre].max()} vbat={vb[pre].mean():.2f}")
# yaw stats overall in air
print(f"  in-air yaw: |I| p50/p99 = {np.percentile(np.abs(I[lift,2]),50):.0f}/{np.percentile(np.abs(I[lift,2]),99):.0f}, |pidSum| p99={np.percentile(np.abs(ps[lift,2]),99):.0f}, |D| p99={np.percentile(np.abs(D[lift,2]),99):.0f}; roll |D| p99={np.percentile(np.abs(D[lift,0]),99):.0f}")
print(f"  motor time at 2047: {(m==2047).any(1)[lift].mean()*100:.2f}%, at floor<=48: {(m<=48).any(1)[lift].mean()*100:.2f}%")
