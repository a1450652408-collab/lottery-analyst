"""
快乐8 增强推荐 vs 实际开奖 逐期对比
复现网站 EMA+16池 算法，生成最近30期的推荐号码与开奖号对比
"""
import json, math

with open('data/kl8_500.json', encoding='utf-8') as f:
    raw = json.load(f)
# 日期倒序（最新在前）
raw_sorted = sorted(raw, key=lambda x: x['p'], reverse=True)

def get_nums(d):
    return d.get('n', d.get('r', []))

def website_ema_16pool(window, data_all, predict_idx):
    """
    复现网站算法:
    1. EMA评分
    2. 四区TOP4=16码池
    3. 滑动窗口5组选五
    """
    period = len(window)
    # EMA
    ema = {}
    for n in range(1, 81):
        seq = [1 if n in get_nums(d) else 0 for d in window]
        if not seq: ema[n] = 0; continue
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e = 0.3 * v + 0.7 * e
        ema[n] = e
    
    # 动量
    r5, p5 = {}, {}
    for n in range(1, 81): r5[n] = 0; p5[n] = 0
    for j in range(min(10, period)):
        for n in get_nums(window[j]):
            if not (1 <= n <= 80): continue
            if j < 5: r5[n] += 1
            else: p5[n] += 1
    mom = {}
    for n in range(1, 81):
        m_ = (r5[n] - p5[n]) / max(p5[n], 1)
        mom[n] = max(-2, min(2, m_))
    
    # 近30期频率
    freq30 = {}
    win30 = min(30, period)
    for n in range(1, 81): freq30[n] = 0
    for j in range(win30):
        for n in get_nums(window[j]):
            if 1 <= n <= 80: freq30[n] += 1
    
    # 重号（上期）
    prev_set = set()
    if len(window) > 0:
        for n in get_nums(window[0]): prev_set.add(n)
    
    # 杀号
    freq_all = {}
    for n in range(1, 81): freq_all[n] = 0
    for d in window:
        for n in get_nums(d):
            if 1 <= n <= 80: freq_all[n] += 1
    last_seen = {}
    for idx, d in enumerate(window):
        for n in get_nums(d):
            if 1 <= n <= 80: last_seen[n] = idx
    for n in range(1, 81):
        if n not in last_seen: last_seen[n] = -1
    miss = {n: period - 1 - last_seen[n] for n in range(1, 81)}
    kills = []
    for n in range(1, 81):
        if freq_all[n] == 0 and miss[n] >= 15: kills.append(n)
        elif miss[n] >= 12: kills.append(n)
    kill_set = set(kills[:5])
    
    # 综合评分
    scores = {}
    for n in range(1, 81):
        s = ema.get(n, 0) * 5.0 + (freq30.get(n, 0) / win30) * 3.0 + mom.get(n, 0) * 2.0
        if n in prev_set: s += 3.0
        if n in kill_set: s = -999
        scores[n] = s
    
    # 冷号混合
    last_seen2 = {n: -1 for n in range(1, 81)}
    for idx, d in enumerate(data_all[:predict_idx]):
        for n in get_nums(d):
            if 1 <= n <= 80: last_seen2[n] = idx
    miss2 = {n: predict_idx - 1 - last_seen2[n] for n in range(1, 81)}
    for n in range(1, 81):
        scores[n] += max(0, 10 - miss2[n]) * 0.5
    
    # 全部排名
    ranked = sorted(range(1, 81), key=lambda x: -scores[x])
    top35 = ranked[:35]
    
    # 四区TOP4=16码池
    pool_16 = []
    for zs in [1, 21, 41, 61]:
        zn = list(range(zs, zs + 20))
        zn.sort(key=lambda n: -scores.get(n, 0))
        pool_16.extend(zn[:4])
    
    # 16码池按评分排序
    sorted_16 = sorted(pool_16, key=lambda n: -scores.get(n, 0))
    
    # 滑动窗口5组选五
    windows = [[0, 4], [3, 7], [5, 9], [8, 12], [11, 15]]
    groups = []
    for w in windows:
        grp = sorted_16[w[0]:w[1] + 1]
        if len(grp) < 5: continue
        grp.sort()
        groups.append(grp)
    
    return {
        'pool_16': sorted(pool_16),
        'pool_16_sorted': sorted_16,
        'groups_5x5': groups,
        'top35': ranked[:35],
        'scores': scores
    }

# === 回测最近30期 ===
MIN_WINDOW = 50
PERIODS = 30

# 数据按时间正序（最旧在前）
data = sorted(raw, key=lambda x: x['p'])
N = len(data)

