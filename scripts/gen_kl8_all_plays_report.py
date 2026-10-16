# -*- coding: utf-8 -*-
"""生成: 快乐8全部玩法 指定月份 逐期中奖明细报告
用法: python gen_kl8_all_plays_report.py 2026-07
"""
import json, os, sys

BASE = r"C:\Users\14506\WorkBuddy\Claw"
MONTH = sys.argv[1] if len(sys.argv) > 1 else "2026-08"
OUT = os.path.join(BASE, "outputs", f"kl8_all_plays_{MONTH[:4]}_{MONTH[5:]}_report.html")

MONTH_CN = {"2026-07": "7月", "2026-08": "8月"}.get(MONTH, MONTH)

X3_BY_MONTH = {
    "2026-07": [20, 33, 44],
    "2026-08": [4, 32, 50],
}
x3 = X3_BY_MONTH.get(MONTH, [4, 32, 50])

with open(os.path.join(BASE, "data", "kl8_500.json"), encoding="utf-8") as f:
    kl8 = json.load(f)
with open(os.path.join(BASE, "data", "kl8_orange_purple_hits.json"), encoding="utf-8") as f:
    op = json.load(f)
with open(os.path.join(BASE, "data", "all_recommendations_archive.json"), encoding="utf-8") as f:
    arch = json.load(f)
with open(os.path.join(BASE, "data", "sh15x5_data.json"), encoding="utf-8") as f:
    sh15 = json.load(f)

days = sorted([d for d in kl8 if d["d"].startswith(MONTH)], key=lambda x: x["d"])
print(f"{MONTH} 开奖: {len(days)}期")

# ============ 1. 固定复式守号4组 ============
fixed_plays = {
    "选五9码复式(252元/天)": {"nums": [5,11,12,18,19,62,63,77,78], "need": 5},
    "选八9码复式(18元/天)":  {"nums": [5,11,12,18,19,62,63,77,78], "need": 8},
    "选九10码复式(20元/天)": {"nums": [8,9,15,16,65,66,72,73,79,80], "need": 9},
    "选十11码复式(22元/天)": {"nums": [1,2,5,6,12,18,19,27,40,41,53], "need": 10},
}

fixed_rows = {}
for name, cfg in fixed_plays.items():
    rows = []
    for d in days:
        draw = set(d["n"])
        hs = [n for n in cfg["nums"] if n in draw]
        rows.append((d, len(hs), hs))
    fixed_rows[name] = rows

# ============ 2. 选三每月追号 ============
x3_rows = []
for d in days:
    draw = set(d["n"])
    hs = [n for n in x3 if n in draw]
    h = len(hs)
    prize = 53 if h == 3 else 3 if h == 2 else 0
    x3_rows.append((d, h, hs, prize))

# ============ 3. 橙紫卡4玩法 ============
op_days = sorted([r for r in op if r["date"].startswith(MONTH)], key=lambda x: x["date"])
op_cards = {
    "orange_x2": "橙卡选二(1-40区)",
    "purple_x2": "紫卡选二(41-80区)",
    "orange_x3": "橙卡选三(1-40区)",
    "purple_x3": "紫卡选三(41-80区)",
}

# ============ 4. 基础/增强20码 ============
arch_days = sorted([r for r in arch["kl8"] if r["date"].startswith(MONTH)], key=lambda x: x["date"])

# ============ 5. 1-15区间选五3胆7拖 ============
dan15 = [1, 7, 11]
tuo15 = [2, 4, 5, 6, 8, 12, 13]
sh15_days = sorted([r for r in sh15 if r["d"].startswith(MONTH)], key=lambda x: x["d"])
sh15_rows = []
for d in sh15_days:
    draw = set(d["n"])
    dan_hit = [n for n in dan15 if n in draw]
    tuo_hit = [n for n in tuo15 if n in draw]
    sh15_rows.append((d, dan_hit, tuo_hit))

