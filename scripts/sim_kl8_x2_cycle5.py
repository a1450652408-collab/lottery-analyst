# -*- coding: utf-8 -*-
"""×2翻倍 + 5期强制止损周期 模拟（7月20/33/44 / 8月04/32/50）"""
import json
from itertools import combinations

BASE = r"C:\Users\14506\WorkBuddy\Claw"

with open(BASE + r"\data\kl8_500.json", encoding="utf-8") as f:
    kl8 = json.load(f)

def bets_of(triple):
    return list(combinations(triple, 2))

def day_notes(draw_set, bets):
    return sum(1 for b in bets if all(n in draw_set for n in b))

def simulate_x2_cycle(triple, days, cycle=5):
    bets = bets_of(triple)
    stage = 1
    cum_inv = 0
    cum_prize = 0
    rows = []
    cycles = []
    cur_cycle_inv = 0
    cycle_start = days[0]["d"] if days else ""
    busts = 0
    wins = 0
    for d in days:
        inv = 6 * (2 ** (stage - 1))
        notes = day_notes(set(d["n"]), bets)
        prize = 19 * notes * (2 ** (stage - 1)) if notes > 0 else 0
        cum_inv += inv
        cum_prize += prize
        cur_cycle_inv += inv
        won = prize > 0
        if won:
            wins += 1
        rows.append({"d": d["d"], "p": d["p"], "stage": stage, "inv": inv,
                     "notes": notes, "prize": prize, "net": cum_prize - cum_inv, "won": won})
        if won:
            cycles.append((cycle_start, d["d"], stage, cur_cycle_inv, True))
            stage = 1
            cur_cycle_inv = 0
            cycle_start = d["d"]
        else:
            stage += 1
            if stage > cycle:
                cycles.append((cycle_start, d["d"], cycle, cur_cycle_inv, False))
                busts += 1
                stage = 1
                cur_cycle_inv = 0
    if cur_cycle_inv > 0 and stage > 1:
        cycles.append((cycle_start, days[-1]["d"], stage - 1, cur_cycle_inv, False))
    return rows, cum_inv, cum_prize, cycles, busts, wins

for ym, label, triple in [("2026-07", "7月", [20, 33, 44]), ("2026-08", "8月", [4, 32, 50])]:
    days = sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])
    rows, ci, cp, cycles, busts, wins = simulate_x2_cycle(triple, days, 5)
    net = cp - ci
    peak = max(r["inv"] for r in rows)
    print("===== {} {} ×2翻倍+5期周期 =====".format(label, triple))
    print("投入{} 奖金{} 净{:+} ROI {:+.1f}% 峰值{} 止损周期{}个 中奖{}次".format(
        ci, cp, net, net / ci * 100, peak, busts, wins))
    print("{} {:10} {:3} {:6} {:5} {:7} {:8}".format("日期", "期号", "档", "投入", "中注", "奖金", "累计净"))
    for r in rows:
        tag = "★中{}注".format(r["notes"]) if r["notes"] > 0 else "未中"
        print("{} {:10} {:3} {:6} {} {:7} {:+}".format(
            r["d"], r["p"], r["stage"], r["inv"], tag, r["prize"], r["net"]))
    print("周期明细: {}个周期".format(len(cycles)))
    for cs, ce, st, inv, won in cycles:
        print("  {}~{} 追{}期 投入{:.0f} {}".format(cs, ce, st, inv, "✓中" if won else "✗止损"))
    print()
