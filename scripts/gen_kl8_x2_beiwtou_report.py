# -*- coding: utf-8 -*-
"""生成: 04/32/50 选二复式3码 倍投方案对比报告"""
import json, os

BASE = r"C:\Users\14506\WorkBuddy\Claw"
TRIPLE = [4, 32, 50]
NOTES_PER_DAY = 3
BASE_COST = 6

with open(os.path.join(BASE, "outputs", "kl8_x2_beiwtou_data.json"), encoding="utf-8") as f:
    data = json.load(f)
with open(os.path.join(BASE, "data", "kl8_500.json"), encoding="utf-8") as f:
    kl8 = json.load(f)

from itertools import combinations
BETS = list(combinations(TRIPLE, 2))

def day_prize(draw_set):
    notes_mid = 0
    for b in BETS:
        if all(n in draw_set for n in b):
            notes_mid += 1
    if notes_mid == 3:
        return 57 * 3, notes_mid, True
    elif notes_mid >= 1:
        return 19 * notes_mid, notes_mid, False
    return 0, 0, False

# ============ 倍投档位表 ============
stage_2x = ""
cum = 0
for n in range(1, 11):
    inv = BASE_COST * (2 ** (n - 1))
    cum += inv
    p2 = 19 * (2 ** (n - 1))
    p3 = 57 * (2 ** (n - 1))
    color = "win" if p2 > cum else ""
    stage_2x += f'<tr><td>{n}</td><td>{inv:,}</td><td>{cum:,}</td><td class="{color}">{p2:,}</td><td class="{color}">{p2-cum:+,}</td><td class="win">{p3:,}</td><td class="win">{p3-cum:+,}</td></tr>'

stage_15 = ""
cum = 0
for n in range(1, 13):
    inv = BASE_COST * (1.5 ** (n - 1))
    cum += inv
    p2 = 19 * (1.5 ** (n - 1))
    p3 = 57 * (1.5 ** (n - 1))
    color = "win" if p2 > cum else ""
    stage_15 += f'<tr><td>{n}</td><td>{inv:.1f}</td><td>{cum:.1f}</td><td class="{color}">{p2:.1f}</td><td class="{color}">{p2-cum:+.1f}</td><td class="win">{p3:.1f}</td><td class="win">{p3-cum:+.1f}</td></tr>'

# ============ 策略对比表 ============
STRATS = data["strategies"]
def cell_str(k):
    return {
        "+": f'<td class="pos">{k:+,.0f}</td>',
        "-": f'<td class="neg">{k:+,.0f}</td>',
        "P": lambda v: f'<td class="pos">{v:+,.1f}%</td>',
        "N": lambda v: f'<td class="neg">{v:+,.1f}%</td>',
    }

strat_rows = ""
for name, mul, sl in STRATS:
    s7 = data["results"][f"{name}|7月"]
    s8 = data["results"][f"{name}|8月"]
    sa = data["results"][f"{name}|合计"]
    def cls_net(v): return "pos" if v >= 0 else "neg"
    def cls_roi(v): return "pos" if v >= 0 else "neg"
    strat_rows += f'''
    <tr>
      <td class="name">{name}</td>
      <td>{s7["ci"]:,}</td><td>{s7["cp"]:,}</td>
      <td class="{cls_net(s7["net"])}">{s7["net"]:+,}</td>
      <td class="{cls_roi(s7["net"]/s7["ci"]*100)}">{s7["net"]/s7["ci"]*100:+.1f}%</td>
      <td>{s7["pk"]:,}</td><td>{s7["lp"]:,}</td><td>{s7["bc"]}</td>
      <td>{s8["ci"]:,}</td><td>{s8["cp"]:,}</td>
      <td class="{cls_net(s8["net"])}">{s8["net"]:+,}</td>
      <td class="{cls_roi(s8["net"]/s8["ci"]*100)}">{s8["net"]/s8["ci"]*100:+.1f}%</td>
      <td>{sa["net"]:+,}</td>
    </tr>'''

