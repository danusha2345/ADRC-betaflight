import sys, json, numpy as np
import log_check3 as L
from log_check import read_headers, load_csv
out=[]
for f in sys.argv[1:]:
    hdr=read_headers(f.replace('.csv','.headers.csv')); wc=[float(v) for v in hdr['adrcWC'].split(',')]; wo=[float(v) for v in hdr['adrcWO'].split(',')]; b0=[float(v) for v in hdr['adrcB0'].split(',')]
    z3s=float(hdr.get('adrc_z3_log_scale',16)); pslim=float(hdr.get('pidsum_limit',500)); loop_dt=float(hdr['looptime'])*1e-6*float(hdr.get('pid_process_denom',1)); lpf=float(hdr.get('adrc_gyro_lpf_hz',150)); sigma=float(hdr.get('adrc_sigma_decay',3))/10
    cols=['time (us)']+[f'axis{k}[{a}]' for a in (0,1) for k in 'PIDF']+[f'setpoint[{a}]' for a in (0,1)]+[f'gyroADC[{a}]' for a in (0,1)]+[f'debug[{i}]' for i in range(8)]
    d=load_csv(f,cols); t=d['time (us)']*1e-6; dt=np.median(np.diff(t)); scale=np.abs(d['debug[7]'])/100; gate=d['debug[7]']>0
    for ax,axname,zi in ((0,'roll',(0,1,2)),(1,'pitch',(3,4,5))):
        u=np.clip(sum(d[f'axis{k}[{ax}]'] for k in 'PIDF'),-pslim,pslim); y=d[f'gyroADC[{ax}]']; r=d[f'setpoint[{ax}]']; z2,z3=d[f'debug[{zi[1]}]'],d[f'debug[{zi[2]}]']*z3s
        moves=[mv for mv in L.find_moves(r,dt) if gate[max(0,mv[0]-int(0.05/dt)):mv[1]].all()]
        if len(moves)>30: moves=[moves[i] for i in np.linspace(0,len(moves)-1,30).astype(int)]
        if len(moves)<5: continue
        pre=int(0.05/dt); n_steps=int(0.30/loop_dt)-2; tt=np.arange(n_steps)*loop_dt
        R=[];Y=[];y0=[];z20=[];z30=[];u0=[];sc=[];sg=[]
        for (i0,i1,s_) in moves:
            w0=i0-pre; seg=slice(w0,i1); tseg=t[seg]-t[w0]; R.append(np.interp(tt,tseg,r[seg])); Y.append(np.interp(tt,tseg,y[seg])); y0.append(y[w0]); z20.append(z2[w0]); z30.append(z3[w0]); u0.append(u[w0]); sc.append(scale[seg].mean()); sg.append(s_)
        R,Y=np.array(R),np.array(Y); y0,z20,z30,u0,sc,sg=map(np.array,(y0,z20,z30,u0,sc,sg)); R0=R[:,:1]; pk=np.max(sg[:,None]*(R-R0),axis=1); ok=pk>=120
        R,Y,y0,z20,z30,u0,sc,sg,pk=R[ok],Y[ok],y0[ok],z20[ok],z30[ok],u0[ok],sc[ok],sg[ok],pk[ok]
        if len(R)<5: continue
        best=None
        for ratio in (0.3,0.4,0.5,0.65,0.8,1.0,1.25,1.55,1.9,2.4,3.0):
            S=L.replay_vec(R,y0,z20,z30,u0,sc,wc[ax],wo[ax],b0[ax],sigma,lpf,pslim,loop_dt,b0[ax]*0.004*ratio,0.004,0.0)
            e=np.median(np.sqrt(np.mean((S-Y)**2,axis=1))/pk)
            if best is None or e<best[0]: best=(e,ratio)
        out.append(dict(log=f.split('/')[-1],axis=axname,err0=best[0],ratio0=best[1]))
json.dump(out,open('nolag_rows.json','w'),indent=1); print("nolag done", len(out))