results = []
for i in range(N - MIN_WINDOW - PERIODS, N - MIN_WINDOW):
    predict_idx = i + MIN_WINDOW
    if predict_idx >= N: break
    
    window = data[i:i + MIN_WINDOW]
    if len(window) < 30: continue
    
    actual = data[predict_idx]
    draw_set = set(get_nums(actual))
    
    algo = website_ema_16pool(window, data, predict_idx)
    
    # 每组命中数
    group_hits = []
    for gi, grp in enumerate(algo['groups_5x5']):
        hit = len(set(grp) & draw_set)
        group_hits.append({'group': gi + 1, 'nums': grp, 'hits': hit})
    
    total_hits = sum(gh['hits'] for gh in group_hits)
    pool_16_hits = len(set(algo['pool_16']) & draw_set)
    
    # 选五奖金计算
    def x5_prize(h):
        if h >= 5: return 1000
        if h == 4: return 21
        if h == 3: return 3
        return 0
    
    prize = sum(x5_prize(gh['hits']) for gh in group_hits)
    
    results.append({
        'period': actual['p'],
        'date': actual.get('d', ''),
        'draw': sorted(get_nums(actual)),
        'group_hits': group_hits,
        'total_hits': total_hits,
        'pool_16': algo['pool_16'],
        'pool_16_hits': pool_16_hits,
        'prize': prize,
        'top35': algo['top35']
    })

# === 输出表格 ===
print("=" * 130)
print("快乐8 增强推荐（EMA+16池选五5组）逐期对比 - 最新%d期" % PERIODS)
print("=" * 130)

header = "期号\t日期\t\t16池中\t选五5组推荐\t\t\t\t\t实际开奖号(20码)\t\t\t\t\t\t\t\t奖金"
print(header)
print("-" * 130)

total_cost = 0
total_prize = 0
total_pool_hits = 0
hit5plus = 0

for r in results:
    cost = 10  # 5组×2元
    total_cost += cost
    total_prize += r['prize']
    total_pool_hits += r['pool_16_hits']
    
    if r['prize'] >= 1000: hit5plus += 1
    
    # 组推荐号码
    groups_str = []
    for gh in r['group_hits']:
        nums_str = ','.join(str(n).zfill(2) for n in gh['nums'])
        groups_str.append("G%d[%s]" % (gh['group'], nums_str))
    
    groups_text = ' | '.join(groups_str)
    
    # 实际开奖号
    draw_str = ','.join(str(n).zfill(2) for n in r['draw'])
    
    # 标记中5+
    prize_str = str(r['prize'])
    if r['prize'] >= 1000: prize_str = "★" + prize_str
    
    print("%s\t%s\t%d/16\t%s\t%s\t%s" % (
        r['period'], r['date'], r['pool_16_hits'],
        groups_text, draw_str, prize_str
    ))

print("-" * 130)
payout = total_prize / total_cost * 100 if total_cost > 0 else 0
print("汇总: %d期 | 总投入%d元 | 总奖金%d元 | 返奖率%.1f%% | 16池均中%.1f/20 | 中5+%d次" % (
    len(results), total_cost, total_prize, payout,
    total_pool_hits / len(results), hit5plus
))

print()
print()
print("=" * 130)
print("详细命中数据")
print("=" * 130)

# 按命中数分组
hit_dist = {}
for r in results:
    for gh in r['group_hits']:
        hit_dist[gh['hits']] = hit_dist.get(gh['hits'], 0) + 1

print("选五单注命中分布 (5组×%d期=%d注):" % (len(results), len(results) * 5))
for h in sorted(hit_dist.keys(), reverse=True):
    bar = '█' * int(hit_dist[h] / max(1, max(hit_dist.values()) / 30))
    print("  中%d个: %d注 (%4.1f%%)  %s" % (h, hit_dist[h], hit_dist[h] / (len(results)*5) * 100, bar))

print()
print("逐组命中详情:")
group_stats = {g: {'hits': 0, 'max_hit': 0, 'prize': 0, 'hit3plus': 0, 'hit4plus': 0, 'hit5': 0} for g in range(1, 6)}
for r in results:
    for gh in r['group_hits']:
        g = gh['group']
        group_stats[g]['hits'] += gh['hits']
        if gh['hits'] > group_stats[g]['max_hit']:
            group_stats[g]['max_hit'] = gh['hits']
        if gh['hits'] >= 3: group_stats[g]['hit3plus'] += 1
        if gh['hits'] >= 4: group_stats[g]['hit4plus'] += 1
        if gh['hits'] >= 5: group_stats[g]['hit5'] += 1
        group_stats[g]['prize'] += x5_prize(gh['hits'])

for g in range(1, 6):
    st = group_stats[g]
    print("  G%d: 总中%d | 均中%.1f | 中3+%d期 | 中4+%d期 | 中5+%d期 | 奖金%d元" % (
        g, st['hits'], st['hits'] / len(results), st['hit3plus'], st['hit4plus'], st['hit5'], st['prize']
    ))
