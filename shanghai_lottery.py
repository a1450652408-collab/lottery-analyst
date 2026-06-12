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


# ===== 预测算法 =====

def ema_score(data, window=30):
    """EMA 评分+动量评分，类似紫色卡片逻辑"""
    if not data:
        return {}
    train = data[:window] if len(data) >= window else data[:]
    work = train[::-1]  # 时间正序
    
    total = len(work)
    if total == 0:
        return {}
    
    # 频率
    freq = Counter()
    for d in work:
        for n in d["n"]:
            freq[n] += 1
    
    # EMA
    ema_vals = {}
    all_nums = list(range(1, 16)) if "n" in data[0] and max(data[0]["n"]) > 9 else list(range(0, 10))
    if data and len(data) > 0 and max(data[0].get("n", [0])) <= 15:
        all_nums = list(range(1, 16))
    
    for n in all_nums:
        seq = [1 if n in d["n"] else 0 for d in work]
        e = seq[-1] if seq else 0
        for v in seq[:-1][::-1]:
            e = 0.5 * v + 0.5 * e
        ema_vals[n] = e
    
    # 动量：前5期 vs 前6-10期
    mom = {}
    for n in all_nums:
        r5 = sum(1 for d in work[:5] if n in d["n"]) if len(work) >= 5 else 0
        p5 = sum(1 for d in work[5:10] if n in d["n"]) if len(work) >= 10 else 0
        km = (r5 - p5) / max(p5, 1)
        mom[n] = max(-2, min(2, km))
    
    # 综合评分（用最大频率归一化）
    max_freq = max(freq.values()) if freq else 1
    scores = {}
    for n in all_nums:
        s = ema_vals.get(n, 0) * 5.0 + (freq.get(n, 0) / max_freq) * 3.0 + mom.get(n, 0) * 2.0
        scores[n] = s
    
    return {
        "scores": scores,
        "ranked": sorted(all_nums, key=lambda n: -scores.get(n, -999)),
        "freq": freq,
        "ema": ema_vals,
        "mom": mom
    }


