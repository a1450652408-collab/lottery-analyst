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
            try:
                nums.append(int(v))
            except:
                pass
    return {"p": str(item.get("code","")), "d": str(item.get("day","")), "n": nums[:3]}

all_data = []
for page in [1, 2, 3]:
    items = fetch_page(page)
    if items:
        for item in items:
            all_data.append(parse_item(item))
    time.sleep(1)

seen = set()
deduped = []
for item in all_data:
    if item['p'] not in seen:
        seen.add(item['p'])
        deduped.append(item)

print(f'数据: {len(deduped)}期, {deduped[-1]["d"]} ~ {deduped[0]["d"]}')
print()

# 基础评分
def get_scores(data_pool, window=30):
    use_data = data_pool[1:1+window]
    n = len(use_data)
    scores = {d: 0 for d in range(10)}
    for pos in range(3):
        seq_list = {d: [1 if (len(r['n']) > pos and r['n'][pos] == d) else 0 for r in use_data] for d in range(10)}
        miss = {}
        freq = {}
        for d in range(10):
            s = seq_list[d]
            mv = n
            for j in range(n):
                if s[j] == 1:
                    mv = j
                    break
            miss[d] = mv
            freq[d] = sum(s)
        for d in range(10):
            s = seq_list[d]
            e = s[0] if s else 0
            for v in s[1:]:
                e = 0.5 * v + 0.5 * e
            shortE = s[0] if s else 0
            longE = s[0] if s else 0
            for v in s[1:]:
                shortE = 0.5 * v + 0.5 * shortE
                longE = 0.15 * v + 0.85 * longE
            macd = shortE - longE
            burst = sum(s[:3])
            scores[d] += (e * 0.20 + max(-0.3, min(0.3, macd)) * 0.10 +
                          (burst / 3) * 0.10 +
                          (1.0 - miss[d] / max(n, 1)) * 0.30 +
                          (freq[d] / max(n, 1)) * 0.30)
    return scores

# A: 当前算法
def algo_A(data_pool):
    scores = get_scores(data_pool)
    cooc = {d: {dd: 0 for dd in range(10)} for d in range(10)}
    win = min(31, len(data_pool))
    for ci in range(win):
        cn = data_pool[ci]['n']
        for a in range(len(cn)):
            for b in range(a + 1, len(cn)):
                cooc[cn[a]][cn[b]] += 1
                cooc[cn[b]][cn[a]] += 1
    ranked = sorted(range(10), key=lambda n: -scores[n])
    g = [ranked[0]]
    u = {ranked[0]}
    while len(g) < 5:
        bestN = -1
        bestS = -999
        for dn in ranked:
            if dn in u:
                continue
            cs = sum(cooc[dn][m] for m in g)
            sc = cs * 0.6 + scores[dn] * 0.3
            if sc > bestS:
                bestS = sc
                bestN = dn
        if bestN >= 0:
            g.append(bestN)
            u.add(bestN)
        else:
            break
    return sorted(g)

# B: 冷热均衡 + 半冷号兜底
def algo_B(data_pool):
    scores = get_scores(data_pool)
    # 额外冷号权重
    use_data = data_pool[1:31]
    n = len(use_data)
    extra_cold = {d: 0.0 for d in range(10)}
    for pos in range(3):
        for d in range(10):
            cnt_30 = sum(1 for r in use_data if len(r['n']) > pos and r['n'][pos] == d)
            if cnt_30 == 0:
                extra_cold[d] += 0.5
    for d in range(10):
        scores[d] += extra_cold[d]

    cooc = {d: {dd: 0 for dd in range(10)} for d in range(10)}
    win = min(31, len(data_pool))
    for ci in range(win):
        cn = data_pool[ci]['n']
        for a in range(len(cn)):
            for b in range(a + 1, len(cn)):
                cooc[cn[a]][cn[b]] += 1
                cooc[cn[b]][cn[a]] += 1
    ranked = sorted(range(10), key=lambda n: -scores[n])
    g = [ranked[0]]
    u = {ranked[0]}
    while len(g) < 5:
        bestN = -1
        bestS = -999
        for dn in ranked:
            if dn in u:
                continue
            cs = sum(cooc[dn][m] for m in g)
            sc = cs * 0.5 + scores[dn] * 0.4
            if sc > bestS:
                bestS = sc
                bestN = dn
        if bestN >= 0:
            g.append(bestN)
            u.add(bestN)
        else:
            break
    return sorted(g)

