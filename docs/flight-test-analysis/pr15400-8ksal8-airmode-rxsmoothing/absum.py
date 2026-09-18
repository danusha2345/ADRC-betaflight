import sys,numpy as np
for f in sys.argv[1:]:
    hdr=[c.strip() for c in open(f).readline().strip().split(',')]
    need=['time (us)','adrcState','rcCommand[3]','vbatLatest (V)']+[f'axisI[{i}]' for i in range(3)]+[f'motor[{i}]' for i in range(4)]+[f'gyroADC[{i}]' for i in range(3)]+[f'setpoint[{i}]' for i in range(3)]
    if any(n not in hdr for n in need): print(f.split('/')[-1],'missing cols',[n for n in need if n not in hdr]); continue
    a=np.genfromtxt(f,delimiter=',',skip_header=1,usecols=[hdr.index(n) for n in need],filling_values=0,invalid_raise=False)
    if len(a)<3000 or not ((a[:,1].astype(int)&1)>0).any(): print(f.split('/')[-1],'short',len(a)); continue
    t=(a[:,0]-a[0,0])/1e6; st=a[:,1].astype(int); lift=(st&1)>0; inh=(st&28)>0; thr=a[:,2]; vb=a[:,3]; I=np.abs(a[:,4:7]); m=a[:,7:11]; err=np.abs(a[:,11:14]-a[:,14:17])
    mx=m.max(1); flat=np.zeros_like(mx,bool); flat[1:-1]=(np.abs(np.diff(mx)[:-1])<=3)&(np.abs(np.diff(mx)[1:])<=3)
    top=((mx>=2040)|((mx>=1900)&flat))&lift; both=top&(m.min(1)<=350)
    dt=np.median(np.diff(t)); n30=max(int(0.03/dt),2)
    eps=[];i=0
    while i<len(t):
        if both[i]:
            j=i
            while j<len(t) and both[j]: j+=1
            if j-i>=n30: eps.append((i,j))
            i=j
        else: i+=1
    print(f"{f.split('/')[-1]}: {t[-1]:.0f}s vbat {vb[:300].mean():.2f}->{vb[-300:].mean():.2f} inhibit={inh[lift].sum()} both-end frames={both.sum()} top frames={top.sum()} max|I|={I[lift].max(0).round()} frames rp-err>350={(err[lift][:,:2].max(1)>350).sum()}")
    for i,j in eps:
        k=min(j+int(0.3/dt),len(t)-1); e=err[i:k]
        print(f"    pin t={t[i]:.2f} dur={t[j-1]-t[i]:.2f}s thr={thr[i]:.0f} vbat={vb[i:j].mean():.2f} |I| {I[i].round()}->{I[i:k].max(0).round()} maxErrRP={e[:,:2].max():.0f} yaw={e[:,2].max():.0f}{'  [last 2s of log]' if t[-1]-t[i]<2 else ''}")
    # excursions not tied to pins
    big=(err[:,:2].max(1)>350)&lift; idx=np.where(big)[0]
    if len(idx):
        groups=np.split(idx,np.where(np.diff(idx)>int(0.5/dt))[0]+1)
        print("    excursions:",[f"{t[g[0]]:.1f}s({err[g,:2].max():.0f})" for g in groups])
