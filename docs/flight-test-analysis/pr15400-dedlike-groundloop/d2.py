import csv,math,cmath
MLOW=158.0; MRANGE=2047.0-158.0
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
for f,lab in [('groundloop_btfl_all.01.csv','лог 1/2 (норм)'),('groundloop_btfl_all.02.csv','лог 2/2 (УБЕГАНИЕ)')]:
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        hasD2 = 'axisD[2]' in ix
        for row in r:
            try:
                m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
                rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                    c=float(row[ix['setpoint[3]']])/10.0,
                    g=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                    coll=(sum(m)/4-MLOW)/MRANGE*100,
                    d7=float(row[ix['debug[7]']]),
                    z3=max(abs(float(row[ix[f'debug[{k}]']])) for k in (2,5,6)),
                    P=[float(row[ix[f'axisP[{a}]']]) for a in range(3)],
                    D2=float(row[ix['axisD[2]']]) if hasD2 else None))
            except Exception: pass
    t0=rows[0]['t']; T=lambda x:(x['t']-t0)
    oi=next((i for i,x in enumerate(rows) if x['d7']>0), None)
    print(f'### {lab}  {T(rows[-1]):.2f}с  {len(rows)} кадров  axisD[2]: {"есть" if rows[0]["D2"] is not None else "нет"}')
    print(f'   гейт: {"открыт t=%.3fс"%T(rows[oi]) if oi is not None else "НЕ открывался"}')
    pre = rows[:oi] if oi is not None else rows
    print(f'   до гейта: commanded max {max(x["c"] for x in pre):.1f}%  коллектив max {max(x["coll"] for x in pre):.1f}%  |z3| max {max(x["z3"] for x in pre):.0f}')
    print(f'   вся сессия: коллектив {min(x["coll"] for x in rows):.1f}..{max(x["coll"] for x in rows):.1f}%  commanded {min(x["c"] for x in rows):.1f}..{max(x["c"] for x in rows):.1f}%')
    for a,nm in enumerate(['roll','pitch','yaw']):
        print(f'   {nm:6s}: гиро СКО {rms([x["g"][a] for x in rows]):6.1f} размах {min(x["g"][a] for x in rows):+6.0f}..{max(x["g"][a] for x in rows):+6.0f}  axisP размах {min(x["P"][a] for x in rows):+6.0f}..{max(x["P"][a] for x in rows):+6.0f}')
    if rows[0]['D2'] is not None:
        v=[x['D2'] for x in rows]
        print(f'   axisD[2] (yaw D-эквивалент): размах {min(v):+.0f}..{max(v):+.0f}  СКО {rms(v):.1f}  против axisP[2] СКО {rms([x["P"][2] for x in rows]):.1f}  → D/P {rms(v)/max(rms([x["P"][2] for x in rows]),1e-9):.2f}')
    sat=sum(1 for x in rows if max(x['m'])>=2040)/len(rows)*100
    print(f'   мотор >=2040 (околоупор): {sat:.1f}% кадров')
    print()
