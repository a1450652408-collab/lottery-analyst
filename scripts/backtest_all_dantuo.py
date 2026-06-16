"""
选二~选十三全部胆拖大小回测（新逻辑：top-1 + 动量 + 频率三信号互补）

为每个胆拖大小 N (2~13) 统计：
  - 命中0个、1个、2个...N个的期数分布
  - 至少命中1个、至少命中2个...的概率
  - 平均命中数
  - 与纯随机从35池选N个的对比

运行：python3 scripts/backtest_all_dantuo.py
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
        'top35': top35, 'ordered': ordered, 'scores': scores, 'ranked': ranked,
        'freq30': freq30, 'mom': mom,
    }

def select_n_new(ctx, n):
    """新逻辑：选N，n=2时取top-2，n>=3时 top-1+动量+频率+其余按排名补"""
    if n <= 2:
        return ctx['ordered'][:2]
    picks = [ctx['ordered'][0]]
    rest = ctx['ordered'][1:]
    # 动量最高
    m = sorted(rest, key=lambda x: -(ctx['mom'].get(x, -999)))[0]
    if m not in picks: picks.append(m)
    # 频率最高
    f = sorted(rest, key=lambda x: -(ctx['freq30'].get(x, -999)))[0]
    if f not in picks: picks.append(f)
    # 补满
    for x in ctx['ordered']:
        if len(picks) >= n: break
        if x not in picks: picks.append(x)
    return picks

TRAIN_WINDOW = 50
TOTAL = len(all_data)

# 多因子投票 + 随机 都跑
print("选手二~选十三 新逻辑回测 (390期, 35码池)")
print()

# 选二到选十三的结果
results_new = {n: [] for n in range(2, 14)}     # 新逻辑
results_old = {n: [] for n in range(2, 14)}     # 旧逻辑(top-N)
results_rand = {n: [] for n in range(2, 14)}    # 随机
pool_hits_all = []

for idx in range(TOTAL - 390, TOTAL):
    train_start = idx + 1
    train_end = min(idx + 1 + TRAIN_WINDOW, TOTAL)
    train_data = all_data[train_start:train_end]
    if len(train_data) < 30: continue
    
    actual = set(get_nums(all_data[idx]))
    ctx = compute_context(train_data)
    
    pool_hits = len(set(ctx['top35']) & actual)
    pool_hits_all.append(pool_hits)
    
    random.seed(idx)  # 可复现的随机
    
    for n in range(2, 14):
        # 新逻辑
        picks_new = select_n_new(ctx, n)
        hits_new = len(set(picks_new) & actual)
        results_new[n].append(hits_new)
        
        # 旧逻辑 (top-N by multi-factor voting)
        picks_old = ctx['ordered'][:n]
        hits_old = len(set(picks_old) & actual)
        results_old[n].append(hits_old)
        
        # 随机
        picks_rand = random.sample(ctx['top35'], n)
        hits_rand = len(set(picks_rand) & actual)
        results_rand[n].append(hits_rand)

avg_pool = sum(pool_hits_all) / len(pool_hits_all)
total = len(pool_hits_all)

print(f"35码池平均命中: {avg_pool:.1f}/20 | 回测期数: {total}")
print()

for n in range(2, 14):
    label = "选" + {2:'二',3:'三',4:'四',5:'五',6:'六',7:'七',8:'八',9:'九',10:'十',11:'十一',12:'十二',13:'十三'}[n]
    print(f"{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    
    h_new = Counter(results_new[n])
    h_old = Counter(results_old[n])
    h_rand = Counter(results_rand[n])
    
    # 头部信息
    print(f"  {'命中数':>6} | {'新逻辑':>8} {'新%':>6} | {'旧top-N':>8} {'旧%':>6} | {'随机':>8} {'随%':>6}")
    print(f"  {'-'*56}")
    
    for h in range(0, n+1):
        new_pct = h_new.get(h, 0) / total * 100
        old_pct = h_old.get(h, 0) / total * 100
        rand_pct = h_rand.get(h, 0) / total * 100
        print(f"  {h:>6} | {h_new.get(h,0):>4}期 {new_pct:>5.1f}% | {h_old.get(h,0):>4}期 {old_pct:>5.1f}% | {h_rand.get(h,0):>4}期 {rand_pct:>5.1f}%")
    
    # 累计概率
    print(f"  {'------':>6} | {'------':>8} {'------':>6} | {'------':>8} {'------':>6} | {'------':>8} {'------':>6}")
    
    avg_new = sum(results_new[n]) / total
    avg_old = sum(results_old[n]) / total
    avg_rand = sum(results_rand[n]) / total
    
    for thresh in range(n, 0, -1):
        new_ge = sum(1 for h in results_new[n] if h >= thresh) / total * 100
        old_ge = sum(1 for h in results_old[n] if h >= thresh) / total * 100
        rand_ge = sum(1 for h in results_rand[n] if h >= thresh) / total * 100
        print(f"  ≥{thresh:>3}  | {new_ge:>6.1f}%{'':>8} | {old_ge:>6.1f}%{'':>8} | {rand_ge:>6.1f}%")
    
    print(f"  均命中 | {avg_new:>5.2f}个{'':>5} | {avg_old:>5.2f}个{'':>5} | {avg_rand:>5.2f}个")
    print()

# ===== 汇总表 =====
print(f"{'='*60}")
print(f"  汇总表")
print(f"{'='*60}")
print(f"  35码池均命中 {avg_pool:.1f}/20 | {total}期")
print()
print(f"  {'胆拖':>4} {'新均命中':>8} {'旧均命中':>8} {'随机均':>8} {'新vs旧':>8} {'新vs随':>8}")
print(f"  {'-'*44}")

for n in range(2, 14):
    avg_new = sum(results_new[n]) / total
    avg_old = sum(results_old[n]) / total
    avg_rand = sum(results_rand[n]) / total
    vs_old = avg_new - avg_old
    vs_rand = avg_new - avg_rand
    label = "选" + {2:'二',3:'三',4:'四',5:'五',6:'六',7:'七',8:'八',9:'九',10:'十',11:'十一',12:'十二',13:'十三'}[n]
    print(f"  {label:>4} {avg_new:>7.2f}个 {avg_old:>7.2f}个 {avg_rand:>7.2f}个 {vs_old:>+7.2f} {vs_rand:>+7.2f}")

print()
print("--- 关键命中率对比 (≥X中奖) ---")
print(f"  {'胆拖':>4} {'选2≥1':>8} {'选3≥2':>8} {'选4≥2':>8} {'选5≥2':>8} {'选6≥3':>8} {'选7≥3':>8} {'选8≥4':>8} {'选9≥4':>8} {'选10≥5':>8} {'选11≥5':>8} {'选12≥6':>8} {'选13≥6':>8}")
print(f"  {'-'*105}")

for method_name, data in [('新逻辑', results_new), ('旧top-N', results_old), ('随机   ', results_rand)]:
    thresholds = {2:1, 3:2, 4:2, 5:2, 6:3, 7:3, 8:4, 9:4, 10:5, 11:5, 12:6, 13:6}
    line = f"  {method_name}"
    for n in range(2, 14):
        thr = thresholds[n]
        pct = sum(1 for h in data[n] if h >= thr) / total * 100
        line += f" {pct:>7.1f}%"
    print(line)
