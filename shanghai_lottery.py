"""
上海15选5 & 天天彩选4 数据获取与分析（修复版）
============================================
"""

import json, re, os, sys, urllib.request
from datetime import datetime, timedelta
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SH15_FILE = os.path.join(DATA_DIR, "sh15x5_data.json")
TTCX4_FILE = os.path.join(DATA_DIR, "ttcx4_data.json")
SH15_ANALYSIS = os.path.join(DATA_DIR, "sh15x5_analysis.json")
TTCX4_ANALYSIS = os.path.join(DATA_DIR, "ttcx4_analysis.json")


def fetch_sh15x5():
    """从 ip.cn 获取15选5历史数据（修复版）"""
    req = urllib.request.Request("https://ip.cn/caipiao/15x5.html", headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[15选5] 抓取失败: {e}")
        return None

    results = []
    # 解析格式: <tr><td><span>2026151</span></td><td><span>06-10</span></td><td class="award"><span class="icon-redball">3</span>...
    # 按行拆分
    rows = re.findall(r'<tr>.*?</tr>', html, re.DOTALL)
    for row in rows:
        # 找7位期号
        period_m = re.search(r'<td>\s*<span>\s*(\d{7})\s*</span>\s*</td>', row)
        if not period_m:
            continue
        period = period_m.group(1)

        # 找日期
        date_m = re.search(r'<td>\s*<span>\s*(\d{2}-\d{2})\s*</span>\s*</td>', row)
        if not date_m:
            continue
        date_mmdd = date_m.group(1)

        # 找号码 (icon-redball>数字)
        nums = [int(n) for n in re.findall(r'icon-redball[^>]*>(\d+)</span>', row)]
        if len(nums) != 5:
            continue

        year = datetime.now().year
        if period.startswith("2026"):
            year = 2026
        date_str = f"{year}-{date_mmdd}"

        results.append({"p": period, "d": date_str, "n": nums})

    results.sort(key=lambda x: -int(x["p"]))
    return results


def fetch_ttcx4():
    """从东方财富获取天天彩选4历史数据"""
    req = urllib.request.Request("https://caipiao.eastmoney.com/Result/Category/ttcx4",
                                  headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[天天彩4] 抓取失败: {e}")
        return None

    results = []
    # 格式: <tr><td><a href="#2026152">2026152</a></td><td><span class="text-primary">1</span>...
    # 按tr拆分
    rows = re.findall(r'<tr>.*?</tr>', html, re.DOTALL)
    for row in rows:
        # 找7位期号 (在a标签里)
        period_m = re.search(r'href="#(\d{7})"', row)
        if not period_m:
            continue
        period = period_m.group(1)

        # 找号码 (text-primary里的数字)
        nums = [int(n) for n in re.findall(r'class="text-primary">(\d)</span>', row)]
        if len(nums) != 4:
            continue

        if period not in {r["p"] for r in results}:
            results.append({"p": period, "n": nums})

    # 从详细区找日期: "2026-06-11"
    for m in re.finditer(r'(2026-\d{2}-\d{2})', html):
        date_str = m.group(1)
        nearby = html[max(0, m.start()-150):m.end()+50]
        period_m = re.search(r'(2026\d{3})', nearby)
        if period_m:
            p = period_m.group(1)
            for r in results:
                if r["p"] == p and not r.get("d"):
                    r["d"] = date_str

    # 余下的用期号推算日期
    for r in results:
        if not r.get("d"):
            p = r["p"]
            try:
                doy = int(p[4:])
                d = datetime(int(p[:4]), 1, 1) + timedelta(days=doy - 1)
                r["d"] = d.strftime("%Y-%m-%d")
            except:
                r["d"] = ""

    results.sort(key=lambda x: -int(x["p"]))
    return results


# ===== 分析函数 =====

def analyze(data, num_range):
    """频率+遗漏+冷热号分析"""
    if not data:
        return None
    total = len(data)
    counter = Counter()
    for d in data:
        for n in d["n"]:
            counter[n] += 1

    all_nums = list(range(num_range[0], num_range[1] + 1))
    freq = {}
    for n in all_nums:
        freq[n] = {"count": counter.get(n, 0), "pct": round(counter.get(n, 0) / total * 100, 1)}

    sorted_nums = sorted(freq.items(), key=lambda x: -x[1]["count"])
    hot = [{"num": n, **v} for n, v in sorted_nums[:5]]
    cold = [{"num": n, **v} for n, v in sorted_nums[-5:]]

    # 遗漏
    miss = {}
    for n in all_nums:
        mc = 0
        for d in data:
            if n in d["n"]:
                break
            mc += 1
        miss[n] = mc

    # 配对频率
    pair_counter = Counter()
    for d in data:
        sn = sorted(d["n"])
        for i in range(len(sn)):
            for j in range(i + 1, len(sn)):
                pair_counter[(sn[i], sn[j])] += 1
    top_pairs = [{"pair": [a, b], "count": c, "pct": round(c / total * 100, 1)}
                 for (a, b), c in pair_counter.most_common(15)]

    return {
        "total": total,
        "freq": freq,
        "hot": hot, "cold": cold,
        "miss": miss,
        "max_miss": max(miss.values()),
        "avg_miss": round(sum(miss.values()) / len(miss), 1),
        "pairs": top_pairs
    }


def analyze_position(data):
    """天天彩位置分析"""
    positions = [Counter() for _ in range(4)]
    for d in data:
        for i, n in enumerate(d["n"][:4]):
            positions[i][n] += 1
    return [{
        "pos": i + 1,
        "top": [{"num": n, "count": c, "pct": round(c / len(data) * 100, 1)}
                for n, c in pos.most_common(5)]
    } for i, pos in enumerate(positions)]


def analyze_patterns(data):
    """天天彩形态分析"""
    total = len(data)
    res = {"all_odd": 0, "all_even": 0, "all_big": 0, "all_small": 0, "has_repeat": 0}
    for d in data:
        nums = d["n"]
        odd = sum(1 for n in nums if n % 2 == 1)
        big = sum(1 for n in nums if n >= 5)
        if odd == 4: res["all_odd"] += 1
        if odd == 0: res["all_even"] += 1
        if big == 4: res["all_big"] += 1
        if big == 0: res["all_small"] += 1
        if len(set(nums)) < 4: res["has_repeat"] += 1
    return {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in res.items()}


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] === 上海地方彩票分析 ===")

    # ===== 15选5 =====
    print("\n--- 上海15选5 ---")
    sh15 = fetch_sh15x5()
    if sh15 and len(sh15) >= 5:
        print(f"  ✅ {len(sh15)}期, 最新: {sh15[0]['p']}({sh15[0]['d']})")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(SH15_FILE, "w") as f:
            json.dump(sh15, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  ✅ 数据已保存")

        # 分析
        a = analyze(sh15, (1, 15))
        if a:
            out = {"type": "sh15x5", "date": datetime.now().strftime("%Y-%m-%d"),
                   "data": sh15, "analysis": a}
            with open(SH15_ANALYSIS, "w") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"  📊 热号:{a['hot'][0]['num']}({a['hot'][0]['pct']}%)…冷号:{a['cold'][0]['num']}({a['cold'][0]['pct']}%)")
    else:
        print(f"  ❌ 获取失败" + (f"({len(sh15)}条)" if sh15 else ""))

    # ===== 天天彩选4 =====
    print("\n--- 上海天天彩选4 ---")
    ttcx4 = fetch_ttcx4()
    if ttcx4 and len(ttcx4) >= 5:
        print(f"  ✅ {len(ttcx4)}期, 最新: {ttcx4[0]['p']}({ttcx4[0].get('d','?')})")
        with open(TTCX4_FILE, "w") as f:
            json.dump(ttcx4, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  ✅ 数据已保存")

        a = analyze(ttcx4, (0, 9))
        pos = analyze_position(ttcx4)
        pat = analyze_patterns(ttcx4)
        if a:
            out = {"type": "ttcx4", "date": datetime.now().strftime("%Y-%m-%d"),
                   "data": ttcx4, "analysis": a, "position": pos, "patterns": pat}
            with open(TTCX4_ANALYSIS, "w") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"  📊 热号:{a['hot'][0]['num']}({a['hot'][0]['pct']}%)")
            print(f"  重复号频率: {pat['has_repeat']['pct']}%")
            for pd in pos:
                print(f"  位{pd['pos']}: {[str(t['num']) for t in pd['top'][:3]]}")
    else:
        print(f"  ❌ 获取失败" + (f"({len(ttcx4)}条)" if ttcx4 else ""))

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
