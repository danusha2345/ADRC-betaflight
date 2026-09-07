import sys, numpy as np
sys.path.insert(0,'/tmp/claude-1000/-home-danik-Projects-and-coding-ADRC-betaflight/4b7a05a3-6ed4-4954-bc29-5b6c73d686d9/scratchpad')
from an import load, headers
from scipy.signal import welch, find_peaks
for bbl in sys.argv[1:]:
    h=headers(bbl); d=load(bbl.replace('.bbl','.01.csv')); t=d['time']*1e-6; t-=t[0]; fs=1/np.median(np.diff(t))
    g=d['gyroADC[1]']; mot=np.array([d[f'motor[{k}]'] for k in range(4)]); z3s=float(h.get('adrc_z3_log_scale',16))
    print(f"\n### {bbl.split('/')[-1]} gwc={h.get('adrc_ground_wc')}")
    n=int(fs)
    rows=[]
    for s in range(0,len(t)-n,n):
        seg=g[s:s+n]; f,P=welch(seg-seg.mean(),fs=fs,nperseg=n//2)
        m=(f>=3)&(f<=120); i=np.argmax(P[m]); 
        rows.append((s/fs, np.abs(seg).max(), f[m][i], mot[:,s:s+n].max(), mot[:,s:s+n].mean(), d['adrcAppliedCollective'][s:s+n].max(), d['adrcCommandedCollective'][s:s+n].max(), abs(d['debug[5]'][s:s+n]*z3s).max()/1e3, abs(d['debug[4]'][s:s+n]).max()))
    print(" t  |pitch|max  fpk  motMax motMean appliedMax cmdMax |z3p|k |z2p|")
    for r in rows: print(f"{r[0]:4.0f} {r[1]:8.0f} {r[2]:6.1f} {r[3]:6.0f} {r[4]:6.0f} {r[5]:6.0f} {r[6]:6.0f} {r[7]:6.0f} {r[8]:7.0f}")
    # overall spectrum peaks of pitch gyro in the active part
    act=np.abs(g)>30
    if act.sum()>fs:
        x=g[act]; f,P=welch(x-x.mean(),fs=fs,nperseg=int(fs))
        pk,_=find_peaks(P,prominence=np.max(P)*0.05); top=sorted(pk,key=lambda i:-P[i])[:4]
        print(" spectrum peaks (Hz, rel):", ", ".join(f"{f[i]:.1f} ({P[i]/P.max():.2f})" for i in top))
