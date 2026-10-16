# -*- coding: utf-8 -*-
"""生成: 选二复式三码盈利分析报告 HTML"""
import json, itertools

with open(r"C:\Users\14506\WorkBuddy\Claw\data\sh15x5_data.json", encoding="utf-8") as f:
    raw = json.load(f)
july = sorted([d for d in raw if d["d"].startswith("2026-07")], key=lambda x: x["d"])
N = len(july)

def calc(triple, data):
    rows, tot = [], 0
    for d in data:
        hits = len(set(d["n"]) & set(triple))
        prize = 57 if hits == 3 else (19 if hits == 2 else 0)
        tot += prize
        rows.append((d["p"], d["d"], hits, prize))
    return rows, tot

# ---- 胆码组合 ----
dan_rows, dan_tot = calc([1, 7, 11], july)
dan_w2 = sum(1 for r in dan_rows if r[2] == 2)
dan_w3 = sum(1 for r in dan_rows if r[2] == 3)
dan_win = dan_w2 + dan_w3

# ---- 455组合 ----
results = []
for t in itertools.combinations(range(1, 16), 3):
    _, tot = calc(list(t), july)
    w = sum(1 for r in calc(list(t), july)[0] if r[2] >= 2)
    w2 = sum(1 for r in calc(list(t), july)[0] if r[2] == 2)
    w3 = sum(1 for r in calc(list(t), july)[0] if r[2] == 3)
    results.append((t, tot, w, w2, w3))
results.sort(key=lambda x: -x[1])
profit_n = sum(1 for x in results if x[1] > 6 * N)
avg_net = sum(x[1] - 6 * N for x in results) / len(results)

# ---- 追号 ----
def chase_table():
    rows, cum = "", 0
    for n in range(1, 11):
        inv = 6 * (2 ** (n - 1))
        cum += inv
        p2 = 19 * (2 ** (n - 1))
        p3 = 57 * (2 ** (n - 1))
        q = 0.31  # 胆码组合有奖率
        miss = (1 - q) ** n
        rows += "<tr><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td>+%d</td><td>+%d</td><td>%.1f%%</td></tr>" % (
            n, inv, cum, p2, p3, p2 - cum, p3 - cum, miss * 100)
    return rows

# 胆码组合最长连不中
max_streak, streak = 0, 0
for r in dan_rows:
    if r[3] > 0:
        streak = 0
    else:
        streak += 1
        max_streak = max(max_streak, streak)

# TOP15 明细行
top_rows = ""
for t, tot, w, w2, w3 in results[:15]:
    net = tot - 6 * N
    top_rows += "<tr><td>%02d / %02d / %02d</td><td>%.0f%%</td><td>%d</td><td>%d</td><td>¥%d</td><td>¥%d</td><td class='%s'>%+d</td></tr>" % (
        t[0], t[1], t[2], w / N * 100, w2, w3, 6 * N, tot, "pos" if net > 0 else "neg", net)

