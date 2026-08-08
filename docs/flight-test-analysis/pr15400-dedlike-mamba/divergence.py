import csv, math
MIX=[(-1,+1,-1),(-1,-1,+1),(+1,+1,+1),(+1,-1,-1)]
MLOW=158.0; MRANGE=2047.0-158.0
rows=[]
with open('btfl_003.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
            mn=[(v-MLOW)/MRANGE for v in m]
            rows.append(dict(t=int(row[ix['time (us)']])/1e6, m=m,
                coll=(sum(m)/4-MLOW)/MRANGE*100,
                gu=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                ax=[sum(mn[i]*MIX[i][a] for i in range(4))/4.0 for a in range(3)]))
        except Exception: pass
t0=rows[0]['t']
def rms(v):
    mu=sum(v)/len(v); return (sum((q-mu)**2 for q in v)/len(v))**0.5
print('огибающая по окнам 30 мс (растёт или стоит?):')
print(' окно, мс | коллектив, % | СКО гиро yaw | СКО гиро roll | СКО команды yaw | мотор на 2047')
W=0.030; s=0.0
while s < rows[-1]['t']-t0-1e-9:
    w=[x for x in rows if s <= x[0 if False else 't']-t0 < s+W]
    if len(w)>=8:
        sat=sum(1 for x in w if max(x['m'])>=2040)/len(w)*100
        print(f'  {s*1000:4.0f}-{(s+W)*1000:4.0f} |    {sum(x["coll"] for x in w)/len(w):6.1f}    |    {rms([x["gu"][2] for x in w]):7.1f}   |    {rms([x["gu"][0] for x in w]):7.1f}    |     {rms([x["ax"][2] for x in w]):.3f}      |   {sat:4.0f}%')
    s += W
print()
g=[rms([x['gu'][2] for x in rows if s0 <= x['t']-t0 < s0+W]) for s0 in [0.0,0.03,0.15,0.18]]
print(f'СКО гиро yaw: первое окно {g[0]:.1f} → последнее {g[-1]:.1f} °/с  = рост ×{g[-1]/max(g[0],1e-9):.1f} за 0.18 с')
c=[rms([x['ax'][2] for x in rows if s0 <= x['t']-t0 < s0+W]) for s0 in [0.0,0.18]]
print(f'СКО команды yaw: {c[0]:.3f} → {c[1]:.3f}  = рост ×{c[1]/max(c[0],1e-9):.1f}')
print(f'коллектив: первые 30 мс {sum(x["coll"] for x in rows if x["t"]-t0<0.03)/max(1,len([x for x in rows if x["t"]-t0<0.03])):.1f}% → последние 30 мс {sum(x["coll"] for x in rows if x["t"]-t0>=0.18)/max(1,len([x for x in rows if x["t"]-t0>=0.18])):.1f}%')
import csv
MIX=[(-1,+1,-1),(-1,-1,+1),(+1,+1,+1),(+1,-1,-1)]
MLOW=158.0; MRANGE=2047.0-158.0
rows=[]
with open('btfl_003.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    for row in r:
        try:
            m=[float(row[ix[f'motor[{k}]']]) for k in range(4)]
            mn=[(v-MLOW)/MRANGE for v in m]
            rows.append(dict(t=int(row[ix['time (us)']])/1e6,
                gu=[float(row[ix[f'gyroUnfilt[{k}]']]) for k in range(3)],
                ax=[sum(mn[i]*MIX[i][a] for i in range(4))/4.0 for a in range(3)]))
        except Exception: pass
t0=rows[0]['t']
def zc_freq(v, dur):
    mu=sum(v)/len(v)
    n=sum(1 for i in range(1,len(v)) if (v[i]>mu)!=(v[i-1]>mu))
    return n/2/dur
print('частота по переходам через среднее, окна 50 мс (без ДПФ — разрешение не мешает).')
print('ВНИМАНИЕ: числа по roll в первых двух окнах (235/102 Гц) - шум, а не тон:')
print('там СКО гиро roll всего 1.1-1.3 град/с, переходы через среднее считает шум.')
print('Осмысленное значение по roll появляется с окна 100-150 мс, когда ось зажигается.')
print(' окно, мс | yaw гиро | yaw команда | roll гиро')
W=0.050; s=0.0
while s < rows[-1]['t']-t0-1e-9:
    w=[x for x in rows if s <= x['t']-t0 < s+W]
    if len(w)>=20:
        d=w[-1]['t']-w[0]['t']
        print(f'  {s*1000:3.0f}-{(s+W)*1000:3.0f} |  {zc_freq([x["gu"][2] for x in w],d):5.0f} Гц |   {zc_freq([x["ax"][2] for x in w],d):5.0f} Гц   |  {zc_freq([x["gu"][0] for x in w],d):5.0f} Гц')
    s += W
