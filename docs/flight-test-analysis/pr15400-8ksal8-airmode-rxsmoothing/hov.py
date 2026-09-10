import sys, numpy as np
sys.path.insert(0,'/tmp/claude-1000/-home-danik-Projects-and-coding-ADRC-betaflight/4b7a05a3-6ed4-4954-bc29-5b6c73d686d9/scratchpad')
from an import load, headers, liftmask, line
rows=[]
for bbl in sys.argv[1:]:
    h=headers(bbl); d=load(bbl.replace('.bbl','.01.csv')); t=d['time']*1e-6; fs=1/np.median(np.diff(t)); i0=np.argmax(liftmask(d))
    mot=[d[f'motor[{k}]'] for k in range(4)]; n=int(2*fs); thr=(d['rcCommand[3]']-1000)/10; sc=d['debug[7]']/100
    for s in range(i0,len(t)-n,n):
        m=np.mean([mm[s:s+n].mean() for mm in mot]); r=np.mean([line(mm[s:s+n],fs)[1] for mm in mot])/m*100
        rows.append((int(h['adrc_hover_throttle']), np.median(thr[s:s+n]), np.median(sc[s:s+n]), np.median(d['vbatLatest'][s:s+n]), r, m))
R=np.array(rows)
print("hover  n  thr_med  scale_med  vbat  line_med  line_p90  motor_mean")
for hv in sorted(set(R[:,0])):
    x=R[R[:,0]==hv]; print(f"{hv:5.0f} {len(x):3d} {np.median(x[:,1]):6.1f} {np.median(x[:,2]):8.2f} {np.median(x[:,3]):6.2f} {np.median(x[:,4]):7.2f} {np.percentile(x[:,4],90):7.2f} {np.median(x[:,5]):7.0f}")
# pooled correlations
print("corr(line, scale) =", np.corrcoef(R[:,4],R[:,2])[0,1].round(2), " corr(line, thr) =", np.corrcoef(R[:,4],R[:,1])[0,1].round(2), " corr(line, vbat) =", np.corrcoef(R[:,4],R[:,3])[0,1].round(2), " corr(line, hover) =", np.corrcoef(R[:,4],R[:,0])[0,1].round(2))
# effective gain proxy: 1/scale ; bin by scale
for lo,hi in ((1.0,1.3),(1.3,1.6),(1.6,2.0),(2.0,2.5),(2.5,4)):
    x=R[(R[:,2]>=lo)&(R[:,2]<hi)]
    if len(x): print(f"scale {lo}-{hi}: n={len(x)} line med {np.median(x[:,4]):.1f} p90 {np.percentile(x[:,4],90):.1f}  hover values {sorted(set(x[:,0].astype(int)))}")
