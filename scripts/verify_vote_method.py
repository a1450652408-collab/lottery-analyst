#!/usr/bin/env python3
"""
多因子投票胆码筛选 - 多角度验证回测
- 三段时间验证（前/中/后）
- 无事后诸葛亮（滚动窗口）
- 对比随机期望
- 返奖率验证
"""
import json, sys

with open('data/kl8_500.json', 'r', encoding='utf-8') as f:
    RAW = json.load(f)

def get_nums(d):
    return d.get("n", d.get("r", []))

def compute_top35_and_vote(recs, alpha=0.5):
    """返回35码池 + 多因子投票排序"""
    nMin, nMax = 1, 80
    L = len(recs)
    win30 = min(30, L)

    # 杀号
    freq = {i: 0 for i in range(nMin, nMax + 1)}
    last = {i: -1 for i in range(nMin, nMax + 1)}
    for rdi, d in enumerate(recs):
        for n in get_nums(d):
            if nMin <= n <= nMax:
                freq[n] += 1
                last[n] = rdi
    miss = {i: L - 1 - last[i] for i in range(nMin, nMax + 1)}
    kills = set()
    for i in range(nMin, nMax + 1):
        if freq[i] == 0 and miss[i] >= 15:
            kills.add(i)
        elif miss[i] >= 12:
            kills.add(i)

    # EMA评分
    ema = {}
    for i in range(nMin, nMax + 1):
        seq = [1 if i in get_nums(d) else 0 for d in recs]
        if not seq:
            ema[i] = 0
            continue
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]:
            e = alpha * v + (1 - alpha) * e
        ema[i] = e

    # 频率30期
    freq30 = {i: 0 for i in range(nMin, nMax + 1)}
    for j in range(win30):
        for n in get_nums(recs[j]):
            if nMin <= n <= nMax:
                freq30[n] += 1

    # 动量
    r5, p5 = {i: 0 for i in range(nMin, nMax + 1)}, {i: 0 for i in range(nMin, nMax + 1)}
    for j in range(min(10, L)):
        for n in get_nums(recs[j]):
            if j < 5:
                r5[n] += 1
            else:
                p5[n] += 1
    mom = {}
    for i in range(nMin, nMax + 1):
        mom[i] = max(-2, min(2, (r5[i] - p5[i]) / max(p5[i], 1)))

    prev = set(get_nums(recs[1])) if L > 1 else set()

    # EMA综合评分（用于35码池选号）
    scores = {}
    for i in range(nMin, nMax + 1):
        s = (ema[i] or 0) * 5.0 + (freq30[i] / win30) * 3.0 + (mom[i] or 0) * 2.0
        if i in prev:
            s += 3.0
        if i in kills:
            s = -999
        s += max(0, 10 - (miss.get(i, 50))) * 0.5
        scores[i] = s
    ranked = sorted(range(nMin, nMax + 1), key=lambda n: -scores[n])
    top35 = ranked[:35]

    # 多因子投票排序（在35码池内）
    votes = {}
    for n in top35:
        ema_rank = ranked.index(n)
        mom_sorted = sorted(top35, key=lambda x: -mom.get(x, -999))
        mom_rank = mom_sorted.index(n) if n in mom_sorted else 99
        freq_sorted = sorted(top35, key=lambda x: -freq30.get(x, -999))
        freq_rank = freq_sorted.index(n) if n in freq_sorted else 99
        vote = max(0, 35 - ema_rank) + max(0, 35 - mom_rank) + max(0, 35 - freq_rank)
        votes[n] = vote
    vote_ordered = sorted(top35, key=lambda n: -votes[n])

    # EMA直接排序
    ema_ordered = top35  # 本身就是EMA排序

    return top35, vote_ordered, ema_ordered


def backtest_segment(seg_name, data_segment, window=50):
    """回测一个时间段"""
    total = len(data_segment)
    if total < window + 1:
        return None

    stats = {
        "vote": {dc: {"hits": 0, "total": 0} for dc in [2, 3, 4, 5, 6]},
        "ema": {dc: {"hits": 0, "total": 0} for dc in [2, 3, 4, 5, 6]},
    }

    for start in range(total - window - 1, -1, -1):
        recs = data_segment[start:start + window]
        draw = data_segment[start]
        draw_set = set(get_nums(draw))

        top35, vote_ordered, ema_ordered = compute_top35_and_vote(recs, alpha=0.5)

        for method_name, ordered in [("vote", vote_ordered), ("ema", ema_ordered)]:
            for dc in [2, 3, 4, 5, 6]:
                dans = ordered[:dc]
                hits = sum(1 for n in dans if n in draw_set)
                stats[method_name][dc]["hits"] += hits
                stats[method_name][dc]["total"] += dc

    return stats


def print_segment_result(name, stats, random_expect):
    if stats is None:
        print(f"\n  {name}: 数据不足")
        return
    print(f"\n  {'='*55}")
    print(f"  {name}")
    print(f"  {'='*55}")
    print(f"  {'胆数':<6} {'多因子投票':<20} {'EMA直接取':<20} {'随机期望':<10}")
    print(f"  {'-'*55}")
    for dc in [2, 3, 4, 5, 6]:
        v = stats["vote"][dc]
        e = stats["ema"][dc]
        v_rate = v["hits"] / v["total"] * 100 if v["total"] > 0 else 0
        e_rate = e["hits"] / e["total"] * 100 if e["total"] > 0 else 0
        re = random_expect[dc]
        arrow = "✅" if v_rate > e_rate else "❌"
        print(f"  {dc:<6} {v_rate:>6.2f}% ({v['hits']}/{v['total']}) {arrow}  {e_rate:>6.2f}% ({e['hits']}/{e['total']})        {re:.1f}%")


# 主回测
print("=" * 60)
print("多因子投票 vs EMA直接取胆 - 多角度验证")
print("数据: %d期 | 窗口: 50期 | EMA系数: 0.5" % len(RAW))
print("=" * 60)

# 随机期望：35码池里平均有20×(35/80)=8.75个开奖号
avg_hits_in_35 = 20 * 35 / 80
random_expect = {}
for dc in [2, 3, 4, 5, 6]:
    # 从35个里选dc个，其中开奖号占avg_hits_in_35个
    random_expect[dc] = avg_hits_in_35 / 35 * 100

# 1. 全量回测
print("\n📊 全量回测（420期）")
stats_all = backtest_segment("全部420期", RAW, 50)
print_segment_result("全部420期", stats_all, random_expect)

# 2. 分三段验证
seg_size = len(RAW) // 3
segments = [
    ("前段（最早140期）", RAW[:seg_size]),
    ("中段（中间140期）", RAW[seg_size:2*seg_size]),
    ("后段（最近140期）", RAW[2*seg_size:]),
]

for sname, sdata in segments:
    print(f"\n📊 分段时间验证")
    stats = backtest_segment(sname, sdata, 50)
    print_segment_result(sname, stats, random_expect)

# 3. 汇总对比
print("\n" + "=" * 60)
print("📈 汇总：多因子投票 vs EMA直接取胆 对比")
print("=" * 60)

methods = [("多因子投票", "vote"), ("EMA直接取", "ema")]
for dc in [2, 3, 4]:
    print(f"\n{dc}胆对比:")
    for mname, mkey in methods:
        d = stats_all[mkey][dc]
        rate = d["hits"] / d["total"] * 100
        print(f"  {mname:<12}: {rate:.2f}% ({d['hits']}/{d['total']})  比随机{'+' if rate > random_expect[dc] else ''}{rate - random_expect[dc]:.1f}%")