# E: 冷热均衡 + 主动轮换 (如果同一组5码连续推荐10期不中，强制换2个号)
def algo_E(data_pool, history=None):
    scores = get_scores(data_pool)
    # 冷号加成
    use_data = data_pool[1:31]
    for pos in range(3):
        for d in range(10):
            cnt_30 = sum(1 for r in use_data if len(r['n']) > pos and r['n'][pos] == d)
            if cnt_30 == 0:
                scores[d] += 0.5
    
    cooc = {d: {dd: 0 for dd in range(10)} for d in range(10)}
    win = min(31, len(data_pool))
    for ci in range(win):
        cn = data_pool[ci]['n']
        for a in range(len(cn)):
            for b in range(a + 1, len(cn)):
                cooc[cn[a]][cn[b]] += 1
                cooc[cn[b]][cn[a]] += 1
    ranked = sorted(range(10), key=lambda n: -scores[n])
    g = [ranked[0]]
    u = {ranked[0]}
    while len(g) < 5:
        bestN = -1
        bestS = -999
        for dn in ranked:
            if dn in u:
                continue
            cs = sum(cooc[dn][m] for m in g)
            sc = cs * 0.5 + scores[dn] * 0.4
            if sc > bestS:
                bestS = sc
                bestN = dn
        if bestN >= 0:
            g.append(bestN)
            u.add(bestN)
        else:
            break
    return sorted(g)

# F: 评分TOP5 + 冷号兜底
def algo_F(data_pool):
    scores = get_scores(data_pool)
    # 冷号加成
    use_data = data_pool[1:31]
    for pos in range(3):
        for d in range(10):
            cnt_30 = sum(1 for r in use_data if len(r['n']) > pos and r['n'][pos] == d)
            if cnt_30 == 0:
                scores[d] += 0.5
    ranked = sorted(range(10), key=lambda n: -scores[n])
    return sorted(ranked[:5])

# G: 冷热均衡 + 主动轮换(同组推荐5期不中就换)
def algo_G(data_pool, force_change=None):
    scores = get_scores(data_pool)
    use_data = data_pool[1:31]
    for pos in range(3):
        for d in range(10):
            cnt_30 = sum(1 for r in use_data if len(r['n']) > pos and r['n'][pos] == d)
            if cnt_30 == 0:
                scores[d] += 0.5
    
    cooc = {d: {dd: 0 for dd in range(10)} for d in range(10)}
    win = min(31, len(data_pool))
    for ci in range(win):
        cn = data_pool[ci]['n']
        for a in range(len(cn)):
            for b in range(a + 1, len(cn)):
                cooc[cn[a]][cn[b]] += 1
                cooc[cn[b]][cn[a]] += 1
    ranked = sorted(range(10), key=lambda n: -scores[n])
    g = [ranked[0]]
    u = {ranked[0]}
    while len(g) < 5:
        bestN = -1
        bestS = -999
        for dn in ranked:
            if dn in u:
                continue
            cs = sum(cooc[dn][m] for m in g)
            sc = cs * 0.5 + scores[dn] * 0.4
            if sc > bestS:
                bestS = sc
                bestN = dn
        if bestN >= 0:
            g.append(bestN)
            u.add(bestN)
        else:
            break
    return sorted(g)

# H: 双组覆盖 - 把10个数字分成两组5码，轮换推荐
def algo_H_all_groups(data_pool):
    scores = get_scores(data_pool)
    cooc = {d: {dd: 0 for dd in range(10)} for d in range(10)}
    win = min(31, len(data_pool))
    for ci in range(win):
        cn = data_pool[ci]['n']
        for a in range(len(cn)):
            for b in range(a + 1, len(cn)):
                cooc[cn[a]][cn[b]] += 1
                cooc[cn[b]][cn[a]] += 1
    ranked = sorted(range(10), key=lambda n: -scores[n])

    # 组1: 从最高分开始
    def build_group(start, used_set):
        g = [start]
        u = set(used_set) if used_set else set()
        u.add(start)
        while len(g) < 5:
            bestN = -1
            bestS = -999
            for dn in ranked:
                if dn in u:
                    continue
                cs = sum(cooc[dn][m] for m in g)
                sc = cs * 0.6 + scores[dn] * 0.3
                if sc > bestS:
                    bestS = sc
                    bestN = dn
            if bestN >= 0:
                g.append(bestN)
                u.add(bestN)
            else:
                break
        return sorted(g)

    g1 = build_group(ranked[0], None)
    g1_set = set(g1)
    g2_start = None
    for dn in ranked:
        if dn not in g1_set:
            g2_start = dn
            break
    g2 = build_group(g2_start, g1_set) if g2_start else g1[:]
    
    return [g1, g2]

def algo_H(data_pool):
    groups = algo_H_all_groups(data_pool)
    # 选组: 看哪组在最近10期表现更好
    recent = data_pool[1:11]
    def score_grp(g):
        return sum(len(set(r['n']) & set(g)) for r in recent)
    s1, s2 = score_grp(groups[0]), score_grp(groups[1])
    return groups[0] if s1 >= s2 else groups[1]

