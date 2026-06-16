"""
第二轮用历史回溯法: 随机生成10万组9胆组合,找历史最优
"""
import json, urllib.request, math, random
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

print('=== 全新思路: 历史回溯法 (不评分,直接组合寻优) ===')
print()

# 先用6投票生成35码池
def get_pool35(data):
    recent = data[:30]
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
    return sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))[:35], freq, ema_s

# 方法1: 动量(旧)
# 方法2: 历史回溯法 - 从过往数据中找到最匹配的"模板期"
# 方法3: 分群互补法 - 不排名,找互不重复的9个号

total = 0
old_d9 = []
backtest_d9 = []
complement_d9 = []

for idx in range(30, len(data)):
    past = data[idx-30:idx]
    draw = data[idx]
    drawn_set = set(gn(draw))
    recent = past[:30]
    total += 1
    
    pool35, freq, ema_s = get_pool35(past)
    
    # === 方法1: 动量(旧) ===
    mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5 for n in pool35}
    old_d9.append(sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn_set))
    
    # === 方法2: 历史回溯法 ===
    # 在近20期中,看每期35码池里哪些号实际中了
    # 找出"如果当时选了这9个,能中几个"
    best_set = None
    best_score = -1
    n_trials = 2000  # 每期随机试2000组
    
    for _ in range(n_trials):
        trial = random.sample(pool35, 9)
        # 看这9个在近20期的命中表现
        score = 0
        for k in range(1, 21):
            if idx - k >= 30:
                hist_draw = set(gn(data[idx-k]))
                hits_in_hist = sum(1 for n in trial if n in hist_draw)
                # 更看重近期 + 高命中(≥6)
                weight = (21 - k) * (1 + max(0, hits_in_hist - 5))
                score += weight
        if score > best_score:
            best_score = score
            best_set = trial[:]
    
    backtest_d9.append(sum(1 for n in best_set if n in drawn_set))
    
    # === 方法3: 分群互补法 ===
    # 把35码池按尾数分成10个组
    groups = {}
    for n in pool35:
        t = n % 10
        if t not in groups: groups[t] = []
        groups[t].append(n)
    
    # 从每组选1个(按动量选组内最好的),最多9组
    comp_result = []
    used_groups = sorted(groups.keys(), key=lambda g: -len(groups[g]))
    for g in used_groups:
        if len(comp_result) >= 9: break
        if groups[g]:
            # 组内按动量选最好的
            best_in_group = max(groups[g], key=lambda n: mom.get(n, 0))
            if best_in_group not in comp_result:
                comp_result.append(best_in_group)
    
    # 如果不够9个,从剩余号里补
    remaining = [n for n in pool35 if n not in comp_result]
    remaining.sort(key=lambda n: -mom.get(n, 0))
    comp_result.extend(remaining[:9 - len(comp_result)])
    complement_d9.append(sum(1 for n in comp_result[:9] if n in drawn_set))

print(f'{"方法":>16} | {"均命中":>6} | {"≥5":>4} | {"≥6":>4} | {"≥7":>4} | {"≥8":>4} | 最高')
print('-' * 55)
for name, vals in [('动量(旧)', old_d9), ('历史回溯法', backtest_d9), ('分群互补法', complement_d9)]:
    avg = sum(vals) / total
    g5 = sum(1 for v in vals if v >= 5)
    g6 = sum(1 for v in vals if v >= 6)
    g7 = sum(1 for v in vals if v >= 7)
    g8 = sum(1 for v in vals if v >= 8)
    mx = max(vals)
    print(f'{name:>16} | {avg:>5.2f} | {g5:>3} | {g6:>3} | {g7:>3} | {g8:>3} | {mx:>3}')

# 高命中期
print(f'\n=== 35码池中13+时 ===')
for idx in range(30, len(data)):
    past = data[idx-30:idx]
    recent = past[:30]
    pool35, freq, ema_s = get_pool35(past)
    draw = data[idx]
    drawn_set = set(gn(draw))
    h35 = sum(1 for n in pool35 if n in drawn_set)
    if h35 >= 13:
        mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5 for n in pool35}
        
        # 回溯法重算
        best_set = None
        best_score = -1
        for _ in range(2000):
            trial = random.sample(pool35, 9)
            score = 0
            for k in range(1, 21):
                if idx - k >= 30:
                    hist_draw = set(gn(data[idx-k]))
                    hits = sum(1 for n in trial if n in hist_draw)
                    score += (21 - k) * (1 + max(0, hits - 5))
            if score > best_score:
                best_score = score
                best_set = trial[:]
        
        d9m = sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn_set)
        d9b = sum(1 for n in best_set if n in drawn_set) if best_set else 0
        
        # 分群法
        groups = {}
        for n in pool35:
            t = n % 10
            if t not in groups: groups[t] = []
            groups[t].append(n)
        comp = []
        for g in sorted(groups.keys(), key=lambda g: -len(groups[g])):
            if len(comp) >= 9: break
            if groups[g]:
                best = max(groups[g], key=lambda n: mom.get(n, 0))
                if best not in comp: comp.append(best)
        remaining = [n for n in pool35 if n not in comp]
        remaining.sort(key=lambda n: -mom.get(n, 0))
        comp.extend(remaining[:9 - len(comp)])
        d9c = sum(1 for n in comp[:9] if n in drawn_set)
        
        print(f'  池中{h35:>2}个 | 动量{d9m}个 | 回溯{d9b}个 | 互补{d9c}个')
