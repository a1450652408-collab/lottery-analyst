# -*- coding: utf-8 -*-
"""04/32/50 选二复式3码 倍投方案 多策略模拟"""
import json, os
from itertools import combinations

BASE = r"C:\Users\14506\WorkBuddy\Claw"
TRIPLE = [4, 32, 50]
BETS = list(combinations(TRIPLE, 2))  # [(4,32),(4,50),(32,50)]
NOTES_PER_DAY = 3  # 每天3注
PRICE_PER_NOTE = 2
BASE_COST = NOTES_PER_DAY * PRICE_PER_NOTE  # 6元

# 选二奖金：每注中19元；3注全中（3个号都中）每注+57元
def day_prize(draw_set):
    notes_mid = 0
    for b in BETS:
        if all(n in draw_set for n in b):
            notes_mid += 1
    # 中2全中：每注19元；3注全中：每注57元
    if notes_mid == 3:
        return 57 * 3, notes_mid
    elif notes_mid >= 1:
        return 19 * notes_mid, notes_mid
    return 0, 0

# ============ 数据 ============
with open(os.path.join(BASE, "data", "kl8_500.json"), encoding="utf-8") as f:
    kl8 = json.load(f)

def get_days(ym):
    return sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])

# ============ 倍投策略 ============
def simulate(days, max_stage, multiplier=2):
    """基础6元起，未中翻倍 max_stage 倍后放弃，从基础重置
    multiplier=2: 6/12/24/48/96/192/384...
    multiplier=1.5: 6/9/13.5/20.25...
    """
    base = BASE_COST
    rows = []
    stage = 1; cum_inv = 0; cum_prize = 0; peak = 0; cum_loss_peak = 0; busted_count = 0
    for d in days:
        if stage > max_stage:
            # 止损：放弃本次，重置
            busted_count += 1
            stage = 1
            continue
        inv = base * (multiplier ** (stage - 1))
        # 实际3注，金额按比例增加（这里简化为"放大倍率"）
        # 严格说，3注只能从3增加到3*2=6注到3*4=12注，但选二复式3注就是3注，所以"倍投"通常指金额翻倍
        # 这里按"金额倍增"模拟（即相当于多买 N 套）
        # 简化：每档投入 = 基础 × 倍数（相当于多买若干套相同3注）
        notes_this = NOTES_PER_DAY * (multiplier ** (stage - 1))
        notes_mid = 0
        for b in BETS:
            if all(n in set(d["n"]) for n in b):
                notes_mid += 1
        if notes_mid == 3:
            prize = 57 * notes_this
        elif notes_mid >= 1:
            prize = 19 * notes_this
        else:
            prize = 0

        cum_inv += inv
        cum_prize += prize
        peak = max(peak, inv)
        net = cum_prize - cum_inv
        cum_loss_peak = max(cum_loss_peak, -net if net < 0 else 0)

        won = prize > 0
        rows.append({"d": d["d"], "p": d["p"], "stage": stage, "inv": inv,
                     "notes_this": notes_this, "notes_mid": notes_mid,
                     "prize": prize, "cum_inv": cum_inv, "cum_prize": cum_prize,
                     "net": net, "won": won})
        if won:
            stage = 1
        else:
            stage += 1
    return rows, cum_inv, cum_prize, peak, cum_loss_peak, busted_count

# ============ 不同策略对比 ============
STRATEGIES = [
    ("2倍 倍投 止损3期", 2, 3),
    ("2倍 倍投 止损5期", 2, 5),
    ("2倍 倍投 止损7期", 2, 7),
    ("2倍 倍投 止损10期", 2, 10),
    ("1.5倍 倍投 止损5期", 1.5, 5),
    ("1.5倍 倍投 止损7期", 1.5, 7),
    ("1.5倍 倍投 止损10期", 1.5, 10),
    ("1.5倍 倍投 止损12期", 1.5, 12),
    ("无倍投 每天固定6元", 1, 999),  # 永远不翻倍
]