# I: 冷热 + 5期轮换 (如果推荐一直不换，强制换)
class AlgoI:
    def __init__(self):
        self.last_group = None
        self.no_hit_count = 0
    
    def __call__(self, data_pool):
        scores = get_scores(data_pool)
        use_data = data_pool[1:31]
        for pos in range(3):
            for d in range(10):
                cnt_30 = sum(1 for r in use_data if len(r['n']) > pos and r['n'][pos] == d)
                if cnt_30 == 0:
                    scores[d] += 0.5
        
        cooc = {d: {dd: 0 for dd in range(10)} for d in range(10)}
        win = min(31, len(data_pool))
        for ci in range(win):
            cn = data_pool[ci]['n']
            for a in range(len(cn)):
                for b in range(a + 1, len(cn)):
                    cooc[cn[a]][cn[b]] += 1
                    cooc[cn[b]][cn[a]] += 1
        ranked = sorted(range(10), key=lambda n: -scores[n])
        
        # 如果连续5期同一组不中，强制从第2高分起步
        start_rank = 0
        if self.last_group is not None and self.no_hit_count >= 5:
            start_rank = 1  # 从第2名开始
            self.no_hit_count = 0
        
        g = [ranked[start_rank]]
        u = {ranked[start_rank]}
        if start_rank == 1:
            # 同时踢掉上次推荐里的最冷号
            pass
        
        while len(g) < 5:
            bestN = -1
            bestS = -999
            for dn in ranked:
                if dn in u: continue
                cs = sum(cooc[dn][m] for m in g)
                sc = cs * 0.5 + scores[dn] * 0.4
                if sc > bestS: bestS = sc; bestN = dn
            if bestN >= 0: g.append(bestN); u.add(bestN)
            else: break
        result = sorted(g)
        self.last_group = result
        return result

# 回测
algos = [
    ('A: 当前', algo_A),
    ('B: 冷热均衡', algo_B),
    ('G: 冷热+冷号兜底', algo_G),
    ('H: 双组择优', algo_H),
]

# 回测（带状态重置）
print('===== 全部数据回测(1470期) =====')
for name, algo in algos:
    # 对有状态的算法重置
    if hasattr(algo, '_reset'):
        algo._reset()
    if name == 'I: 冷热+5期轮换':
        ai = AlgoI()
        algo_fn = ai
    else:
        algo_fn = algo
    
    hit3 = total = 0
    max_streak = streak = 0
    streaks = []
    
    for i in range(0, len(deduped) - 30):
        dp = deduped[i:i + 31]
        draw_set = set(deduped[i]['n'])
        group = algo_fn(dp) if name == 'I: 冷热+5期轮换' else algo(dp)
        h = len(draw_set & set(group))
        total += 1
        
        if h < 3:
            streak += 1
            if streak > max_streak:
                max_streak = streak
            # 轮换算法需要知道没中
            if name == 'I: 冷热+5期轮换':
                if ai.last_group and group == ai.last_group:
                    ai.no_hit_count += 1
                else:
                    ai.no_hit_count = 0
        else:
            hit3 += 1
            if streak > 0:
                streaks.append(streak)
            streak = 0
            if name == 'I: 冷热+5期轮换':
                ai.no_hit_count = 0
    if streak > 0:
        streaks.append(streak)
    
    long_20 = sum(1 for s in streaks if s >= 20)
    streaks.sort(reverse=True)
    top3 = streaks[:3]
    
    print(f'{name}:')
    print(f'  中3: {hit3}/{total} ({hit3/total*100:.1f}%) 约{total/max(hit3,1):.1f}期/次')
    print(f'  最长连失: {max_streak}期')
    print(f'  20+连失: {long_20}次')
    print(f'  连失TOP3: {", ".join(str(s) for s in top3)}')
    print()

# 组六开奖只看
print('===== 只看组六开奖 =====')
for name, algo in [('A: 当前', algo_A), ('B: 冷热均衡', algo_B)]:
    hit3 = total = 0
    max_streak = streak = 0
    for i in range(0, len(deduped) - 30):
        dp = deduped[i:i + 31]
        draw_set = set(deduped[i]['n'])
        if len(draw_set) < 3:
            continue
        total += 1
        group = algo(dp)
        h = len(draw_set & set(group))
        if h < 3:
            streak += 1
            if streak > max_streak:
                max_streak = streak
        else:
            hit3 += 1
            streak = 0
    print(f'{name}: 中3:{hit3}/{total}({hit3/total*100:.1f}%) 最长连失:{max_streak}期')
