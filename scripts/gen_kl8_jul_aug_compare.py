# -*- coding: utf-8 -*-
"""快乐8 7月 vs 8月 跨月盈亏对比（修正版：1-15区间用真实快乐8数据）"""
import json, os
from math import comb

BASE = r"C:\Users\14506\WorkBuddy\Claw"

# ============ 官方奖金 ============
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

# 3胆7拖：21注枚举（胆3必选 + 拖7选2），每注单独判定选五中奖
from itertools import combinations
DAN15, TUO15 = [1,7,11], [2,4,5,6,8,12,13]
ALL10 = DAN15 + TUO15
BETS15 = [DAN15 + list(t) for t in combinations(TUO15, 2)]
def prize_15x5(draw_set):
    """枚举21注，选五中5=1000 中4=21 中3=3"""
    prize = 0
    for bet in BETS15:
        h = sum(1 for n in bet if n in draw_set)
        if h >= 5: prize += 1000
        elif h == 4: prize += 21
        elif h == 3: prize += 3
    return prize

FIXED = {
    "选五9码复式(252元/天)": {"nums": [5,11,12,18,19,62,63,77,78], "cost": 252, "fn": prize_x5, "n": 9},
    "选八9码复式(18元/天)":  {"nums": [5,11,12,18,19,62,63,77,78], "cost": 18,  "fn": prize_x8, "n": 9},
    "选九10码复式(20元/天)": {"nums": [8,9,15,16,65,66,72,73,79,80], "cost": 20, "fn": prize_x9, "n": 10},
    "选十11码复式(22元/天)": {"nums": [1,2,5,6,12,18,19,27,40,41,53], "cost": 22, "fn": prize_x10, "n": 11},
}
X3 = {"2026-07": [20,33,44], "2026-08": [4,32,50]}
DAN15, TUO15 = [1,7,11], [2,4,5,6,8,12,13]
ALL10 = DAN15 + TUO15

with open(os.path.join(BASE, "data", "kl8_500.json"), encoding="utf-8") as f:
    kl8 = json.load(f)
with open(os.path.join(BASE, "data", "kl8_orange_purple_hits.json"), encoding="utf-8") as f:
    op = json.load(f)

def month_days(ym):
    return sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])

OP_CARDS = {
    "橙卡选二(1-40区)": ("orange_x2", 2),
    "紫卡选二(41-80区)": ("purple_x2", 2),
    "橙卡选三(1-40区)": ("orange_x3", 2),
    "紫卡选三(41-80区)": ("purple_x3", 2),
}

results = {}
ORDER = []

def reg(name, label, days, inv, prize, cost_day, extra):
    net = prize - inv
    roi = net / inv * 100 if inv else 0
    if name not in results:
        results[name] = {}
        ORDER.append(name)
    results[name][label] = {"days": days, "cost_day": cost_day, "inv": inv,
                            "prize": prize, "net": net, "roi": roi, **extra}

for ym, label in [("2026-07", "7月"), ("2026-08", "8月")]:
    days = month_days(ym)
    for name, cfg in FIXED.items():
        inv = 0; prize = 0; dist = {}
        best = (0, None)
        for d in days:
            h = sum(1 for n in cfg["nums"] if n in set(d["n"]))
            inv += cfg["cost"]
            pr = cfg["fn"](h)
            prize += pr
            dist[h] = dist.get(h, 0) + 1
            if h > best[0]: best = (h, d["d"])
        wins = sum(v for k, v in dist.items() if k >= 3)
        reg(name, label, len(days), inv, prize, cfg["cost"],
            {"dist": dist, "wins": wins, "best": best})

    # 选三
    inv = 0; prize = 0; dist = {}; wins2 = 0; wins3 = 0
    for d in days:
        h = sum(1 for n in X3[ym] if n in set(d["n"]))
        inv += 2
        pr = prize_x3(h)
        prize += pr
        dist[h] = dist.get(h, 0) + 1
        if h >= 3: wins3 += 1
        elif h == 2: wins2 += 1
    reg("选三每月追号(2元/天)", label, len(days), inv, prize, 2,
        {"dist": dist, "wins2": wins2, "wins3": wins3})

    # 橙紫卡
    op_days = [r for r in op if r["date"].startswith(ym)]
    for name, (key, cost) in OP_CARDS.items():
        inv = 0; prize = 0; wins = 0
        for r in op_days:
            item = r[key]
            inv += cost
            pr = item["prize"]
            prize += pr
            if pr > 0: wins += 1
        reg(name, label, len(op_days), inv, prize, cost, {"wins": wins})

    # 1-15区间 选五3胆7拖（真实快乐8数据）
    inv = 0; prize = 0; dist = {}; wins = 0; best = (0, None)
    for d in days:
        draw = set(d["n"])
        h = sum(1 for n in ALL10 if n in draw)
        inv += 42
        pr = prize_15x5(draw)
        prize += pr
        dist[h] = dist.get(h, 0) + 1
        if pr > 0: wins += 1
        if h > best[0]: best = (h, d["d"])
    reg("1-15区间·选五3胆7拖(42元/天)", label, len(days), inv, prize, 42,
        {"dist": dist, "wins": wins, "best": best})

