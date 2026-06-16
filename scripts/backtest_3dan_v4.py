"""
选三优化 V4 - 区域占位策略

核心思路：不选"前三热号"，而是从3个不同数值段各选1个最优号。
这样确保覆盖在不同区域，不管热号集中在哪个区，至少能抓住另一个区的奖号。

策略:
  K: 三区分区占位 - 将35码池按数值排序后三等分(低/中/高)，每段取最佳
  L: 数值间隔 - 从35码池取3个，要求两两之间最小数值间隔尽可能大
  M: 混合型 - top-1 + 将35池按奇偶分3组，从不同权重组取最优
  N: 动量反转 - top-1(多因子) + 近5期频率最高的2个（覆盖近期趋势）
  O: 权重分散 - 多因子投票得分修正：同数值区间扣分，迫使其分散
"""
import json, sys, os, random
from collections import Counter

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'kl8_500.json')
with open(DATA_FILE) as f:
    all_data = json.load(f)

def get_nums(x):
    return x.get('n', x.get('r', []))

def compute_context(data_slice):
    ema = {}
    for i in range(1, 81):
        seq = [1 if i in get_nums(x) else 0 for x in data_slice]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]:
            e = 0.5 * v + 0.5 * e
        ema[i] = e
    win30 = min(30, len(data_slice))
    freq30 = Counter()
    for j in range(win30):
        for n in get_nums(data_slice[j]):
            freq30[n] += 1
    r5, p5 = Counter(), Counter()
    for j in range(min(10, len(data_slice))):
        for n in get_nums(data_slice[j]):
            if j < 5: r5[n] += 1
            else: p5[n] += 1
    mom = {}
    for i in range(1, 81):
        pp = max(p5[i], 1)
        mom[i] = max(-2, min(2, (r5[i] - p5[i]) / pp))
    re_freq = Counter()
    re_last = {}
    for rdi, x in enumerate(data_slice):
        for n in get_nums(x):
            re_freq[n] += 1; re_last[n] = rdi
    re_miss = {i: len(data_slice) - 1 - re_last.get(i, len(data_slice)) for i in range(1, 81)}
    kills = set()
    for i in range(1, 81):
        if re_freq[i] == 0 and re_miss[i] >= 15: kills.add(i)
        elif re_miss[i] >= 12: kills.add(i)
    prev_set = set(get_nums(data_slice[1])) if len(data_slice) > 1 else set()
    scores = {}
    for i in range(1, 81):
        s = (ema[i] or 0) * 5.0 + (freq30[i] / win30) * 3.0 + (mom[i] or 0) * 2.0
        if i in prev_set: s += 3.0
        if i in kills: s = -999
        s += max(0, 10 - re_miss.get(i, 50)) * 0.5
        scores[i] = s
    ranked = sorted(range(1, 81), key=lambda n: -scores[n])
    top35 = ranked[:35]
    
    # 多因子投票
    mom_rank = sorted(top35, key=lambda n: -(mom.get(n, -999)))
    freq_rank = sorted(top35, key=lambda n: -(freq30.get(n, -999)))
    votes = {}
    for n in top35:
        ema_r = ranked.index(n)
        mom_r = mom_rank.index(n)
        freq_r = freq_rank.index(n)
        vote = (35 - min(ema_r, 34)) + (35 - min(mom_r, 34)) + (35 - min(freq_r, 34))
        c = r5.get(n, 0)
        if c >= 5: vote -= 35
        elif c >= 4: vote -= 20
        elif c >= 3: vote -= 10
        elif c >= 2: vote -= 3
        votes[n] = vote
    ordered = sorted(top35, key=lambda n: -votes[n])
    
    return {
        'top35': top35, 'ordered': ordered, 'scores': scores,
        'freq30': freq30, 'mom': mom, 'r5': r5,
        'ranked': ranked, 're_miss': re_miss,
    }