# ============ 生成HTML ============
def tr_fixed(name, rows):
    cfg = fixed_plays[name]
    need = cfg["need"]
    body = ""
    for d, h, hs in rows:
        if name.startswith("选五"):
            pr = 1000 if h>=5 else 21 if h==4 else 3 if h==3 else 0
        elif name.startswith("选八"):
            pr = 50000 if h>=8 else 800 if h==7 else 88 if h==6 else 0
        elif name.startswith("选九"):
            pr = 300000 if h>=9 else 800 if h==7 else 88 if h==6 else 0
        else:
            pr = 5000000 if h>=10 else 8000 if h==9 else 800 if h==8 else 80 if h==7 else 0
        cls = "win" if pr > 0 else ("hit" if h >= 3 else "")
        body += '<tr><td>{}</td><td>{}</td><td class="{}">{}/{}</td><td>{}</td><td>{}</td></tr>'.format(
            d["d"][5:], d["p"], cls, h, need,
            ",".join("{:02d}".format(x) for x in hs) if hs else "—",
            pr if pr > 0 else 0)
    return body

def tr_x3(rows):
    body = ""
    tp = 0
    for d, h, hs, prize in rows:
        tp += prize
        cls = "win" if prize > 0 else ("hit" if h >= 2 else "")
        lvl = "★中3" if h >= 3 else ("中2" if h >= 2 else "-")
        body += '<tr><td>{}</td><td>{}</td><td class="{}">{}</td><td>{}</td><td>{}</td></tr>'.format(
            d["d"][5:], d["p"], cls, lvl,
            ",".join("{:02d}".format(x) for x in hs) if hs else "—", prize)
    return body, tp

def tr_op(rows, key):
    body = ""
    tp = 0
    for r in rows:
        item = r[key]
        hit = item["hit"]; prize = item["prize"]
        tp += prize
        cls = "win" if prize > 0 else ("hit" if len(hit) > 0 else "")
        body += '<tr><td>{}</td><td>{}</td><td>{}</td><td class="{}">{}</td><td>{}</td></tr>'.format(
            r["date"][5:], r["period"],
            ",".join("{:02d}".format(x) for x in item["rec"]),
            cls,
            ",".join("{:02d}".format(x) for x in hit) if hit else "—",
            prize)
    return body, tp

def tr_arch(rows):
    body = ""
    for r in rows:
        b = r["basic"]; e = r["enhanced"]
        bh = b["hit_count"]; eh = e["hit_count"]
        bc = "win" if bh >= 7 else ("hit" if bh >= 5 else "")
        ec = "win" if eh >= 7 else ("hit" if eh >= 5 else "")
        body += '<tr><td>{}</td><td>{}</td><td class="{}">{}</td><td>{}</td><td class="{}">{}</td><td>{}</td></tr>'.format(
            r["date"][5:], r["period"], bc, bh,
            ",".join("{:02d}".format(x) for x in b["hit"]) if b["hit"] else "—",
            ec, eh,
            ",".join("{:02d}".format(x) for x in e["hit"]) if e["hit"] else "—")
    return body

def tr_sh15(rows):
    body = ""
    for d, dan_hit, tuo_hit in rows:
        total = len(dan_hit) + len(tuo_hit)
        cls = "win" if total >= 5 else ("hit" if total >= 3 else "")
        body += '<tr><td>{}</td><td>{}</td><td>{}</td><td class="hit">{}</td><td>{}</td><td class="{}">{}/10</td></tr>'.format(
            d["d"][5:], d["p"],
            ",".join("{:02d}".format(x) for x in d["n"]),
            ",".join("{:02d}".format(x) for x in dan_hit) if dan_hit else "—",
            ",".join("{:02d}".format(x) for x in tuo_hit) if tuo_hit else "—",
            cls, total)
    return body

