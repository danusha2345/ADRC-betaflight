import csv,glob
MLOW=158.0; MHIGH=2047.0; FULLRANGE=MHIGH-MLOW
VFULL=420.0; VWARN=350.0; CELLS=6; SAGF=1.0
RANGE_CV=VFULL-VWARN
THR=10.0; FLOOR=5.0; GYRO_T=255.0; APP_HOLD=0.250
def load(f):
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        for row in r:
            try:
                m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
                rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                    c=max(0.0,(float(row[ix['rcCommand[3]']])-1000)/10),
                    g=max(abs(float(row[ix[f'gyroADC[{k}]']])) for k in range(3)),
                    d7=float(row[ix['debug[7]']]), vb=float(row[ix['vbatLatest (V)']])))
            except Exception: pass
    return rows
for f in sorted(glob.glob('test14.0*.csv')):
    rows=load(f)
    if not rows: continue
    # сглаженное напряжение банки, как getBatterySagCellVoltage (PT1, ~0.5 c)
    sag=rows[0]['vb']; a=1-2.718**(-0.0005/0.5)
    for x in rows:
        sag += a*(x['vb']-sag); x['sag']=sag
        cv=sag/CELLS*100.0
        good=1.0-max(0.0,min(1.0,(VFULL-cv)/RANGE_CV))
        att=(RANGE_CV/VFULL)*good*SAGF
        rng=(MHIGH-att*FULLRANGE)-MLOW
        x['rng']=rng
        x['a']=(sum(x['m'])/4-MLOW)/rng*100.0       # верно: с учётом sag
        x['a_old']=(sum(x['m'])/4-MLOW)/FULLRANGE*100.0  # как я считал раньше
    t0=rows[0]['t']; T=lambda x:(x['t']-t0)
    oi=next((i for i,x in enumerate(rows) if x['d7']>0), None)
    pre=rows[:oi] if oi is not None else rows
    print(f"### {f}  vbat {min(x['vb'] for x in rows):.2f}..{max(x['vb'] for x in rows):.2f} В  диапазон мотора {min(x['rng'] for x in rows):.0f}..{max(x['rng'] for x in rows):.0f}")
    if oi is None:
        print(f"   гейт не открылся | applied max: было {max(x['a_old'] for x in pre):.2f}% → верно {max(x['a'] for x in pre):.2f}%")
        print(); continue
    x=rows[oi]
    print(f"   ГЕЙТ t={T(x):.3f}с  стик={x['c']:.2f}%  гиро={x['g']:.0f}  applied: было {x['a_old']:.2f}% → ВЕРНО {x['a']:.2f}%")
    # сколько непрерывно держалось applied>=10 при стике в коридоре
    run=0.0; best=0.0; pt=rows[0]['t']
    for y in pre:
        dt=y['t']-pt; pt=y['t']
        if dt<=0 or dt>0.05: dt=0.0
        if y['c']>=FLOOR and y['a']>=THR: run+=dt; best=max(best,run)
        else: run=0.0
    print(f"   непрерывное окно (стик>={FLOOR:.0f}%, applied>={THR:.0f}%) перед открытием: {run*1000:.0f} мс (нужно {APP_HOLD*1000:.0f})")
    print(f"   прямая ветвь: стик max до гейта {max(y['c'] for y in pre):.2f}% (порог {THR:.0f})  | гиро-ветвь: max {max(y['g'] for y in pre):.0f} (порог {GYRO_T:.0f})")
    print()
