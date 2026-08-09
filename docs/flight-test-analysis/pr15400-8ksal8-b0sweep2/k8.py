import csv,glob,os,math,cmath
MLOW=158.0; MRANGE=2047.0-158.0   # sag_compensation=0, dyn_idle=0 -> статическая нормировка верна
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
def load(f):
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        for row in r:
            try:
                m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
                rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                    thr=float(row[ix['rcCommand[3]']]),
                    g=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                    gf=[float(row[ix[f'gyroADC[{k}]']]) for k in range(3)],
                    sp=[float(row[ix[f'setpoint[{k}]']]) for k in range(3)],
                    coll=(sum(m)/4-MLOW)/MRANGE*100,
                    d7=float(row[ix['debug[7]']])))
            except Exception: pass
    return rows
for d,label in [('.scratch/8ksal8-b0sweep2/logs','СТАРЫЙ wc 87/87/190 wo 112/112/130 b0 6500/4000/22000'),
                ('.scratch/8ksal8-b0sweep3/logs','НОВЫЙ  wc 80/80/96  wo 103/103/125 b0 7007/4312/5848')]:
    print(f'##### {label}')
    print(f'  {"закон":11s} {"err R/P/Y медиана":>18s} {"p90":>14s}  {"сат.%":>6s} {"гейт":>7s}  {"коллектив макс":>14s}')
    for f in sorted(glob.glob(os.path.join(d,'*.01.csv'))):
        rows=load(f)
        if len(rows)<500: continue
        errs=[]; p90=[]
        for a in range(3):
            e=sorted(abs(x['sp'][a]-x['gf'][a]) for x in rows)
            errs.append(e[len(e)//2]); p90.append(e[int(len(e)*0.9)])
        sat=sum(1 for x in rows if max(x['m'])>=2040)/len(rows)*100
        oi=next((i for i,x in enumerate(rows) if x['d7']>0), None)
        gt=f"{rows[oi]['t']-rows[0]['t']:.1f}с" if oi is not None else "нет"
        nm=os.path.basename(f).split('_')[0]
        print(f'  {nm:11s} {errs[0]:5.0f}/{errs[1]:4.0f}/{errs[2]:4.0f}   {p90[0]:5.0f}/{p90[1]:4.0f}/{p90[2]:4.0f}  {sat:6.1f} {gt:>7s}  {max(x["coll"] for x in rows):13.1f}%')
    print()