# 固定复式 汇总
fixed_summary = ""
fixed_stats = {}
for name in fixed_plays:
    rows = fixed_rows[name]
    body = tr_fixed(name, rows)
    cfg = fixed_plays[name]
    best = max(rows, key=lambda x: x[1])
    hit3 = sum(1 for _, h, _ in rows if h >= 3)
    fixed_stats[name] = (best[1], cfg["need"], hit3)
    fixed_summary += f'''
    <div class="section">
      <h2>{name}</h2>
      <div class="note">母码: {", ".join(f"{n:02d}" for n in cfg["nums"])} · {MONTH_CN} {len(rows)}期 · 最佳命中 {best[1]}/{cfg["need"]} ({best[0]["d"]}) · 中3+共{hit3}期</div>
      <table><thead><tr><th>日期</th><th>期号</th><th>命中</th><th>命中号码</th><th>奖金(元)</th></tr></thead><tbody>{body}</tbody></table>
    </div>'''

# 选三
x3_body, x3_total = tr_x3(x3_rows)
x3_win2 = sum(1 for _, h, _, _ in x3_rows if h == 2)
x3_win3 = sum(1 for _, h, _, _ in x3_rows if h == 3)
x3_summary = f'''
    <div class="section">
      <h2>选三·每月追号计划（{MONTH_CN}号码 {" ".join(f"{n:02d}" for n in x3)}）</h2>
      <div class="note">{MONTH_CN} {len(x3_rows)}期 · 中3={x3_win3}次 中2={x3_win2}次 · 累计奖金 ¥{x3_total}（投入 ¥{len(x3_rows)*2}，净 {x3_total-len(x3_rows)*2:+d}）</div>
      <table><thead><tr><th>日期</th><th>期号</th><th>结果</th><th>命中号码</th><th>奖金(元)</th></tr></thead><tbody>{x3_body}</tbody></table>
    </div>'''

# 橙紫卡
op_summary = ""
op_stats = {}
for key, label in op_cards.items():
    body, tp = tr_op(op_days, key)
    wins = sum(1 for r in op_days if r[key]["prize"] > 0)
    op_stats[label] = (wins, tp)
    op_summary += f'''
    <div class="section">
      <h2>{label}</h2>
      <div class="note">{MONTH_CN} {len(op_days)}期 · 中奖{wins}期 · 累计奖金 ¥{tp}</div>
      <table><thead><tr><th>日期</th><th>期号</th><th>推荐号码</th><th>命中</th><th>奖金(元)</th></tr></thead><tbody>{body}</tbody></table>
    </div>'''

# 基础/增强20码
arch_body = tr_arch(arch_days)
b_avg = sum(r["basic"]["hit_count"] for r in arch_days) / len(arch_days) if arch_days else 0
e_avg = sum(r["enhanced"]["hit_count"] for r in arch_days) / len(arch_days) if arch_days else 0
arch_summary = f'''
    <div class="section">
      <h2>基础/增强 20码大复式（EMA评分推荐）</h2>
      <div class="note">{MONTH_CN} {len(arch_days)}期 · 基础月均命中 {b_avg:.1f}个/期 · 增强月均 {e_avg:.1f}个/期（理论均值5）</div>
      <table><thead><tr><th>日期</th><th>期号</th><th>基础命中</th><th>基础命中号</th><th>增强命中</th><th>增强命中号</th></tr></thead><tbody>{arch_body}</tbody></table>
    </div>'''

