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

def old_20pool_9dan(recent, prev):
    """网站当前算法: 20码池取前9, 无二次矫正"""
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
    pool20=sorted(range(1,81), key=lambda nn:(-votes[nn], -freq[nn]))[:20]
    return pool20[:9]  # 直接取前9,无二次矫正

def old_20pool_6dan(recent, prev):
    """网站当前算法: 20码池取前6"""
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
    pool20=sorted(range(1,81), key=lambda nn:(-votes[nn], -freq[nn]))[:20]
    return pool20[:6]

def new_35pool_9dan(recent, prev, pool35, mom, miss):
    """35码池综合方法选9胆"""
    must=list(set([n for n in pool35 if n in prev][:3]+[n for n in pool35 if 6<=miss.get(n,100)<=12][:3]+[n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2))>=2][:3]))
    top9=sorted(pool35,key=lambda n:-mom[n])[:9]
    sel=list(top9)
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
    return sel

def new_35pool_6dan(recent, prev, pool35, mom, miss):
    """35码池综合方法选6胆"""
    must=list(set([n for n in pool35 if n in prev][:3]+[n for n in pool35 if 6<=miss.get(n,100)<=12][:3]+[n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2))>=2][:3]))
    top6=sorted(pool35,key=lambda n:-mom[n])[:6]
    sel=list(top6)
    for n in must:
        if n not in sel: sel[-1]=n; sel.sort(key=lambda n:-mom[n])
    for _ in range(3):
        zc={}
        for n in sel: z=((n-1)//20); zc[z]=zc.get(z,0)+1
        overload=[z for z,c in zc.items() if c>2]
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
        if len(ti)>=4: break
        ct=[t for t in range(10) if t not in ti]
        if ct:
            bt=max(ct,key=lambda t:th[t]); cands=[n for n in pool35 if n%10==bt and n not in sel]
            if cands: cands.sort(key=lambda n:-mom[n]); sel[-1]=cands[0]; sel.sort(key=lambda n:-mom[n])
    oc=sum(1 for n in sel if n%2==1)
    if oc>4:
        extra=[n for n in sel if n%2==1]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc<=4: break
            evens=[x for x in pool35 if x%2==0 and x not in sel]
            evens.sort(key=lambda n:-mom[n])
            if evens: sel.remove(n); sel.append(evens[0]); oc-=1
    if oc<2:
        extra=[n for n in sel if n%2==0]; extra.sort(key=lambda n:mom[n])
        for n in extra:
            if oc>=2: break
            odds=[x for x in pool35 if x%2==1 and x not in sel]
            odds.sort(key=lambda n:-mom[n])
            if odds: sel.remove(n); sel.append(odds[0]); oc+=1
    return sel

def get_35pool_and_scores(recent):
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
    return pool35, mom, miss

P7={7:10000,6:288,5:28,4:4,3:2,0:2}
P3={3:53,0:0}

total=0
old9_hits=[]; new9_hits=[]; old6_hits=[]; new6_hits=[]
for idx in range(30,len(data)):
    past=data[idx-30:idx]; draw=data[idx]; drawn=set(gn(draw))
    recent=past[:30]; total+=1
    prev=set(gn(data[idx-1]))
    pool35, mom, miss = get_35pool_and_scores(recent)
    
    old9=old_20pool_9dan(recent, prev)
    new9=new_35pool_9dan(recent, prev, pool35, mom, miss)
    old6=old_20pool_6dan(recent, prev)
    new6=new_35pool_6dan(recent, prev, pool35, mom, miss)
    
    old9_hits.append(sum(1 for n in old9[:9] if n in drawn))
    new9_hits.append(sum(1 for n in new9[:9] if n in drawn))
    old6_hits.append(sum(1 for n in old6[:6] if n in drawn))
    new6_hits.append(sum(1 for n in new6[:6] if n in drawn))

def calc_prize_7(hits):
    tp=0
    for h in hits:
        p=0
        for k in [7,6,5,4,3,0]:
            if h>=k: p+=P7[k]*comb(h,k)*comb(9-h,7-k)
        tp+=p
    return tp

def calc_prize_3(hits):
    tp=0
    for h in hits:
        p=0
        if h>=3: p+=53*comb(h,3)*comb(6-h,0)
        tp+=p
    return tp

print('='*70)
print('网站当前算法(20码池) vs 35码池综合方法 对比')
print('='*70)

# 9胆选七
old9_avg=sum(old9_hits)/total; new9_avg=sum(new9_hits)/total
old9_tp=calc_prize_7(old9_hits); new9_tp=calc_prize_7(new9_hits)
old9_tc=total*comb(9,7)*2; new9_tc=total*comb(9,7)*2

print(f'\n📊 9胆选七复式(36注/72元/期)')
print(f'{"指标":>16} | {"20码池(现网站)":>18} | {"35码池+综合":>18} | {"变化":>10}')
print('-'*68)
print(f'{"平均命中":>16} | {old9_avg:>15.2f}个 | {new9_avg:>15.2f}个 | {new9_avg-old9_avg:>+9.2f}')
print(f'{"中8+":>16} | {sum(1 for h in old9_hits if h>=8):>5}期/{total} | {sum(1 for h in new9_hits if h>=8):>5}期/{total}')
print(f'{"中7+":>16} | {sum(1 for h in old9_hits if h>=7):>5}期/{total} | {sum(1 for h in new9_hits if h>=7):>5}期/{total}')
print(f'{"总奖金":>16} | {old9_tp:>15,}元 | {new9_tp:>15,}元 | {new9_tp-old9_tp:>+9,}')
print(f'{"净盈亏":>16} | {old9_tp-old9_tc:>+15,}元 | {new9_tp-new9_tc:>+15,}元 | {(new9_tp-new9_tc)-(old9_tp-old9_tc):>+9,}')
print(f'{"回报率":>16} | {old9_tp/old9_tc*100:>14.1f}% | {new9_tp/new9_tc*100:>14.1f}% | {(new9_tp/new9_tc-old9_tp/old9_tc)*100:>+8.1f}%')

old9_dist=Counter(old9_hits); new9_dist=Counter(new9_hits)
print(f'\n命中分布:')
for h in [8,7,6,5,4,3]:
    oc=old9_dist.get(h,0); nc=new9_dist.get(h,0)
    print(f'  中{h}个: 原{oc}期({oc/total*100:.2f}%) | 新{nc}期({nc/total*100:.2f}%)')

# 6胆选三
old6_avg=sum(old6_hits)/total; new6_avg=sum(new6_hits)/total
old6_tp=calc_prize_3(old6_hits); new6_tp=calc_prize_3(new6_hits)
old6_tc=total*comb(6,3)*2; new6_tc=total*comb(6,3)*2

print(f'\n📊 6胆选三复式(20注/40元/期)')
print(f'{"指标":>16} | {"20码池(现网站)":>18} | {"35码池+综合":>18} | {"变化":>10}')
print('-'*68)
print(f'{"平均命中":>16} | {old6_avg:>15.2f}个 | {new6_avg:>15.2f}个 | {new6_avg-old6_avg:>+9.2f}')
print(f'{"中3+":>16} | {sum(1 for h in old6_hits if h>=3):>5}期/{total} | {sum(1 for h in new6_hits if h>=3):>5}期/{total}')
print(f'{"总奖金":>16} | {old6_tp:>15,}元 | {new6_tp:>15,}元 | {new6_tp-old6_tp:>+9,}')
print(f'{"净盈亏":>16} | {old6_tp-old6_tc:>+15,}元 | {new6_tp-new6_tc:>+15,}元 | {(new6_tp-new6_tc)-(old6_tp-old6_tc):>+9,}')
print(f'{"回报率":>16} | {old6_tp/old6_tc*100:>14.1f}% | {new6_tp/new6_tc*100:>14.1f}%')

old6_dist=Counter(old6_hits); new6_dist=Counter(new6_hits)
print(f'\n命中分布:')
for h in [6,5,4,3]:
    oc=old6_dist.get(h,0); nc=new6_dist.get(h,0)
    print(f'  中{h}个: 原{oc}期({oc/total*100:.2f}%) | 新{nc}期({nc/total*100:.2f}%)')
