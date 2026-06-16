#!/usr/bin/env python3
"""
35码池选三回测 v3 — 完全对齐网站算法（含冷号混合）
"""
import json, math, random
from collections import Counter

with open('data/kl8_500.json', 'r', encoding='utf-8') as f:
    RAW = json.load(f)

def get_nums(d):
    return d.get("n", d.get("r", []))

def compute_top35_website(train, kills_set, miss):
    """完全复现网站的35码池计算"""
    # 1. EMA
    ema = {}
    for i in range(1, 81):
        seq = [1 if i in get_nums(d) else 0 for d in train]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]:
            e = 0.5 * v + 0.5 * e
        ema[i] = e

    # 2. 30期频率
    win30 = min(30, len(train))
    freq30 = Counter()
    for j in range(win30):
        for n in get_nums(train[j]):
            freq30[n] += 1

    # 3. 动量
    r5, p5 = Counter(), Counter()
    for j in range(min(10, len(train))):
        for n in get_nums(train[j]):
            if j < 5: r5[n] += 1
            else: p5[n] += 1

    mom = {}
    for i in range(1, 81):
        mom[i] = max(-2, min(2, (r5[i] - p5[i]) / max(p5[i], 1)))

    prev = set(get_nums(train[1])) if len(train) > 1 else set()

    # 4. 综合评分（完全对齐网站公式）
    scores = {}
    for i in range(1, 81):
        s = (ema[i] or 0) * 5.0 + (freq30[i] / win30) * 3.0 + (mom[i] or 0) * 2.0
        if i in prev: s += 3.0
        if i in kills_set: s = -999
        # 冷号混合：遗漏越短分越高
        mv = miss.get(i, 50)
        s += max(0, 10 - mv) * 0.5
        scores[i] = s

    ranked = sorted(range(1, 81), key=lambda n: -scores[n])
    top35 = ranked[:35]
    return top35, ranked, scores, freq30, mom, r5

def backtest_segment(data, label, start_idx, count):
    train_w = 50  # 网站实际使用50期
    hit2, hit3, total = 0, 0, 0
    rand2, rand3 = 0, 0
    pool_winners = 0
    random.seed(42)

    for offset in range(count):
        pred_idx = start_idx + offset
        if pred_idx + train_w >= len(data):
            break
        train = data[pred_idx:pred_idx + train_w]  # 网站用前50期
        actual = set(get_nums(data[pred_idx - 1]))  # 预测pred_idx-1期

        # 计算杀号和遗漏（对齐网站）
        freq50 = Counter()
        last = {}
        for rdi, d in enumerate(train):
            for n in get_nums(d):
                freq50[n] += 1
                last[n] = rdi
        kills = set()
        for i in range(1, 81):
            if freq50[i] == 0 and (len(train) - 1 - last.get(i, -1)) >= 15:
                kills.add(i)
            elif (len(train) - 1 - last.get(i, -1)) >= 12:
                kills.add(i)
        # 取前5个kill
        kill_list = sorted(list(kills))[:5]
        kills_set = set(kill_list)

        # 遗漏值
        miss = {}
        for i in range(1, 81):
            miss[i] = len(train) - 1 - last.get(i, -1)

        # 35码池
        top35, ranked, scores, freq30, mom, r5 = compute_top35_website(train, kills_set, miss)

        # 35码池质量
        pool_hits = len(set(top35) & actual)
        pool_winners += pool_hits

        # 多因子投票
        mom_ranked = sorted(top35, key=lambda n: -mom.get(n, -999))
        freq_ranked = sorted(top35, key=lambda n: -freq30.get(n, -999))

        votes = {}
        for n in top35:
            ema_r = ranked.index(n)
            mom_r = mom_ranked.index(n)
            freq_r = freq_ranked.index(n)
            vote = (35 - min(ema_r, 34)) + (35 - min(mom_r, 34)) + (35 - min(freq_r, 34))
            c = r5.get(n, 0)
            if c >= 5: vote -= 35
            elif c >= 4: vote -= 20
            elif c >= 3: vote -= 10
            elif c >= 2: vote -= 3
            votes[n] = vote

        voted = sorted(top35, key=lambda n: -votes[n])
        dantuo3 = set(voted[:3])

        hit_cnt = len(dantuo3 & actual)
        if hit_cnt >= 2: hit2 += 1
        if hit_cnt >= 3: hit3 += 1

        rand3pool = set(random.sample(top35, 3))
        rand_hit = len(rand3pool & actual)
        if rand_hit >= 2: rand2 += 1
        if rand_hit >= 3: rand3 += 1

        total += 1

    avg_pool = pool_winners / total if total else 0
    print(f"\n【{label}】{total}期")
    print(f"  35码池平均命中: {avg_pool:.1f}/20个开奖号")
    print(f"  算法 选三中2+: {hit2}/{total} = {hit2/total*100:.1f}% | 中3: {hit3}/{total} = {hit3/total*100:.1f}%")
    print(f"  随机 选三中2+: {rand2}/{total} = {rand2/total*100:.1f}% | 中3: {rand3}/{total} = {rand3/total*100:.1f}%")
    return avg_pool, hit2/total*100, hit3/total*100, rand2/total*100, rand3/total*100

print("=" * 60)
print("  35码池 · 多因子投票 · 选三回测 v3（对齐网站算法）")
print("  窗口50期 | EMA=0.5 | 冷号混合 | 温和过热惩罚")
print("=" * 60)

segments = [
    ("段1(近140期)", 150, 140),
    ("段2(前140期)", 295, 140),
    ("段3(再前140期)", 440, 140),
]

s_pool, s_p2, s_p3, s_r2, s_r3 = 0, 0, 0, 0, 0
n_seg = 0

for label, start, count in segments:
    ap, p2, p3, r2, r3 = backtest_segment(RAW, label, start, count)
    s_pool += ap; s_p2 += p2; s_p3 += p3; s_r2 += r2; s_r3 += r3
    n_seg += 1

print("\n" + "=" * 60)
print(f"三段平均:")
print(f"  35码池均中: {s_pool/n_seg:.1f}/20")
print(f"  算法: 中2+ {s_p2/n_seg:.1f}% | 中3 {s_p3/n_seg:.1f}%")
print(f"  随机: 中2+ {s_r2/n_seg:.1f}% | 中3 {s_r3/n_seg:.1f}%")
print("=" * 60)
