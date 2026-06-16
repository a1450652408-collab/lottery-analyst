"""
KL8 选三优化回测：测试4种选三策略，看哪种在35码池中命中2+的概率最高

策略定义：
  A: 当前多因子投票 top-3（baseline）
  B: 分层选号 - 35码池按排名分3档(1-12/13-24/25-35)，每档取最佳
  C: 数值分散 - top-1 + 距离top-1数值最远的2个高分号
  D: 尾部混合 - top-1 + 从rank 10-35中选2个最佳

运行：python3 scripts/backtest_3dan_optimize.py
"""
import json, sys, os
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'kl8_500.json')

with open(DATA_FILE) as f:
    all_data = json.load(f)

def get_nums(x):
    return x.get('n', x.get('r', []))

# ============ 算法实现（完全复刻网站代码） ============
def compute_top35(data_slice):
    """给定一段历史数据（从最新开始），计算35码池和评分"""
    # EMA计算 (alpha=0.5)
    ema = {}
    for i in range(1, 81):
        seq = [1 if i in get_nums(x) else 0 for x in data_slice]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]:
            e = 0.5 * v + 0.5 * e
        ema[i] = e
    
    # 近30期频率
    win30 = min(30, len(data_slice))
    freq30 = Counter()
    for j in range(win30):
        for n in get_nums(data_slice[j]):
            freq30[n] += 1
    
    # 动量：近5期 vs 6-10期
    r5, p5 = Counter(), Counter()
    for j in range(min(10, len(data_slice))):
        for n in get_nums(data_slice[j]):
            if j < 5:
                r5[n] += 1
            else:
                p5[n] += 1
    
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
        if re_freq[i] == 0 and re_miss[i] >= 15:
            kills.add(i)
        elif re_miss[i] >= 12:
            kills.add(i)
    
    # EMA综合评分
    prev_set = set(get_nums(data_slice[1])) if len(data_slice) > 1 else set()
    scores = {}
    for i in range(1, 81):
        s = (ema[i] or 0) * 5.0 + (freq30[i] / win30) * 3.0 + (mom[i] or 0) * 2.0
        if i in prev_set:
            s += 3.0
        if i in kills:
            s = -999
        miss_val = re_miss.get(i, 50)
        s += max(0, 10 - miss_val) * 0.5
        scores[i] = s
    
    ranked = sorted(range(1, 81), key=lambda n: -scores[n])
    top35 = ranked[:35]
    top35_sorted = sorted(top35)
    
    return {
        'top35': top35,
        'top35_sorted': top35_sorted,
        'scores': scores,
        'freq30': freq30,
        'mom': mom,
        'r5': r5,
        'recent5': data_slice[:5],
        'ranked': ranked,
    }


def multi_factor_vote(top35, scores, freq30, mom, r5):
    """复刻网站多因子投票"""
    mom_rank = sorted(top35, key=lambda n: -(mom.get(n, -999)))
    freq_rank = sorted(top35, key=lambda n: -(freq30.get(n, -999)))
    
    sorted_ranked = sorted(range(1, 81), key=lambda n: -scores[n])
    
    votes = {}
    for n in top35:
        ema_r = sorted_ranked.index(n)  # 0-based
        mom_r = mom_rank.index(n)
        freq_r = freq_rank.index(n)
        vote = (35 - min(ema_r, 34)) + (35 - min(mom_r, 34)) + (35 - min(freq_r, 34))
        # 过热惩罚
        c = r5.get(n, 0)
        if c >= 5: vote -= 35
        elif c >= 4: vote -= 20
        elif c >= 3: vote -= 10
        elif c >= 2: vote -= 3
        votes[n] = vote
    
    ordered = sorted(top35, key=lambda n: -votes[n])
    return ordered, votes


# ============ 4种选三策略 ============

def strategy_A_current(ordered, top35, scores):
    """A: 当前策略 - 多因子投票 top-3"""
    return list(ordered[:3])

