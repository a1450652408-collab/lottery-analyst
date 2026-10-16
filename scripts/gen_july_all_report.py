# -*- coding: utf-8 -*-
"""生成: 8彩种 7月(2026-07) 推荐号码逐期中奖明细报告 HTML"""
import json, os

BASE = r"C:\Users\14506\WorkBuddy\Claw"
OUT = os.path.join(BASE, "outputs", "july_all_lottery_report.html")

with open(os.path.join(BASE, "data", "all_recommendations_archive.json"), encoding="utf-8") as f:
    data = json.load(f)

MONTH = "2026-07"

def july_recs(k):
    return sorted([r for r in data[k] if r.get("date", "").startswith(MONTH)], key=lambda x: x["date"])

# ---------- 汇总统计 ----------
summary = {}  # k -> dict

for k in ["kl8", "fc3d", "pl3", "pl5", "ssq", "dlt", "qlc", "qxc"]:
    recs = july_recs(k)
    s = {"n": len(recs)}
    if k == "kl8":
        b = [r["basic"]["hit_count"] for r in recs]
        e = [r["enhanced"]["hit_count"] for r in recs]
        s["basic_avg"] = sum(b) / len(b)
        s["enh_avg"] = sum(e) / len(e)
        s["best_basic"] = max(b)
        s["zones"] = "20码"
    elif k in ("fc3d", "pl3", "pl5", "qxc"):
        for i in range(3):
            zk = f"z{i+1}"
            hc = [r["basic"][zk]["hit_count"] for r in recs]
            pr = [r["basic"][zk]["prize"] for r in recs]
            s[f"{zk}_hits"] = hc
            s[f"{zk}_prize"] = pr
            s[f"{zk}_avg"] = sum(hc) / len(hc)
            s[f"{zk}_win"] = sum(1 for x in pr if x > 0)
    elif k in ("ssq", "dlt", "qlc"):
        s["reds"] = [r["basic"]["reds"]["hit_count"] for r in recs]
        s["blues"] = [r["basic"]["blues"]["hit_count"] for r in recs]
        s["reds_avg"] = sum(s["reds"]) / len(s["reds"])
        s["blues_avg"] = sum(s["blues"]) / len(s["blues"])
    summary[k] = s

# ---------- 生成 HTML ----------
def fmt_hits(hits, prize):
    """命中数单元格: 奖金>0 高亮"""
    if prize > 0:
        return f'<td class="win">{hits}</td>'
    if hits > 0:
        return f'<td class="hit">{hits}</td>'
    return f"<td>{hits}</td>"

def daily_table(recs, kind):
    """日更彩种(kind: kl8/fc3d/pl3/pl5/qxc) 明细表"""
    rows = []
    if kind == "kl8":
        for r in recs:
            b = r["basic"]; e = r["enhanced"]
            bh = b["hit_count"]; eh = e["hit_count"]
            bc = "win" if bh >= 7 else ("hit" if bh >= 5 else "")
            ec = "win" if eh >= 7 else ("hit" if eh >= 5 else "")
            rows.append(f'<tr><td>{r["date"][5:]}</td><td>{r["period"]}</td>'
                        f'<td class="{bc}">{bh}</td><td>{",".join(str(x) for x in b["hit"])}</td>'
                        f'<td class="{ec}">{eh}</td><td>{",".join(str(x) for x in e["hit"])}</td></tr>')
        head = ("日期", "期号", "基础20码命中", "基础命中号", "增强20码命中", "增强命中号")
    elif kind in ("fc3d", "pl3", "pl5", "qxc"):
        for r in recs:
            cells = [f'<td>{r["date"][5:]}</td><td>{r["period"]}</td>']
            for i in range(3):
                zk = f"z{i+1}"
                hc = r["basic"][zk]["hit_count"]
                pr = r["basic"][zk]["prize"]
                cells.append(fmt_hits(hc, pr))
            rows.append("<tr>" + "".join(cells) + "</tr>")
        head = ("日期", "期号", "位1命中", "位2命中", "位3命中")
    return head, "".join(rows)

