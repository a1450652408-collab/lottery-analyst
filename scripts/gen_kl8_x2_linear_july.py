# -*- coding: utf-8 -*-
"""生成: 7月 20/33/44 选二复式3码 线性加注(+6元/档) 详细报告"""
import json, os
from itertools import combinations

BASE = r"C:\Users\14506\WorkBuddy\Claw"
OUT = os.path.join(BASE, "outputs", "kl8_x2_linear_july_report.html")

with open(os.path.join(BASE, "data", "kl8_500.json"), encoding="utf-8") as f:
    kl8 = json.load(f)

TRIPLE = [20, 33, 44]
BETS = list(combinations(TRIPLE, 2))
jul = sorted([d for d in kl8 if d["d"].startswith("2026-07")], key=lambda x: x["d"])

# ============ 模拟 ============
stage = 1
cum_inv = 0; cum_prize = 0
rows = []
max_stage = 1
win_days = []
for d in jul:
    draw = set(d["n"])
    hit_nums = [n for n in TRIPLE if n in draw]
    notes = sum(1 for b in BETS if all(n in draw for n in b))
    inv = 6 * stage
    prize = 19 * notes * stage
    cum_inv += inv; cum_prize += prize
    max_stage = max(max_stage, stage)
    if prize > 0: win_days.append((d["d"], stage, inv, prize, notes))
    rows.append({"d": d["d"], "p": d["p"], "hit": hit_nums, "stage": stage,
                 "inv": inv, "cum_inv": cum_inv, "notes": notes,
                 "prize": prize, "net": cum_prize - cum_inv})
    stage = 1 if prize > 0 else stage + 1

# ============ 档位表 ============
stage_html = ""
for n in range(1, 16):
    inv = 6 * n
    cum = 3 * n * (n + 1)
    p1 = 19 * n
    p3 = 57 * n
    ok = "✓" if p1 > cum else "✗"
    cls = "win" if ok == "✓" else "neg"
    stage_html += f'<tr><td>{n}</td><td>{inv}</td><td>{cum:,}</td><td class="win">{p1}</td><td class="{cls}">{p1-cum:+,}</td><td>{p3}</td><td>{p3-cum:+,}</td><td>{ok}</td></tr>'

# ============ 逐期明细 ============
rows_html = ""
for r in rows:
    cls = "win" if r["prize"] > 0 else ("hit" if r["notes"] > 0 else "")
    tag = f"★中{r['notes']}注" if r["notes"] > 0 else "未中"
    rows_html += f'<tr><td>{r["d"][5:]}</td><td>{r["p"]}</td><td>{" ".join(f"{n:02d}" for n in r["hit"]) if r["hit"] else "—"}</td><td>{r["stage"]}</td><td>{r["inv"]}</td><td>{r["cum_inv"]:,}</td><td class="{cls}">{tag}</td><td>{r["prize"]}</td><td class="{"pos" if r["net"]>=0 else "neg"}">{r["net"]:+,}</td></tr>'

# ============ 统计 ============
win7 = [w for w in win_days if w[3] > 0]
net = cum_prize - cum_inv
# 连不中段（以中1注以上为达标）
seq = [1 if r["prize"] > 0 else 0 for r in rows]
runs = []; cur = 0
for s in seq:
    if s == 0: cur += 1
    else:
        if cur > 0: runs.append(cur)
        cur = 0
if cur > 0: runs.append(cur)
max_run = max(runs) if runs else 0