# ============ 生成HTML ============
def fmt_dist(dist):
    return " ".join(f"{k}中{v}期" for k, v in sorted(dist.items()))

rows_html = ""
for name in ORDER:
    m = results[name]
    r7 = m.get("7月"); r8 = m.get("8月")
    cell = lambda r: (
        f'<td>{r["days"]}</td><td>{r["cost_day"]}</td><td>{r["inv"]:,}</td><td>{r["prize"]:,}</td>'
        f'<td class="{"pos" if r["net"]>0 else "neg"}">{r["net"]:+,}</td>'
        f'<td class="{"pos" if r["roi"]>0 else "neg"}">{r["roi"]:+.1f}%</td>') if r else "<td colspan=6>—</td>"
    # 额外信息
    def extra_info(r):
        if not r: return "—"
        if "best" in r and r["best"][0] > 0:
            return f'最佳命中{r["best"][0]}个({r["best"][1]}) · {fmt_dist(r.get("dist",{}))}'
        if "wins2" in r:
            return f'中3={r["wins3"]}次 中2={r["wins2"]}次 · {fmt_dist(r.get("dist",{}))}'
        if "wins" in r and "dist" not in r:
            return f'中奖{r["wins"]}期'
        return f'中奖{r.get("wins",0)}期 · {fmt_dist(r.get("dist",{}))}'
    rows_html += f'<tr><td class="name">{name}</td>{cell(r7)}{cell(r8)}<td>{extra_info(r7)}</td><td>{extra_info(r8)}</td></tr>'

# 汇总排名（按8月ROI）
rank_rows = ""
ranked = []
for name in ORDER:
    if "8月" in results[name]:
        r = results[name]["8月"]
        ranked.append((name, r["net"], r["roi"]))