# 1-15区间选五3胆7拖
sh15_body = tr_sh15(sh15_rows)
sh15_total = sum(1 for _, dh, th in sh15_rows if len(dh) + len(th) >= 5)
sh15_summary = f'''
    <div class="section">
      <h2>1-15区间·选五3胆7拖（固定胆拖对照：胆01/07/11 拖02/04/05/06/08/12/13）</h2>
      <div class="note">快乐8 1-15区间真实开奖 · {MONTH_CN} {len(sh15_rows)}期 · 胆拖合计命中5+共{sh15_total}期（10码选五理论中5）</div>
      <table><thead><tr><th>日期</th><th>期号</th><th>区间开奖号</th><th>胆命中</th><th>拖命中</th><th>合计</th></tr></thead><tbody>{sh15_body}</tbody></table>
    </div>'''

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>快乐8全部玩法 {MONTH_CN}中奖明细</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#fce4ec 0%,#fff8e1 100%); padding:24px; color:#1a1a1a; }}
.container {{ max-width:1150px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#880e4f 0%,#ad1457 100%); color:#fff; padding:26px 32px; border-radius:16px; margin-bottom:22px; box-shadow:0 8px 24px rgba(136,14,79,.22); }}
.header h1 {{ font-size:22px; margin-bottom:10px; }}
.header .sub {{ font-size:14px; opacity:.92; line-height:1.7; }}
.header .badge {{ display:inline-block; background:rgba(255,255,255,.2); padding:4px 12px; border-radius:20px; font-size:12px; margin:8px 8px 0 0; }}
.section {{ background:#fff; border-radius:12px; padding:20px 24px; margin-bottom:18px; box-shadow:0 4px 12px rgba(0,0,0,.06); }}
.section h2 {{ font-size:16px; color:#880e4f; margin-bottom:8px; border-left:4px solid #ad1457; padding-left:10px; }}
.note {{ font-size:12px; color:#888; margin-bottom:10px; }}
table {{ width:100%; border-collapse:collapse; font-size:12px; }}
th,td {{ padding:5px 7px; text-align:center; border-bottom:1px solid #eee; }}
th {{ background:#fce4ec; color:#880e4f; font-weight:600; }}
tr:hover {{ background:#f5f5f5; }}
td.hit {{ color:#e65100; font-weight:700; background:#fff8e1; }}
td.win {{ color:#2e7d32; font-weight:700; background:#e8f5e9; }}
.foot {{ background:#fff3e0; border-left:4px solid #ff9800; padding:14px 18px; border-radius:6px; font-size:13px; color:#5d4037; margin-top:18px; line-height:1.9; }}
@media (max-width:800px){{ table {{ font-size:10px; }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>🎯 快乐8 全部玩法 · 2026年{MONTH_CN}中奖明细</h1>
  <div class="sub">{MONTH_CN}真实开奖核对（{len(days)}期）· 覆盖：固定复式守号4组 / 选三每月追号 / 橙紫卡4玩法 / 20码大复式 / 1-15区间3胆7拖</div>
  <div><span class="badge">数据源: kl8_500.json + 橙紫卡存档 + 推荐存档</span><span class="badge">纯回测展示</span></div>
</div>

{fixed_summary}
{x3_summary}
{op_summary}
{arch_summary}
{sh15_summary}

<div class="foot">
  <b>阅读说明：</b>① 固定复式按母码与真实开奖逐期核对，奖金按官方中奖等级计算。② 选三每月追号为{MONTH_CN}号码逐期核对。③ 橙紫卡4玩法来自每日存档（data/kl8_orange_purple_hits.json）。④ 20码大复式来自推荐存档（data/all_recommendations_archive.json）。⑤ 1-15区间3胆7拖为固定胆拖对照1-15区间真实开奖。⑥ 历史数据不代表未来。
</div>

</div>
</body>
</html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK ->", OUT)

# 汇总
print(f"\n===== {MONTH_CN} 汇总 =====")
for name in fixed_plays:
    rows = fixed_rows[name]
    best = max(rows, key=lambda x: x[1])
    hit3 = sum(1 for _, h, _ in rows if h >= 3)
    print(f"{name}: 最佳命中{best[1]}/{fixed_plays[name]['need']} 中3+ {hit3}期")
print(f"选三({MONTH_CN}号 {' '.join(f'{n:02d}' for n in x3)}): 中3={x3_win3} 中2={x3_win2} 奖金¥{x3_total} (投入¥{len(x3_rows)*2} 净{x3_total-len(x3_rows)*2:+d})")
for label, (wins, tp) in op_stats.items():
    print(f"{label}: 中奖{wins}期 奖金¥{tp}")
print(f"20码大复式: 基础月均{b_avg:.1f} 增强月均{e_avg:.1f}")
print(f"1-15区间3胆7拖: 命中5+共{sh15_total}期")
