import json, urllib.request
from collections import Counter
from math import comb

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

def get_pool_and_scores(recent):
    freq={n:0 for n in range(1,81)}
    for d2 in recent:
        for nn in gn(d2):
            if 1<=nn<=80: freq[nn]+=1
    for ri in range(min(5,len(recent))):
        for nn in gn(recent[ri]):
            if 1<=nn<=80: freq[nn]+=2
    hot=sorted(range(1,81),key=lambda nn:-freq[nn])
    fm=sum(freq.values())/80
    ema_s={}; miss={}
    for nn in range(1,81):
        seq=[1 if nn in gn(d2) else 0 for d2 in recent]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e=0.5*v+0.5*e; ema_s[nn]=e
        for i2,d2 in enumerate(recent):
            if nn in gn(d2): miss[nn]=i2;break
        else: miss[nn]=len(recent)
    s1=set(hot[:20]); s2=set()
    for si in range(0,len(hot),3):
        s2.add(hot[si])
        if len(s2)>=20: break
    if len(s2)<20:
        for si in range(1,len(hot),3):
            s2.add(hot[si])
            if len(s2)>=20: break
    s3=set()
    for zmin,zmax in [[1,20],[21,40],[41,60],[61,80]]:
        c=0
        for nn in hot:
            if zmin<=nn<=zmax:
                s3.add(nn); c+=1
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
    return pool35, mom, freq, ema_s, miss

def select_dantuo(pool35, mom, miss, prev, recent, dc):
    must=list(set([n for n in pool35 if n in prev][:3]+[n for n in pool35 if 6<=miss.get(n,100)<=12][:3]+[n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2))>=2][:3]))
    top=sorted(pool35,key=lambda n:-mom[n])[:dc]
    sel=list(top)
    for n in must:
        if n not in sel: sel[-1]=n; sel.sort(key=lambda n:-mom[n])
    max_per_zone=max(2, dc//3)
    for _ in range(3):
        zc={}
        for n in sel: z=((n-1)//20); zc[z]=zc.get(z,0)+1
        overload=[z for z,c in zc.items() if c>max_per_zone]
        if not overload: break
        for oz in overload:
            onums=[n for n in sel if (n-1)//20==oz]
            other=[n for n in pool35 if (n-1)//20!=oz and n not in sel]
            other.sort(key=lambda n:-mom[n])
            if other: sel.remove(min(onums,key=lambda n:mom[n])); sel.append(other[0])
    th={}
    for t in range(10): th[t]=sum(1 for d2 in recent[:10] for nn in gn(d2) if nn%10==t)
    min_tails=max(3, dc//2)
    for _ in range(3):
        ti=set(n%10 for n in sel)
        if len(ti)>=min_tails: break
        ct=[t for t in range(10) if t not in ti]
        if ct:
            bt=max(ct,key=lambda t:th[t]); cands=[n for n in pool35 if n%10==bt and n not in sel]
            if cands: cands.sort(key=lambda n:-mom[n]); sel[-1]=cands[0]; sel.sort(key=lambda n:-mom[n])
    oc=sum(1 for n in sel if n%2==1)
    tgt_hi=dc//2+1; tgt_lo=max(1, dc//2-1)
    if oc>tgt_hi:
        extra=[n for n in sel if n%2==1]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc<=tgt_hi: break
            opp=[x for x in pool35 if x%2==0 and x not in sel]
            opp.sort(key=lambda n:-mom[n])
            if opp: sel.remove(n); sel.append(opp[0]); oc-=1
    if oc<tgt_lo:
        extra=[n for n in sel if n%2==0]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc>=tgt_lo: break
            opp=[x for x in pool35 if x%2==1 and x not in sel]
            opp.sort(key=lambda n:-mom[n])
            if opp: sel.remove(n); sel.append(opp[0]); oc+=1
    return sel

total=0
d7_hits=[]; d8_hits=[]
for idx in range(30,len(data)):
    past=data[idx-30:idx]; draw=data[idx]; drawn=set(gn(draw))
    recent=past[:30]; total+=1
    prev=set(gn(data[idx-1]))
    pool35, mom, freq, ema_s, miss = get_pool_and_scores(recent)
    
    sel7=select_dantuo(pool35, mom, miss, prev, recent, 7)
    d7_hits.append(sum(1 for n in sel7[:7] if n in drawn))
    
    sel8=select_dantuo(pool35, mom, miss, prev, recent, 8)
    d8_hits.append(sum(1 for n in sel8[:8] if n in drawn))

P5={5:1000,4:21,3:3,0:2}
bets5=comb(7,5); cost5=bets5*2; tp5=0
for h in d7_hits:
    p=0
    for k in [5,4,3,0]:
        if h>=k: p+=P5[k]*comb(h,k)*comb(7-h,5-k)
    tp5+=p
tc5=total*cost5

P6={6:3000,5:30,4:10,3:3,0:2}
bets6=comb(8,6); cost6=bets6*2; tp6=0
for h in d8_hits:
    p=0
    for k in [6,5,4,3,0]:
        if h>=k: p+=P6[k]*comb(h,k)*comb(8-h,6-k)
    tp6+=p
tc6=total*cost6

print(f'=== 7胆选五复式(21注/42元/期) ===')
d7=Counter(d7_hits)
for h in sorted(d7.keys(), reverse=True):
    cnt=d7.get(h,0)
    print(f'  {h}个: {cnt}期 ({cnt/total*100:.2f}%)')
avg7=sum(d7_hits)/total
print(f'平均: {avg7:.2f}个 | 净:{tp5-tc5:,}元 | 回报:{tp5/tc5*100:.1f}%')

print(f'\n=== 8胆选六复式(28注/56元/期) ===')
d8=Counter(d8_hits)
for h in sorted(d8.keys(), reverse=True):
    cnt=d8.get(h,0)
    print(f'  {h}个: {cnt}期 ({cnt/total*100:.2f}%)')
avg8=sum(d8_hits)/total
print(f'平均: {avg8:.2f}个 | 净:{tp6-tc6:,}元 | 回报:{tp6/tc6*100:.1f}%')

print(f'\n对比 9胆选七复式(36注/72元): 净+87,030元 | 回报182.2%')