def strategy_B_stratified(ordered, top35, scores):
    """B: 分层选号 - 35码池按排名分3档"""
    # 按多因子投票结果分档
    tier1 = ordered[:12]    # 精英档
    tier2 = ordered[12:24]  # 中间档
    tier3 = ordered[24:35]  # 底部档
    return [tier1[0], tier2[0], tier3[0]]

def strategy_C_numerical(ordered, top35, scores):
    """C: 数值分散 - top-1 + 离top-1数值最远的2个高分号"""
    first = ordered[0]
    # 从剩下的里面选2个，优先选数值距离远的
    rest = [n for n in ordered[1:] if n != first]
    rest.sort(key=lambda n: abs(n - first), reverse=True)
    # 取最远距离的1个，再从剩下的取另一个不同方向最远的
    second = rest[0]
    rest2 = [n for n in rest[1:] if n != second]
    rest2.sort(key=lambda n: abs(n - first))
    # 选距离first最远的（尽可能分布在数值两端）
    third = rest2[-1] if rest2 else (rest[1] if len(rest) > 1 else rest[0])
    return [first, second, third]

def strategy_D_tail_mix(ordered, top35, scores):
    """D: 尾部混合 - top-1 + 从rank 10-35中选2个最佳的多因子投票号"""
    first = ordered[0]
    # 从排名10-35里取最好的2个
    tail_best = ordered[9:35]  # index 9 = rank 10
    # 如果first已在其中，去掉它
    tail_best = [n for n in tail_best if n != first]
    return [first, tail_best[0], tail_best[1]] if len(tail_best) >= 2 else [first, ordered[1], ordered[2]]


# ============ 回测框架 ============
# 使用滚动回测：每期训练窗口50期
TRAIN_WINDOW = 50
# 算上最新一期当预测目标
TOTAL = len(all_data)
print(f"总数据: {TOTAL} 期\n")

# 三段测试
segments = [
    ("段1(前)", TOTAL - 420, TOTAL - 280),
    ("段2(中)", TOTAL - 280, TOTAL - 140),
    ("段3(后)", TOTAL - 140, TOTAL),
]

strategies = {
    'A:多因子投票top-3': strategy_A_current,
    'B:分层(12/12/11)': strategy_B_stratified,
    'C:数值分散': strategy_C_numerical,
    'D:尾部混合': strategy_D_tail_mix,
}

for seg_name, start, end in segments:
    print(f"{'='*60}")
    print(f"  {seg_name}（周期 {all_data[start].get('p','?')} → {all_data[end-1].get('p','?')}）")
    print(f"{'='*60}")
    
    results = {name: {'hits': [], 'h2': 0, 'h3': 0, 'total': 0, 'pool_hits': []} for name in strategies}
    # 加上随机对照
    import random
    random_hits = []
    
    for idx in range(start, end):
        # 训练窗口
        train_start = idx + 1
        train_end = min(idx + 1 + TRAIN_WINDOW, TOTAL)
        train_data = all_data[train_start:train_end]
        
        if len(train_data) < 30:
            continue
        
        # 当前期开奖号
        actual = set(get_nums(all_data[idx]))
        
        # 计算
        ctx = compute_top35(train_data)
        top35 = ctx['top35']
        ordered, _ = multi_factor_vote(top35, ctx['scores'], ctx['freq30'], ctx['mom'], ctx['r5'])
        
        # 35池命中
        pool_hits = len(set(top35) & actual)
        
        for name, func in strategies.items():
            picks = func(ordered, top35, ctx['scores'])
            picks = list(set(picks))  # 去重
            n_hits = len(set(picks) & actual)
            results[name]['hits'].append(n_hits)
            results[name]['h2'] += (1 if n_hits >= 2 else 0)
            results[name]['h3'] += (1 if n_hits >= 3 else 0)
            results[name]['total'] += 1
            results[name]['pool_hits'].append(pool_hits)
        
        # 随机对照：从35码池随机选3个
        rand3 = random.sample(top35, min(3, len(top35)))
        random_hits.append(len(set(rand3) & actual))
    
    avg_pool = sum(results['A:多因子投票top-3']['pool_hits']) / max(results['A:多因子投票top-3']['total'], 1)
    total = results['A:多因子投票top-3']['total']
    
    print(f"  35码池平均命中: {avg_pool:.1f}/20 | 测试期数: {total}")
    print()
    print(f"  {'策略':<20} {'中2+':>8} {'中3':>8} {'中2+%':>8} {'相对随机':>10}")
    print(f"  {'-'*54}")
    
    rand_h2 = sum(1 for h in random_hits if h >= 2)
    rand_pct = rand_h2 / max(len(random_hits), 1) * 100
    
    for name in strategies:
        r = results[name]
        pct_h2 = r['h2'] / max(r['total'], 1) * 100
        pct_h3 = r['h3'] / max(r['total'], 1) * 100
        vs_random = pct_h2 - rand_pct
        print(f"  {name:<20} {r['h2']:>6}期 {r['h3']:>6}期 {pct_h2:>7.1f}% {vs_random:>+9.1f}%")
    
    rand_total = len(random_hits)
    print(f"  {'随机(35池)':<20} {rand_h2:>6}期 {'-':>6} {rand_pct:>7.1f}% {'(基准)':>10}")
    print()

