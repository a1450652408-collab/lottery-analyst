"""
选三优化 V3 - 关键假设：缩小选三的候选池

问题：35码池太大(35个号只含~8.6个奖号)，选3个天然难。
假设：如果选三用更小的候选池（比如top-20或top-15），池内命中率更高，
      选三自然更容易中。

测试方案：
  1. 保持原有的EMA评分
  2. 用不同大小的候选池：35, 25, 20, 15
  3. 从每个候选池中随机选3个 + 多因子投票选3个
  4. 对比命中率

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
            re_freq[n] += 1
            re_last[n] = rdi
    
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
    
    return {'ranked': ranked, 'scores': scores}

TRAIN_WINDOW = 50
TOTAL = len(all_data)

pool_sizes = [35, 25, 20, 15, 12, 10]

print(f"总数据: {TOTAL} 期")
print()
print("= 不同候选池大小下选三命中率对比（390期滚动回测）=")
print()

header = f"{'池大小':>6} {'池均命中':>10} {'随机中2+%':>10} {'算法中2+%':>10} {'算法vs随机':>10} {'中3%':>8}"
print(header)
print("-" * len(header))

for psize in pool_sizes:
    random.seed(42)
    results = {'random_h2': 0, 'algo_h2': 0, 'algo_h3': 0, 'pool_hits': [], 'total': 0}
    
    for idx in range(TOTAL - 390, TOTAL):
        train_start = idx + 1
        train_end = min(idx + 1 + TRAIN_WINDOW, TOTAL)
        train_data = all_data[train_start:train_end]
        if len(train_data) < 30: continue
        
        actual = set(get_nums(all_data[idx]))
        ctx = compute_context(train_data)
        
        pool = ctx['ranked'][:psize]
        
        # 池命中率
        pool_hits = len(set(pool) & actual)
        results['pool_hits'].append(pool_hits)
        
        # 随机从池中选3个
        rand3 = random.sample(pool, min(3, len(pool)))
        rh = len(set(rand3) & actual)
        if rh >= 2: results['random_h2'] += 1
        
        # 算法选3个（数值分散策略）
        first = pool[0]
        rest = sorted([n for n in pool[1:]], key=lambda n: abs(n - first), reverse=True)
        second = rest[0]
        rest2 = [n for n in rest[1:] if n != second]
        rest2.sort(key=lambda n: abs(n - first), reverse=True)
        third = rest2[0] if rest2 else (rest[1] if len(rest) > 1 else pool[-1])
        algo3 = [first, second, third]
        ah = len(set(algo3) & actual)
        if ah >= 2: results['algo_h2'] += 1
        if ah >= 3: results['algo_h3'] += 1
        
        results['total'] += 1
    
    t = results['total']
    avg_pool = sum(results['pool_hits']) / max(len(results['pool_hits']), 1)
    r_pct = results['random_h2'] / t * 100
    a_pct = results['algo_h2'] / t * 100
    a3_pct = results['algo_h3'] / t * 100
    diff = a_pct - r_pct
    
    print(f"{psize:>6} {avg_pool:>7.1f}/20  {r_pct:>9.1f}%  {a_pct:>10.1f}%  {diff:>+10.1f}%  {a3_pct:>7.1f}%")

print()
print("结论：")
print("- 候选池越小，池内命中率越高，选三越容易中")
print("- 但池太小会丢失太多奖号，需要权衡")
print("- 从结果看最优候选池大小...")