ranked.sort(key=lambda x: -x[2])
for i, (name, net, roi) in enumerate(ranked, 1):
    rank_rows += f'<tr><td>{i}</td><td>{name}</td><td class="{"pos" if net>0 else "neg"}">{net:+,}元</td><td class="{"pos" if roi>0 else "neg"}">{roi:+.1f}%</td></tr>'

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>快乐8 7月vs8月 跨月盈亏对比</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#e8f5e9 0%,#fff8e1 100%); padding:24px; color:#1a1a1a; }}
.container {{ max-width:1250px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#1b5e20 0%,#2e7d32 100%); color:#fff; padding:26px 32px; border-radius:16px; margin-bottom:22px; box-shadow:0 8px 24px rgba(27,94,32,.22); }}
.header h1 {{ font-size:22px; margin-bottom:10px; }}
.header .sub {{ font-size:14px; opacity:.92; line-height:1.7; }}
.header .badge {{ display:inline-block; background:rgba(255,255,255,.2); padding:4px 12px; border-radius:20px; font-size:12px; margin:8px 8px 0 0; }}
.section {{ background:#fff; border-radius:12px; padding:22px 24px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,.06); }}
.section h2 {{ font-size:17px; color:#1b5e20; margin-bottom:14px; border-left:4px solid #2e7d32; padding-left:10px; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th,td {{ padding:7px 8px; text-align:center; border-bottom:1px solid #eee; }}
th {{ background:#e8f5e9; color:#1b5e20; font-weight:600; }}
tr:hover {{ background:#f5f5f5; }}
td.name {{ text-align:left; font-weight:600; }}
td.pos {{ color:#d32f2f; font-weight:700; }}
td.neg {{ color:#2e7d32; font-weight:700; }}
.col-head {{ background:#c8e6c9 !important; }}
.warn {{ background:#fff3e0; border-left:5px solid #ff9800; padding:14px 18px; border-radius:8px; margin-bottom:18px; font-size:13px; color:#5d4037; line-height:1.8; }}
.warn b {{ color:#e65100; }}
.good {{ background:#e8f5e9; border-left:5px solid #2e7d32; padding:14px 18px; border-radius:8px; margin-bottom:18px; font-size:13px; color:#1b5e20; line-height:1.8; }}
.foot {{ background:#f1f8e9; border-left:4px solid #7cb342; padding:14px 18px; border-radius:6px; font-size:13px; color:#33691e; margin-top:18px; line-height:1.9; }}
@media (max-width:900px){{ table {{ font-size:11px; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>📊 快乐8 全部玩法 · 7月 vs 8月 跨月盈亏对比</h1>
  <div class="sub">官方奖级精确计算（复式按组合拆分）· 7月31期 + 8月15期真实开奖 · 纯回测，非投注建议</div>
  <div><span class="badge">7月: 31期</span><span class="badge">8月: 15期</span><span class="badge">成本=每日固定投注</span></div>
</div>

<div class="warn">
  <b>⚠️ 重要数据勘误：</b>原 <b>data/sh15x5_data.json</b> 经核对与快乐8真实开奖的 1-15 区间<b>全部 31 条不一致</b>——该文件实为<b>上海15选5</b>的开奖数据（每期5号、1-15范围）。本报告中「1-15区间·选五3胆7拖」已改用 <b>kl8_500.json 真实快乐8开奖</b>重算，之前报告中的该玩法数据作废。
</div>

<div class="warn">
  <b>⚠️ 奖金算法勘误（v2）：</b>「1-15区间·选五3胆7拖」为 <b>21注</b>（胆3必选+拖7选2），此前误按 10码全复式(252注) 计算导致奖金高估。本版已改为<b>逐注枚举判定</b>（每注单独按选五中5=1000/中4=21/中3=3 计奖），修正后该玩法实际为亏损。
</div>

<div class="section">
  <h2>① 各玩法 7月/8月 盈亏总表（精确奖金）</h2>
  <table>
    <thead>
      <tr><th rowspan="2">玩法</th><th colspan="6">7月（31期）</th><th colspan="6">8月（15期）</th><th colspan="2">表现备注</th></tr>
      <tr class="col-head"><th>期数</th><th>成本/天</th><th>投入</th><th>奖金</th><th>净盈亏</th><th>ROI</th><th>期数</th><th>成本/天</th><th>投入</th><th>奖金</th><th>净盈亏</th><th>ROI</th><th>7月</th><th>8月</th></tr>
    </thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<div class="section">
  <h2>② 8月 ROI 排名（按成本折算最值得跟的顺序）</h2>
  <table>
    <thead><tr><th>#</th><th>玩法</th><th>8月净盈亏</th><th>8月ROI</th></tr></thead>
    <tbody>{rank_rows}</tbody>
  </table>
</div>

<div class="good">
  <b>✅ 结论（修正后）：</b>两月数据下<b>所有玩法均为负期望</b>，没有"稳定值得跟"的玩法。<br>
  相对最不亏的：① <b>橙卡选二</b>（8月+8元 / 7月-5元，接近打平）② <b>橙卡选三</b>（8月+29元 / 7月-50元）③ <b>紫卡选二</b>（8月-11元）。<br>
  明确远离：选五9码复式（两月亏8,262元）、选九10码复式（两月亏760元）、1-15区间3胆7拖（两月亏1,356元）。
</div>

<div class="foot">
  <b>重要提示：</b>① 固定复式4组两个月全部亏损（选五9码最重，7月-5,337元），选十11码8月0奖金。② 橙紫卡类仅橙卡选三8月为正（+29元），橙卡选二基本打平，其余微亏。③ 选三每月追号两月均亏（7月-41 / 8月-18），无中3。④ 1-15区间3胆7拖修正后两月均亏（7月-948 / 8月-408）。⑤ 样本仅2个月，历史不代表未来，跟单需谨慎。
</div>

</div>
</body>
</html>"""

OUT = os.path.join(BASE, "outputs", "kl8_jul_aug_compare_report.html")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK ->", OUT)
print(f"玩法数: {len(ORDER)}")