def weekly_table(recs, kind):
    """周更彩种(ssq/dlt/qlc) 明细表"""
    rows = []
    if kind in ("ssq", "dlt", "qlc"):
        for r in recs:
            rd = r["basic"]["reds"]; bl = r["basic"]["blues"]
            rc = "win" if rd["hit_count"] >= 4 else ("hit" if rd["hit_count"] >= 2 else "")
            bc = "win" if bl["hit_count"] > 0 else ("hit" if bl["hit_count"] > 0 else "")
            rows.append(f'<tr><td>{r["date"][5:]}</td><td>{r["period"]}</td>'
                        f'<td class="{rc}">{rd["hit_count"]}</td><td>{",".join(str(x) for x in rd["hit"])}</td>'
                        f'<td class="{bc}">{bl["hit_count"]}</td><td>{",".join(str(x) for x in bl["hit"])}</td></tr>')
        head = ("日期", "期号", "红球命中", "红球命中号", "蓝球命中", "蓝球命中号")
    return head, "".join(rows)

# 各彩种说明
notes = {
    "kl8": "快乐8 · 每日20码大复式（基础/增强两版）· 每期开20个号，理论均值5个",
    "fc3d": "福彩3D · 定位复式（百/十/个位各3码）· 命中数=该位置3码覆盖开奖号个数",
    "pl3": "排列三 · 定位复式（百/十/个位各3码）",
    "pl5": "排列五 · 定位复式（万/千/百位各3码）",
    "ssq": "双色球 · 6红+1蓝",
    "dlt": "大乐透 · 5前+2后",
    "qlc": "七乐彩 · 7红(无蓝)",
    "qxc": "七星彩 · 定位复式（7位取前3位方案）",
}
names = {"kl8": "快乐8", "fc3d": "福彩3D", "pl3": "排列三", "pl5": "排列五", "ssq": "双色球", "dlt": "大乐透", "qlc": "七乐彩", "qxc": "七星彩"}

# 汇总卡片
kpi_cards = ""
kpi_defs = {
    "kl8": ("月均命中/期", lambda s: f"{s['basic_avg']:.1f}个", "basic_avg"),
    "fc3d": ("三位置命中率", lambda s: f"{sum(s[f'z{i}_avg'] for i in range(1,4)):.2f}/期", None),
    "pl3": ("三位置命中率", lambda s: f"{sum(s[f'z{i}_avg'] for i in range(1,4)):.2f}/期", None),
    "pl5": ("三位置命中率", lambda s: f"{sum(s[f'z{i}_avg'] for i in range(1,4)):.2f}/期", None),
    "ssq": ("红球月均", lambda s: f"{s['reds_avg']:.1f}个", "reds_avg"),
    "dlt": ("前区月均", lambda s: f"{s['reds_avg']:.1f}个", "reds_avg"),
    "qlc": ("红球月均", lambda s: f"{s['reds_avg']:.1f}个", "reds_avg"),
    "qxc": ("三位置命中率", lambda s: f"{sum(s[f'z{i}_avg'] for i in range(1,4)):.2f}/期", None),
}

for k in ["kl8", "fc3d", "pl3", "pl5", "ssq", "dlt", "qlc", "qxc"]:
    s = summary[k]
    label, fn, _ = kpi_defs[k]
    kpi_cards += f'<div class="kpi-card"><div class="label">{names[k]} · {s["n"]}期</div><div class="value">{fn(s)}</div><div class="unit">{label}</div></div>'

