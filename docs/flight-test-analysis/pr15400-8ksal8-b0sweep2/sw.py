import csv,math,cmath,glob,os
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
for f in sorted(glob.glob('*.01.csv')):
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        for row in r:
            try:
                rows.append((int(row[ix['time (us)']])/1e6,
                    float(row[ix['gyroADC[2]']]), float(row[ix['setpoint[2]']]),
                    float(row[ix['gyroUnfilt[2]']]),
                    [float(row[ix[f'motor[{k}]']]) for k in range(4)],
                    float(row[ix['axisP[2]']])))
            except Exception: pass
    if len(rows)<500: print(f'{f}: мало'); continue
    err=[abs(x[2]-x[1]) for x in rows]; err.sort()
    sat=sum(1 for x in rows if max(x[4])>=2040)/len(rows)*100
    # спектр yaw-гироскопа на спокойных участках
    calm=[x for x in rows if abs(x[2])<50]
    print(f'{f[:12]:13s} ошибка yaw медиана {err[len(err)//2]:5.1f} p90 {err[int(len(err)*0.9)]:6.1f} | СКО гиро yaw {rms([x[3] for x in rows]):6.1f} | спок. {rms([x[3] for x in calm]) if calm else 0:6.1f} | мотор на упоре {sat:4.1f}%')