# ============ 新策略 ============
def strat_K_zone_3way(ctx):
    """K: 三区分区 - 35码池按数值排序后三等分，每段取最优"""
    # 按数值排序（升序）
    sorted_by_val = sorted(ctx['top35'])
    n = len(sorted_by_val)
    tier1 = sorted_by_val[:n//3] if n >= 3 else sorted_by_val[:1]
    tier2 = sorted_by_val[n//3:2*n//3] if n >= 3 else []
    tier3 = sorted_by_val[2*n//3:] if n >= 3 else []
    
    def best_in(tier):
        """从tier中取多因子投票最高分"""
        return max(tier, key=lambda n: ctx['ordered'].index(n))
    
    picks = []
    if tier1: picks.append(best_in(tier1))
    if tier2: picks.append(best_in(tier2))
    if tier3: picks.append(best_in(tier3))
    # 如果某个区空了，从其他区补
    while len(picks) < 3:
        for t in [tier1, tier2, tier3]:
            remaining = [n for n in t if n not in picks]
            if remaining:
                picks.append(best_in(remaining))
                break
        else:
            for n in ctx['ordered']:
                if n not in picks:
                    picks.append(n)
                    break
    return picks[:3]

def strat_L_max_spread(ctx):
    """L: 数值间隔最大化 - 选3个让两两之间最小间隔最大"""
    ordered = ctx['ordered']
    best_combo = None
    best_min_gap = -1
    
    # 只搜索前15个（暴力搜全部35选3太大了）
    candidates = ordered[:15]
    for i in range(len(candidates)):
        for j in range(i+1, len(candidates)):
            for k in range(j+1, len(candidates)):
                a, b, c = candidates[i], candidates[j], candidates[k]
                gap = min(abs(a-b), abs(a-c), abs(b-c))
                if gap > best_min_gap:
                    best_min_gap = gap
                    best_combo = [a, b, c]
    return best_combo or ordered[:3]

def strat_M_mix_weight(ctx):
    """M: 混合权重 - top-1 + 从35池中选动量最高+频率最高"""
    ordered = ctx['ordered']
    rest = [n for n in ordered[1:]]
    
    mom_sorted = sorted(rest, key=lambda n: -(ctx['mom'].get(n, -999)))
    freq_sorted = sorted(rest, key=lambda n: -(ctx['freq30'].get(n, -999)))
    
    top_mom = mom_sorted[0] if mom_sorted else ordered[-1]
    top_freq = freq_sorted[0] if freq_sorted else ordered[-1]
    
    picks = [ordered[0], top_mom]
    if top_freq not in picks and len(picks) < 3:
        picks.append(top_freq)
    while len(picks) < 3:
        for n in ordered:
            if n not in picks:
                picks.append(n)
                break
    return picks

def strat_N_momentum_reversal(ctx):
    """N: 动量反转 - 选近5期最热的3个（不用多因子投票）"""
    r5 = ctx['r5']
    top35 = ctx['top35']
    candidates = sorted(top35, key=lambda n: -(r5.get(n, 0) * 10 + (35 - ctx['ordered'].index(n))))
    return candidates[:3]

def strat_O_diversity_vote(ctx):
    """O: 权重分散版多因子投票 - 同数值区相互扣分"""
    ordered = ctx['ordered']
    # 35池中选票数前10的
    top10 = ordered[:10]
    
    # 区域分组(1-20, 21-40, 41-60, 61-80)
    zones = {1: range(1,21), 2: range(21,41), 3: range(41,61), 4: range(61,81)}
    def get_zone(n):
        for z, rng in zones.items():
            if n in rng: return z
        return 0
    
    # 再次投票，但同区号互相减分
    from collections import defaultdict
    adj_votes = {}
    for n in top10:
        vote = 35 - ordered.index(n)
        zone = get_zone(n)
        # 同区其他号被选的情况下扣分
        for other in top10:
            if other != n and get_zone(other) == zone:
                vote -= 5
        adj_votes[n] = vote
    
    adj_ordered = sorted(top10, key=lambda n: -adj_votes[n])
    return adj_ordered[:3]

strategies = {
    'K:三区分区占位': strat_K_zone_3way,
    'L:数值间隔最大': strat_L_max_spread,
    'M:动量+频率补': strat_M_mix_weight,
    'N:近5期最热': strat_N_momentum_reversal,
    'O:同区互扣': strat_O_diversity_vote,
}

TRAIN_WINDOW = 50
TOTAL = len(all_data)

# 加入对照策略
all_strategies = {
    'A:当前top-3': lambda ctx: ctx['ordered'][:3],
    'C:数值分散': lambda ctx: (lambda o: [o[0], sorted([n for n in o[1:]], key=lambda n:abs(n-o[0]), reverse=True)[0], [n for n in sorted([n for n in o[2:]], key=lambda n:abs(n-o[0]), reverse=True) if n != sorted([n for n in o[1:]], key=lambda n:abs(n-o[0]), reverse=True)[0]][0] if len([n for n in o[2:]]) > 0 else o[2]])(ctx['ordered']),
    **strategies,
    'H:随机': lambda ctx: random.sample(ctx['top35'], 3),
}

agg = {name: {'h2': 0, 'h3': 0, 'total': 0} for name in all_strategies}

print("选三优化 V4 - 区域占位等策略对比 (390期)")
print()

segments = [(TOTAL - 390, TOTAL - 260), (TOTAL - 260, TOTAL - 130), (TOTAL - 130, TOTAL)]
for seg_idx, (start, end) in enumerate(segments):
    print(f"  段{seg_idx+1}: {all_data[start].get('p','?')} → {all_data[end-1].get('p','?')} ({end-start}期)")
    
    seg_rand = {'h2': 0, 'total': 0}
    for idx in range(start, end):
        train_start = idx + 1
        train_end = min(idx + 1 + TRAIN_WINDOW, TOTAL)
        train_data = all_data[train_start:train_end]
        if len(train_data) < 30: continue
        
        actual = set(get_nums(all_data[idx]))
        ctx = compute_context(train_data)
        
        for name, func in all_strategies.items():
            picks = func(ctx)
            picks = list(set(picks))
            n_hits = len(set(picks) & actual)
            agg[name]['h2'] += (1 if n_hits >= 2 else 0)
            agg[name]['h3'] += (1 if n_hits >= 3 else 0)
            agg[name]['total'] += 1
    
t = agg['H:随机']['total']
rand_pct = agg['H:随机']['h2'] / t * 100

print(f"\n  {'策略':<18} {'中2+':>6} {'中3':>6} {'中2+%':>7} {'vs随机':>8}")
print(f"  {'-'*45}")
sorted_names = sorted(all_strategies.keys(), key=lambda n: -agg[n]['h2']/max(agg[n]['total'],1))
for name in sorted_names:
    r = agg[name]
    pct = r['h2'] / max(r['total'], 1) * 100
    pct3 = r['h3'] / max(r['total'], 1) * 100
    vs = pct - rand_pct
    print(f"  {name:<18} {r['h2']:>4}期 {r['h3']:>4}期 {pct:>6.1f}% {vs:>+7.1f}%")
print(f"  {'H:随机(35池)':<18} {agg['H:随机']['h2']:>4}期 {'-':>4} {rand_pct:>6.1f}% {'(基准)':>8}")
