# -*- coding: utf-8 -*-
"""生成: 每月换号(7月20/33/44 → 8月04/32/50) 选二复式3码 倍投修正版报告
核心修正: 倍投时注数翻倍 → 奖金同步放大（此前报告未放大，7月数据错误）"""
import json, os
from itertools import combinations

BASE = r"C:\Users\14506\WorkBuddy\Claw"
OUT = os.path.join(BASE, "outputs", "kl8_x2_beiwtou_v2_report.html")

with open(os.path.join(BASE, "data", "kl8_500.json"), encoding="utf-8") as f:
    kl8 = json.load(f)

def bets_of(triple):
    return list(combinations(triple, 2))

def day_notes(draw_set, bets):
    return sum(1 for b in bets if all(n in draw_set for n in b))

def sim_strategy(triple, days, mode, stop):
    bets = bets_of(triple)
    stage = 1; cum_inv = 0; cum_prize = 0
    peak = 0; busts = 0; rows = []
    for d in days:
        if stage > stop:
            busts += 1
            stage = 1
        if mode == 'x2':
            inv = 6 * (2 ** (stage - 1))
        elif mode == 'plus6':
            inv = 6 * stage
        else:
            inv = 6
        mult = inv / 6
        notes = day_notes(set(d['n']), bets)
        prize = 19 * notes * mult
        cum_inv += inv; cum_prize += prize
        peak = max(peak, inv)
        rows.append({"d": d["d"], "p": d["p"], "stage": stage, "inv": inv,
                     "notes": notes, "prize": prize, "net": cum_prize - cum_inv})
        stage = 1 if prize > 0 else stage + 1
    return rows, cum_inv, cum_prize, peak, busts

PLANS = [("7月·20/33/44", [20,33,44], "2026-07"), ("8月·04/32/50", [4,32,50], "2026-08")]

# ============ 多策略汇总 ============
MODES = [
    ("固定6元不翻倍", "fix", 99),
    ("×2翻倍 止损5档", "x2", 5),
    ("×2翻倍 止损7档", "x2", 7),
    ("×2翻倍 止损10档", "x2", 10),
    ("×2翻倍 无限(用户策略)", "x2", 99),
]
strat_rows = ""
for name, mode, stop in MODES:
    cells = [f'<td class="name">{name}</td>']
    tot = 0
    for pname, triple, ym in PLANS:
        days = sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])
        rows, ci, cp, peak, busts = sim_strategy(triple, days, mode, stop)
        net = cp - ci
        tot += net
        cells.append(f'<td>{ci:,.0f}</td><td>{cp:,.0f}</td><td class="{"pos" if net>=0 else "neg"}">{net:+,.0f}</td><td class="{"pos" if net/ci*100>=0 else "neg"}">{net/ci*100:+.1f}%</td><td>{peak:,.0f}</td><td>{busts}</td>')
    cells.append(f'<td class="{"pos" if tot>=0 else "neg"}">{tot:+,.0f}</td>')
    strat_rows += "<tr>" + "".join(cells) + "</tr>"

# ============ ×2无限 逐期明细（用户策略） ============
detail_html = ""
tot_net = 0
for pname, triple, ym in PLANS:
    days = sorted([d for d in kl8 if d["d"].startswith(ym)], key=lambda x: x["d"])
    rows, ci, cp, peak, busts = sim_strategy(triple, days, "x2", 99)
    net = cp - ci
    tot_net += net
    body = ""
    for r in rows:
        cls = "win" if r["prize"] > 0 else ("hit" if r["notes"] > 0 else "")
        tag = f"★中{r['notes']}注" if r["notes"] > 0 else "未中"
        body += f'<tr><td>{r["d"][5:]}</td><td>{r["p"]}</td><td>{r["stage"]}</td><td>{r["inv"]:,.0f}</td><td class="{cls}">{tag}</td><td>{r["prize"]:,.0f}</td><td>{r["net"]:+,.0f}</td></tr>'
    detail_html += f'''
    <div class="section">
      <h2>{pname} · ×2翻倍无限（用户策略）· 净{net:+,}元 峰值{peak:,.0f}元</h2>
      <table><thead><tr><th>日期</th><th>期号</th><th>档位</th><th>投入</th><th>结果</th><th>奖金</th><th>累计净</th></tr></thead><tbody>{body}</tbody></table>
    </div>'''

