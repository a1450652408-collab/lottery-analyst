# -*- coding: utf-8 -*-
"""快乐8 7月 vs 8月 跨月盈亏对比（精确复式奖金）"""
import json, os
from math import comb

BASE = r"C:\Users\14506\WorkBuddy\Claw"

# ============ 官方奖金表 ============
def prize_x5(h, n=9):
    return comb(h,5)*1000 + comb(h,4)*comb(n-h,1)*21 + comb(h,3)*comb(n-h,2)*3

def prize_x8(h, n=9):
    return (comb(h,8)*50000 + comb(h,7)*comb(n-h,1)*800 +
            comb(h,6)*comb(n-h,2)*88 + comb(h,5)*comb(n-h,3)*10 + comb(h,4)*comb(n-h,4)*3)

def prize_x9(h, n=10):
    return (comb(h,9)*300000 + comb(h,8)*comb(n-h,1)*2000 +
            comb(h,7)*comb(n-h,2)*200 + comb(h,6)*comb(n-h,3)*20 + comb(h,5)*comb(n-h,4)*5)

def prize_x10(h, n=11):
    return (comb(h,10)*5000000 + comb(h,9)*comb(n-h,1)*8000 +
            comb(h,8)*comb(n-h,2)*800 + comb(h,7)*comb(n-h,3)*80 + comb(h,6)*comb(n-h,4)*5)

def prize_x3(h):
    return 53 if h >= 3 else 3 if h == 2 else 0

def prize_x2(h):
    return 19 if h >= 2 else 0

# 1-15 区间选五（胆3拖7 = 10码，选五需中5，实际开奖1-15内约5个）
def prize_15x5(h):
    return comb(h,5)*1000 + comb(h,4)*comb(10-h,1)*21 + comb(h,3)*comb(10-h,2)*3

# ============ 玩法定义 ============
# 固定复式（每日固定号）
FIXED = {
    "选五9码复式": {"nums": [5,11,12,18,19,62,63,77,78], "cost": 252, "fn": prize_x5},
    "选八9码复式": {"nums": [5,11,12,18,19,62,63,77,78], "cost": 18,  "fn": prize_x8},
    "选九10码复式": {"nums": [8,9,15,16,65,66,72,73,79,80], "cost": 20, "fn": prize_x9},
    "选十11码复式": {"nums": [1,2,5,6,12,18,19,27,40,41,53], "cost": 22, "fn": prize_x10},
}

# 选三每月追号（每日1注2元）
X3 = {"2026-07": [20,33,44], "2026-08": [4,32,50]}

# ============ 数据加载 ============
with open(os.path.join(BASE, "data", "kl8_500.json"), encoding="utf-8") as f:
    kl8 = json.load(f)

def month_days(ym):
    return sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])

results = {}  # 玩法 -> {月: {inv, prize, net, days, hits3, hits2}}

for ym in ["2026-07", "2026-08"]:
    days = month_days(ym)
    label = "7月" if ym == "2026-07" else "8月"
    for name, cfg in FIXED.items():
        key = f"{name}"
        if key not in results:
            results[key] = {}
        inv = 0; prize = 0; h3 = 0; h2 = 0; hit_dist = {}
        for d in days:
            draw = set(d["n"])
            h = sum(1 for n in cfg["nums"] if n in draw)
            inv += cfg["cost"]
            pr = cfg["fn"](h)
            prize += pr
            hit_dist[h] = hit_dist.get(h, 0) + 1
            if h >= 3: h3 += 1
            elif h == 2: h2 += 1
        results[key][label] = {"inv": inv, "prize": prize, "net": prize - inv,
                                "days": len(days), "h3": h3, "h2": h2, "dist": hit_dist,
                                "cost_day": cfg["cost"]}

    # 选三
    key = "选三每月追号(2元/天)"
    if key not in results:
        results[key] = {}
    inv = 0; prize = 0; h3 = 0; h2 = 0; hit_dist = {}
    nums = X3[ym]
    for d in days:
        draw = set(d["n"])
        h = sum(1 for n in nums if n in draw)
        inv += 2
        pr = prize_x3(h)
        prize += pr
        hit_dist[h] = hit_dist.get(h, 0) + 1
        if h >= 3: h3 += 1
        elif h == 2: h2 += 1
    results[key][label] = {"inv": inv, "prize": prize, "net": prize - inv,
                            "days": len(days), "h3": h3, "h2": h2, "dist": hit_dist,
                            "cost_day": 2}