print(f"{'策略':<25} {'月份':<5} {'总投入':>8} {'总奖金':>8} {'净盈亏':>9} {'ROI':>8} {'峰值投入':>10} {'最大亏损':>10} {'止损次数':>8}")
print("-" * 110)
all_results = {}
for name, mul, sl in STRATEGIES:
    for ym, label in [("2026-07", "7月"), ("2026-08", "8月"), ("7+8月", "合计")]:
        if ym == "7+8月":
            days = get_days("2026-07") + get_days("2026-08")
        else:
            days = get_days(ym)
        rows, ci, cp, pk, lp, bc = simulate(days, sl, mul)
        net = cp - ci
        roi = net/ci*100 if ci else 0
        print(f"{name:<25} {label:<5} {ci:>8,} {cp:>8,} {net:>+9,} {roi:>+7.1f}% {pk:>10,} {lp:>10,} {bc:>8}")
        all_results[(name, label)] = {"rows": rows, "ci": ci, "cp": cp, "net": net, "pk": pk, "lp": lp, "bc": bc}

# ============ 连不中分布（按"中1注以上"） ============
all_days = get_days("2026-07") + get_days("2026-08")
seq = [1 if day_prize(set(d["n"]))[1] >= 1 else 0 for d in all_days]
# 连不中段
runs = []; cur = 0
for s in seq:
    if s == 0: cur += 1
    else:
        if cur > 0: runs.append(cur)
        cur = 0
if cur > 0: runs.append(cur)
print(f"\n连不中分布(46天,按'中1注以上'为达标): 共{len(runs)}段, 最长{max(runs) if runs else 0}期, 段长{runs}")

# 按"3注全中"达标
seq2 = [1 if day_prize(set(d["n"]))[1] == 3 else 0 for d in all_days]
runs2 = []; cur = 0
for s in seq2:
    if s == 0: cur += 1
    else:
        if cur > 0: runs2.append(cur)
        cur = 0
if cur > 0: runs2.append(cur)
print(f"连不中分布(46天,按'3注全中'=54元为达标): 共{len(runs2)}段, 最长{max(runs2) if runs2 else 0}期")

# ============ 倍投档位表 ============
print("\n===== 倍投档位表(2倍) =====")
print(f"{'档位':<6} {'本期投入':<10} {'累计投入':<10} {'中2奖金':<10} {'中2净':<10} {'中3奖金':<10} {'中3净':<10}")
cum = 0
for n in range(1, 13):
    inv = BASE_COST * (2 ** (n - 1))
    cum += inv
    p2 = 19 * (2 ** (n - 1))  # 翻倍投入，奖金也按注数翻倍
    p3 = 57 * (2 ** (n - 1))
    print(f"{n:<6} {inv:<10} {cum:<10} {p2:<10} {p2-cum:<+10} {p3:<10} {p3-cum:<+10}")

print("\n===== 倍投档位表(1.5倍) =====")
print(f"{'档位':<6} {'本期投入':<10} {'累计投入':<10} {'中2奖金':<10} {'中2净':<10} {'中3奖金':<10} {'中3净':<10}")
cum = 0
for n in range(1, 13):
    inv = BASE_COST * (1.5 ** (n - 1))
    cum += inv
    p2 = 19 * (1.5 ** (n - 1))
    p3 = 57 * (1.5 ** (n - 1))
    print(f"{n:<6} {inv:<10.1f} {cum:<10.1f} {p2:<10.1f} {p2-cum:<+10.1f} {p3:<10.1f} {p3-cum:<+10.1f}")

# ============ 输出JSON供HTML用 ============
out = {
    "strategies": STRATEGIES,
    "results": {f"{n}|{l}": {k: v for k, v in r.items() if k != "rows"} for (n, l), r in all_results.items()},
    "runs_by_hit1": runs,
    "runs_max_hit1": max(runs) if runs else 0,
    "runs_by_hit3": runs2,
    "runs_max_hit3": max(runs2) if runs2 else 0,
}
with open(os.path.join(BASE, "outputs", "kl8_x2_beiwtou_data.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\n数据已存 outputs/kl8_x2_beiwtou_data.json")