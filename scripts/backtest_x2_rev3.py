# -*- coding: utf-8 -*-
"""
快乐8卡片玩法(1-15区间) 把"选三追号卡片"改成"选二复式三码"的盈利分析
- 选二复式三码: 3个号码组成 C(3,2)=3注, 每期成本 3*2=6元
- 中奖规则(快乐8选二): 3码中≥2个命中 → 中1注19元; 3个全中 → 中3注57元
- 数据源: sh15x5_data.json (快乐8卡片玩法, 1-15区间每期5个号)
"""
import json, itertools
from collections import Counter

with open(r"C:\Users\14506\WorkBuddy\Claw\data\sh15x5_data.json", encoding="utf-8") as f:
    raw = json.load(f)

july = sorted([d for d in raw if d["d"].startswith("2026-07")], key=lambda x: x["d"])
print("7月期数:", len(july))

# ============ 1) 指定3码组合(胆码)逐期明细 ============
def backtest(triple, data):
    """返回逐期记录和汇总"""
    rows = []
    for d in data:
        hits = len(set(d["n"]) & set(triple))
        if hits >= 3:
            prize = 57
        elif hits == 2:
            prize = 19
        else:
            prize = 0
        rows.append((d["p"], d["d"], d["n"], hits, prize))
    total_cost = 6 * len(data)
    total_prize = sum(r[4] for r in rows)
    win2 = sum(1 for r in rows if r[3] == 2)
    win3 = sum(1 for r in rows if r[3] == 3)
    win_any = sum(1 for r in rows if r[3] >= 2)
    return {
        "rows": rows, "cost": total_cost, "prize": total_prize,
        "net": total_prize - total_cost,
        "win2": win2, "win3": win3, "win_any": win_any,
        "win_rate": win_any / len(data),
    }

dan_triple = [1, 7, 11]
res_dan = backtest(dan_triple, july)
print("\n===== 胆码 01/07/11 当选二复式三码 (7月30期) =====")
print("每期3注6元, 30期总投入 %d元, 中奖 %d元, 净 %d元" % (res_dan["cost"], res_dan["prize"], res_dan["net"]))
print("中2个%d期 / 中3个%d期 / 有奖率 %.1f%%" % (res_dan["win2"], res_dan["win3"], res_dan["win_rate"] * 100))
print("\n逐期明细:")
for p, dt, nums, hits, prize in res_dan["rows"]:
    mark = "★" if prize > 0 else " "
    print("%s %s %s 命中%d 奖金%3d元 %s" % (p, dt, str(nums), hits, prize, mark))

# ============ 2) 穷举1-15所有3码组合 ============
print("\n===== 穷举 C(15,3)=455组, 每组30期选二复式3码 =====")
results = []
for triple in itertools.combinations(range(1, 16), 3):
    r = backtest(list(triple), july)
    results.append((triple, r))

results.sort(key=lambda x: -x[1]["net"])
print("\n--- 收益 TOP15 ---")
for triple, r in results[:15]:
    print("三码 %02d-%02d-%02d | 投入%3d 中奖%4d 净%+4d | 中2:%d期 中3:%d期 有奖率%.0f%%" % (
        triple[0], triple[1], triple[2], r["cost"], r["prize"], r["net"],
        r["win2"], r["win3"], r["win_rate"] * 100))

profitable = [x for x in results if x[1]["net"] > 0]
print("\n--- 盈利组合统计 ---")
print("455组中净盈利: %d组 (%.1f%%), 打平: %d组" % (
    len(profitable), len(profitable) / 455 * 100,
    sum(1 for x in results if x[1]["net"] == 0)))

# 理论期望(若1-15均匀开出5个): 单码p=5/15=1/3
import math
p = 5 / 15
p2 = 3 * (p ** 2) * (1 - p)
p3 = p ** 3
ev = 19 * p2 + 57 * p3 - 6
print("\n===== 理论期望(假设1-15均匀, 每期5个) =====")
print("单码命中率 p=%.4f, 中2概率=%.4f, 中3概率=%.4f, 有奖率=%.4f (%.1f%%)" % (p, p2, p3, p2 + p3, (p2 + p3) * 100))
print("每期期望收益 = %.3f元 (投入6元) → 期望净 %.3f元/期, 返奖率 %.1f%%" % (ev + 6, ev, (ev + 6) / 6 * 100))

# 真实命中率(全7月所有组合平均)
avg_win_rate = sum(r["win_rate"] for _, r in results) / len(results)
avg_net = sum(r["net"] for _, r in results) / len(results)
print("\n===== 7月真实回测汇总(455组合平均) =====")
print("平均有奖率: %.2f%% (理论 %.1f%%)" % (avg_win_rate * 100, (p2 + p3) * 100))
print("平均净收益: %.2f元/30期 (每期%.2f元)" % (avg_net, avg_net / 30))

# ============ 3) 最佳组合的追号分析 ============
print("\n===== 追号(倍投)可行性: 以最佳组合为例 =====")
best = results[0]
print("最佳组合:", best[0], "30期净 %+d元, 有奖率 %.1f%%" % (best[1]["net"], best[1]["win_rate"] * 100))
# 最长连不中
streak = max_s = 0
for p, dt, nums, hits, prize in best[1]["rows"]:
    if prize > 0:
        streak = 0
    else:
        streak += 1
        max_s = max(max_s, streak)
print("30期内最长连不中期数: %d期" % max_s)

# 2倍倍投资金需求表
print("\n2倍倍投资金需求(第n期投入=6*2^(n-1), 累计=6*(2^n-1)):")
print("期数 | 本期投入 | 累计投入 | 本期中奖(中2) | 中奖后净")
cum = 0
for n in range(1, 16):
    invest = 6 * (2 ** (n - 1))
    cum += invest
    prize2 = 19 * (2 ** (n - 1))
    print("%2d期 | %8d | %10d | %10d | %+8d" % (n, invest, cum, prize2, prize2 - cum))