# ============ 橙紫卡 ============
with open(os.path.join(BASE, "data", "kl8_orange_purple_hits.json"), encoding="utf-8") as f:
    op = json.load(f)

OP_CARDS = {
    "橙卡选二(1-40区)": ("orange_x2", prize_x2, 2),
    "紫卡选二(41-80区)": ("purple_x2", prize_x2, 2),
    "橙卡选三(1-40区)": ("orange_x3", prize_x3, 2),
    "紫卡选三(41-80区)": ("purple_x3", prize_x3, 2),
}
for ym in ["2026-07", "2026-08"]:
    label = "7月" if ym == "2026-07" else "8月"
    op_days = [r for r in op if r["date"].startswith(ym)]
    for name, (key, fn, cost) in OP_CARDS.items():
        if name not in results:
            results[name] = {}
        inv = 0; prize = 0; wins = 0; hit_dist = {}
        for r in op_days:
            item = r[key]
            h = len(item["hit"])
            inv += cost
            pr = item["prize"]
            prize += pr
            if pr > 0: wins += 1
            hit_dist[h] = hit_dist.get(h, 0) + 1
        results[name][label] = {"inv": inv, "prize": prize, "net": prize - inv,
                                "days": len(op_days), "wins": wins, "dist": hit_dist,
                                "cost_day": cost}

# ============ 1-15 区间选五3胆7拖 ============
with open(os.path.join(BASE, "data", "sh15x5_data.json"), encoding="utf-8") as f:
    sh15 = json.load(f)

dan15 = [1, 7, 11]
tuo15 = [2, 4, 5, 6, 8, 12, 13]
all10 = dan15 + tuo15
# 3胆7拖 选五 = C(7,2)=21注 × 2元 = 42元/天
key = "1-15区间选五3胆7拖(42元/天)"
if key not in results:
    results[key] = {}
for ym in ["2026-07", "2026-08"]:
    label = "7月" if ym == "2026-07" else "8月"
    sh_days = [r for r in sh15 if r["d"].startswith(ym)]
    inv = 0; prize = 0; wins = 0; hit_dist = {}
    for d in sh_days:
        draw = set(d["n"])
        h = sum(1 for n in all10 if n in draw)
        inv += 42
        pr = prize_15x5(h)
        prize += pr
        if pr > 0: wins += 1
        hit_dist[h] = hit_dist.get(h, 0) + 1
    results[key][label] = {"inv": inv, "prize": prize, "net": prize - inv,
                            "days": len(sh_days), "wins": wins, "dist": hit_dist,
                            "cost_day": 42}

# ============ 输出 ============
print(f"{'玩法':<28} {'月份':<4} {'天数':<4} {'成本/天':<7} {'总投入':<8} {'总奖金':<8} {'净盈亏':<9} {'ROI':<8} {'明细'}")
print("-" * 120)
summary = []
for name, months in results.items():
    for label in ["7月", "8月"]:
        if label not in months:
            continue
        r = months[label]
        roi = r["net"] / r["inv"] * 100 if r["inv"] else 0
        dist = r.get("dist", {})
        dist_s = ",".join(f"{k}个:{v}期" for k, v in sorted(dist.items()))
        summary.append((name, label, r, roi))
        print(f"{name:<28} {label:<4} {r['days']:<4} {r['cost_day']:<7} {r['inv']:<8} {r['prize']:<8} {r['net']:+<9} {roi:+.1f}%  {dist_s}")

print()
print("===== 按ROI排序 =====")
ranked = sorted(summary, key=lambda x: -x[3])
for name, label, r, roi in ranked:
    print(f"{label} {name:<28} 净{r['net']:+d}元  ROI {roi:+.1f}%")

# 保存结果供HTML使用
with open(os.path.join(BASE, "outputs", "kl8_monthly_compare_data.json"), "w", encoding="utf-8") as f:
    json.dump({name: {l: {k: v for k, v in m.items() if k != "dist"} for l, m in months.items()} for name, months in results.items()},
              f, ensure_ascii=False, indent=1)
print("\n数据已存 outputs/kl8_monthly_compare_data.json")
