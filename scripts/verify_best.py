# -*- coding: utf-8 -*-
"""验证最优方案 + 探索改进方向"""
import json
from itertools import combinations

with open("data/kl8_500.json", encoding="utf-8") as f:
    kl8 = json.load(f)

def compute_x3_picks(data, ym):
    x3Data = []
    for it in data:
        if not it or not it.get("d"): continue
        if it["d"][:7] < ym: x3Data.append(it)
        if len(x3Data) >= 50: break
    if len(x3Data) < 10: x3Data = data[:min(50, len(data))]
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
        for n in x3Data[j]["n"]: freq30[n] += 1
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
            if score[n] > bs: bs = score[n]; best = n
        picks.append(best)
    return picks

def day_notes(draw_set, bets):
    return sum(1 for b in bets if all(n in draw_set for n in b))

def sim_detail(triple, days, warm, mult, in_stop):
    bets = list(combinations(triple, 2))
    miss = 0; investing = False; stage = 1; in_miss = 0
    cum_inv = 0; cum_prize = 0; peak = 0; wins = 0; busts = 0
    for d in days:
        notes = day_notes(set(d["n"]), bets)
        if investing:
            inv = 6 * (mult ** (stage - 1))
            prize = 19 * notes * (mult ** (stage - 1)) if notes > 0 else 0
            cum_inv += inv; cum_prize += prize
            peak = max(peak, inv)
            if prize > 0:
                wins += 1; investing = False; miss = 0; stage = 1; in_miss = 0
            else:
                stage += 1; in_miss += 1; miss += 1
                if in_miss >= in_stop:
                    busts += 1; investing = False; miss = 0; stage = 1; in_miss = 0
        else:
            if notes > 0: miss = 0
            else:
                miss += 1
                if miss >= warm:
                    investing = True; stage = 1; in_miss = 0
    return {"inv": cum_inv, "prize": cum_prize, "net": cum_prize - cum_inv,
            "peak": peak, "wins": wins, "busts": busts}

months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
          "2026-04", "2026-05", "2026-06", "2026-07", "2026-08"]
month_picks = {}
for ym in months:
    days = sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])
    if days:
        month_picks[ym] = (compute_x3_picks(kl8, ym), days)

print("===== 方案A：预警7 + ×2 + 止损5（峰值最低96元）=====")
tot_inv = 0; tot_prize = 0; max_peak = 0
for ym, (triple, days) in month_picks.items():
    r = sim_detail(triple, days, 7, 2.0, 5)
    tot_inv += r["inv"]; tot_prize += r["prize"]; max_peak = max(max_peak, r["peak"])
    print("  {} {} 净{:>+7,} 峰值{:>4,} 中{}次 止损{}次".format(
        ym, " ".join("{:02d}".format(n) for n in triple), r["net"], r["peak"], r["wins"], r["busts"]))
print("  合计: 净{:+,} ROI {:+.1f}% 峰值{:,} 投入{:,}".format(
    tot_prize - tot_inv, (tot_prize - tot_inv) / tot_inv * 100, max_peak, tot_inv))

print("\n===== 方案B：预警5 + ×2 + 止损7 =====")
tot_inv = 0; tot_prize = 0; max_peak = 0
for ym, (triple, days) in month_picks.items():
    r = sim_detail(triple, days, 5, 2.0, 7)
    tot_inv += r["inv"]; tot_prize += r["prize"]; max_peak = max(max_peak, r["peak"])
print("  合计: 净{:+,} ROI {:+.1f}% 峰值{:,} 投入{:,}".format(
    tot_prize - tot_inv, (tot_prize - tot_inv) / tot_inv * 100, max_peak, tot_inv))

# 探索：选二复式4码（6注12元）
print("\n===== 探索：选二复式4码（6注12元/期）=====")
def compute_x4_picks(data, ym):
    picks = compute_x3_picks(data, ym)
    x3Data = []
    for it in data:
        if not it or not it.get("d"): continue
        if it["d"][:7] < ym: x3Data.append(it)
        if len(x3Data) >= 50: break
    if len(x3Data) < 10: x3Data = data[:min(50, len(data))]
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
        for n in x3Data[j]["n"]: freq30[n] += 1
    zones = [(1, 20), (21, 40), (41, 60), (61, 80)]
    win = min(30, len(x3Data))
    score = {n: ema[n] * 5 + (min(freq30[n], win) / win) * 3 + mom[n] * 2 for n in range(1, 81)}
    candidates = [(n, score[n]) for n in range(1, 81) if n not in picks]
    candidates.sort(key=lambda x: -x[1])
    return picks + [candidates[0][0]]

def sim_x4(triple4, days, warm, mult, in_stop):
    bets = list(combinations(triple4, 2))
    cost = 12
    miss = 0; investing = False; stage = 1; in_miss = 0
    cum_inv = 0; cum_prize = 0; peak = 0
    for d in days:
        notes = day_notes(set(d["n"]), bets)
        if investing:
            inv = cost * (mult ** (stage - 1))
            prize = 19 * notes * (mult ** (stage - 1)) if notes > 0 else 0
            cum_inv += inv; cum_prize += prize
            peak = max(peak, inv)
            if prize > 0:
                investing = False; miss = 0; stage = 1; in_miss = 0
            else:
                stage += 1; in_miss += 1; miss += 1
                if in_miss >= in_stop:
                    investing = False; miss = 0; stage = 1; in_miss = 0
        else:
            if notes > 0: miss = 0
            else:
                miss += 1
                if miss >= warm:
                    investing = True; stage = 1; in_miss = 0
    return cum_inv, cum_prize, peak

for warm, stop in [(5, 7), (7, 5), (6, 6)]:
    tot_inv = 0; tot_prize = 0; max_peak = 0
    for ym, (triple3, days) in month_picks.items():
        triple4 = compute_x4_picks(kl8, ym)
        ci, cp, pk = sim_x4(triple4, days, warm, 2.0, stop)
        tot_inv += ci; tot_prize += cp; max_peak = max(max_peak, pk)
    net = tot_prize - tot_inv
    print("  4码 预警{} 止损{}: 净{:>+10,} ROI {:>+6.1f}% 峰值{:>8,} 投入{:>8,}".format(
        warm, stop, net, net / tot_inv * 100 if tot_inv else 0, max_peak, tot_inv))
