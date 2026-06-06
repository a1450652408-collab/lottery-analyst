import json, urllib.request, time

FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

def fetch_page(page):
    r = urllib.request.Request(
        f'http://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page={page}&limit=500',
        headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(r, timeout=30) as resp:
        d = json.loads(resp.read().decode('utf-8'))
    if d.get('code') == 1:
        return d['data']['data']['list']
    return []

def parse_item(item):
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    return {"p": str(item.get("code","")), "d": str(item.get("day","")), "n": nums[:3]}

all_data = []
for page in [1, 2, 3]:
    items = fetch_page(page)
    if items:
        for item in items: all_data.append(parse_item(item))
    time.sleep(1)

seen = set()
deduped = []
for item in all_data:
    if item['p'] not in seen:
        seen.add(item['p']); deduped.append(item)

print(f'数据: {len(deduped)}期, {deduped[-1]["d"]} ~ {deduped[0]["d"]}\n')

def get_scores(data_pool, window=30):
    use_data = data_pool[1:1+window]
    n = len(use_data)
    scores = {d: 0 for d in range(10)}
    for pos in range(3):
        sl = {d: [1 if (len(r['n']) > pos and r['n'][pos] == d) else 0 for r in use_data] for d in range(10)}
        miss = {d: next((j for j in range(n) if sl[d][j] == 1), n) for d in range(10)}
        freq = {d: sum(sl[d]) for d in range(10)}
        for d in range(10):
            s = sl[d]; e = s[0] if s else 0
            for v in s[1:]: e = 0.5 * v + 0.5 * e
            shortE = s[0] if s else 0; longE = s[0] if s else 0
            for v in s[1:]:
                shortE = 0.5 * v + 0.5 * shortE
                longE = 0.15 * v + 0.85 * longE
            macd = shortE - longE; burst = sum(s[:3])
            scores[d] += (e * 0.20 + max(-0.3, min(0.3, macd)) * 0.10 +
                          (burst/3) * 0.10 + (1.0 - miss[d]/max(n,1)) * 0.30 +
                          (freq[d]/max(n,1)) * 0.30)
    return scores

def build_group_from_ranked(ranked, scores, cooc, group_size=5, zone_boost=False, exclude_last=False):
    g = [ranked[0]]; u = {ranked[0]}
    small_zone = {0,1,2,3}; mid_zone = {4,5,6}; large_zone = {7,8,9}
    while len(g) < group_size:
        bestN = -1; bestS = -999
        for dn in ranked:
            if dn in u: continue
            cs = sum(cooc[dn][m] for m in g)
            sc = cs * 0.5 + scores[dn] * 0.4
            if zone_boost:
                has_small = any(x in small_zone for x in g)
                has_mid = any(x in mid_zone for x in g)
                has_large = any(x in large_zone for x in g)
                if dn in small_zone and not has_small: sc += 0.3
                if dn in mid_zone and not has_mid: sc += 0.2
                if dn in large_zone and not has_large: sc += 0.3
            if sc > bestS: bestS = sc; bestN = dn
        if bestN >= 0: g.append(bestN); u.add(bestN)
        else: break
    return sorted(g)

# === 算法定义 ===

# A: baseline
def algo_A(dp):
    s = get_scores(dp)
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    for ci in range(min(31,len(dp))):
        cn = dp[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1,len(cn)): cooc[cn[a]][cn[b]]+=1; cooc[cn[b]][cn[a]]+=1
    ranked = sorted(range(10), key=lambda n:-s[n])
    return build_group_from_ranked(ranked, s, cooc, 5)

# B: 冷热均衡(当前上线)
def algo_B(dp):
    s = get_scores(dp)
    use = dp[1:31]
    for pos in range(3):
        for d in range(10):
            if not any(len(r['n'])>pos and r['n'][pos]==d for r in use): s[d] += 0.5
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    for ci in range(min(31,len(dp))):
        cn = dp[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1,len(cn)): cooc[cn[a]][cn[b]]+=1; cooc[cn[b]][cn[a]]+=1
    ranked = sorted(range(10), key=lambda n:-s[n])
    return build_group_from_ranked(ranked, s, cooc, 5)

# J: 冷热 + 排除上期
def algo_J(dp):
    s = get_scores(dp)
    use = dp[1:31]
    for pos in range(3):
        for d in range(10):
            if not any(len(r['n'])>pos and r['n'][pos]==d for r in use): s[d] += 0.5
    if len(dp) > 1:
        for d in set(dp[0]['n']): s[d] -= 0.3
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    for ci in range(min(31,len(dp))):
        cn = dp[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1,len(cn)): cooc[cn[a]][cn[b]]+=1; cooc[cn[b]][cn[a]]+=1
    ranked = sorted(range(10), key=lambda n:-s[n])
    return build_group_from_ranked(ranked, s, cooc, 5)

# K: 三期融合(短10+中20+长40)
def algo_K(dp):
    s10 = get_scores(dp, 10); s20 = get_scores(dp, 20); s40 = get_scores(dp, 40)
    s = {d: s10[d]*0.3 + s20[d]*0.4 + s40[d]*0.3 for d in range(10)}
    use = dp[1:31]
    for pos in range(3):
        for d in range(10):
            if not any(len(r['n'])>pos and r['n'][pos]==d for r in use): s[d] += 0.5
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    for ci in range(min(31,len(dp))):
        cn = dp[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1,len(cn)): cooc[cn[a]][cn[b]]+=1; cooc[cn[b]][cn[a]]+=1
    ranked = sorted(range(10), key=lambda n:-s[n])
    # 三期融合用更高的评分权重
    g = [ranked[0]]; u = {ranked[0]}
    while len(g) < 5:
        bestN=-1; bestS=-999
        for dn in ranked:
            if dn in u: continue
            cs = sum(cooc[dn][m] for m in g)
            sc = cs*0.4 + s[dn]*0.5
            if sc > bestS: bestS=sc; bestN=dn
        if bestN>=0: g.append(bestN); u.add(bestN)
        else: break
    return sorted(g)

# L: 位置加权(百位0.4,十位0.35,个位0.25) + 遗漏分段
def algo_L(dp):
    use = dp[1:31]; n = len(use)
    scores = {d:0 for d in range(10)}
    pw = [0.4, 0.35, 0.25]
    for pi, pos in enumerate(range(3)):
        sl = {d:[1 if r['n'][pos]==d else 0 for r in use] for d in range(10)}
        miss = {d:next((j for j in range(n) if sl[d][j]==1), n) for d in range(10)}
        freq = {d:sum(sl[d]) for d in range(10)}
        for d in range(10):
            s = sl[d]; e = s[0] if s else 0
            for v in s[1:]: e=0.5*v+0.5*e
            shortE=s[0] if s else 0; longE=s[0] if s else 0
            for v in s[1:]: shortE=0.5*v+0.5*shortE; longE=0.15*v+0.85*longE
            macd=shortE-longE; burst=sum(s[:3])
            m = miss[d]
            if m >= 8: mb = 0.5
            elif m >= 4: mb = 0.25
            else: mb = 0
            scores[d] += pw[pi] * (e*0.20 + max(-0.3,min(0.3,macd))*0.10 + (burst/3)*0.10 +
                                   (1.0-m/n)*0.20 + (freq[d]/n)*0.20 + mb)
    for pos in range(3):
        for d in range(10):
            if not any(len(r['n'])>pos and r['n'][pos]==d for r in use): scores[d] += 0.5
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    for ci in range(min(31,len(dp))):
        cn = dp[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1,len(cn)): cooc[cn[a]][cn[b]]+=1; cooc[cn[b]][cn[a]]+=1
    ranked = sorted(range(10), key=lambda n:-scores[n])
    return build_group_from_ranked(ranked, scores, cooc, 5)

# M: 冷热 + 排除上期 + 大中小均衡
def algo_M(dp):
    s = get_scores(dp)
    use = dp[1:31]
    for pos in range(3):
        for d in range(10):
            if not any(len(r['n'])>pos and r['n'][pos]==d for r in use): s[d] += 0.5
    if len(dp) > 1:
        for d in set(dp[0]['n']): s[d] -= 0.3
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    for ci in range(min(31,len(dp))):
        cn = dp[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1,len(cn)): cooc[cn[a]][cn[b]]+=1; cooc[cn[b]][cn[a]]+=1
    ranked = sorted(range(10), key=lambda n:-s[n])
    return build_group_from_ranked(ranked, s, cooc, 5, zone_boost=True)

# N: 冷热 + 排除上期 + 大中小 + 三期融合
def algo_N(dp):
    s10 = get_scores(dp, 10); s20 = get_scores(dp, 20); s40 = get_scores(dp, 40)
    s = {d: s10[d]*0.3 + s20[d]*0.4 + s40[d]*0.3 for d in range(10)}
    use = dp[1:31]
    for pos in range(3):
        for d in range(10):
            if not any(len(r['n'])>pos and r['n'][pos]==d for r in use): s[d] += 0.5
    if len(dp) > 1:
        for d in set(dp[0]['n']): s[d] -= 0.3
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    for ci in range(min(31,len(dp))):
        cn = dp[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1,len(cn)): cooc[cn[a]][cn[b]]+=1; cooc[cn[b]][cn[a]]+=1
    ranked = sorted(range(10), key=lambda n:-s[n])
    return build_group_from_ranked(ranked, s, cooc, 5, zone_boost=True)

algos = [
    ('A: 当前baseline', algo_A),
    ('B: 冷热均衡(已上线)', algo_B),
    ('J: +排除上期', algo_J),
    ('K: 三期融合评分', algo_K),
    ('L: 位置加权+遗漏分段', algo_L),
    ('M: +排除上期+大中小', algo_M),
    ('N: 三期+排除+大中小', algo_N),
]

print(f'{"算法":24s} {"中3率":>8s} {"频率":>8s} {"最长连失":>10s} {"20+":>5s}')
print('-' * 60)

for name, algo in algos:
    hit3 = total = 0
    max_streak = streak = 0
    streaks = []
    for i in range(0, len(deduped) - 30):
        dp = deduped[i:i+31]
        draw_set = set(deduped[i]['n'])
        group = algo(dp)
        h = len(draw_set & set(group))
        total += 1
        if h < 3:
            streak += 1
            if streak > max_streak: max_streak = streak
        else:
            hit3 += 1
            if streak > 0: streaks.append(streak)
            streak = 0
    if streak > 0: streaks.append(streak)
    streaks.sort(reverse=True)
    long20 = sum(1 for s in streaks if s >= 20)
    freq = total/max(hit3,1)
    top3 = ', '.join(str(s) for s in streaks[:3])
    print(f'{name:24s} {hit3/total*100:6.1f}% {freq:5.1f}期 {max_streak:5d}期    {long20:3d}次  [{top3}]')

# 只看组六
print(f'\n===== 只看组六开奖 =====')
for name, algo in [('B: 冷热均衡', algo_B), ('N: 三期+排除+大中小', algo_N)]:
    hit3 = total = 0
    max_streak = streak = 0
    for i in range(0, len(deduped) - 30):
        dp = deduped[i:i+31]
        draw_set = set(deduped[i]['n'])
        if len(draw_set) < 3: continue
        total += 1
        group = algo(dp)
        h = len(draw_set & set(group))
        if h < 3:
            streak += 1
            if streak > max_streak: max_streak = streak
        else:
            hit3 += 1; streak = 0
    print(f'{name:30s} 中3:{hit3}/{total}({hit3/total*100:.1f}%) 最长连失:{max_streak}期')
