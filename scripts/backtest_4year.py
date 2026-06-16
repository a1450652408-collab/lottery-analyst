import json, urllib.request, time
from collections import Counter
from math import comb

print('拉取数据...')
all_items = []
for page in [1, 2, 3]:
    url=f'http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page={page}&limit=500'
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    resp=urllib.request.urlopen(req,timeout=30)
    d=json.loads(resp.read().decode('utf-8'))
    items=d['data']['data']['list']
    all_items.extend(items)

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
    data.append({'n':sorted(nums),'p':str(item.get('code','')),'d':str(item.get('day',''))})

d1=data[-1]['d'] if data else ''
d0=data[0]['d'] if data else ''
print(f'共{len(data)}期 | {d1} ~ {d0} (约{len(data)//365:.0f}年)')

def gn(d): return d.get('n',[])

# 开始回测
t0=time.time()
total=0
all_hits=[]  # 12码命中数
all_d9=[]    # 9胆命中数
all_fill3=[] # 3补位命中数

for idx in range(30, len(data)):
    past=data[idx-30:idx]; draw=data[idx]; drawn=set(gn(draw))
    recent=past[:30]; total+=1
    
    # 基础评分
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
    
    # === 9胆选取 ===
    must=list(set([n for n in pool35 if n in prev_draw][:3]+[n for n in pool35 if 6<=miss.get(n,100)<=12][:3]+[n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2))>=2][:3]))
    top9=sorted(pool35,key=lambda n:-mom[n])[:9]
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
            other=[n for n in pool35 if (n-1)//20!=oz and n not in sel9]
            other.sort(key=lambda n:-mom[n])
            if other: sel9.remove(min(onums,key=lambda n:mom[n])); sel9.append(other[0])
    th={}
    for t in range(10): th[t]=sum(1 for d2 in recent[:10] for nn in gn(d2) if nn%10==t)
    for _ in range(3):
        ti=set(n%10 for n in sel9)
        if len(ti)>=5: break
        ct=[t for t in range(10) if t not in ti]
        if ct:
            bt=max(ct,key=lambda t:th[t]); cands=[n for n in pool35 if n%10==bt and n not in sel9]
            if cands: cands.sort(key=lambda n:-mom[n]); sel9[-1]=cands[0]; sel9.sort(key=lambda n:-mom[n])
    oc=sum(1 for n in sel9 if n%2==1)
    if oc>5:
        extra=[n for n in sel9 if n%2==1]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc<=5: break
            evens=[x for x in pool35 if x%2==0 and x not in sel9]
            evens.sort(key=lambda n:-mom[n])
            if evens: sel9.remove(n); sel9.append(evens[0]); oc-=1
    if oc<3:
        extra=[n for n in sel9 if n%2==0]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc>=3: break
            odds=[x for x in pool35 if x%2==1 and x not in sel9]
            odds.sort(key=lambda n:-mom[n])
            if odds: sel9.remove(n); sel9.append(odds[0]); oc+=1
    
    d9=sum(1 for n in sel9 if n in drawn)
    all_d9.append(d9)
    
    # === 3补位码 ===
    remaining=[n for n in pool35 if n not in sel9]
    t9_tails=set(n%10 for n in sel9)
    missing_tails=[t for t in range(10) if t not in t9_tails]
    candidates=[]
    for n in remaining:
        s=0
        if n%10 in missing_tails: s+=6
        tail_pool_count=sum(1 for x in pool35 if x%10==n%10)
        if tail_pool_count<=3: s+=3
        if n in prev_draw: s+=3
        if 6<=miss.get(n,100)<=12: s+=3
        s+=mom.get(n,0)*0.1
        candidates.append((n,s))
    candidates.sort(key=lambda x:-x[1])
    picks=[n for n,s in candidates[:3]]
    while len(picks)<3 and remaining:
        for n in remaining:
            if n not in picks: picks.append(n); break
    
    fill3=sum(1 for n in picks if n in drawn)
    all_fill3.append(fill3)
    
    # 12码命中
    all12=sel9+picks
    h=sum(1 for n in all12 if n in drawn)
    all_hits.append(h)

elapsed=time.time()-t0
print(f'\\n回测{total}期, 耗时{elapsed:.0f}s')
print()

# 分布
dist12=Counter(all_hits)
dist9=Counter(all_d9)
dist_f3=Counter(all_fill3)

print('📊 12码选十复式(66注/132元) 回测结果')
print('='*55)
print(f'{"12码中":>6} | {"期数":>5} | {"占比":>6} | {"选十奖金":>14}')
print('-'*35)
for h in [12,11,10,9,8,7,6,5,4,3,2,1,0]:
    cnt=dist12.get(h,0)
    if cnt>0:
        prize=0
        if h>=10: prize=5000000
        elif h==9: prize=8000
        elif h==8: prize=800
        elif h==7: prize=80
        elif h==6: prize=6
        elif h==5: prize=5
        elif h==4: prize=4
        elif h>0: prize=2
        else: prize=2
        print(f'{h:>6}个 | {cnt:>5}期 | {cnt/total*100:>5.2f}% | {prize:>10,}元')

# 收益
tp=0
for h in all_hits:
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
net=tp-tc
print()
print(f'💰 收益汇总:')
print(f'   总投入: {tc:,}元')
print(f'   总奖金: {tp:,}元')
print(f'   净盈亏: {net:,}元')
print(f'   回报率: {tp/tc*100:.1f}%')

print(f'\\n📋 关键指标:')
avg=sum(all_hits)/total
print(f'   平均命中: {avg:.2f}个')
print(f'   最高命中: {max(all_hits)}个')
print(f'   中10+: {dist12.get(10,0)+dist12.get(11,0)+dist12.get(12,0)}期')
print(f'   中9+: {sum(1 for h in all_hits if h>=9)}期')
print(f'   中8+: {sum(1 for h in all_hits if h>=8)}期')

# 9胆和补位码的贡献
print(f'\\n📋 9胆 vs 3补位 贡献:')
avg9=sum(all_d9)/total
avg_f3=sum(all_fill3)/total
print(f'   9胆平均: {avg9:.2f}个')
print(f'   3补位平均: {avg_f3:.2f}个')
print(f'   合计: {avg9+avg_f3:.2f}个')
print(f'   9胆占比: {avg9/(avg9+avg_f3)*100:.0f}%')
print(f'   补位占比: {avg_f3/(avg9+avg_f3)*100:.0f}%')

# 列出中10+的期次
print(f'\\n🏆 中10+期详细记录:')
for idx in range(30, len(data)):
    pid=data[idx]['p']; pdate=data[idx]['d']
    h=all_hits[idx-30]
    if h>=10:
        d9=all_d9[idx-30]; f3=all_fill3[idx-30]
        print(f'   {pid}期({pdate}): 12码中{h}个 | 9胆中{d9}个 + 补位中{f3}个')
    if h>=10 and h<12:
        break

# 对比10码选十
tp10=0; tc10=total*2
for h2 in all_hits:
    if h2==9: p=8000
    elif h2==10: p=5000000
    else: p=0
    # 10码选十只能看到前10个
    # 简化: 用12码的命中数估算 实际10码命中≤12码
    tp10+=p
print(f'\\n📊 对比: 10码选十(2元/期) 模拟估算:')
print(f'   投入{tc10:,}元 | 奖金{tp10:,}元(上限)')

# 每期成本对比
print(f'\\n=== 方案日常成本对比 ===')
print(f'{"方案":>16} | 每期 | 每月 | 年投')
print(f'{"─"*45}')
for name, cost in [('2胆拖选三',36),('10码选十',2),('10码选九复式',20),('12码选十',132)]:
    print(f'{name:>16} | {cost:>4}元 | {cost*30:>5}元 | {cost*365:>6}元')
