import csv
rows=[]
with open('btfl_003.01.csv') as fh:
    r=csv.reader(fh); hdr=[h.strip() for h in next(r)]
    ix={h:i for i,h in enumerate(hdr)}
    have=lambda k: k in ix
    for row in r:
        try:
            d=dict(t=int(row[ix['time (us)']])/1e6)
            for k in ['axisP','axisD','axisF','axisI','axisSum']:
                for a in range(3):
                    c=f'{k}[{a}]'
                    if have(c): d[c]=float(row[ix[c]])
            rows.append(d)
        except Exception: pass
names=['roll','pitch','yaw']
print('слагаемые ADRC, логируемые бортом (pid.c:1113-1115 — под ADRC это P/D самого ADRC):')
for a in range(3):
    line=f'  {names[a]:6s}: '
    for k in ['axisP','axisD','axisF','axisI','axisSum']:
        c=f'{k}[{a}]'
        if c in rows[0]:
            v=[x[c] for x in rows]
            line+=f'{k[4:]} {min(v):+6.0f}..{max(v):+6.0f}   '
    print(line)
print()
# сколько кадров сумма P+D упирается в лимит
for a in range(2):
    s=[x[f'axisP[{a}]']+x[f'axisD[{a}]'] for x in rows]
    lim=500
    n=sum(1 for q in s if abs(q)>=lim*0.98)
    print(f'  {names[a]}: |P+D| >= 490 в {n} кадрах ({n/len(rows)*100:.0f}%), max |P+D| = {max(abs(q) for q in s):.0f} при лимите {lim}')
