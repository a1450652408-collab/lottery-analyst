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

P9 = {0:2,1:0,2:0,3:2,4:4,5:5,6:20,7:200,8:2000,9:300000}
total=0; d10_hits=[]

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

    prev=set(gn(data[idx-1]))
    must=list(set([n for n in pool35 if n in prev][:3]+[n for n in pool35 if 6<=miss.get(n,100)<=12][:3]+[n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2))>=2][:3]))
    top=sorted(pool35,key=lambda n:-mom[n])[:9]
    sel=list(top)
    for n in must:
        if n not in sel: sel[-1]=n; sel.sort(key=lambda n:-mom[n])
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

    remaining=[n for n in pool35 if n not in sel]
    t10=list(sel)
    t9_tails=set(n%10 for n in sel); missing_tails=[t for t in range(10) if t not in t9_tails]
    cands2=[]
    for n in remaining:
        s=0
        if n%10 in missing_tails: s+=5
        if n in prev: s+=2
        if 6<=miss.get(n,100)<=12: s+=2
        s+=mom.get(n,0)*0.1
        cands2.append((n,s))
    cands2.sort(key=lambda x:-x[1])
    pick=cands2[0][0] if cands2 else remaining[0] if remaining else -1
    t10.append(pick)

    d10=sum(1 for n in t10 if n in drawn)
    d10_hits.append(d10)

# 10码选九复式 C(10,9)=10注/20元
total_prize=0; total_cost=total*20
for h in d10_hits:
    prize=0
    prize += P9.get(9,0)*comb(h,9) if h>=9 else 0
    prize += P9.get(8,0)*comb(h,8)*comb(10-h,1) if h>=8 else 0
    prize += P9.get(7,0)*comb(h,7)*comb(10-h,2) if h>=7 else 0
    prize += P9.get(6,0)*comb(h,6)*comb(10-h,3) if h>=6 else 0
    prize += P9.get(5,0)*comb(h,5)*comb(10-h,4) if h>=5 else 0
    prize += P9.get(4,0)*comb(h,4)*comb(10-h,5) if h>=4 else 0
    prize += P9.get(3,0)*comb(h,3)*comb(10-h,6) if h>=3 else 0
    prize += P9.get(0,0)*comb(h,0)*comb(10-h,9)  # 中0个也有2元
    total_prize+=prize

dist=Counter(d10_hits)
print(f'10码选九复式(10注/20元) 回测{total}期:')
print()
print(f'{"10码中":>6} | {"期数":>4} | {"占比":>6} | {"选九复式奖金":>16}')
print(f'{"─"*40}')
for h in [10,9,8,7,6,5,4,3,2,1,0]:
    cnt=dist.get(h,0)
    if cnt>0:
        if h>=9:
            p_ex = P9[9]*comb(h,9) + P9[8]*comb(h,8)*comb(10-h,1) + P9[7]*comb(h,7)*comb(10-h,2)
        elif h==8:
            p_ex = P9[8]*1 + P9[7]*comb(8,7)*comb(2,2) + P9[6]*comb(8,6)*comb(2,3)
        elif h==7:
            p_ex = P9[7]*comb(7,7)*comb(3,2) + P9[6]*comb(7,6)*comb(3,3)
        elif h==6:
            p_ex = P9[6]*comb(6,6)*comb(4,3) + P9[5]*comb(6,5)*comb(4,4)
        else:
            p_ex = 0
        print(f'{h:>6}个 | {cnt:>4}期 | {cnt/total*100:>5.1f}% | {p_ex:>10,}~元')

avg=sum(d10_hits)/total; mx=max(d10_hits)
net=total_prize-total_cost
print(f'')
print(f'平均命中: {avg:.2f}个 | 最高: {mx}个')
print(f'总投入: {total_cost:,}元 | 总奖金: {total_prize:,}元 | 净盈亏: {net:,}元')
print(f'回报率: {total_prize/total_cost*100:.1f}%')

# 对比
tp2=0; tc2=total*2
for h in d10_hits:
    if h>=10: p=5000000
    elif h==9: p=8000
    elif h==8: p=800
    elif h==7: p=80
    elif h==6: p=6
    elif h==5: p=5
    elif h==4: p=4
    elif h>0: p=2
    else: p=2
    tp2+=p
print(f'')
print(f'对比: 同样号码买选十(1注/2元): 投入{tc2}元 | 奖金{tp2:,}元 | 净{tp2-tc2:,}元 | 回报{tp2/tc2*100:.1f}%')
print(f'对比: 10码选九复式(10注/20元): 投入{total_cost}元 | 奖金{total_prize:,}元 | 净{net:,}元 | 回报{total_prize/total_cost*100:.1f}%')