# 各彩种明细
sections = ""
for k in ["kl8", "fc3d", "pl3", "pl5", "ssq", "dlt", "qlc", "qxc"]:
    recs = july_recs(k)
    if k in ("ssq", "dlt", "qlc"):
        head, body = weekly_table(recs, k)
    else:
        head, body = daily_table(recs, k)
    th = "".join(f"<th>{h}</th>" for h in head)
    sections += f'''
<div class="section">
  <h2>{names[k]} · 7月明细（{len(recs)}期）</h2>
  <div class="note">{notes[k]}</div>
  <table>
    <thead><tr>{th}</tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>'''

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>8彩种 2026年7月 推荐中奖明细</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:linear-gradient(135deg,#eef6ff 0%,#fdf2e9 100%); padding:24px; color:#1a1a1a; }}
.container {{ max-width:1200px; margin:0 auto; }}
.header {{ background:linear-gradient(135deg,#1a237e 0%,#283593 100%); color:#fff; padding:26px 32px; border-radius:16px; margin-bottom:22px; box-shadow:0 8px 24px rgba(26,35,126,.22); }}
.header h1 {{ font-size:22px; margin-bottom:10px; }}
.header .sub {{ font-size:14px; opacity:.92; line-height:1.7; }}
.header .badge {{ display:inline-block; background:rgba(255,255,255,.2); padding:4px 12px; border-radius:20px; font-size:12px; margin:8px 8px 0 0; }}
.kpi-row {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:22px; }}
.kpi-card {{ background:#fff; border-radius:12px; padding:16px 18px; box-shadow:0 4px 12px rgba(0,0,0,.06); border-left:4px solid #283593; }}
.kpi-card .label {{ font-size:12.5px; color:#666; margin-bottom:6px; }}
.kpi-card .value {{ font-size:20px; font-weight:700; color:#283593; }}
.kpi-card .unit {{ font-size:11px; color:#999; margin-left:4px; }}
.section {{ background:#fff; border-radius:12px; padding:22px 24px; margin-bottom:20px; box-shadow:0 4px 12px rgba(0,0,0,.06); }}
.section h2 {{ font-size:17px; color:#1a237e; margin-bottom:10px; border-left:4px solid #283593; padding-left:10px; }}
.note {{ font-size:12px; color:#888; margin-bottom:10px; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; }}
th,td {{ padding:6px 8px; text-align:center; border-bottom:1px solid #eee; }}
th {{ background:#e8eaf6; color:#1a237e; font-weight:600; }}
tr:hover {{ background:#f5f5f5; }}
td.hit {{ color:#e65100; font-weight:700; background:#fff8e1; }}
td.win {{ color:#2e7d32; font-weight:700; background:#e8f5e9; }}
.foot {{ background:#fff3e0; border-left:4px solid #ff9800; padding:14px 18px; border-radius:6px; font-size:13px; color:#5d4037; margin-top:18px; line-height:1.9; }}
@media (max-width:900px){{ .kpi-row {{ grid-template-columns:repeat(2,1fr); }} }}
</style>
</head>
<body>
<div class="container">
<div class="header">
  <h1>📊 8彩种 2026年7月 推荐号码中奖明细</h1>
  <div class="sub">数据源：data/all_recommendations_archive.json · 逐期真实开奖核对 · 共 {sum(summary[k]["n"] for k in summary)} 期推荐</div>
  <div><span class="badge">日更：快乐8/3D/排三/排五 每日</span><span class="badge">周更：双色球/大乐透/七乐彩/七星彩</span><span class="badge">纯回测展示，非投注建议</span></div>
</div>

<div class="kpi-row">{kpi_cards}</div>

{sections}

<div class="foot">
  <b>阅读说明：</b>① 快乐8 每期开20个号，20码复式命中5个=理论均值；7个及以上标记绿色。② 定位复式（3D/排三/排五/七星彩）命中数指该位置推荐3码中覆盖开奖号的个数，全部命中才中奖（奖金行全0说明7月无直选命中）。③ 双色球/大乐透/七乐彩标记"命中"=红球中2+或蓝球中1+。④ 本报告为历史数据核对，不代表未来表现。
</div>

</div>
</body>
</html>"""

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)
print("OK ->", OUT)
print(f"总期数: {sum(summary[k]['n'] for k in summary)}")
