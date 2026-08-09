import csv
MLOW=158.0; MRANGE=2047.0-158.0
rows=[]
with open('test14.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
            rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                c=max(0.0,(float(row[ix['rcCommand[3]']])-1000)/10),
                a=(sum(m)/4-MLOW)/MRANGE*100,
                g=[float(row[ix[f'gyroADC[{k}]']]) for k in range(3)],
                d7=float(row[ix['debug[7]']])))
        except Exception: pass
t0=rows[0]['t']; T=lambda x:(x['t']-t0)
oi=next(i for i,x in enumerate(rows) if x['d7']>0)
tr=[i for i in range(1,len(rows)) if (rows[i]['d7']>0)!=(rows[i-1]['d7']>0)]
print('переходов debug[7]:', len(tr), '| первые:', [f'{T(rows[i]):.3f}с {"откр" if rows[i]["d7"]>0 else "закр"}' for i in tr[:6]])
print()
print('кадры вокруг первого открытия:')
for i in range(max(0,oi-6), min(len(rows),oi+7)):
    x=rows[i]; gm=max(abs(v) for v in x['g'])
    print(f'  t={T(x):8.4f} d7={x["d7"]:+6.0f} стик={x["c"]:5.2f}% applied={x["a"]:6.2f}% гиро max={gm:5.0f} моторы={[int(v) for v in x["m"]]}')
print()
w=[x for x in rows if T(rows[oi])-0.300 <= T(x) <= T(rows[oi])]
print(f'за 300 мс до открытия: стик max {max(x["c"] for x in w):.2f}%  applied max {max(x["a"] for x in w):.2f}%  гиро max {max(max(abs(v) for v in x["g"]) for x in w):.0f}')
print(f'  кадров applied>=10: {sum(1 for x in w if x["a"]>=10)}   гиро>255: {sum(1 for x in w if max(abs(v) for v in x["g"])>255)}')
