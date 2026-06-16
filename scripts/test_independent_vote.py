"""
独立特征投票法: 6种完全不同的统计特征,独立投票取共识
"""
import json, urllib.request, math
from collections import Counter

URL = 'http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=500'
FIELDS = ['one','two','three','four','five','six','seven','eight','nine','ten',
          'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty']
req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=30)
d = json.loads(resp.read().decode('utf-8'))
items = d['data']['data']['list']
data = []
for item in items:
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    data.append({'n': sorted(nums)})
def gn(d): return d.get('n', [])

print('=== 独立特征投票法: 6种完全独立统计特征 ===')
print()

total = 0
old_d9 = []   # 动量(旧基准)
vote_d9 = []  # 独立特征投票

for i in range(30, len(data)):
    past = data[i-30:i]
    draw = data[i]
    drawn = set(gn(draw))
    recent = past[:30]
    total += 1

    # ===== 6个完全独立的特征 =====
    
    # 特征1: 纯频率(30期原始计数,不加权)
    f1 = {n: sum(1 for d2 in recent if n in gn(d2)) for n in range(1, 81)}
    
    # 特征2: 纯EMA(最近趋势,不用频率辅助)
    f2 = {}
    for n in range(1, 81):
        seq = [1 if n in gn(d2) else 0 for d2 in recent]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e = 0.5 * v + 0.5 * e
        f2[n] = e
    
    # 特征3: 遗漏值(越久没出的号分数越高)
    f3 = {}
    for n in range(1, 81):
        for i2, d2 in enumerate(recent):
            if n in gn(d2): f3[n] = i2; break
        else: f3[n] = len(recent)
    # 遗漏越长分数越低, 遗漏3-8期最高分
    f3_scored = {n: (8 - min(f3[n], 20)) if f3[n] <= 8 else 0 for n in range(1, 81)}
    
    # 特征4: 近期爆发力(近3期 vs 近10期的比例)
    f4 = {}
    for n in range(1, 81):
        r3 = sum(1 for d2 in recent[:3] if n in gn(d2))
        r10 = sum(1 for d2 in recent[:10] if n in gn(d2))
        # 比例 > 1 = 近期加速
        f4[n] = r3 * 3 - r10 * 0.3  # 简单加速指标
    
    # 特征5: 跨度/区间位置(只看号在1-80中的位置)
    # 把80个号分成5个区, 每区最近出号比例
    zone_hot = {}
    for z in range(5):
        z_start = z * 16 + 1
        z_end = (z + 1) * 16
        zone_count = sum(1 for d2 in recent for nn in gn(d2) if z_start <= nn <= z_end)
        zone_hot[z] = zone_count / max(1, len(recent))
    f5 = {}
    for n in range(1, 81):
        z = (n - 1) // 16
        f5[n] = zone_hot.get(z, 0)
    
    # 特征6: 连续性(看号码是否经常连续出现)
    f6 = {}
    for n in range(1, 81):
        streak = 0
        for d2 in recent:
            if n in gn(d2):
                streak += 1
            else:
                streak = 0
        f6[n] = streak  # 当前连续出现期数
    
    # ===== 6投票 → 35码池 (和之前一样作为基础池) =====
    freq = {n: 0 for n in range(1, 81)}
    for d2 in recent:
        for nn in gn(d2): 
            if 1 <= nn <= 80: freq[nn] += 1
    for ri in range(min(5, len(recent))):
        for nn in gn(recent[ri]): 
            if 1 <= nn <= 80: freq[nn] += 2
    hot = sorted(range(1, 81), key=lambda nn: -freq[nn])
    freq_mean = sum(freq.values()) / 80
    ema_s = {}
    for nn in range(1, 81):
        seq = [1 if nn in gn(d2) else 0 for d2 in recent]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e = 0.5 * v + 0.5 * e; ema_s[nn] = e
    miss = {}
    for nn in range(1, 81):
        for i2, d2 in enumerate(recent):
            if nn in gn(d2): miss[nn] = i2; break
        else: miss[nn] = len(recent)
    s1 = set(hot[:20]); s2 = set()
    for si in range(0, len(hot), 3): s2.add(hot[si])
    if len(s2) < 20:
        for si in range(1, len(hot), 3): s2.add(hot[si])
    s3 = set()
    for zmin, zmax in [[1, 20], [21, 40], [41, 60], [61, 80]]:
        c = 0
        for nn in hot:
            if zmin <= nn <= zmax: s3.add(nn); c += 1
            if c >= 5: break
    s4 = set()
    fs = {nn: (freq[nn] / freq_mean * 10 if freq_mean > 0 else 0) + miss[nn] / len(recent) * 8 + ema_s[nn] * 12
          for nn in range(1, 81)}
    fl = sorted(range(1, 81), key=lambda nn: -fs[nn])
    for fi in range(20): s4.add(fl[fi])
    s5 = set(hot[:60])
    cold = sorted(range(1, 81), key=lambda nn: -miss[nn])
    for nn in cold[:40]: s5.add(nn)
    s6 = set(s1)
    for nn in hot:
        s6.add(nn)
        if len(s6) >= 20: break
    votes = {nn: sum(1 for s in [s1, s2, s3, s4, s5, s6] if nn in s) for nn in range(1, 81)}
    pool35 = sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))[:35]
    
    # 动量(旧基准)
    mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5
           for n in pool35}
    old_d9.append(sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn))
    
    # ===== 独立特征投票 =====
    # 对35码池中的每个号,6个特征独立投票
    vote_counts = {n: 0 for n in pool35}
    
    for n in pool35:
        # 特征1投票: 频率是否在池中前15
        by_f1 = sorted(pool35, key=lambda x: -f1[x])
        if by_f1.index(n) < 15: vote_counts[n] += 1
        
        # 特征2投票: EMA是否在池中前15
        by_f2 = sorted(pool35, key=lambda x: -f2[x])
        if by_f2.index(n) < 15: vote_counts[n] += 1
        
        # 特征3投票: 遗漏回补是否在池中前15
        by_f3 = sorted(pool35, key=lambda x: -f3_scored[x])
        if by_f3.index(n) < 15: vote_counts[n] += 1
        
        # 特征4投票: 近期爆发力是否在池中前15
        by_f4 = sorted(pool35, key=lambda x: -f4[x])
        if by_f4.index(n) < 15: vote_counts[n] += 1
        
        # 特征5投票: 区位热度是否在池中前15
        by_f5 = sorted(pool35, key=lambda x: -f5[x])
        if by_f5.index(n) < 15: vote_counts[n] += 1
        
        # 特征6投票: 连续性是否在池中前15
        by_f6 = sorted(pool35, key=lambda x: -f6[x])
        if by_f6.index(n) < 15: vote_counts[n] += 1
    
    # 按票数排序(6个特征都投=最高共识)
    consensus_ranked = sorted(pool35, key=lambda n: (-vote_counts[n], -mom[n]))
    vote_d9.append(sum(1 for n in consensus_ranked[:9] if n in drawn))

