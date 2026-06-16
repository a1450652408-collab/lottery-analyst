"""
彩票界真实选号方法: 分层约束过滤法
不是打分排名,而是用规则一层层筛
"""
import json, urllib.request, random
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

print('=== 彩票界真实方法: 分层约束过滤法 (不是评分,是筛) ===')
print()

total = 0
old_d9 = []
filter_d9 = []

for idx in range(30, len(data)):
    past = data[idx-30:idx]
    draw = data[idx]
    drawn_set = set(gn(draw))
    recent = past[:30]
    total += 1

    # === 阶段1: 6投票→35码池(热号初选) ===
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
    fs = {nn: (freq[nn] / freq_mean * 10 if freq_mean > 0 else 0) + miss[nn] / len(recent) * 8 + ema_s[nn] * 12 for nn in range(1, 81)}
    fl = sorted(range(1, 81), key=lambda nn: -fs[nn])
    for fi in range(20): s4.add(fl[fi])
    s5 = set(hot[:60]); cold = sorted(range(1, 81), key=lambda nn: -miss[nn])
    for nn in cold[:40]: s5.add(nn)
    s6 = set(s1)
    for nn in hot:
        s6.add(nn)
        if len(s6) >= 20: break
    votes = {nn: sum(1 for s in [s1, s2, s3, s4, s5, s6] if nn in s) for nn in range(1, 81)}
    pool35 = sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))[:35]

    # 动量(旧基准)
    mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5 for n in pool35}
    old_d9.append(sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn_set))

    # === 阶段2: 分层约束过滤法 (完全不同的思路) ===
    # 从35码池中,用彩票界方法筛选9个
    
    # 约束1: 四分区均衡 - 每个区至少1个,最多3个
    zones = {0: [], 1: [], 2: [], 3: []}
    for n in pool35:
        z = (n - 1) // 20
        zones[z].append(n)
    
    # 约束2: 奇偶平衡 - 4-5奇 + 4-5偶
    odds = [n for n in pool35 if n % 2 == 1]
    evens = [n for n in pool35 if n % 2 == 0]
    
    # 约束3: 必须含重号(上期号码)
    prev_draw = set(gn(data[idx-1])) if idx > 30 else set()
    repeats = [n for n in pool35 if n in prev_draw]
    
    # 约束4: 必须含热号(近5期高频)
    hot5 = [n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2)) >= 2]
    
    # 约束5: 必须含回补号(遗漏6-12期)
    rebound = [n for n in pool35 if 6 <= miss.get(n, 100) <= 12]
    
    # 约束6: 包含1组连号
    consecutive_groups = []
    pool35_sorted = sorted(pool35)
    i = 0
    while i < len(pool35_sorted) - 1:
        if pool35_sorted[i+1] == pool35_sorted[i] + 1:
            consecutive_groups.append((pool35_sorted[i], pool35_sorted[i+1]))
            i += 2
        else:
            i += 1
    
    # === 用约束条件从35中选出9个 ===
    # 先强制选: 重号(如果有), 回补号, 热号
    must_pick = []
    must_pick.extend(repeats[:2])     # 最多2个重号
    must_pick.extend(rebound[:2])     # 最多2个回补号
    must_pick.extend(hot5[:2])        # 最多2个热号
    
    # 去重
    must_pick = list(set(must_pick))
    
    # 从每个区补充,保证四区均衡
    remaining = 9 - len(must_pick)
    selected = list(must_pick)
    
    # 按动量给所有未选号码排优先级
    candidates = [n for n in pool35 if n not in selected]
    candidates.sort(key=lambda n: -mom[n])
    
    # 填充到9个
    for n in candidates:
        if len(selected) >= 9: break
        # 检查四区均衡: 每个区最多3个
        z = (n - 1) // 20
        zone_count = sum(1 for s in selected if (s - 1) // 20 == z)
        if zone_count < 3:
            selected.append(n)
    
    # 如果还不够9个, 直接补动量最高的
    if len(selected) < 9:
        for n in candidates:
            if len(selected) >= 9: break
            if n not in selected:
                selected.append(n)
    
    filter_d9.append(sum(1 for n in selected[:9] if n in drawn_set))

print(f'{"方法":>18} | {"均命中":>6} | {"≥5":>4} | {"≥6":>4} | {"≥7":>4} | {"≥8":>4} | 最高')
print('-' * 55)
for name, vals in [('动量(旧)', old_d9), ('分层约束过滤', filter_d9)]:
    avg = sum(vals) / total
    g5 = sum(1 for v in vals if v >= 5)
    g6 = sum(1 for v in vals if v >= 6)
    g7 = sum(1 for v in vals if v >= 7)
    g8 = sum(1 for v in vals if v >= 8)
    mx = max(vals)
    print(f'{name:>18} | {avg:>5.2f} | {g5:>3} | {g6:>3} | {g7:>3} | {g8:>3} | {mx:>3}')

# 高命中期
print(f'\n=== 35码池中13+时 ===')
for idx in range(30, len(data)):
    past = data[idx-30:idx]
    draw = data[idx]
    drawn_set = set(gn(draw))
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
    s5 = set(hot[:60]); cold = sorted(range(1, 81), key=lambda nn: -miss[nn])
    for nn in cold[:40]: s5.add(nn)
    s6 = set(s1)
    for nn in hot:
        s6.add(nn)
        if len(s6) >= 20: break
    votes = {nn: sum(1 for s in [s1, s2, s3, s4, s5, s6] if nn in s) for nn in range(1, 81)}
    pool35 = sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))[:35]
    h35 = sum(1 for n in pool35 if n in drawn_set)
    
    if h35 >= 13:
        mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5 for n in pool35}
        prev_draw = set(gn(data[idx-1]))
        repeats = [n for n in pool35 if n in prev_draw]
        rebound = [n for n in pool35 if 6 <= miss.get(n, 100) <= 12]
        hot5 = [n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2)) >= 2]
        
        must = list(set((repeats[:2] + rebound[:2] + hot5[:2])))
        selected = list(must)
        candidates = [n for n in pool35 if n not in selected]
        candidates.sort(key=lambda n: -mom[n])
        
        for n in candidates:
            if len(selected) >= 9: break
            z = (n - 1) // 20
            if sum(1 for s in selected if (s - 1) // 20 == z) < 3:
                selected.append(n)
        if len(selected) < 9:
            for n in candidates:
                if len(selected) >= 9: break
                if n not in selected: selected.append(n)
        
        d9m = sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn_set)
        d9f = sum(1 for n in selected[:9] if n in drawn_set)
        print(f'  池中{h35:>2}个 | 动量{d9m}个 | 分层过滤{d9f}个')