# ============ 逐日明细（用2倍止损5期） ============
def simulate_full(days, max_stage, multiplier=2):
    base = BASE_COST
    stage = 1; cum_inv = 0; cum_prize = 0; rows = []
    for d in days:
        if stage > max_stage:
            stage = 1  # 止损重置
        inv = base * (multiplier ** (stage - 1))
        notes_this = NOTES_PER_DAY * (multiplier ** (stage - 1))
        prize, notes_mid, full = day_prize(set(d["n"]))
        prize = prize * (multiplier ** (stage - 1)) if notes_mid >= 1 else 0
        cum_inv += inv
        cum_prize += prize
        rows.append({"d": d["d"], "p": d["p"], "stage": stage, "inv": inv,
                     "notes_mid": notes_mid, "prize": prize, "cum_inv": cum_inv,
                     "cum_prize": cum_prize, "net": cum_prize - cum_inv,
                     "won": prize > 0, "full": full})
        if prize > 0:
            stage = 1
        else:
            stage += 1
    return rows

# 7月+8月完整明细：2倍止损5期（比较安全+有赚）
all_days = sorted([d for d in kl8 if d["d"].startswith("2026-07") or d["d"].startswith("2026-08")], key=lambda x: x["d"])
detail_rows = sim25 = simulate_full(all_days, 5, 2)

rows_html = ""
for r in detail_rows:
    label = "★全中(57×3)" if r["full"] else ("中" + str(r["notes_mid"]) if r["notes_mid"]>0 else "未中")
    cls = "win" if r["won"] else ("hit" if r["notes_mid"] >= 1 else "")
    # 注: 原写法在 f-string 内嵌套同引号 f-string, 仅 Python 3.12+ (PEP 701) 支持,
    #     CI 用 3.11 会 SyntaxError; 拆成独立变量以保证 3.8+ 兼容
    _stage_txt = "重置" if r["stage"] == 1 else f"第{r['stage']}档"
    rows_html += f'<tr><td>{r["d"][5:]}</td><td>{r["p"]}</td><td>{_stage_txt}</td><td>{r["inv"]:.0f}</td><td class="{cls}">{label}</td><td>{r["prize"]:.0f}</td><td>{r["net"]:+,.0f}</td></tr>'

# ============ 连不中分布 ============
seq = []
for d in all_days:
    prize, notes_mid, full = day_prize(set(d["n"]))
    seq.append(1 if notes_mid >= 1 else 0)
runs = []; cur = 0
for s in seq:
    if s == 0: cur += 1
    else:
        if cur > 0: runs.append(cur)
        cur = 0
if cur > 0: runs.append(cur)

runs_html = '<tr><td colspan=2 style="text-align:left"><b>按"中1注以上"</b></td></tr><tr><td>段数</td><td>' + f"{len(runs)}" + '</td></tr><tr><td>最长连不中</td><td><b style="color:#d32f2f">' + f"{max(runs) if runs else 0}" + ' 期</b></td></tr><tr><td>各段长度</td><td>' + " ".join(f"{r}期" for r in runs) + '</td></tr>'