# ============ HTML ============
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>7月 20/33/44 选二复式3码 线性加注明细</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#e8f5e9 0%,#fff8e1 100%); padding:24px; color:#1a1a1a; }}
.container {{ max-width:1200px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#1b5e20 0%,#2e7d32 100%); color:#fff; padding:26px 32px; border-radius:16px; margin-bottom:22px; box-shadow:0 8px 24px rgba(27,94,32,.22); }}
.header h1 {{ font-size:22px; margin-bottom:10px; }}
.header .sub {{ font-size:14px; opacity:.92; line-height:1.7; }}
.header .badge {{ display:inline-block; background:rgba(255,255,255,.2); padding:4px 12px; border-radius:20px; font-size:12px; margin:8px 8px 0 0; }}
.section {{ background:#fff; border-radius:12px; padding:22px 24px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,.06); }}
.section h2 {{ font-size:17px; color:#1b5e20; margin-bottom:14px; border-left:4px solid #2e7d32; padding-left:10px; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th,td {{ padding:6px 8px; text-align:center; border-bottom:1px solid #eee; }}
th {{ background:#e8f5e9; color:#1b5e20; font-weight:600; }}
tr:hover {{ background:#f5f5f5; }}
td.pos {{ color:#d32f2f; font-weight:700; }}
td.neg {{ color:#2e7d32; font-weight:700; }}
td.hit {{ color:#e65100; font-weight:700; background:#fff8e1; }}
td.win {{ color:#2e7d32; font-weight:700; background:#e8f5e9; }}
.warn {{ background:#fff3e0; border-left:5px solid #ff9800; padding:14px 18px; border-radius:8px; margin-bottom:18px; font-size:13px; color:#5d4037; line-height:1.8; }}
.warn b {{ color:#e65100; }}
.good {{ background:#e8f5e9; border-left:5px solid #2e7d32; padding:14px 18px; border-radius:8px; margin-bottom:18px; font-size:13px; color:#1b5e20; line-height:1.8; }}
.foot {{ background:#fff8e1; border-left:4px solid #ffa726; padding:14px 18px; border-radius:6px; font-size:13px; color:#5d4037; margin-top:18px; line-height:1.9; }}
.metric-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }}
.metric {{ background:#fff; border-radius:12px; padding:16px 18px; box-shadow:0 4px 12px rgba(0,0,0,.06); border-left:4px solid #2e7d32; }}
.metric .label {{ font-size:12.5px; color:#666; margin-bottom:6px; }}
.metric .value {{ font-size:22px; font-weight:700; color:#1b5e20; }}
.metric.red {{ border-left-color:#d32f2f; }} .metric.red .value {{ color:#d32f2f; }}
.metric.orange {{ border-left-color:#f57c00; }} .metric.orange .value {{ color:#f57c00; }}
@media (max-width:900px){{ .metric-grid {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>🎯 7月 · 20/33/44 选二复式3码 · 线性加注（每档+6元）</h1>
  <div class="sub">选二复式3注=6元起 · 第n档投入=6n元 · 中1注奖金=19n元（随档位放大）· 中奖回第1档<br>数据：2026-07-01 ~ 2026-07-31 共31期真实开奖 · 纯回测，非投注建议</div>
  <div><span class="badge">3注: (20,33)(20,44)(33,44)</span><span class="badge">每档+6元</span><span class="badge">奖金×档位</span></div>
</div>

<div class="metric-grid">
  <div class="metric red"><div class="label">7月净盈亏</div><div class="value">{net:+,}元</div><div class="unit">投入{cum_inv:,} 奖金{cum_prize:,}</div></div>
  <div class="metric"><div class="label">ROI</div><div class="value">{net/cum_inv*100:+.1f}%</div><div class="unit">负收益</div></div>
  <div class="metric orange"><div class="label">最长连不中</div><div class="value">{max_run}期</div><div class="unit">段长: {runs}</div></div>
  <div class="metric"><div class="label">中奖次数</div><div class="value">{len(win7)}次</div><div class="unit">峰值档位{max_stage}档</div></div>
</div>

<div class="warn">
  <b>⚠️ 关键结论：线性+6元方案 7月亏损 {-net}元。</b><br>
  <b>回本边界：只有第1~5档中奖才回本</b>（第n档累计投入=3n(n+1)，中1注=19n，需 19n &gt; 3n(n+1) → n ≤ 5）。<br>
  但7月出现了<b>两次超长连不中</b>：7/8~7/17（第10档才中）和 7/18~7/28（第11档才中），两次深蹲都落在第6档之后的亏损区，是7月亏损的主因。<br>
  对比×2翻倍方案：翻倍时中奖=19×2ⁿ⁻¹ 恒大于累计投入（因为19&gt;12），<b>任意档位中1注即回本</b>；线性+6元则做不到，第6档起越追越亏。
</div>

<div class="section">
  <h2>① 档位回本验证表（第1~15档）</h2>
  <table>
    <thead><tr><th>档位</th><th>本期投入</th><th>累计投入</th><th>中1注奖金</th><th>中1注净</th><th>中3注奖金(3码全中)</th><th>中3注净</th><th>回本?</th></tr></thead>
    <tbody>{stage_html}</tbody>
  </table>
  <div class="foot"><b>规律：</b>线性方案下 19n vs 3n(n+1)，两条线在第6档交叉——<b>第1~5档中奖盈利，第6档起中奖也开始亏损</b>（中3注57n 可撑到第18档，但"3码全中"在7月从未发生）。这就是线性方案不如翻倍方案的根本原因。</div>
</div>

<div class="section">
  <h2>② 7月逐期明细（31期）</h2>
  <table>
    <thead><tr><th>日期</th><th>期号</th><th>三码命中</th><th>档位</th><th>投入</th><th>累计投入</th><th>结果</th><th>奖金</th><th>累计净</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>

<div class="section">
  <h2>③ 7月全部中奖记录</h2>
  <table>
    <thead><tr><th>日期</th><th>档位</th><th>投入</th><th>中注</th><th>奖金</th></tr></thead>
    <tbody>
      {"".join(f'<tr><td>{w[0]}</td><td>{w[1]}</td><td>{w[2]}</td><td>{w[3]}注</td><td class="win">{w[4]}</td></tr>' for w in win_days)}
    </tbody>
  </table>
</div>

<div class="good">
  <b>✅ 对比建议：</b>同样是"6元起不中加注"，<b>×2翻倍方案（7月+10,839元）远优于线性+6元方案（7月-{int(abs(net))}元）</b>。<br>
  原因：翻倍时中奖奖金指数放大、任意档回本；线性时奖金线性放大、第6档起必亏。<br>
  若资金有限担不起翻倍峰值（7月最深6,144元），可改用 <b>1.5倍加注</b>（6/9/13.5/20.25...），中1注也恒回本（19×1.5ⁿ⁻¹ &gt; 累计），且峰值温和得多。
</div>

<div class="foot">
  <b>风险提示：</b>① 用户原话号码"20,33,40"应为 <b>20/33/44</b>（7月卡片实际号码）。② 线性方案两段超长连不中（9期、10期）导致深亏，若未来再现≥11期连不中，第12档投入72元、累计936元、中1注仅228元——亏损会继续扩大。③ 3码全中(57n)7月未出现，该奖金列为理论值。④ 历史数据不代表未来，跟单需谨慎。
</div>

</div>
</body>
</html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK ->", OUT)
print(f"7月线性+6元: 投入{cum_inv} 奖金{cum_prize} 净{net:+,} ROI {net/cum_inv*100:+.1f}%")
print(f"最长连不中{max_run}期 段长{runs} 中奖{len(win_days)}次 峰值档{max_stage}")
