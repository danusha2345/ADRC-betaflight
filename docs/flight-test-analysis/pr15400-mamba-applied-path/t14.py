import csv,glob
MLOW=158.0; MRANGE=2047.0-158.0
THR=10.0; FLOOR=5.0; GYRO_T=255.0; HOLD=0.025; APP_HOLD=0.250
def cmd(rc): return max(0.0,min(1.0,(rc-1000.0)/1000.0))*100.0
for f in sorted(glob.glob('test14.0*.csv')):
    rows=[]
    with open(f) as fh:
        r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
        ix={h:i for i,h in enumerate(hdr)}
        for row in r:
            try:
                m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
                rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                    c=cmd(float(row[ix['rcCommand[3]']])),
                    a=(sum(m)/4-MLOW)/MRANGE*100,
                    g=max(abs(float(row[ix[f'gyroADC[{k}]']])) for k in range(3)),
                    d7=float(row[ix['debug[7]']]),
                    z3=max(abs(float(row[ix[f'debug[{k}]']])) for k in (2,5,6)),
                    vb=float(row[ix['vbatLatest (V)']])))
            except Exception: pass
    if not rows: continue
    t0=rows[0]['t']; T=lambda x:(x['t']-t0)
    oi=next((i for i,x in enumerate(rows) if x['d7']>0), None)
    pre=rows[:oi] if oi is not None else rows
    print(f"### {f}  {T(rows[-1]):.1f}с  {len(rows)} кадров  vbat {min(x['vb'] for x in rows):.2f}..{max(x['vb'] for x in rows):.2f} В")
    print(f"   до гейта: стик {min(x['c'] for x in pre):.1f}..{max(x['c'] for x in pre):.1f}%  applied {min(x['a'] for x in pre):.1f}..{max(x['a'] for x in pre):.1f}%  гиро max {max(x['g'] for x in pre):.0f}  |z3| max {max(x['z3'] for x in pre):.0f}")
    # окно, где условия applied-ветви выполнены
    ok=[x for x in pre if x['c']>=FLOOR and x['c']<THR and x['a']>=THR]
    print(f"   кадров, где applied-условие выполнено (пол<=стик<{THR:.0f}, applied>={THR:.0f}): {len(ok)}")
    # реконструкция веток
    gs=asS=0.0; res={'direct':None,'gyro':None,'applied':None}; pt=rows[0]['t']; app_at=None
    for i,x in enumerate(rows):
        dt=x['t']-pt; pt=x['t']
        if dt<=0 or dt>0.05: dt=0.0
        idle = x['c']<FLOOR
        if not idle and x['c']>=THR and res['direct'] is None: res['direct']=T(x)
        if not idle and x['g']>GYRO_T:
            gs+=dt
            if gs>=HOLD and res['gyro'] is None: res['gyro']=T(x)
        else: gs=0.0
        if not idle and x['a']>=THR:
            asS+=dt
            if asS>=APP_HOLD and res['applied'] is None: res['applied']=T(x)
        else: asS=0.0
        if oi is not None and i==oi: app_at=asS*1000
    fm=lambda v: f'{v:.3f}с' if v is not None else '—'
    if oi is None:
        print("   ГЕЙТ НЕ ОТКРЫЛСЯ")
    else:
        x=rows[oi]
        print(f"   ГЕЙТ ОТКРЫТ t={T(x):.3f}с  стик={x['c']:.1f}%  applied={x['a']:.1f}%  гиро={x['g']:.0f}")
        print(f"   applied-таймер на момент открытия: {app_at:.0f} мс")
    print(f"   реконструкция: direct={fm(res['direct'])}  gyro={fm(res['gyro'])}  applied={fm(res['applied'])}")
    print()
