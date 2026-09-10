import sys, numpy as np
sys.path.insert(0,'/tmp/claude-1000/-home-danik-Projects-and-coding-ADRC-betaflight/4b7a05a3-6ed4-4954-bc29-5b6c73d686d9/scratchpad')
from an import load, headers, liftmask, line
from scipy.signal import welch
print("hover  gate%  n_win  bursts(>5%)  thr@burst  thr@calm  scale@burst scale@calm  r(line,thr)  gyro76Hz amp@burst(°/s)  gyro peak f")
for bbl in sys.argv[1:]:
    h=headers(bbl); d=load(bbl.replace('.bbl','.01.csv')); t=d['time']*1e-6; fs=1/np.median(np.diff(t)); lift=liftmask(d); i0=np.argmax(lift)
    mot=[d[f'motor[{k}]'] for k in range(4)]; n=int(fs); thr=(d['rcCommand[3]']-1000)/10; sc=d['debug[7]']/100; g=d['gyroADC[0]']
    W=[]
    for s in range(i0,len(t)-n,n):
        if not lift[s:s+n].all(): continue
        m=np.mean([mm[s:s+n].mean() for mm in mot]); r=np.mean([line(mm[s:s+n],fs)[1] for mm in mot])/m*100
        seg=g[s:s+n]; f,P=welch(seg-seg.mean(),fs=fs,nperseg=n//2); band=(f>=70)&(f<=82); amp=np.sqrt(np.trapz(P[band],f[band]))*np.sqrt(2)
        fp=f[(f>=20)][np.argmax(P[f>=20])]
        W.append((r,np.median(thr[s:s+n]),np.median(sc[s:s+n]),amp,fp))
    W=np.array(W); b=W[:,0]>5; c=~b
    rr=np.corrcoef(W[:,0],W[:,1])[0,1] if len(W)>3 else np.nan
    print(f"{h['adrc_hover_throttle']:>5s} {lift[i0:].mean()*100:5.0f} {len(W):5d} {b.sum():6d}      {np.median(W[b,1]) if b.any() else float('nan'):5.1f}     {np.median(W[c,1]):5.1f}     {np.median(W[b,2]) if b.any() else float('nan'):5.2f}     {np.median(W[c,2]):5.2f}     {rr:6.2f}      {np.median(W[b,3]) if b.any() else float('nan'):6.1f}                {np.median(W[b,4]) if b.any() else float('nan'):5.1f}")
