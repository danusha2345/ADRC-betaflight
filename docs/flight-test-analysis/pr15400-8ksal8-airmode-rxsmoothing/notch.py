import sys,numpy as np
bands=[(10,25),(25,40),(40,70),(70,120),(120,250)]
for f in sys.argv[1:]:
    hdr=[c.strip() for c in open(f).readline().strip().split(',')]
    cols=['time (us)','adrcState','rcCommand[3]','vbatLatest (V)']+[f'gyroUnfilt[{i}]' for i in range(3)]+[f'gyroADC[{i}]' for i in range(3)]+[f'motor[{i}]' for i in range(4)]+[f'setpoint[{i}]' for i in range(3)]
    a=np.genfromtxt(f,delimiter=',',skip_header=1,usecols=[hdr.index(c) for c in cols],filling_values=0,invalid_raise=False)
    t=(a[:,0]-a[0,0])/1e6; fs=1/np.median(np.diff(t)); N=int(fs*2); lift=(a[:,1].astype(int)&1)>0; thr=a[:,2]
    fr=np.fft.rfftfreq(N,1/fs); win=np.hanning(N); norm=np.sqrt(2)/ (win.sum())
    res={k:[] for k in ['gu0','gu1','gu2','g0','g1','g2','mot','err']}; used=0; vb=[]
    for i in range(0,len(t)-N,N):
        s=slice(i,i+N)
        if not lift[s].all() or t[i]>170: continue
        th=thr[s]; sp=a[s,14:17]
        if th.mean()<1250 or th.mean()>1600 or th.std()>80 or np.abs(sp).max()>150: continue
        used+=1; vb.append(a[s,3].mean())
        def b(x):
            X=np.abs(np.fft.rfft((x-x.mean())*win))*norm
            return [np.sqrt((X[(fr>=lo)&(fr<hi)]**2).sum()) for lo,hi in bands]
        for k,idx in [('gu0',4),('gu1',5),('gu2',6),('g0',7),('g1',8),('g2',9)]: res[k].append(b(a[s,idx]))
        res['mot'].append(np.mean([b(a[s,10+m]) for m in range(4)],0))
        res['err'].append([np.abs(a[s,7+k]-a[s,14+k]).mean() for k in range(3)]+[0,0])
    print(f"{f}: calm windows={used}, vbat {np.mean(vb):.2f} (range {min(vb):.2f}-{max(vb):.2f}); bands {bands}")
    for k,name in [('gu0','gyroUnfilt roll'),('gu1','gyroUnfilt pitch'),('gu2','gyroUnfilt yaw'),('g0','gyro roll'),('g1','gyro pitch'),('g2','gyro yaw'),('mot','motor (mean of 4)')]:
        m=np.median(np.array(res[k]),0); print(f"   {name:18s} median RMS: "+"  ".join(f"{v:6.2f}" for v in m))
    e=np.median(np.array(res['err']),0); print(f"   mean |gyro-setpoint| r/p/y: {e[0]:.1f} {e[1]:.1f} {e[2]:.1f} deg/s")
