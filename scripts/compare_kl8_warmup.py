# -*- coding: utf-8 -*-
"""每月换号 + 选二复式3码：三策略对比
A: ×2无限倍投（第1期开始）
B: 连不中≥5期后进场 ×2翻倍（预警值5期）
C: 无倍投固定6元
"""
import json
from itertools import combinations

BASE = r"C:\Users\14506\WorkBuddy\Claw"

with open(BASE + r"\data\kl8_500.json", encoding="utf-8") as f:
    kl8 = json.load(f)

# ============ 复刻选三每月追号算法 ============
def compute_x3_picks(data, ym):
    x3Data = []
    for it in data:
        if not it or not it.get("d"):
            continue
        if it["d"][:7] < ym:
            x3Data.append(it)
        if len(x3Data) >= 50:
            break
    if len(x3Data) < 10:
        x3Data = data[:min(50, len(data))]
    period = len(x3Data)
    ema = {}
    for n in range(1, 81):
        seq = [1 if n in it["n"] else 0 for it in x3Data]
        if not seq:
            ema[n] = 0; continue
        e = seq[-1]
        for j in range(len(seq) - 2, -1, -1):
            e = 0.5 * seq[j] + 0.5 * e
        ema[n] = e
    R5, P5 = {n: 0 for n in range(1, 81)}, {n: 0 for n in range(1, 81)}
    for j in range(min(10, period)):
        for n in x3Data[j]["n"]:
            if j < 5: R5[n] += 1
            else: P5[n] += 1
    mom = {n: max(-2, min(2, (R5[n] - P5[n]) / max(P5[n], 1))) for n in range(1, 81)}
    freq30 = {n: 0 for n in range(1, 81)}
    for j in range(min(30, period)):
        for n in x3Data[j]["n"]:
            freq30[n] += 1
    zones = [(1, 20), (21, 40), (41, 60), (61, 80)]
    win = min(30, len(x3Data))
    score = {n: ema[n] * 5 + (min(freq30[n], win) / win) * 3 + mom[n] * 2 for n in range(1, 81)}
    za = []
    for i, (a, b) in enumerate(zones):
        za.append({"i": i, "a": sum(score[n] for n in range(a, b + 1)) / 20})
    za.sort(key=lambda x: -x["a"])
    picks = []
    for z in za[:3]:
        zr = zones[z["i"]]
        best = zr[0]; bs = -999
        for n in range(zr[0], zr[1] + 1):
            if score[n] > bs:
                bs = score[n]; best = n
        picks.append(best)
    return picks

def day_notes(draw_set, bets):
    return sum(1 for b in bets if all(n in draw_set for n in b))

# ============ 策略模拟 ============
def sim_strategy(triple, days, strategy, warm=5):
    """strategy: 'immediate' 立即×2 / 'warm' 连不中warm期后进场×2 / 'fix' 固定6元"""
    bets = list(combinations(triple, 2))
    stage = 1          # 当前档位
    miss_streak = 0    # 连不中期数（用于warm判断）
    investing = False  # warm策略：是否已进场
    cum_inv = 0; cum_prize = 0
    peak = 0; max_miss = 0; wins = 0
    rows = []
    for d in days:
        notes = day_notes(set(d["n"]), bets)
        prize = 0; inv = 0
        if strategy == "immediate":
            inv = 6 * (2 ** (stage - 1))
            mult = 2 ** (stage - 1)
            if notes > 0:
                prize = 19 * notes * mult
            cum_inv += inv; cum_prize += prize
            peak = max(peak, inv)
            if prize > 0:
                wins += 1; max_miss = max(max_miss, miss_streak); miss_streak = 0; stage = 1
            else:
                miss_streak += 1; stage += 1
        elif strategy == "warm":
            if investing:
                inv = 6 * (2 ** (stage - 1))
                mult = 2 ** (stage - 1)
                if notes > 0:
                    prize = 19 * notes * mult
                cum_inv += inv; cum_prize += prize
                peak = max(peak, inv)
                if prize > 0:
                    wins += 1; investing = False; miss_streak = 0; stage = 1
                else:
                    miss_streak += 1; stage += 1
                    if miss_streak >= warm:
                        pass  # 已进场，继续跟
            else:
                # 未进场：观察
                if notes > 0:
                    miss_streak = 0
                else:
                    miss_streak += 1
                    if miss_streak >= warm:
                        investing = True
                        stage = 1  # 进场从第1档6元开始
        else:  # fix
            inv = 6
            if notes > 0:
                prize = 19 * notes
            cum_inv += inv; cum_prize += prize
            if prize > 0:
                wins += 1; max_miss = max(max_miss, miss_streak); miss_streak = 0
            else:
                miss_streak += 1
        rows.append({"d": d["d"], "notes": notes, "inv": inv, "prize": prize,
                     "cum": cum_prize - cum_inv})
    max_miss = max(max_miss, miss_streak)
    return {"inv": cum_inv, "prize": cum_prize, "net": cum_prize - cum_inv,
            "peak": peak, "max_miss": max_miss, "wins": wins, "days": len(days),
            "rows": rows}

months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
          "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]

results = {"A-立即×2": {}, "B-等5期进场×2": {}, "C-固定6元": {}}

print("===== 每月换号 · 三策略 10个月对比 =====\n")
print(f"{'月份':<8} {'号码':<14} | {'A立即×2 净':>12} {'A峰值':>8} | {'B等5期×2 净':>12} {'B峰值':>8} | {'C固定6元 净':>11} {'C峰值':>7}")
for ym in months:
    days = sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])
    if not days:
        continue
    triple = compute_x3_picks(kl8, ym)
    ra = sim_strategy(triple, days, "immediate")
    rb = sim_strategy(triple, days, "warm", 5)
    rc = sim_strategy(triple, days, "fix")
    results["A-立即×2"][ym] = ra
    results["B-等5期进场×2"][ym] = rb
    results["C-固定6元"][ym] = rc
    nums = " ".join("{:02d}".format(n) for n in triple)
    print("{:<8} {:<14} | {:>+12,} {:>8,} | {:>+12,} {:>8,} | {:>+11,} {:>7,}".format(
        ym, nums, ra["net"], ra["peak"], rb["net"], rb["peak"], rc["net"], rc["peak"]))

print("-" * 110)
for name in ["A-立即×2", "B-等5期进场×2", "C-固定6元"]:
    tot_inv = sum(v["inv"] for v in results[name].values())
    tot_prize = sum(v["prize"] for v in results[name].values())
    tot_net = tot_prize - tot_inv
    max_peak = max(v["peak"] for v in results[name].values())
    max_miss = max(v["max_miss"] for v in results[name].values())
    print("{}: 合计净 {:>+12,} | ROI {:>+7.1f}% | 最大峰值 {:>8,} | 最长连不中 {}期".format(
        name, tot_net, tot_net / tot_inv * 100, max_peak, max_miss))

# B策略细节：哪些月份进场了、次数
print("\n===== B策略（等5期进场）逐月明细 =====")
for ym in months:
    if ym not in results["B-等5期进场×2"]:
        continue
    r = results["B-等5期进场×2"][ym]
    print("{}: 投入{} 奖金{} 净{:+,} 峰值{} 中奖{}次".format(
        ym, r["inv"], r["prize"], r["net"], r["peak"], r["wins"]))
