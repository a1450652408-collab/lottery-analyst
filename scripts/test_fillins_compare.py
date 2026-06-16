import json, urllib.request
from collections import Counter
from math import comb

URL='http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=500'
FIELDS=['one','two','three','four','five','six','seven','eight','nine','ten',
        'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty']
req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'})
resp=urllib.request.urlopen(req,timeout=30)
d=json.loads(resp.read().decode('utf-8'))
items=d['data']['data']['list']
data=[]
for item in items:
    nums=[]
    for f in FIELDS:
        v=item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    data.append({'n':sorted(nums)})
def gn(d): return d.get('n',[])

def get_9dan_and_pool(recent, pool35, freq, ema_s, miss, votes, mom, prev_draw):
    """统一9胆选取逻辑"""
    must=list(set([n for n in pool35 if n in prev_draw][:3]+[n for n in pool35 if 6<=miss.get(n,100)<=12][:3]+[n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2))>=2][:3]))
    top=sorted(pool35,key=lambda n:-mom[n])[:9]
    sel=list(top)
    for n in must:
        if n not in sel: sel[-1]=n; sel.sort(key=lambda n:-mom[n])
    # 分区矫正
    for _ in range(5):
        zc={}
        for n in sel: z=((n-1)//20); zc[z]=zc.get(z,0)+1
        overload=[z for z,c in zc.items() if c>3]
        if not overload: break
        for oz in overload:
            onums=[n for n in sel if (n-1)//20==oz]
            other=[n for n in pool35 if (n-1)//20!=oz and n not in sel]
            other.sort(key=lambda n:-mom[n])
            if other: sel.remove(min(onums,key=lambda n:mom[n])); sel.append(other[0])
    th={}
    for t in range(10): th[t]=sum(1 for d2 in recent[:10] for nn in gn(d2) if nn%10==t)
    for _ in range(3):
        ti=set(n%10 for n in sel)
        if len(ti)>=5: break
        ct=[t for t in range(10) if t not in ti]
        if ct:
            bt=max(ct,key=lambda t:th[t]); cands=[n for n in pool35 if n%10==bt and n not in sel]
            if cands: cands.sort(key=lambda n:-mom[n]); sel[-1]=cands[0]; sel.sort(key=lambda n:-mom[n])
    oc=sum(1 for n in sel if n%2==1)
    if oc>5:
        extra=[n for n in sel if n%2==1]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc<=5: break
            evens=[x for x in pool35 if x%2==0 and x not in sel]
            evens.sort(key=lambda n:-mom[n])
            if evens: sel.remove(n); sel.append(evens[0]); oc-=1
    if oc<3:
        extra=[n for n in sel if n%2==0]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc>=3: break
            odds=[x for x in pool35 if x%2==1 and x not in sel]
            odds.sort(key=lambda n:-mom[n])
            if odds: sel.remove(n); sel.append(odds[0]); oc+=1
    return sel

def get_fillins(sel, pool35, count, mom, miss, prev_draw, recent):
    """取N个补位码(动量最高+尾数/分区互补)"""
    remaining=[n for n in pool35 if n not in sel]
    t9_tails=set(n%10 for n in sel)
    missing_tails=[t for t in range(10) if t not in t9_tails]
    candidates=[]
    for n in remaining:
        s=0
        if n%10 in missing_tails: s+=6
        tail_pool_count=sum(1 for x in pool35 if x%10==n%10)
        if tail_pool_count<=3: s+=3  # 该尾数在池中稀有
        if n in prev_draw: s+=3
        if 6<=miss.get(n,100)<=12: s+=3
        s+=mom.get(n,0)*0.1
        candidates.append((n,s))
    candidates.sort(key=lambda x:-x[1])
    picks=[n for n,s in candidates[:count]]
    # 不够的话补动量最高的
    while len(picks)<count and remaining:
        for n in remaining:
            if n not in picks:
                picks.append(n)
                break
    return picks

print('=== 9胆+N补位 → 选十复式 各方案对比 ===')
print()

for fillins in [1,2,3,4,5]:
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
        pool35=sorted(range(1,81), key=lambda nn:(-votes[nn], -freq[nn]))[:35]
        mom={n:sum(1 for d2 in recent[:5] if n in gn(d2))*3+ema_s.get(n,0)*12+freq.get(n,0)*0.5 for n in pool35}
        prev_draw=set(gn(data[idx-1]))

        sel9=get_9dan_and_pool(recent, pool35, freq, ema_s, miss, votes, mom, prev_draw)
        picks=get_fillins(sel9, pool35, fillins, mom, miss, prev_draw, recent)
        all_codes=sel9+picks
        
        h=sum(1 for n in all_codes if n in drawn)
        hits.append(h)
    
    total_codes=9+fillins
    bets=comb(total_codes,10) if total_codes>=10 else 0
    cost_per=bets*2
    total_cost=total*cost_per
    
    # 选十奖金
    tp=0
    for h in hits:
        if h>=10: p=5000000
        elif h==9: p=8000
        elif h==8: p=800
        elif h==7: p=80
        elif h==6: p=6
        elif h==5: p=5
        elif h==4: p=4
        elif h>0: p=2
        else: p=2
        tp+=p
    
    avg=sum(hits)/total; mx=max(hits)
    g9=sum(1 for h in hits if h>=9)
    g10=sum(1 for h in hits if h>=10)
    net=tp-total_cost
    roi=tp/total_cost*100 if total_cost>0 else 0
    
    print(f'9胆+{fillins}补位 = {total_codes}码选十:')
    print(f'  C({total_codes},10)={bets}注 | {cost_per}元/期 | 投入{total_cost:,}元')
    print(f'  平均命中: {avg:.2f}个 | 最高: {mx}个 | ≥9: {g9}期 | ≥10: {g10}期')
    print(f'  奖金:{tp:,}元 | 净:{net:,}元 | 回报:{roi:.1f}%')
    # 分布
    dist=Counter(hits)
    top_hits=sorted(dist.keys(), reverse=True)[:3]
    for h in top_hits:
        print(f'    中{h}个: {dist[h]}期 ({dist[h]/total*100:.1f}%)')
    print()