print(f'{"方法":>18} | {"均命中":>6} | {"≥5":>4} | {"≥6":>4} | {"≥7":>4} | {"≥8":>4} | 最高')
print('-' * 55)
for name, vals in [('动量(旧)', old_d9), ('独立特征投票', vote_d9)]:
    avg = sum(vals) / total
    g5 = sum(1 for v in vals if v >= 5)
    g6 = sum(1 for v in vals if v >= 6)
    g7 = sum(1 for v in vals if v >= 7)
    g8 = sum(1 for v in vals if v >= 8)
    mx = max(vals)
    print(f'{name:>18} | {avg:>5.2f} | {g5:>3} | {g6:>3} | {g7:>3} | {g8:>3} | {mx:>3}')

# 高命中期
print(f'\n=== 35码池中13+时 ===')
for i in range(30, len(data)):
    past = data[i-30:i]
    recent = past[:30]
    freq = {n: 0 for n in range(1, 81)}
    for d2 in recent:
        for nn in gn(d2): 
            if 1 <= nn <= 80: freq[nn] += 1
    for ri in range(min(5, len(recent))):
        for nn in gn(recent[ri]): 
            if 1 <= nn <= 80: freq[nn] += 2
    hot = sorted(range(1, 81), key=lambda nn: -freq[nn])
    freq_mean = sum(freq.values()) / 80
    ema_s = {}
    for nn in range(1, 81):
        seq = [1 if nn in gn(d2) else 0 for d2 in recent]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e = 0.5 * v + 0.5 * e; ema_s[nn] = e
    miss = {}
    for nn in range(1, 81):
        for i2, d2 in enumerate(recent):
            if nn in gn(d2): miss[nn] = i2; break
        else: miss[nn] = len(recent)
    s1 = set(hot[:20]); s2 = set()
    for si in range(0, len(hot), 3): s2.add(hot[si])
    if len(s2) < 20:
        for si in range(1, len(hot), 3): s2.add(hot[si])
    s3 = set()
    for zmin, zmax in [[1, 20], [21, 40], [41, 60], [61, 80]]:
        c = 0
        for nn in hot:
            if zmin <= nn <= zmax: s3.add(nn); c += 1
            if c >= 5: break
    s4 = set()
    fs = {nn: (freq[nn] / freq_mean * 10 if freq_mean > 0 else 0) + miss[nn] / len(recent) * 8 + ema_s[nn] * 12
          for nn in range(1, 81)}
    fl = sorted(range(1, 81), key=lambda nn: -fs[nn])
    for fi in range(20): s4.add(fl[fi])
    s5 = set(hot[:60])
    cold = sorted(range(1, 81), key=lambda nn: -miss[nn])
    for nn in cold[:40]: s5.add(nn)
    s6 = set(s1)
    for nn in hot:
        s6.add(nn)
        if len(s6) >= 20: break
    votes = {nn: sum(1 for s in [s1, s2, s3, s4, s5, s6] if nn in s) for nn in range(1, 81)}
    pool35 = sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))[:35]
    
    draw = data[i]
    drawn_set = set(gn(draw))
    h35 = sum(1 for n in pool35 if n in drawn_set)
    if h35 >= 13:
        f1 = {n: sum(1 for d2 in recent if n in gn(d2)) for n in pool35}
        f2 = {}
        for n in pool35:
            seq = [1 if n in gn(d2) else 0 for d2 in recent]
            seq_rev = seq[::-1]
            e = seq_rev[0]
            for v in seq[1:]: e = 0.5 * v + 0.5 * e; f2[n] = e
        f3 = {}
        for n in pool35:
            for i2, d2 in enumerate(recent):
                if n in gn(d2): f3[n] = i2; break
            else: f3[n] = len(recent)
        f3s = {n: (8 - min(f3[n], 20)) if f3[n] <= 8 else 0 for n in pool35}
        f4 = {n: sum(1 for d2 in recent[:3] if n in gn(d2)) * 3 - sum(1 for d2 in recent[:10] if n in gn(d2)) * 0.3 for n in pool35}
        mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5 for n in pool35}
        
        vc = {n: 0 for n in pool35}
        for n in pool35:
            b1 = sorted(pool35, key=lambda x: -f1.get(x,0))
            if b1.index(n) < 15: vc[n] += 1
            b2 = sorted(pool35, key=lambda x: -f2.get(x,0))
            if b2.index(n) < 15: vc[n] += 1
            b3 = sorted(pool35, key=lambda x: -f3s.get(x,0))
            if b3.index(n) < 15: vc[n] += 1
            b4 = sorted(pool35, key=lambda x: -f4.get(x,0))
            if b4.index(n) < 15: vc[n] += 1
        
        d9_old = sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn_set)
        d9_new = sum(1 for n in sorted(pool35, key=lambda n: (-vc[n], -mom[n]))[:9] if n in drawn_set)
        print(f'  池中{h35:>2}个 | 动量{d9_old}个 | 独立投票{d9_new}个')