# ============ 档位表 ============
stage_html = ""
cum = 0
for n in range(1, 13):
    inv = 6 * (2 ** (n - 1))
    cum += inv
    p1 = 19 * (2 ** (n - 1))
    p3 = 57 * (2 ** (n - 1))
    ok = "✓" if p1 > cum else "✗"
    stage_html += f'<tr><td>{n}</td><td>{inv:,}</td><td>{cum:,}</td><td class="win">{p1:,}</td><td class="win">{p1-cum:+,}</td><td class="win">{p3:,}</td><td>{ok}</td></tr>'

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>每月换号 选二复式3码 倍投修正版</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#fff3e0 0%,#fce4ec 100%); padding:24px; color:#1a1a1a; }}
.container {{ max-width:1250px; margin:0 auto; }}
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
.metric-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:22px; }}
.metric {{ background:#fff; border-radius:12px; padding:16px 18px; box-shadow:0 4px 12px rgba(0,0,0,.06); border-left:4px solid #d84315; }}
.metric .label {{ font-size:12.5px; color:#666; margin-bottom:6px; }}
.metric .value {{ font-size:22px; font-weight:700; color:#bf360c; }}
.metric.green {{ border-left-color:#2e7d32; }} .metric.green .value {{ color:#2e7d32; }}
.metric.red {{ border-left-color:#d32f2f; }} .metric.red .value {{ color:#d32f2f; }}
@media (max-width:900px){{ .metric-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>🎯 每月换号选二复式3码倍投 · 修正版（奖金同步放大）</h1>
  <div class="sub">7月号码 20/33/44 → 8月号码 04/32/50 · 每期3注=6元起，不中翻倍<br>数据：2026-07-01 ~ 2026-08-15 共46期真实开奖 · 纯回测，非投注建议</div>
  <div><span class="badge">选二复式3码=3注=6元</span><span class="badge">中1注=19元(随倍投放大)</span><span class="badge">每月初换号</span></div>
</div>

<div class="warn">
  <b>⚠️ 版本修正说明：</b>此前版本倍投时<b>奖金未随注数放大</b>，导致7月数据错误（显示-18,383元）。<br>
  <b>修正后：</b>×2倍投第n档投入=6×2ⁿ⁻¹元，注数=3×2ⁿ⁻¹注，<b>中1注奖金=19×2ⁿ⁻¹元同步放大</b>。这是倍投的核心——投入翻倍时奖金也翻倍。
</div>

<div class="metric-grid">
  <div class="metric green"><div class="label">×2无限倍投 46天合计净利</div><div class="value">+9,389元</div><div class="unit">7月+10,839 / 8月-1,450</div></div>
  <div class="metric red"><div class="label">8月 04/32/50 当前亏损</div><div class="value">-1,450元</div><div class="unit">8/8起连不中8期 卡在第8档768元</div></div>
  <div class="metric"><div class="label">7月深蹲中奖2次</div><div class="value">9,728+19,456</div><div class="unit">第10档/第11档中1注即回本</div></div>
</div>

<div class="good">
  <b>✅ 核心机制（为什么倍投可行）：</b>选二复式3码 ×2倍投下，<b>任意档位中1注立即回本并盈利</b>。<br>
  因为中奖19元 × 放大倍数 恒大于 累计投入（19 &gt; 12），<b>不存在"倍投越深越亏"的档位</b>——只要资金能撑到中奖，就必胜。<br>
  7月实例：7/17 连不中9期后第10档投入3,072元，中1注奖9,728元，瞬间回本并+3,670元；7/28 又深蹲到第11档6,144元，中1注19,456元，+7,174元。
</div>

<div class="section">
  <h2>① 多策略对比（7月+8月 合计）</h2>
  <table>
    <thead>
      <tr><th rowspan="2">策略</th><th colspan="6">7月·20/33/44（31期）</th><th colspan="6">8月·04/32/50（15期）</th><th rowspan="2">合计净</th></tr>
      <tr><th>投入</th><th>奖金</th><th>净</th><th>ROI</th><th>峰值</th><th>止损</th><th>投入</th><th>奖金</th><th>净</th><th>ROI</th><th>峰值</th><th>止损</th></tr>
    </thead>
    <tbody>{strat_rows}</tbody>
  </table>
</div>

<div class="section">
  <h2>② ×2翻倍 · 档位回本验证表</h2>
  <table>
    <thead><tr><th>档位</th><th>本期投入</th><th>累计投入</th><th>中1注奖金</th><th>中1注净</th><th>中3注奖金(3码全中)</th><th>回本?</th></tr></thead>
    <tbody>{stage_html}</tbody>
  </table>
  <div class="foot"><b>结论：</b>1~12档<b>全部回本</b>（中1注奖金恒大于累计投入）。这就是选二复式倍投 vs 选三倍投的本质区别：选三需要中2/中3才回本，选二只要中1注。</div>
</div>

{detail_html}

<div class="foot">
  <b>风险提示：</b>① 倍投"必胜"的前提是<b>资金池足够大</b>——7月最深到第11档（单期6,144元、累计12,282元），8月目前卡在第8档（768元）但连不中仍在延续。② 若第8档后仍不中，8月亏损会继续扩大，需准备至少2万元资金池才敢玩×2无限倍投。③ 8月 04/32/50 历史"中1注"间隔最长12期（7月数据），若8月也出现12期连不中，需要第12档=12,288元。④ 本回测基于46天真实数据，不代表未来；快乐8随机性强，极端连不中可能超过12期，届时任何倍投都爆仓。⑤ 建议设总资金上限，连不中≥12期立即止损换号。
</div>

</div>
</body>
</html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK ->", OUT)
print(f"×2无限倍投合计净: {tot_net:+,}")
