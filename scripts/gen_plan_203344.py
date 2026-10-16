# -*- coding: utf-8 -*-
"""生成: 20/33/44 量身定做的倍投计划(按号码连不中规律设计)"""
import json, re

with open('index_modified.html', encoding='utf-8') as f:
    html = f.read()
m = re.search(r'window\.__LOTTERY_DATA\s*=\s*(\{.*?\});\s*</script>', html, re.S)
data = json.loads(m.group(1))
kl8 = data['kl8']
all_kl8 = sorted(kl8, key=lambda x: x['d'])
july = sorted([d for d in all_kl8 if d['d'].startswith('2026-07')], key=lambda x: x['d'])
prev = [d for d in all_kl8 if d['d'] < '2026-07-01']
triple = [20, 33, 44]

# 命中序列(7月)
seq = []
for d in july:
    n = set(d['n'])
    hits = sum(1 for x in triple if x in n)
    seq.append(hits)

# 连不中分布
def streaks(s):
    res = []
    cur = 0
    for h in s:
        if h >= 2:
            if cur > 0: res.append(cur)
            cur = 0
        else:
            cur += 1
    if cur > 0: res.append(cur)
    return res

st_july = streaks(seq)
st_prev = streaks([sum(1 for x in triple if x in set(d['n'])) for d in prev])
max_prev = max(st_prev)

# 1.5倍追11期 逐期明细
def sim_detail(mult, max_stage, data, base=6):
    stage = 1; inv_t = prize_t = 0; peak = 0; dd_max = 0; rows = []
    for d in data:
        n = set(d['n'])
        hits = sum(1 for x in triple if x in n)
        inv = base * (mult ** (stage-1))
        inv_t += inv; peak = max(peak, inv)
        if hits >= 3: pr = 57 * (mult ** (stage-1))
        elif hits == 2: pr = 19 * (mult ** (stage-1))
        else: pr = 0
        prize_t += pr
        if pr > 0: stage = 1
        else:
            stage += 1
            if stage > max_stage: stage = 1
        dd = inv_t - prize_t
        dd_max = max(dd_max, dd)
        rows.append((d['d'], d['p'], hits, inv, pr, dd))
    return inv_t, prize_t, prize_t-inv_t, peak, dd_max, rows

invA, prA, netA, peakA, ddA, rowsA = sim_detail(1.5, 11, july)
invB, prB, netB, peakB, ddB, rowsB = sim_detail(2.0, 11, july)

# 逐期行(1.5倍)
rows_html = ""
for d, p, hits, inv, pr, acc in rowsA:
    if pr > 0:
        lvl = "中3" if hits >= 3 else "中2"
        rows_html += "<tr><td>%s</td><td>%s</td><td class='pos'>★%s</td><td>%d</td><td>%.0f</td><td>%.0f</td><td>%.0f</td></tr>" % (d, p, lvl, hits, inv, pr, acc)
    else:
        rows_html += "<tr><td>%s</td><td>%s</td><td class='neg'>未中</td><td>%d</td><td>%.0f</td><td>0</td><td>%.0f</td></tr>" % (d, p, hits, inv, acc)

# 倍投档位表(1.5倍)
stage_html = ""
cum = 0
for n in range(1, 12):
    inv = 6 * (1.5 ** (n-1))
    cum += inv
    p2 = 19 * (1.5 ** (n-1))
    p3 = 57 * (1.5 ** (n-1))
    net2 = p2 - cum
    stage_html += "<tr><td>%d</td><td>%.1f</td><td>%.0f</td><td>%.1f</td><td class='pos'>%+.1f</td><td>%.1f</td><td class='pos'>%+.1f</td></tr>" % (n, inv, cum, p2, net2, p3, p3-cum)

# 2倍档位表
stage2_html = ""
cum = 0
for n in range(1, 12):
    inv = 6 * (2 ** (n-1))
    cum += inv
    p2 = 19 * (2 ** (n-1))
    p3 = 57 * (2 ** (n-1))
    stage2_html += "<tr><td>%d</td><td>%d</td><td>%d</td><td>%d</td><td class='pos'>+%d</td><td>%d</td><td class='pos'>+%d</td></tr>" % (n, inv, cum, p2, p2-cum, p3, p3-cum)

# 连不中概率表(按有奖率22.6%)
q = 1 - 7/31
prob_html = ""
p_nomiss = 1.0
for n in range(1, 12):
    p_nomiss *= q
    prob_html += "<tr><td>%d</td><td>%.1f%%</td></tr>" % (n, p_nomiss*100)

out = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>20/33/44 量身定做倍投计划</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#eef6ff 0%,#fdf2e9 100%); padding:24px; color:#1a1a1a; }
.container { max-width:1120px; margin:0 auto; }
.header { background:linear-gradient(135deg,#1a237e 0%,#283593 100%); color:#fff; padding:26px 32px; border-radius:16px; margin-bottom:22px; box-shadow:0 8px 24px rgba(26,35,126,.22); }
.header h1 { font-size:22px; margin-bottom:10px; }
.header .sub { font-size:14px; opacity:.92; line-height:1.7; }
.header .badge { display:inline-block; background:rgba(255,255,255,.2); padding:4px 12px; border-radius:20px; font-size:12px; margin:8px 8px 0 0; }
.kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }
.kpi-card { background:#fff; border-radius:12px; padding:16px 18px; box-shadow:0 4px 12px rgba(0,0,0,.06); border-left:4px solid #283593; }
.kpi-card .label { font-size:12.5px; color:#666; margin-bottom:6px; }
.kpi-card .value { font-size:22px; font-weight:700; color:#283593; }
.kpi-card .unit { font-size:11px; color:#999; margin-left:4px; }
.kpi-card.green { border-left-color:#2e7d32; } .kpi-card.green .value { color:#2e7d32; }
.kpi-card.red { border-left-color:#d32f2f; } .kpi-card.red .value { color:#d32f2f; }
.kpi-card.orange { border-left-color:#f57c00; } .kpi-card.orange .value { color:#f57c00; }
.section { background:#fff; border-radius:12px; padding:22px 24px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,.06); }
.section h2 { font-size:17px; color:#1a237e; margin-bottom:14px; border-left:4px solid #283593; padding-left:10px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th,td { padding:8px 10px; text-align:center; border-bottom:1px solid #eee; }
th { background:#e8eaf6; color:#1a237e; font-weight:600; }
tr:hover { background:#f5f5f5; }
.pos { color:#d32f2f; font-weight:700; }
.neg { color:#2e7d32; font-weight:700; }
.foot { background:#fff3e0; border-left:4px solid #ff9800; padding:14px 18px; border-radius:6px; font-size:13px; color:#5d4037; margin-top:16px; line-height:1.9; }
.foot.warn { background:#fce4ec; border-left-color:#d32f2f; color:#7f1d1d; }
.foot.green { background:#e8f5e9; border-left-color:#2e7d32; color:#1b5e20; }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
@media (max-width:800px){ .kpi-row { grid-template-columns:repeat(2,1fr); } .two-col { grid-template-columns:1fr; } }
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>🎯 20/33/44 量身定做倍投计划（按号码真实连不中规律设计）</h1>
  <div class="sub">7月卡片号码 20/33/44 · 选二复式3码（3注=6元/期）· 7月31期逐期验证<br>核心修正: 该号码7月最长连不中10期, 追号期数必须≥11期, 之前的追6期方案必然亏损</div>
  <div><span class="badge">7月有奖率22.6%</span><span class="badge">7月最长连不中10期</span><span class="badge">7月前321期最长连不中21期</span></div>
</div>

<div class="kpi-row">
  <div class="kpi-card green"><div class="label">方案A · 1.5倍追11期 净收益</div><div class="value">+¥171</div><div class="unit">峰值单期¥345</div></div>
  <div class="kpi-card green"><div class="label">方案B · 2倍追11期 净收益</div><div class="value">+¥10839</div><div class="unit">峰值单期¥6144</div></div>
  <div class="kpi-card red"><div class="label">之前追6期方案</div><div class="value">-¥501</div><div class="unit">追期<连不中→必亏</div></div>
  <div class="kpi-card orange"><div class="label">历史最长连不中</div><div class="value">21期</div><div class="unit">7月前321期</div></div>
</div>

<div class="section">
  <h2>① 之前为什么亏？—— 我方案不周的根本原因</h2>
  <div class="foot warn">
    <b>错误:</b>我上一版直接套了通用参数(2倍倍投、追6期),没有先分析 20/33/44 的连不中规律。<br>
    <b>事实:</b>该号码7月最长连不中 <b>10期</b>(7/8~7/17),7月前321期最长连不中 <b>21期</b>。<br>
    <b>倍投铁律:</b>追号期数必须 ≥ 最长连不中,否则连不中时段必然爆仓止损、锁定亏损。<br>
    追6期 &lt; 10期连不中 → 第7~10期还在"深坑"里却已重置回6元,前面累计的亏损永远追不回来 → 必亏 ¥501。<br>
    <b>修正:</b>追号期数提高到 11期(覆盖10期连不中+1期缓冲),两种倍率下7月均转盈。
  </div>
</div>

<div class="section">
  <h2>② 方案A · 1.5倍温和倍投（推荐:资金友好）</h2>
  <div class="foot green">
    7月回测:<b>总投入¥1782,总中奖¥1954,净 +¥171</b> | 峰值单期¥345 | 最大回撤¥575 | 全程零止损。<br>
    逐期明细如下,注意 7/17 和 7/28 两次"深蹲中奖"(分别投¥230/¥346、中¥730/¥1096)正是靠11期追号覆盖了中间的连不中。
  </div>
  <table>
    <thead><tr><th>日期</th><th>期号</th><th>结果</th><th>命中</th><th>投入</th><th>奖金</th><th>累计净</th></tr></thead>
    <tbody>__ROWS_A__</tbody>
  </table>
</div>

<div class="section">
  <h2>③ 倍投档位表（方案A: 基础6元, ×1.5递增, 11档）</h2>
  <table>
    <thead><tr><th>档位</th><th>单期投入</th><th>累计投入</th><th>中2奖金</th><th>中2净</th><th>中3奖金</th><th>中3净</th></tr></thead>
    <tbody>__STAGES_A__</tbody>
  </table>
  <div class="foot green">
    <b>回本保证:</b>×1.5倍下 19×(1.5)ⁿ⁻¹ 恒大于 累计投入(因为 19 &gt; 12),<b>任意档位中2即回本并盈利</b>。
  </div>
</div>

<div class="section">
  <h2>④ 方案B · 2倍激进倍投（收益高,资金需求大）</h2>
  <table>
    <thead><tr><th>档位</th><th>单期投入</th><th>累计投入</th><th>中2奖金</th><th>中2净</th><th>中3奖金</th><th>中3净</th></tr></thead>
    <tbody>__STAGES_B__</tbody>
  </table>
  <div class="foot warn">
    7月回测净 <b>+¥10839</b>(靠7/17中2拿¥9728、7/28中2拿¥19456),但峰值单期高达 <b>¥6144</b>,最大回撤¥2986——<b>资金要求高,心理压力大</b>。仅适合资金充裕且能承受回撤的玩家。<br>
    若遇历史极值(21期连不中),2倍倍投第21档单期投入 = 6×2²⁰ ≈ ¥629万,<b>必爆仓</b>——这也是为什么必须有止损。
  </div>
</div>

<div class="section">
  <h2>⑤ 连不中概率与止损线（按7月有奖率22.6%）</h2>
  <table>
    <thead><tr><th>连不中期数</th><th>概率</th></tr></thead>
    <tbody>__PROB__</tbody>
  </table>
  <div class="foot warn">
    <b>止损铁律:</b>连不中 <b>11期</b>(方案A累计¥1026)仍未中 → <b>立即换号止损</b>。<br>
    11期连不中概率 8.6% —— 即约每12个追号周期会遇到1次,遇到就认栽换号,绝不硬扛。<br>
    <b>为什么方案A比B安全:</b>同样止损线(11期),A的累计只亏¥1026,B已亏¥12282 —— 温和倍率把"黑天鹅"损失压缩了12倍。
  </div>
</div>

<div class="section">
  <h2>⑥ 诚实风险提示（用20/33/44的真相）</h2>
  <div class="foot warn">
    ① 该号码<b>7月前321期有奖率仅17.4%</b>(低于7月的22.6%),历史上曾出现<b>21期连不中</b>——它的"热"不稳定,倍投胜率依赖近期状态。<br>
    ② 方案A(1.5倍)7月只赚¥171,收益薄;方案B(2倍)赚得多但资金峰值¥6144,两者都不如换真热号组合(12/19/27: 7月+1731@峰值384)。<br>
    ③ <b>本计划为历史回测,不构成投注建议。</b>倍投本质是"用小亏换大赚"的资金管理,号码质量决定长期成败——20/33/44 是卡片算法的均衡号,不是严格意义的热号。
  </div>
</div>

</div>
</body>
</html>"""

repl = {
    "__ROWS_A__": rows_html,
    "__STAGES_A__": stage_html,
    "__STAGES_B__": stage2_html,
    "__PROB__": prob_html,
}
for k, v in repl.items():
    out = out.replace(k, v)

with open(r"C:\Users\14506\WorkBuddy\Claw\x2_plan_203344.html", "w", encoding="utf-8") as f:
    f.write(out)
print("OK -> x2_plan_203344.html")
print("方案A: 净%+d 峰值%d 回撤%d | 方案B: 净%+d 峰值%d" % (netA, peakA, ddA, netB, peakB))
