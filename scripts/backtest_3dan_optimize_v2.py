"""
KL8 选三优化回测 V2 - 8种策略深度对比

关键发现 V1:
- 35码池平均命中8.5/20，基数有限
- 选三之所以难，是因为算法对第3个号没有信号优势
- 最好的策略是"选二+补防"思路，而非"选三"思路

V2测试策略：
  A: 多因子投票 top-3 (baseline)
  C: 数值分散 (V1最佳)
  E: 选二核心 + 近5期补号
  F: 选二核心 + 遗漏值补偿
  G: 选二核心 + 区域分散
  H: 纯随机从35池选3 (基准)
  I: EMA top-3 (不用多因子投票)
  J: 选二核心 + 动量最高(不在前二)

运行：python3 scripts/backtest_3dan_optimize.py
"""
import json, sys, os, random
from collections import Counter

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'kl8_500.json')

with open(DATA_FILE) as f:
    all_data = json.load(f)

def get_nums(x):
    return x.get('n', x.get('r', []))

# ============ 算法实现 ============
def compute_context(data_slice):
    """完全复刻网站评分系统"""
    # EMA 0.5
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
    
    # 动量
    r5, p5 = Counter(), Counter()
    for j in range(min(10, len(data_slice))):
        for n in get_nums(data_slice[j]):
            if j < 5: r5[n] += 1
            else: p5[n] += 1
    
    mom = {}
    for i in range(1, 81):
        pp = max(p5[i], 1)
        mom[i] = max(-2, min(2, (r5[i] - p5[i]) / pp))
    
    # 杀号
    re_freq = Counter()
    re_last = {}
    for rdi, x in enumerate(data_slice):
        for n in get_nums(x):
            re_freq[n] += 1
            re_last[n] = rdi
    
    re_miss = {i: len(data_slice) - 1 - re_last.get(i, len(data_slice)) for i in range(1, 81)}
    kills = set()
    for i in range(1, 81):
        if re_freq[i] == 0 and re_miss[i] >= 15: kills.add(i)
        elif re_miss[i] >= 12: kills.add(i)
    
    # 评分
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


# ============ 8种策略 ============
def strat_A_current(ctx):
    """A: 当前 - 多因子投票 top-3"""
    return ctx['ordered'][:3]

def strat_C_numerical(ctx):
    """C: 数值分散 - top-1 + 离它最远的2个高分号"""
    ordered = ctx['ordered']
    first = ordered[0]
    rest = [n for n in ordered[1:]]
    rest.sort(key=lambda n: abs(n - first), reverse=True)
    second = rest[0]
    rest2 = [n for n in rest[1:] if n != second]
    rest2.sort(key=lambda n: abs(n - first), reverse=True)
    third = rest2[0] if rest2 else (rest[1] if len(rest) > 1 else ordered[-1])
    return [first, second, third]