def predict_sh15x5(data):
    """15选5多策略预测"""
    if not data or len(data) < 20:
        return None
    
    total = len(data)
    pred = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": total,
        "latest": data[0],
        "strategies": []
    }
    
    # ===== 策略1: EMA多因子评分 Top5 =====
    es = ema_score(data, window=min(50, total))
    top5 = es["ranked"][:5]
    pred["strategies"].append({
        "name": "EMA多因子评分(最优)",
        "desc": "综合EMA热度(50%)+频率(30%)+动量(20%)，近50期数据",
        "nums": sorted(top5),
        "method": "ema",
        "cost": 2,
        "confidence": "★★★★"
    })
    
    # ===== 策略2: 追热（近30期最热5个）=====
    freq30 = Counter()
    for d in data[:min(30, total)]:
        for n in d["n"]:
            freq30[n] += 1
    hot5 = [n for n, _ in freq30.most_common(5)]
    pred["strategies"].append({
        "name": "追热策略(W=30)",
        "desc": "近30期出现最多的5个号",
        "nums": sorted(hot5),
        "method": "hot",
        "cost": 2,
        "confidence": "★★★"
    })
    
    # ===== 策略3: 追冷（当前遗漏最久的5个）=====
    miss_cnt = {}
    for n in range(1, 16):
        mc = 0
        for d in data:
            if n in d["n"]:
                break
            mc += 1
        miss_cnt[n] = mc
    cold5 = sorted(range(1, 16), key=lambda n: -miss_cnt[n])[:5]
    pred["strategies"].append({
        "name": "追冷策略(遗漏最大)",
        "desc": f"当前遗漏最大的5个号(最大遗漏{max(miss_cnt.values())}期)",
        "nums": sorted(cold5),
        "method": "cold",
        "cost": 2,
        "confidence": "★★★"
    })
    
    # ===== 策略4: 均衡组合(热3+冷2) =====
    balanced = sorted(hot5[:3] + cold5[:2])
    pred["strategies"].append({
        "name": "均衡组合(热3冷2)",
        "desc": "3个热号(高频) + 2个冷号(遗漏大), 平衡覆盖",
        "nums": balanced,
        "method": "balanced",
        "cost": 2,
        "confidence": "★★★"
    })
    
    # ===== 策略5: 7码复式推荐(热7) =====
    from math import comb
    hot7 = [n for n, _ in freq30.most_common(7)]
    cost7 = comb(7, 5) * 2
    pred["strategies"].append({
        "name": "7码复式(追热)",
        "desc": f"近30期最热7个号, {comb(7,5)}注{cost7}元, 任意奖概率10%",
        "nums": sorted(hot7),
        "method": "fushi_7",
        "cost": cost7,
        "confidence": "★★★"
    })
    
    # ===== 策略6: 10码复式推荐(追热) =====
    hot10 = [n for n, _ in freq30.most_common(10)]
    cost10 = comb(10, 5) * 2
    p10_any = (comb(10,5) + comb(10,4)*comb(5,1)) / comb(15,5)
    pred["strategies"].append({
        "name": "10码复式(追热)",
        "desc": f"近30期最热10个号, {comb(10,5)}注{cost10}元, 任意奖概率{p10_any*100:.1f}%",
        "nums": sorted(hot10),
        "method": "fushi_10",
        "cost": cost10,
        "confidence": "★★★★"
    })

    # ===== 策略7: 胆拖推荐 =====
    dan = top5[:2]  # 用2个EMA最高分做胆
    tuo_candidates = [n for n in es["ranked"][2:9] if n not in dan]
    cost_dt = comb(len(tuo_candidates), 3) * 2
    pred["strategies"].append({
        "name": f"2胆{len(tuo_candidates)}拖(EMA)",
        "desc": f"胆码:{sorted(dan)} 拖码:{sorted(tuo_candidates)}, {cost_dt}元/期",
        "nums": {"dan": sorted(dan), "tuo": sorted(tuo_candidates)},
        "method": "dantuo",
        "cost": cost_dt,
        "confidence": "★★★"
    })
    
    return pred