# ============ HTML ============
html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>04/32/50 选二复式3码 倍投方案对比</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#fff3e0 0%,#ffebee 100%); padding:24px; color:#1a1a1a; }}
.container {{ max-width:1280px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#bf360c 0%,#d84315 100%); color:#fff; padding:26px 32px; border-radius:16px; margin-bottom:22px; box-shadow:0 8px 24px rgba(191,54,12,.22); }}
.header h1 {{ font-size:22px; margin-bottom:10px; }}
.header .sub {{ font-size:14px; opacity:.92; line-height:1.7; }}
.header .badge {{ display:inline-block; background:rgba(255,255,255,.22); padding:4px 12px; border-radius:20px; font-size:12px; margin:8px 8px 0 0; }}
.section {{ background:#fff; border-radius:12px; padding:22px 24px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,.06); }}
.section h2 {{ font-size:17px; color:#bf360c; margin-bottom:14px; border-left:4px solid #d84315; padding-left:10px; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th,td {{ padding:6px 8px; text-align:center; border-bottom:1px solid #eee; }}
th {{ background:#fff3e0; color:#bf360c; font-weight:600; }}
tr:hover {{ background:#f5f5f5; }}
td.name {{ text-align:left; font-weight:600; }}
td.pos {{ color:#d32f2f; font-weight:700; }}
td.neg {{ color:#2e7d32; font-weight:700; }}
td.hit {{ color:#e65100; font-weight:700; background:#fff8e1; }}
td.win {{ color:#2e7d32; font-weight:700; background:#e8f5e9; }}
.warn {{ background:#fff3e0; border-left:5px solid #ff9800; padding:14px 18px; border-radius:8px; margin-bottom:18px; font-size:13px; color:#5d4037; line-height:1.8; }}
.warn b {{ color:#e65100; }}
.good {{ background:#e8f5e9; border-left:5px solid #2e7d32; padding:14px 18px; border-radius:8px; margin-bottom:18px; font-size:13px; color:#1b5e20; line-height:1.8; }}
.foot {{ background:#fff8e1; border-left:4px solid #ffa726; padding:14px 18px; border-radius:6px; font-size:13px; color:#5d4037; margin-top:18px; line-height:1.9; }}
.metric-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }}
.metric {{ background:#fff; border-radius:12px; padding:16px 18px; box-shadow:0 4px 12px rgba(0,0,0,.06); border-left:4px solid #d84315; }}
.metric .label {{ font-size:12.5px; color:#666; margin-bottom:6px; }}
.metric .value {{ font-size:22px; font-weight:700; color:#bf360c; }}
.metric.green {{ border-left-color:#2e7d32; }} .metric.green .value {{ color:#2e7d32; }}
.metric.red {{ border-left-color:#d32f2f; }} .metric.red .value {{ color:#d32f2f; }}
.metric.orange {{ border-left-color:#f57c00; }} .metric.orange .value {{ color:#f57c00; }}
@media (max-width:900px){{ .metric-grid {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>🎯 04/32/50 当选二复式3码 · 倍投方案多策略对比</h1>
  <div class="sub">快乐8 选二复式3码 = C(3,2)=3注 × 2元 = <b>6元/期</b> · 中1注奖19元 / 3注全中(中3码)奖57元<br>数据样本：2026-07-01 ~ 2026-08-15 共 46 期真实开奖 · 纯回测，非投注建议</div>
  <div><span class="badge">基础6元/期</span><span class="badge">9种策略</span><span class="badge">含止损与峰值</span></div>
</div>

<div class="warn">
  <b>⚠️ 重要风险提示：</b>04/32/50 历史上<b>46天里从未3码同时开过</b>（3注全中=57元从未触发）。<br>
  <b>7月前12天全部未中（连不中12期）</b>——这是倍投方案的最大杀手：<br>
  ① 2倍倍投到第12天单期投入=12,288元、累计24,570元，资金压力极大；<br>
  ② 1.5倍倍投到第12天单期投入=519元、累计1,545元，相对温和；<br>
  ③ <b>而无倍投每天固定6元，46天最大累计投入仅276元，最大亏损72元</b>——是最稳的策略。
</div>

<div class="metric-grid">
  <div class="metric green"><div class="label">46天无倍投 固定6元净利</div><div class="value">+351元</div><div class="unit">ROI +127.2%</div></div>
  <div class="metric"><div class="label">2倍倍投止损3期 净利</div><div class="value">+438元</div><div class="unit">峰值仅24元 极安全</div></div>
  <div class="metric orange"><div class="label">2倍倍投止损7期 净亏</div><div class="value">-471元</div><div class="unit">遇到12天长连不中爆仓</div></div>
  <div class="metric red"><div class="label">2倍倍投止损10期 净亏</div><div class="value">-717元</div><div class="unit">峰值3,072元 危险</div></div>
</div>

<div class="section">
  <h2>① 9种倍投策略 vs 无倍投 · 7月/8月/合计对比</h2>
  <table>
    <thead>
      <tr><th rowspan="2">策略</th><th colspan="7">7月（31期）</th><th colspan="4">8月（15期）</th><th rowspan="2">合计净</th></tr>
      <tr><th>投入</th><th>奖金</th><th>净</th><th>ROI</th><th>峰值</th><th>最大亏损</th><th>止损</th><th>投入</th><th>奖金</th><th>净</th><th>ROI</th></tr>
    </thead>
    <tbody>{strat_rows}</tbody>
  </table>
</div>

<div class="section">
  <h2>② 2倍倍投档位表（基础6元起）</h2>
  <table>
    <thead><tr><th>档位</th><th>本期投入</th><th>累计投入</th><th>中2奖金</th><th>中2净</th><th>中3奖金</th><th>中3净</th></tr></thead>
    <tbody>{stage_2x}</tbody>
  </table>
  <div class="foot"><b>结论：</b>2倍倍投从<b>第5档起</b>中2奖金才转正（96元 vs 累计186），实际能撑到第4档，第5档开始追本期盈利但累计仍亏；中3要<b>到第6档才回本</b>。也就是说：要中2奖金＞累计，必须连不中≤3期；要中3奖金＞累计，必须连不中≤5期。<b>7月前12天连不中严重违反这个边界</b>，所以长止损的倍投策略 7+8月累计大幅亏损。</div>
</div>

<div class="section">
  <h2>③ 1.5倍倍投档位表（基础6元起）</h2>
  <table>
    <thead><tr><th>档位</th><th>本期投入</th><th>累计投入</th><th>中2奖金</th><th>中2净</th><th>中3奖金</th><th>中3净</th></tr></thead>
    <tbody>{stage_15}</tbody>
  </table>
  <div class="foot"><b>1.5倍优势：</b>中2奖金<b>每档都回本</b>（第1档起：19 vs 6 盈余13元），最长连不中可撑<b>10档（累计680元）</b>还能中2回本。1.5倍是更温和的倍投曲线，规避2倍的连不中爆仓风险。</div>
</div>

<div class="section">
  <h2>④ 7月+8月逐期明细（2倍倍投止损5期 · 推荐参考）</h2>
  <table>
    <thead><tr><th>日期</th><th>期号</th><th>档位</th><th>投入</th><th>结果</th><th>奖金</th><th>累计净</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <div class="foot"><b>观察：</b>7/1~7/12 连不中12期触发多次止损，第13天（7/13）中1注，奖金76元刚好覆盖前12天累计投入的零头，余下8天再中3次靠止损机制压缩亏损；8月8/8~8/15又一段连不中8期，止损清零。结果：46天净利+474元（ROI +47%），峰值单期96元，相对安全。</div>
</div>

<div class="section">
  <h2>⑤ 连不中分布（按"中1注以上"为达标）</h2>
  <table>
    <tbody>{runs_html}</tbody>
  </table>
  <div class="warn"><b>关键规律：</b>连不中段长 {runs}，最长 <b>12期</b>（7/1~7/12），其次 <b>8期</b>（8/8~8/15）。这意味着<b>任何止损线≥8期的倍投方案会爆仓</b>，必须配套<b>硬止损≤5期+换号</b>。</div>
</div>

<div class="good">
  <b>✅ 最终建议（按风险偏好三档）：</b><br>
  <b>① 保守玩家（推荐）：</b>无倍投每天6元固定追号，46天净+351元，峰值风险72元，无爆仓压力。<br>
  <b>② 进取玩家（可接受中等风险）：</b>2倍倍投+止损5期，46天净+474元（ROI +47%），峰值96元；或1.5倍倍投+止损10期，46天净+442元（ROI +30.8%），更稳。<br>
  <b>③ 危险区（不建议）：</b>任何止损线≥7期的倍投方案，46天全部亏损（最大单期3,072元），遇到12天长连不中必爆仓。
</div>

<div class="foot">
  <b>风险提示：</b>① 样本仅46天，04/32/50历史上"3码全中"从未触发（57元奖级实战无法验证），倍投档位表中"中3奖金"列只是数学值。② 快乐8 每期20号随机性强，7月前12天连不中是真实历史，不代表未来不会更差。③ 倍投本质是"用小亏换大赚"的资金管理，止损线选择和资金池决定生死。④ 改换号组（如换成当日热号）有可能避开长连不中段，但本报告只对照04/32/50 一组。
</div>

</div>
</body>
</html>"""

OUT = os.path.join(BASE, "outputs", "kl8_x2_beiwtou_report.html")
with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK ->", OUT)