def strat_E_top2_plus_recent5(ctx):
    """E: 选二核心 + 近5期补号"""
    ordered = ctx['ordered']
    top2 = ordered[:2]
    r5 = ctx['r5']
    # 从剩余号码中找近5期出现最频繁的
    candidates = [n for n in ctx['ordered'] if n not in top2]
    candidates.sort(key=lambda n: -(r5.get(n, 0) * 5 + (35 - ctx['ordered'].index(n)) // 5))
    return top2 + [candidates[0]]

def strat_F_top2_plus_cold(ctx):
    """F: 选二核心 + 遗漏值补偿"""
    ordered = ctx['ordered']
    top2 = ordered[:2]
    re_miss = ctx['re_miss']
    # 从剩余号码中找遗漏值最大的（最近没出的号）
    candidates = [n for n in ordered if n not in top2]
    candidates.sort(key=lambda n: -(re_miss.get(n, 0)))
    return top2 + [candidates[0]]

def strat_G_top2_plus_zone(ctx):
    """G: 选二核心 + 不同区"""
    ordered = ctx['ordered']
    top2 = ordered[:2]
    # 找出top2所在的四区
    zones = {1: 0, 2: 0, 3: 0, 4: 0}
    for n in top2:
        z = (n - 1) // 20 + 1
        zones[z] = zones.get(z, 0) + 1
    
    # 找top2最缺的区域
    min_zone = min(zones, key=lambda z: zones[z])
    min_count = zones[min_zone]
    
    # 最缺的区如果有多个，全找出来
    missing_zones = [z for z in range(1,5) if zones[z] == min_count]
    
    candidates = [n for n in ordered if n not in top2 and (n-1)//20+1 in missing_zones]
    if candidates:
        return top2 + [candidates[0]]
    # 保底
    return top2 + [ordered[2]]

def strat_H_random(ctx):
    """H: 纯随机"""
    return random.sample(ctx['top35'], 3)

def strat_I_ema_top3(ctx):
    """I: EMA评分top-3（不用多因子投票）"""
    ranked = ctx['ranked']
    return [n for n in ranked if n in ctx['top35']][:3]

def strat_J_top2_plus_momentum(ctx):
    """J: 选二核心 + 动量最高"""
    ordered = ctx['ordered']
    top2 = ordered[:2]
    mom = ctx['mom']
    candidates = [n for n in ordered if n not in top2]
    candidates.sort(key=lambda n: -(mom.get(n, -999)))
    return top2 + [candidates[0]]


strategies = {
    'A:多因子投票top-3': strat_A_current,
    'C:数值分散': strat_C_numerical,
    'E:选二+近5期补': strat_E_top2_plus_recent5,
    'F:选二+遗漏补偿': strat_F_top2_plus_cold,
    'G:选二+异区补': strat_G_top2_plus_zone,
    'I:EMA评分top-3': strat_I_ema_top3,
    'J:选二+动量补': strat_J_top2_plus_momentum,
    'H:随机(35池)': strat_H_random,
}

TRAIN_WINDOW = 50
TOTAL = len(all_data)

print(f"总数据: {TOTAL} 期")
print(f"35码池平均命中: 运行中...")
print()

segments = [
    ("段1(前", TOTAL - 420, TOTAL - 280),
    ("段2(中)", TOTAL - 280, TOTAL - 140),
    ("段3(后)", TOTAL - 140, TOTAL),
]

pool_avg_list = []
agg = {name: {'h2': 0, 'h3': 0, 'total': 0, 'h1': 0} for name in strategies}

for seg_name, start, end in segments:
    seg_total = end - start
    print(f"  {seg_name}: {all_data[start].get('p','?')} → {all_data[end-1].get('p','?')} ({seg_total}期)")
    
    seg_results = {name: {'h2': 0, 'h3': 0, 'total': 0} for name in strategies}
    seg_pool_hits = []
    
    for idx in range(start, end):
        train_start = idx + 1
        train_end = min(idx + 1 + TRAIN_WINDOW, TOTAL)
        train_data = all_data[train_start:train_end]
        if len(train_data) < 30: continue
        
        actual = set(get_nums(all_data[idx]))
        ctx = compute_context(train_data)
        
        pool_hits = len(set(ctx['top35']) & actual)
        seg_pool_hits.append(pool_hits)
        
        for name, func in strategies.items():
            picks = func(ctx)
            picks = list(set(picks))
            n_hits = len(set(picks) & actual)
            seg_results[name]['h2'] += (1 if n_hits >= 2 else 0)
            seg_results[name]['h3'] += (1 if n_hits >= 3 else 0)
            seg_results[name]['total'] += 1
            agg[name]['h2'] += (1 if n_hits >= 2 else 0)
            agg[name]['h3'] += (1 if n_hits >= 3 else 0)
            agg[name]['total'] += 1
    
    avg_pool = sum(seg_pool_hits) / max(len(seg_pool_hits), 1)
    pool_avg_list.extend(seg_pool_hits)
    
    total_seg = seg_results['H:随机(35池)']['total']
    rand_h2 = seg_results['H:随机(35池)']['h2']
    rand_pct = rand_h2 / max(total_seg, 1) * 100
    
    print(f"   35码池均命中: {avg_pool:.1f}/20")
    print(f"   {'策略':<18} {'中2+':>6} {'中3':>6} {'中2+%':>7} {'vs随机':>8}")
    print(f"   {'-'*45}")
    for name in strategies:
        r = seg_results[name]
        pct = r['h2'] / max(r['total'], 1) * 100
        vs = pct - rand_pct
        print(f"   {name:<18} {r['h2']:>4}期 {r['h3']:>4}期 {pct:>6.1f}% {vs:>+7.1f}%")
    print()

# 汇总
total_agg = agg['H:随机(35池)']['total']
rand_pct = agg['H:随机(35池)']['h2'] / max(total_agg, 1) * 100
overall_pool = sum(pool_avg_list) / max(len(pool_avg_list), 1)

print(f"{'='*60}")
print(f"  汇总 ({total_agg}期, 35码池均{overall_pool:.1f}/20)")
print(f"{'='*60}")
print(f"   {'策略':<18} {'中2+':>6} {'中3':>6} {'中2+%':>7} {'vs随机':>8}")
print(f"   {'-'*45}")

# 按中2+排序
sorted_strats = sorted(strategies.keys(), key=lambda n: -agg[n]['h2'] / max(agg[n]['total'], 1))
for name in sorted_strats:
    r = agg[name]
    pct = r['h2'] / max(r['total'], 1) * 100
    pct3 = r['h3'] / max(r['total'], 1) * 100
    vs = pct - rand_pct
    marker = " ★ 最优" if pct == max(agg[s]['h2']/max(agg[s]['total'],1) for s in strategies) and name != 'H:随机(35池)' else ""
    marker = marker if name != 'H:随机(35池)' else " (基准)"
    print(f"   {name:<18} {r['h2']:>4}期 {r['h3']:>4}期 {pct:>6.1f}% {vs:>+7.1f}%{marker}")

print()
print("结论分析:")
print(f"  - 35码池平均仅命中{overall_pool:.1f}/20，选三基础就低")
print(f"  - 所有算法策略均未可靠超越随机水平")
print(f"  - 推荐方案：选三用随机从35池选，或集中精力优化选二/选四")
