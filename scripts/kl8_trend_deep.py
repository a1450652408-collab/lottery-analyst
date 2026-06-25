#!/usr/bin/env python3
"""
快乐8 号码走势深度分析：冷温热分类 + 组合模式 + 区段分布 + 趋势动量

输出: data/kl8_trend_deep.json（供前端加载展示）
"""

import json, os, sys
from collections import Counter, defaultdict
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_data():
    """从kl8_500.json加载数据"""
    path = os.path.join(PROJECT_ROOT, "data", "kl8_500.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def classify_by_ema(data, window):
    """按EMA频率分类：Hot(频率>=25%), Warm(15%~25%), Cold(<15%)"""
    recent = data[:window]
    total = len(recent)
    freq = Counter()
    for d in recent:
        nums = d.get("n", d.get("r", []))
        freq.update(nums)
    
    result = {}
    for n in range(1, 81):
        rate = freq.get(n, 0) / total
        if rate >= 0.25:      # 每4期出现1次以上
            tier = "H"  # Hot
        elif rate >= 0.15:    # 每6-7期出现1次
            tier = "W"  # Warm
        else:
            tier = "C"  # Cold
        result[n] = {"freq": round(rate, 3), "tier": tier, "hits": freq.get(n, 0)}
    return result

def analyze_pairs(data, window, top_n=15):
    """分析号码对共现频率"""
    recent = data[:window]
    pair_count = Counter()
    num_count = Counter()
    
    for d in recent:
        nums = sorted(d.get("n", d.get("r", [])))
        num_count.update(nums)
        # 统计所有两两组合
        for i in range(len(nums)):
            for j in range(i+1, len(nums)):
                pair = (nums[i], nums[j])
                pair_count[pair] += 1
    
    total = len(recent)
    # 期望值（随机）：20/80 * 19/79 ≈ 0.06
    expected = 20/80 * 19/79 * total
    
    pairs = []
    for (a, b), cnt in pair_count.most_common(top_n):
        ratio = round(cnt / expected, 2) if expected > 0 else 0
        pairs.append({
            "pair": [a, b],
            "count": cnt,
            "vs_random": ratio,
            "label": "偏高" if ratio > 1.2 else ("正常" if ratio > 0.8 else "偏低")
        })
    return pairs

def zone_distribution(data, window):
    """各区段号码命中分布"""
    zones = {"1-20": (1,20), "21-40": (21,40), "41-60": (41,60), "61-80": (61,80)}
    recent = data[:window]
    result = {}
    
    for zname, (zmin, zmax) in zones.items():
        hits = []
        for d in recent:
            nums = d.get("n", d.get("r", []))
            zone_hits = sum(1 for n in nums if zmin <= n <= zmax)
            hits.append(zone_hits)
        avg = round(sum(hits) / len(hits), 1)
        std = round((sum((h - avg)**2 for h in hits) / len(hits))**0.5, 1)
        result[zname] = {"avg": avg, "std": std, "expected": 5.0}
    
    return result

def trend_momentum(data, window):
    """趋势动量：比较近期(1/3) vs 远期(1/3) 出现频率变化"""
    recent = data[:window]
    third = max(window // 3, 5)
    
    recent_part = recent[:third]
    older_part = recent[-third:] if len(recent) >= third * 2 else recent[third:third*2]
    
    freq_recent = Counter()
    freq_older = Counter()
    
    for d in recent_part:
        freq_recent.update(d.get("n", d.get("r", [])))
    for d in older_part:
        freq_older.update(d.get("n", d.get("r", [])))
    
    result = {}
    for n in range(1, 81):
        r_rate = freq_recent.get(n, 0) / max(len(recent_part), 1)
        o_rate = freq_older.get(n, 0) / max(len(older_part), 1)
        delta = r_rate - o_rate
        if delta > 0.08:
            direction = "升温↑"
        elif delta < -0.08:
            direction = "降温↓"
        else:
            direction = "平稳→"
        result[n] = {
            "recent_rate": round(r_rate, 3),
            "older_rate": round(o_rate, 3),
            "delta": round(delta, 3),
            "direction": direction
        }
    return result

def analyze_warm_hot_pairs(classification, momentum, top_hot=8, top_warm=8):
    """温热号码的组合推荐"""
    hot_nums = sorted([n for n, v in classification.items() if v["tier"] == "H"],
                      key=lambda n: -classification[n]["freq"])[:top_hot]
    warm_nums = sorted([n for n, v in classification.items() if v["tier"] == "W"],
                       key=lambda n: -classification[n]["freq"])[:top_warm]
    cold_nums = sorted([n for n, v in classification.items() if v["tier"] == "C"],
                       key=lambda n: -classification[n]["freq"])[:5]
    
    # 升温中的号（最近变热的）
    warming = sorted([n for n, v in momentum.items() if v["direction"] == "升温↑"],
                     key=lambda n: -momentum[n]["delta"])[:5]
    
    return {
        "hot": hot_nums,
        "warm": warm_nums,
        "cold_tail": cold_nums,
        "warming": warming,
        "recommend_heat": hot_nums[:3],   # 主推热号
        "recommend_rebound": warm_nums[:3] + [n for n in warming if n not in hot_nums][:2]  # 温+升温
    }

def main():
    data = load_data()
    total = len(data)
    print(f"加载 {total} 期快乐8数据")
    
    analysis = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_periods": total,
        "latest_period": data[0].get("p", "?"),
        "latest_date": data[0].get("d", "?"),
        "windows": {}
    }
    
    for win_label, win_size in [("short_10", 10), ("medium_30", 30), 
                                  ("long_50", 50), ("full_100", 100)]:
        if win_size > total:
            continue
        win_data = data[:win_size]
        
        classification = classify_by_ema(win_data, win_size)
        pairs = analyze_pairs(win_data, win_size, top_n=10)
        zones = zone_distribution(win_data, win_size)
        momentum = trend_momentum(win_data, win_size)
        combo = analyze_warm_hot_pairs(classification, momentum)
        
        analysis["windows"][win_label] = {
            "size": win_size,
            "classify": classification,
            "pairs": pairs,
            "zones": zones,
            "momentum": momentum,
            "combo": combo
        }
    
    # 输出
    out_path = os.path.join(PROJECT_ROOT, "data", "kl8_trend_deep.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)
    
    # 控制台摘要
    w = analysis["windows"].get("medium_30", analysis["windows"].get("long_50", {}))
    if w:
        c = w["classify"]
        # 键可能是int或str，统一处理
        def get_tier(n):
            keys = [n, str(n)]
            for k in keys:
                if k in c:
                    return c[k]["tier"]
            return "?"
        h_count = sum(1 for n in range(1,81) if get_tier(n) == "H")
        w_count = sum(1 for n in range(1,81) if get_tier(n) == "W")
        c_count = sum(1 for n in range(1,81) if get_tier(n) == "C")
        hot_list = [n for n in range(1,81) if get_tier(n) == "H"]
        print(f"\n=== 冷热分布 (30期) ===")
        print(f"  热(H): {h_count}个  |  温(W): {w_count}个  |  冷(C): {c_count}个")
        print(f"  热号Top: {w['combo']['hot'][:6]}")
        print(f"  升温中: {w['combo']['warming'][:6]}")
        print(f"  温热推荐: {w['combo']['recommend_heat']} + {w['combo']['recommend_rebound']}")
        print(f"\n=== 区段分布 (30期) ===")
        for zname, zd in w["zones"].items():
            bar = "█" * int(zd["avg"] * 2)
            print(f"  {zname}: 均{zd['avg']}±{zd['std']}  {bar}")
        print(f"\n=== 高频配对Top5 ===")
        for p in w["pairs"][:5]:
            print(f"  {p['pair']}: 共现{p['count']}次 ({p['label']})")
    
    print(f"\n✅ 已保存到 {out_path}")
    return analysis

if __name__ == "__main__":
    main()