# 胆码逐期明细
dan_detail = ""
for p, dt, hits, prize in dan_rows:
    mark = "★" if prize else ""
    dan_detail += "<tr><td>%s</td><td>%s</td><td>%d/3</td><td>%s</td><td class='%s'>%s</td></tr>" % (
        p, dt, hits, "中2" if hits == 2 else ("中3" if hits == 3 else "未中"),
        "pos" if prize else "neg", ("¥%d %s" % (prize, mark)) if prize else "¥0")

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>选二复式三码盈利分析 — 快乐8卡片玩法(1-15区间)</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#eef6ff 0%,#fdf2e9 100%); padding:24px; color:#1a1a1a; }
.container { max-width:1080px; margin:0 auto; }
.header { background:linear-gradient(135deg,#1a237e 0%,#283593 100%); color:#fff; padding:26px 32px; border-radius:16px; margin-bottom:22px; box-shadow:0 8px 24px rgba(26,35,126,.22); }
.header h1 { font-size:23px; margin-bottom:10px; }
.header .sub { font-size:14px; opacity:.92; line-height:1.7; }
.header .badge { display:inline-block; background:rgba(255,255,255,.2); padding:4px 12px; border-radius:20px; font-size:12px; margin:8px 8px 0 0; }
.conclusion { background:linear-gradient(135deg,#e8f5e9,#f1f8e9); border-left:5px solid #2e7d32; padding:18px 22px; border-radius:10px; margin-bottom:22px; font-size:15px; line-height:1.9; }
.conclusion b { color:#2e7d32; }
.kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }
.kpi-card { background:#fff; border-radius:12px; padding:16px 18px; box-shadow:0 4px 12px rgba(0,0,0,.06); border-left:4px solid #283593; }
.kpi-card .label { font-size:12.5px; color:#666; margin-bottom:6px; }
.kpi-card .value { font-size:22px; font-weight:700; color:#283593; }
.kpi-card .unit { font-size:11px; color:#999; margin-left:4px; }
.kpi-card.green { border-left-color:#2e7d32; } .kpi-card.green .value { color:#2e7d32; }
.kpi-card.orange { border-left-color:#f57c00; } .kpi-card.orange .value { color:#f57c00; }
.kpi-card.red { border-left-color:#d32f2f; } .kpi-card.red .value { color:#d32f2f; }
.section { background:#fff; border-radius:12px; padding:22px 24px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,.06); }
.section h2 { font-size:17px; color:#1a237e; margin-bottom:14px; border-left:4px solid #283593; padding-left:10px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { padding:8px 10px; text-align:center; border-bottom:1px solid #eee; }
th { background:#e8eaf6; color:#1a237e; font-weight:600; }
tr:hover { background:#f5f5f5; }
.pos { color:#d32f2f; font-weight:700; }
.neg { color:#2e7d32; font-weight:700; }
.star { color:#f57c00; }
.foot { background:#fff3e0; border-left:4px solid #ff9800; padding:14px 18px; border-radius:6px; font-size:13px; color:#5d4037; margin-top:16px; line-height:1.9; }
.foot.warn { background:#fce4ec; border-left-color:#d32f2f; color:#7f1d1d; }
.foot.green { background:#e8f5e9; border-left-color:#2e7d32; color:#1b5e20; }
.vs-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:6px; }
.vs-box { border:2px solid #e0e0e0; border-radius:10px; padding:16px; }
.vs-box.bad { border-color:#ef9a9a; background:#fff5f5; }
.vs-box.good { border-color:#a5d6a7; background:#f1f8e9; }
.vs-box h3 { font-size:14.5px; margin-bottom:8px; }
.vs-box .row { display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px dashed #eee; font-size:13px; }
.vs-box .row:last-child { border-bottom:none; }
.vs-box .row b { color:#333; }
.big { font-size:19px; font-weight:800; }
@media (max-width:800px){ .kpi-row { grid-template-columns:repeat(2,1fr); } .vs-grid { grid-template-columns:1fr; } }
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>🎯 选二复式三码 · 盈利可行性分析</h1>
  <div class="sub">快乐8 卡片玩法（1-15 区间）· 把上月「选三追号卡片」换成「选二复式三码」<br>数据源：data/sh15x5_data.json · 7月真实回测 __N__ 期（2026174 ~ 2026202）</div>
  <div><span class="badge">3码 = 3注选二</span><span class="badge">每期成本 ¥6</span><span class="badge">中2个 → ¥19</span><span class="badge">中3个 → ¥57</span></div>
</div>

<div class="conclusion">
  <b>一句话结论：能盈利，而且比选五/选三更容易——但前提是「号码选得对」+「用卡片玩法框架（1-15区间）而非标准80码」。</b><br>
  上月胆码 01/07/11 当选二复式3码，7月实际回测 <b>净赚 ¥35</b>（有奖率31%）；若换成当月最优组合 01/07/10，净赚 <b>¥206</b>。7月455组组合中146组盈利、平均净亏¥16.6——说明<span style="color:#d32f2f;font-weight:700">选号决定生死</span>，选热号就赚，选冷号就亏。
</div>

<div class="kpi-row">
  <div class="kpi-card green"><div class="label">胆码 01/07/11 净收益</div><div class="value">+¥35</div><div class="unit">/ 29期</div></div>
  <div class="kpi-card"><div class="label">最优组合 01/07/10</div><div class="value">+¥206</div><div class="unit">/ 29期</div></div>
  <div class="kpi-card orange"><div class="label">理论返奖率(1-15框架)</div><div class="value">105.6%</div><div class="unit">期望 +¥0.33/期</div></div>
  <div class="kpi-card red"><div class="label">标准80码返奖率</div><div class="value">59.4%</div><div class="unit">期望 -¥2.44/期</div></div>
</div>

<div class="section">
  <h2>① 为什么「卡片玩法」框架下能盈利？—— 两种玩法的期望对比</h2>
  <div class="vs-grid">
    <div class="vs-box bad">
      <h3>❌ 标准快乐8选二复式3码（80码开20个）</h3>
      <div class="row"><span>单码命中率</span><b>20/80 = 25%</b></div>
      <div class="row"><span>中2个概率</span><b>14.06%</b></div>
      <div class="row"><span>中3个概率</span><b>1.56%</b></div>
      <div class="row"><span>有奖率</span><b>15.6%</b></div>
      <div class="row"><span>每期期望</span><b class="neg">-¥2.44</b></div>
      <div class="row"><span>长期</span><b class="neg">必亏，返奖率59.4%</b></div>
    </div>
    <div class="vs-box good">
      <h3>✅ 卡片玩法选二复式3码（1-15区间开5个）</h3>
      <div class="row"><span>单码命中率</span><b>5/15 = 33.3%</b></div>
      <div class="row"><span>中2个概率</span><b>22.2%</b></div>
      <div class="row"><span>中3个概率</span><b>3.7%</b></div>
      <div class="row"><span>有奖率</span><b>25.9%</b></div>
      <div class="row"><span>每期期望</span><b class="pos">+¥0.33</b></div>
      <div class="row"><span>长期</span><b class="pos">正期望，返奖率105.6%</b></div>
    </div>
  </div>
  <div class="foot green">
    <strong>关键：</strong>卡片玩法把开奖范围从「80选20」缩到「15选5」，单码命中率从 25% 提到 33.3%，而选二奖金（中2=¥19）不变——所以期望由负转正。这是你上个月选五亏¥741、而选二复式3码能赚的根本原因：<b>玩法框架红利</b>。
  </div>
</div>

<div class="section">
  <h2>② 上月胆码 01/07/11 当选二复式3码 · 逐期明细（7月 __N__ 期）</h2>
  <table>
    <thead><tr><th>期号</th><th>日期</th><th>3码命中</th><th>奖级</th><th>奖金</th></tr></thead>
    <tbody>__DAN_DETAIL__</tbody>
  </table>
  <div class="foot">
    汇总：29期投入 ¥174 → 中奖 ¥209（中2共__DAN_W2__期 ¥19×8，中3共__DAN_W3__期 ¥57×1）→ <b>净 +¥35</b>，有奖率 __DAN_WR__%。<br>
    7月最长连不中 __MAXS__ 期（7/13~7/23之间有过连续8期未中2个，7/24后连续爆发）。
  </div>
</div>

<div class="section">
  <h2>③ 7月全组合收益排行 TOP15（455组穷举）</h2>
  <table>
    <thead><tr><th>三码组合</th><th>有奖率</th><th>中2次数</th><th>中3次数</th><th>总投入</th><th>总中奖</th><th>净收益</th></tr></thead>
    <tbody>__TOP_ROWS__</tbody>
  </table>
  <div class="foot">
    455组中 <b>146组盈利（32.1%）</b>，平均净亏 ¥16.6/29期。共同特征：<b>TOP组合全部含 10 号</b>（7月最热，17次）——选二复式3码盈利的核心 = <b>3码里至少1个近期热号</b>。上月的10号是拖码，如果把它提进3码组合，收益直接翻几倍。
  </div>
</div>

<div class="section">
  <h2>④ 追号（倍投）方案 —— 中一次必回本的数学保证</h2>
  <table>
    <thead><tr><th>期数</th><th>本期投入</th><th>累计投入</th><th>中2奖金</th><th>中3奖金</th><th>中2净赚</th><th>中3净赚</th><th>连续N期不中概率(按31%)</th></tr></thead>
    <tbody>__CHASE_ROWS__</tbody>
  </table>
  <div class="foot green">
    <strong>核心规律：</strong>倍投下「中2奖金 19×2ⁿ⁻¹」恒大于「累计投入 6×(2ⁿ-1)」——因为 19 &gt; 12。也就是说 <b>只要任意一期中2个及以上，本单立即回本并盈利</b>，不需要像选三那样等中3个大奖。<br>
    <strong>建议方案：</strong>2倍倍投、最多追 6~8 期（资金上限 ¥378~1530），6期不中概率仅10.8%、8期仅5.2%；若连不中超过上限 → <b>止损重来</b>，不要硬扛。
  </div>
</div>

<div class="section">
  <h2>⑤ 盈利操作手册（三选一）</h2>
  <table>
    <thead><tr><th>方案</th><th>做法</th><th>每期成本</th><th>特点</th></tr></thead>
    <tbody>
      <tr><td><b>A. 守号</b></td><td>固定3码（如 01/07/10），每期6元不追号</td><td>¥6</td><td>正期望+¥0.33/期，靠长期积累，月均约+¥10</td></tr>
      <tr><td><b>B. 追号</b></td><td>3码+2倍倍投，中即重置，追6期止损</td><td>峰值¥378</td><td>回本快，1次中奖覆盖全部投入，适合胆码组合</td></tr>
      <tr><td><b>C. 热号轮换</b></td><td>每10~20期按100期滚动窗口热号换3码</td><td>¥6</td><td>跟随热号迁移，最大化有奖率，需每天盯数据</td></tr>
    </tbody>
  </table>
  <div class="foot warn">
    <strong>⚠️ 风险提示：</strong>① 29期样本偏小，7月是最热月，8月热号会轮换，勿刻舟求剑；② 若打官方80码票（非卡片框架），期望是负的，任何追号都无法改变长期亏损；③ 设好止损线，倍投是双刃剑。本分析为历史回测，不构成投注建议。
  </div>
</div>

</div>
</body>
</html>"""

repl = {
    "__N__": str(N),
    "__DAN_DETAIL__": dan_detail,
    "__DAN_W2__": str(dan_w2),
    "__DAN_W3__": str(dan_w3),
    "__DAN_WR__": "%.0f%%" % (dan_win / N * 100),
    "__MAXS__": str(max_streak),
    "__TOP_ROWS__": top_rows,
    "__CHASE_ROWS__": chase_table(),
}
for k, v in repl.items():
    html = html.replace(k, v)

with open(r"C:\Users\14506\WorkBuddy\Claw\x2_rev3_profit_report.html", "w", encoding="utf-8") as f:
    f.write(html)
print("OK -> x2_rev3_profit_report.html")
print("胆码净收益 +%d, 有奖率 %.0f%%, 最长连不中 %d期" % (dan_tot - 6*N, dan_win/N*100, max_streak))
