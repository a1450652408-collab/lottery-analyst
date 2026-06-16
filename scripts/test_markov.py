"""
马尔可夫链 + 条件概率 第二轮筛选测试
"""
import json, urllib.request
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

print('=== 马尔可夫链 + 条件概率 第二轮筛选 ===')
print()

# 全局转移概率
all_trans = {n: {'00': 0, '01': 0, '10': 0, '11': 0} for n in range(1, 81)}
for i in range(1, len(data)):
    prev = set(gn(data[i-1]))
    cur = set(gn(data[i]))
    for n in range(1, 81):
        p = 1 if n in prev else 0
        c = 1 if n in cur else 0
        all_trans[n][str(p) + str(c)] += 1

total = 0
old_d9, markov_d9 = [], []

for i in range(30, len(data)):
    past = data[i-30:i]
    draw = data[i]
    drawn = set(gn(draw))
    recent = past[:30]
    total += 1

    # 6投票 → 35码池
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
    s5 = set(hot[:60])
    cold = sorted(range(1, 81), key=lambda nn: -miss[nn])
    for nn in cold[:40]: s5.add(nn)
    s6 = set(s1)
    for nn in hot:
        s6.add(nn)
        if len(s6) >= 20: break
    votes = {nn: sum(1 for s in [s1, s2, s3, s4, s5, s6] if nn in s) for nn in range(1, 81)}
    pool35 = sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))[:35]

    # 动量(旧)
    mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5 for n in pool35}
    old_d9.append(sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn))

    # 马尔可夫链
    prev_draw = set(gn(data[i-1])) if i > 30 else set()
    mk_score = {n: 0 for n in pool35}
    for n in pool35:
        was = 1 if n in prev_draw else 0
        t = all_trans[n]
        if was:
            mk_score[n] = t['11'] / max(1, t['11'] + t['10'])
        else:
            mk_score[n] = t['01'] / max(1, t['01'] + t['00'])
        mk_score[n] += ema_s.get(n, 0) * 10
    mk_r = sorted(pool35, key=lambda n: -mk_score[n])
    markov_d9.append(sum(1 for n in mk_r[:9] if n in drawn))

print(f'{"方法":>14} | {"均命中":>6} | {"≥5":>4} | {"≥6":>4} | {"≥7":>4} | {"≥8":>4} | 最高')
print('-' * 52)
for name, vals in [('动量(旧)', old_d9), ('马尔可夫链', markov_d9)]:
    avg = sum(vals) / total
    g5 = sum(1 for v in vals if v >= 5)
    g6 = sum(1 for v in vals if v >= 6)
    g7 = sum(1 for v in vals if v >= 7)
    g8 = sum(1 for v in vals if v >= 8)
    mx = max(vals)
    print(f'{name:>14} | {avg:>5.2f} | {g5:>3} | {g6:>3} | {g7:>3} | {g8:>3} | {mx:>3}')

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
    h35 = sum(1 for n in pool35 if n in drawn)
    if h35 >= 13:
        prev_draw = set(gn(data[i-1]))
        mk = {n: 0 for n in pool35}
        for n in pool35:
            was = 1 if n in prev_draw else 0
            t = all_trans[n]
            mk[n] = (t['11'] / max(1, t['11'] + t['10']) if was else t['01'] / max(1, t['01'] + t['00'])) + ema_s.get(n, 0) * 10
        mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5
               for n in pool35}
        d9m = sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn)
        d9k = sum(1 for n in sorted(pool35, key=lambda n: -mk[n])[:9] if n in drawn)
        print(f'  池中{h35:>2}个 | 动量{d9m}个 | 马尔可夫{d9k}个')