# ============ 汇总 ============
print(f"{'='*60}")
print(f"  三段汇总")
print(f"{'='*60}")

agg = {name: {'h2': 0, 'h3': 0, 'total': 0} for name in strategies}
agg_random = {'h2': 0, 'total': 0}

# 重跑一遍但跨段
random.seed(42)

# 统一从最前面开始
for idx in range(TOTAL - 420, TOTAL):
    train_start = idx + 1
    train_end = min(idx + 1 + TRAIN_WINDOW, TOTAL)
    train_data = all_data[train_start:train_end]
    if len(train_data) < 30:
        continue
    
    actual = set(get_nums(all_data[idx]))
    ctx = compute_top35(train_data)
    top35 = ctx['top35']
    ordered, _ = multi_factor_vote(top35, ctx['scores'], ctx['freq30'], ctx['mom'], ctx['r5'])
    
    for name, func in strategies.items():
        picks = func(ordered, top35, ctx['scores'])
        picks = list(set(picks))
        n_hits = len(set(picks) & actual)
        agg[name]['h2'] += (1 if n_hits >= 2 else 0)
        agg[name]['h3'] += (1 if n_hits >= 3 else 0)
        agg[name]['total'] += 1
    
    rand3 = random.sample(top35, min(3, len(top35)))
    rh = len(set(rand3) & actual)
    agg_random['h2'] += (1 if rh >= 2 else 0)
    agg_random['total'] += 1

total = agg['A:多因子投票top-3']['total']
print(f"\n  总测试期数: {total}")
print(f"\n  {'策略':<22} {'中2+':>8} {'中3':>8} {'中2+%':>8} {'vs随机':>8}")
print(f"  {'-'*54}")
rand_pct = agg_random['h2'] / max(agg_random['total'], 1) * 100
for name in strategies:
    r = agg[name]
    pct = r['h2'] / max(r['total'], 1) * 100
    pct3 = r['h3'] / max(r['total'], 1) * 100
    vs = pct - rand_pct
    print(f"  {name:<22} {r['h2']:>6}期 {r['h3']:>6}期 {pct:>7.1f}% {vs:>+7.1f}%")
print(f"  {'随机(35池)':<22} {agg_random['h2']:>6}期 {'-':>6} {rand_pct:>7.1f}% {'(基准)':>8}")

# 最优策略建议
best_strat = max(agg.keys(), key=lambda n: agg[n]['h2'] / max(agg[n]['total'], 1))
best_pct = agg[best_strat]['h2'] / max(agg[best_strat]['total'], 1) * 100
print(f"\n  最优策略: {best_strat} ({best_pct:.1f}%)")
print(f"  随机基准: {rand_pct:.1f}%")
print(f"  提升幅度: {best_pct - rand_pct:.1f}%")