def predict_ttcx4(data):
    """天天彩选4多策略预测"""
    if not data or len(data) < 20:
        return None
    
    total = len(data)
    pred = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total": total,
        "latest": data[0],
        "strategies": []
    }
    
    # ===== 策略1: 位置频率直选 =====
    pos_freq = [Counter() for _ in range(4)]
    for d in data:
        for i in range(4):
            if i < len(d["n"]):
                pos_freq[i][d["n"][i]] += 1
    
    zx_nums = [pf.most_common(1)[0][0] for pf in pos_freq]
    pred["strategies"].append({
        "name": "位置频率直选",
        "desc": "每个位置取出现最多的数字, 直选1注",
        "nums": zx_nums,
        "method": "zhixuan",
        "cost": 2,
        "confidence": "★★"
    })
    
    # ===== 策略2: 位置频率Top2直选(2注) =====
    zx2_options = []
    for pf in pos_freq:
        top2 = [n for n, _ in pf.most_common(2)]
        zx2_options.append(top2)
    # 2^4 = 16注, 太多了, 只取前4注组合
    pred["strategies"].append({
        "name": "位置Top2直选(4注)",
        "desc": f"每位置取前2个热门, 组成4个直选组合, 8元/期",
        "nums": {
            "pos1": zx2_options[0],
            "pos2": zx2_options[1],
            "pos3": zx2_options[2],
            "pos4": zx2_options[3]
        },
        "method": "zhixuan_multi",
        "cost": 8,
        "confidence": "★★"
    })
    
    # ===== 策略3: EMA综合评分→组选24推荐 =====
    # 对天天彩, all_nums是0-9
    es = ema_score(data, window=min(100, total))
    # 直接用EMA评分最高的4个不同数字做组选24
    top4_ema = [n for n in es["ranked"] if 0 <= n <= 9][:4]
    pred["strategies"].append({
        "name": "EMA组选24推荐",
        "desc": f"EMA评分最高的4个不同数字, 1注组选24, 2元/期",
        "nums": sorted(top4_ema),
        "method": "zuxuan24",
        "cost": 2,
        "confidence": "★★★★"
    })
    
    # ===== 策略4: 最近重复号预测 =====
    # 统计近20期有重复号的模式
    recent_patterns = []
    for d in data[:min(20, total)]:
        if len(set(d["n"])) < 4:
            recent_patterns.append(d["n"])
    
    # 如果近期重复号多, 推荐组选4/组选12
    has_repeat_pct = len(recent_patterns) / min(20, total) * 100
    if has_repeat_pct > 30:
        # 找最近频繁出现的数字
        recent_counter = Counter()
        for d in data[:min(10, total)]:
            for n in d["n"]:
                recent_counter[n] += 1
        top3 = [n for n, _ in recent_counter.most_common(3)]
        # 组选4: 3同+1异 → 用热号做3同, 另一个号选次热
        z4_nums = [top3[0], top3[0], top3[0], top3[1]]
        pred["strategies"].append({
            "name": "组选4预测(重复号高频期)",
            "desc": f"近10期重复号出现{has_repeat_pct:.0f}%, 推荐组选4: {top3[0]}×3+{top3[1]}",
            "nums": sorted(z4_nums),
            "method": "zuxuan4",
            "cost": 2,
            "confidence": "★★★"
        })
    
    # ===== 策略5: 追热组选24(近30期最热4个不重复) =====
    freq30 = Counter()
    for d in data[:min(30, total)]:
        for n in d["n"]:
            freq30[n] += 1
    hot4 = [n for n, _ in freq30.most_common(10) if n not in pred["strategies"][2]["nums"]][:4]
    if len(set(hot4)) == 4:
        pred["strategies"].append({
            "name": "追热组选24(备选)",
            "desc": "近30期热门数字选4个不同号",
            "nums": sorted(hot4),
            "method": "hot_zuxuan24",
            "cost": 2,
            "confidence": "★★★"
        })
    
    return pred


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
            p = predict_sh15x5(sh15)
            out = {"type": "sh15x5", "date": datetime.now().strftime("%Y-%m-%d"),
                   "data": sh15, "analysis": a, "prediction": p}
            with open(SH15_ANALYSIS, "w") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"  📊 热号:{a['hot'][0]['num']}({a['hot'][0]['pct']}%)…冷号:{a['cold'][0]['num']}({a['cold'][0]['pct']}%)")
            if p:
                print(f"  🎯 推荐: {len(p['strategies'])}种策略, 首选→{p['strategies'][0]['name']}: {p['strategies'][0]['nums']}")
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
            p = predict_ttcx4(ttcx4)
            out = {"type": "ttcx4", "date": datetime.now().strftime("%Y-%m-%d"),
                   "data": ttcx4, "analysis": a, "position": pos, "patterns": pat, "prediction": p}
            with open(TTCX4_ANALYSIS, "w") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"  📊 热号:{a['hot'][0]['num']}({a['hot'][0]['pct']}%)")
            print(f"  重复号频率: {pat['has_repeat']['pct']}%")
            if p:
                print(f"  🎯 推荐: {len(p['strategies'])}种策略, 首选→{p['strategies'][0]['name']}: {p['strategies'][0]['nums']}")
            for pd in pos:
                print(f"  位{pd['pos']}: {[str(t['num']) for t in pd['top'][:3]]}")
    else:
        print(f"  ❌ 获取失败" + (f"({len(ttcx4)}条)" if ttcx4 else ""))

    print("\n✅ 完成")


if __name__ == "__main__":
    main()
