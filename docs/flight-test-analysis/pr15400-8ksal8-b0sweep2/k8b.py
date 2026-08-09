import csv,glob,os
MLOW=158.0; MRANGE=2047.0-158.0
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
for d,label in [('.scratch/8ksal8-b0sweep2/logs','СТАРЫЙ'),('.scratch/8ksal8-b0sweep3/logs','НОВЫЙ')]:
    print(f'##### {label} — фаза до открытия гейта')
    for f in sorted(glob.glob(os.path.join(d,'*.01.csv'))):
        rows=[]
        with open(f) as fh:
            r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
            ix={h:i for i,h in enumerate(hdr)}
            for row in r:
                try:
                    m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
                    rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                        c=max(0.0,(float(row[ix['rcCommand[3]']])-1000)/10),
                        coll=(sum(m)/4-MLOW)/MRANGE*100,
                        g=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                        d7=float(row[ix['debug[7]']]),
                        z3=max(abs(float(row[ix[f'debug[{k}]']])) for k in (2,5,6))))
                except Exception: pass
        oi=next((i for i,x in enumerate(rows) if x['d7']>0), None)
        if oi is None or oi<20: 
            print(f'  {os.path.basename(f).split("_")[0]:10s} гейт на кадре {oi} — фазы почти нет'); continue
        pre=rows[:oi]; t0=rows[0]['t']
        # рост амплитуды по yaw в первых окнах
        segs=[]
        for k in range(3):
            w=[x for x in pre if k*0.3 <= x['t']-t0 < (k+1)*0.3]
            segs.append(rms([x['g'][2] for x in w]) if len(w)>20 else float('nan'))
        print(f'  {os.path.basename(f).split("_")[0]:10s} гейт {rows[oi]["t"]-t0:5.2f}с | стик до гейта max {max(x["c"] for x in pre):5.1f}% | коллектив max {max(x["coll"] for x in pre):5.1f}% | гиро yaw max {max(abs(x["g"][2]) for x in pre):5.0f} | z3 max {max(x["z3"] for x in pre):.0f} | СКО yaw по 300мс: ' + ' '.join(f'{s:.0f}' for s in segs))
    print()
