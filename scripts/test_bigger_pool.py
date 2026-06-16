import json, urllib.request, time
from collections import Counter
from math import comb

print('拉取4年数据...')
all_items = []
for page in [1, 2, 3]:
    url=f'http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page={page}&limit=500'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    resp=urllib.request.urlopen(req,timeout=30)
    d=json.loads(resp.read().decode('utf-8'))
    all_items.extend(d['data']['data']['list'])

FIELDS=['one','two','three','four','five','six','seven','eight','nine','ten',
        'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty']
data=[]
for item in all_items:
    nums=[]
    for f in FIELDS:
        v=item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    data.append({'n':sorted(nums)})
def gn(d): return d.get('n',[])

print(f'共{len(data)}期, 开始回测...')

for pool_size in [35, 40, 45, 50]:
    t0=time.time()
    total=0; hits=[]
    for idx in range(30,len(data)):
        past=data[idx-30:idx]; draw=data[idx]; drawn=set(gn(draw))
        recent=past[:30]; total+=1
        freq={n:0 for n in range(1,81)}
        for d2 in recent:
            for nn in gn(d2):
                if 1<=nn<=80: freq[nn]+=1
        for ri in range(min(5,len(recent))):
            for nn in gn(recent[ri]):
                if 1<=nn<=80: freq[nn]+=2
        hot=sorted(range(1,81),key=lambda nn:-freq[nn])
        fm=sum(freq.values())/80
        ema_s={}
        for nn in range(1,81):
            seq=[1 if nn in gn(d2) else 0 for d2 in recent]
            seq_rev = seq[::-1]
            e = seq_rev[0]
            for v in seq[1:]: e=0.5*v+0.5*e; ema_s[nn]=e
        miss={}
        for nn in range(1,81):
            for i2,d2 in enumerate(recent):
                if nn in gn(d2): miss[nn]=i2;break
            else: miss[nn]=len(recent)
        s1=set(hot[:20]); s2=set()
        for si in range(0,len(hot),3): s2.add(hot[si])
        if len(s2)<20:
            for si in range(1,len(hot),3): s2.add(hot[si])
        s3=set()
        for zmin,zmax in [[1,20],[21,40],[41,60],[61,80]]:
            c=0
            for nn in hot:
                if zmin<=nn<=zmax: s3.add(nn);c+=1
                if c>=5: break
        s4=set()
        fs={nn:(freq[nn]/fm*10 if fm>0 else 0)+miss[nn]/len(recent)*8+ema_s[nn]*12 for nn in range(1,81)}
        fl=sorted(range(1,81),key=lambda nn:-fs[nn])
        for fi in range(20): s4.add(fl[fi])
        s5=set(hot[:60]); cold=sorted(range(1,81),key=lambda nn:-miss[nn])
        for nn in cold[:40]: s5.add(nn)
        s6=set(s1)
        for nn in hot: s6.add(nn)
        votes={nn:sum(1 for s in [s1,s2,s3,s4,s5,s6] if nn in s) for nn in range(1,81)}
        pool=sorted(range(1,81), key=lambda nn:(-votes[nn], -freq[nn]))[:pool_size]
        mom={n:sum(1 for d2 in recent[:5] if n in gn(d2))*3+ema_s.get(n,0)*12+freq.get(n,0)*0.5 for n in pool}
        prev_draw=set(gn(data[idx-1]))
        
        # 9胆
        must=list(set([n for n in pool if n in prev_draw][:3]+[n for n in pool if 6<=miss.get(n,100)<=12][:3]+[n for n in pool if sum(1 for d2 in recent[:5] if n in gn(d2))>=2][:3]))
        top9=sorted(pool,key=lambda n:-mom[n])[:9]
        sel9=list(top9)
        for n in must:
            if n not in sel9: sel9[-1]=n; sel9.sort(key=lambda n:-mom[n])
        for _ in range(5):
            zc={}
            for n in sel9: z=((n-1)//20); zc[z]=zc.get(z,0)+1
            overload=[z for z,c in zc.items() if c>3]
            if not overload: break
            for oz in overload:
                onums=[n for n in sel9 if (n-1)//20==oz]
                other=[n for n in pool[:35] if (n-1)//20!=oz and n not in sel9]
                other.sort(key=lambda n:-mom[n])
                if other: sel9.remove(min(onums,key=lambda n:mom[n])); sel9.append(other[0])
        th={}
        for t in range(10): th[t]=sum(1 for d2 in recent[:10] for nn in gn(d2) if nn%10==t)
        for _ in range(3):
            ti=set(n%10 for n in sel9)
            if len(ti)>=5: break
            ct=[t for t in range(10) if t not in ti]
            if ct:
                bt=max(ct,key=lambda t:th[t]); cands=[n for n in pool[:35] if n%10==bt and n not in sel9]
                if cands: cands.sort(key=lambda n:-mom[n]); sel9[-1]=cands[0]; sel9.sort(key=lambda n:-mom[n])
        oc=sum(1 for n in sel9 if n%2==1)
        if oc>5:
            extra=[n for n in sel9 if n%2==1]; extra.sort(key=lambda n:mom[n])
            for n in extra:
                if oc<=5: break
                evens=[x for x in pool[:35] if x%2==0 and x not in sel9]
                evens.sort(key=lambda n:-mom[n])
                if evens: sel9.remove(n); sel9.append(evens[0]); oc-=1
        if oc<3:
            extra=[n for n in sel9 if n%2==0]; extra.sort(key=lambda n:mom[n])
            for n in extra:
                if oc>=3: break
                odds=[x for x in pool[:35] if x%2==1 and x not in sel9]
                odds.sort(key=lambda n:-mom[n])
                if odds: sel9.remove(n); sel9.append(odds[0]); oc+=1
        
        # 3补位(从整个pool里选,不是只从35)
        remaining=[n for n in pool if n not in sel9]
        t9_tails=set(n%10 for n in sel9); missing_tails=[t for t in range(10) if t not in t9_tails]
        cands2=[]
        for n in remaining:
            s=0
            if n%10 in missing_tails: s+=6
            if n in prev_draw: s+=3
            if 6<=miss.get(n,100)<=12: s+=3
            s+=mom.get(n,0)*0.1
            cands2.append((n,s))
        cands2.sort(key=lambda x:-x[1])
        picks=[n for n,s in cands2[:3]]
        while len(picks)<3 and remaining:
            for n in remaining:
                if n not in picks: picks.append(n); break
        
        all12=sel9+picks
        h=sum(1 for n in all12 if n in drawn)
        hits.append(h)
    
    avg=sum(hits)/total; mx=max(hits)
    g9=sum(1 for h in hits if h>=9); g10=sum(1 for h in hits if h>=10)
    print(f'\\n{pool_size}码池: 均{avg:.2f}个 | 最高{mx}个 | ≥9:{g9}期 | ≥10:{g10}期 | {time.time()-t0:.0f}s')
    
    # 奖金
    tp=0
    for h in hits:
        if h>=10: tp+=5000000
        elif h==9: tp+=8000
        elif h==8: tp+=800
        elif h==7: tp+=80
        elif h==6: tp+=6
        elif h==5: tp+=5
        elif h==4: tp+=4
        elif h>0: tp+=2
        else: tp+=2
    tc=total*132
    print(f'  投入:{tc:,} | 奖金:{tp:,} | 净:{tp-tc:,} | 回报:{tp/tc*100:.1f}%')
