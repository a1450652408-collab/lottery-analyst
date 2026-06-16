"""
第二轮筛选全新方案测试 - 级联/共生/超共识/分群
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
def ema(s, a=0.5):
    if not s: return 0
    s_rev = s[::-1]
    e = s_rev[0]
    for v in s[1:]: e = a * v + (1 - a) * e
    return e

def get_pool(data, topn=35):
    recent = data[:30]
    freq = {}
    for nn in range(1, 81): freq[nn] = 0
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
        ema_s[nn] = ema(seq, 0.5)
    miss = {}
    for nn in range(1, 81):
        for i, d2 in enumerate(recent):
            if nn in gn(d2): miss[nn] = i; break
        else: miss[nn] = len(recent)
    s1 = set(hot[:20]); s2 = set()
    for si in range(0, len(hot), 3):
        s2.add(hot[si])
        if len(s2) >= 20: break
    if len(s2) < 20:
        for si in range(1, len(hot), 3):
            s2.add(hot[si])
            if len(s2) >= 20: break
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
    ranked = sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))
    return ranked[:topn], freq, ema_s, miss, votes

print('=== 第二轮筛选 全新方案对比 (35码池→9胆) ===')
print()

methods = {}
for k in ['动量(旧)', '级联筛选', '共生分析', '超共识', '分群法']:
    methods[k] = []

for i in range(30, len(data)):
    past = data[i-30:i]
    draw = data[i]
    drawn = set(gn(draw))
    pool35, freq, ema_s, miss, votes = get_pool(past, 35)
    recent = past[:30]

    # 基础数据: 动量
    mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5
           for n in pool35}
    d9 = sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn)
    methods['动量(旧)'].append(d9)

    # 级联: 35→20(近10期频率)→9(动量)
    r10f = {n: sum(1 for d2 in recent[:10] if n in gn(d2)) for n in pool35}
    t20 = sorted(pool35, key=lambda n: -r10f[n])[:20]
    mom2 = {n: sum(1 for d2 in recent[:3] if n in gn(d2)) * 5 + ema_s.get(n, 0) * 20 for n in t20}
    d9 = sum(1 for n in sorted(t20, key=lambda n: -mom2[n])[:9] if n in drawn)
    methods['级联筛选'].append(d9)

    # 共生: 池中号码在历史中一起出现的频率
    cooc = {n: 0 for n in pool35}
    for d2 in recent[:20]:
        ips = set(gn(d2)) & set(pool35)
        for n in ips:
            cooc[n] += len(ips) - 1
    d9 = sum(1 for n in sorted(pool35, key=lambda n: -cooc[n])[:9] if n in drawn)
    methods['共生分析'].append(d9)

    # 超共识: 多维度加权
    scores = {n: 0 for n in pool35}
    for n in pool35:
        fr = sorted(freq, key=lambda x: -freq[x])
        if n in fr: scores[n] += max(0, 35 - fr.index(n)) * 0.5
        er = sorted(range(1, 81), key=lambda x: -ema_s.get(x, 0))
        if n in er: scores[n] += max(0, 35 - er.index(n)) * 0.3
        scores[n] += sum(1 for d2 in recent[:3] if n in gn(d2)) * 3
        r5 = sum(1 for d2 in recent[:5] if n in gn(d2))
        r10 = sum(1 for d2 in recent[5:15] if n in gn(d2))
        scores[n] += (r5 - r10) * 2
        m = miss.get(n, 100)
        if 3 <= m <= 6: scores[n] += 2
    d9 = sum(1 for n in sorted(pool35, key=lambda n: -scores[n])[:9] if n in drawn)
    methods['超共识'].append(d9)

    # 分群: 按尾数分群, 每群选1-2个
    groups = {str(t): [n for n in pool35 if n % 10 == t] for t in range(10)}
    result = []
    for g in sorted(groups, key=lambda g: -len(groups[g])):
        if len(result) >= 9: break
        if groups[g]:
            sg = sorted(groups[g], key=lambda n: -mom[n])
            pick = min(2, 9 - len(result), len(sg))
            result.extend(sg[:pick])
    d9 = sum(1 for n in result[:9] if n in drawn)
    methods['分群法'].append(d9)

total = len(list(methods.values())[0])
print(f'{"方法":>12} | {"均命中":>6} | " >=5" | " >=6" | " >=7" | " >=8" | 最高')
print('-' * 55)
for name, vals in methods.items():
    avg = sum(vals) / total
    g5 = sum(1 for v in vals if v >= 5)
    g6 = sum(1 for v in vals if v >= 6)
    g7 = sum(1 for v in vals if v >= 7)
    g8 = sum(1 for v in vals if v >= 8)
    mx = max(vals)
    print(f'{name:>12} | {avg:>5.2f} | {g5:>4} | {g6:>4} | {g7:>4} | {g8:>4} | {mx:>3}')

# 高命中期
print(f'\n=== 35码池中13+时(8期) 各方法9胆对比 ===')
for i in range(30, len(data)):
    past = data[i-30:i]
    draw = data[i]
    drawn = set(gn(draw))
    pool35, freq, ema_s, miss, votes = get_pool(past, 35)
    h35 = sum(1 for n in pool35 if n in drawn)
    if h35 >= 13:
        recent = past[:30]
        mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2)) * 3 + ema_s.get(n, 0) * 12 + freq.get(n, 0) * 0.5
               for n in pool35}
        r10f = {n: sum(1 for d2 in recent[:10] if n in gn(d2)) for n in pool35}
        t20 = sorted(pool35, key=lambda n: -r10f[n])[:20]
        mom2 = {n: sum(1 for d2 in recent[:3] if n in gn(d2)) * 5 + ema_s.get(n, 0) * 20 for n in t20}
        cooc = {n: 0 for n in pool35}
        for d2 in recent[:20]:
            ips = set(gn(d2)) & set(pool35)
            for n in ips: cooc[n] += len(ips) - 1
        scores = {n: 0 for n in pool35}
        for n in pool35:
            fr = sorted(freq, key=lambda x: -freq[x])
            if n in fr: scores[n] += max(0, 35 - fr.index(n)) * 0.5
            er = sorted(range(1, 81), key=lambda x: -ema_s.get(x, 0))
            if n in er: scores[n] += max(0, 35 - er.index(n)) * 0.3
            scores[n] += sum(1 for d2 in recent[:3] if n in gn(d2)) * 3
            r5 = sum(1 for d2 in recent[:5] if n in gn(d2))
            r10 = sum(1 for d2 in recent[5:15] if n in gn(d2))
            scores[n] += (r5 - r10) * 2
            if 3 <= miss.get(n, 100) <= 6: scores[n] += 2
        d9m = sum(1 for n in sorted(pool35, key=lambda n: -mom[n])[:9] if n in drawn)
        d9c = sum(1 for n in sorted(t20, key=lambda n: -mom2[n])[:9] if n in drawn)
        d9o = sum(1 for n in sorted(pool35, key=lambda n: -cooc[n])[:9] if n in drawn)
        d9s = sum(1 for n in sorted(pool35, key=lambda n: -scores[n])[:9] if n in drawn)
        print(f'  池中{h35:>2}个 | 动量{d9m}个 | 级联{d9c}个 | 共生{d9o}个 | 超共识{d9s}个')
