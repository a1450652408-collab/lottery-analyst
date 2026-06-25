#!/usr/bin/env python3
"""
数字彩（福彩3D/排列三/排列五）深度分析系统
每位频率 + 012路 + 奇偶 + 大小 + 和值 + 跨位关联 + 集成推荐

输出: data/digit_*.json（供前端加载展示）
"""

import json, os, math, re
from collections import Counter, defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_html_data():
    path = os.path.join(PROJECT_ROOT, "index_modified.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    m = re.search(r'window\.__LOTTERY_DATA\s*=\s*(\{.*?\});', html, re.DOTALL)
    return json.loads(m.group(1))

def analyze_positions(data, num_count=3):
    """每位频率 + 012路 + 奇偶 + 大小"""
    total = len(data)
    pos_freq = [Counter() for _ in range(num_count)]
    
    for d in data:
        nums = d.get("n", d.get("r", []))
        for i in range(min(num_count, len(nums))):
            pos_freq[i][nums[i]] += 1
    
    result = {}
    for pos in range(num_count):
        freq_list = []
        for d in range(10):
            cnt = pos_freq[pos].get(d, 0)
            pct = round(cnt / total * 100, 1)
            route = d % 3
            oe = "奇" if d % 2 == 1 else "偶"
            bs = "大" if d >= 5 else "小"
            freq_list.append({
                "digit": d, "count": cnt, "pct": pct,
                "route": f"{route}路", "oe": oe, "bs": bs,
                "delta": round(pct - 10, 1)
            })
        freq_list.sort(key=lambda x: -x["count"])
        
        # 012路统计
        r_counts = Counter()
        oe_counts = Counter()
        bs_counts = Counter()
        for d in data:
            nums = d.get("n", d.get("r", []))
            if pos < len(nums):
                r_counts[nums[pos] % 3] += 1
                oe_counts[0 if nums[pos] % 2 == 0 else 1] += 1
                bs_counts[0 if nums[pos] < 5 else 1] += 1
        
        result[f"pos{pos}"] = {
            "freq": freq_list,
            "route_012": {
                "0": round(r_counts.get(0,0)/total*100, 1),
                "1": round(r_counts.get(1,0)/total*100, 1),
                "2": round(r_counts.get(2,0)/total*100, 1)
            },
            "odd_even": {
                "奇": round(oe_counts.get(1,0)/total*100, 1),
                "偶": round(oe_counts.get(0,0)/total*100, 1)
            },
            "big_small": {
                "大": round(bs_counts.get(1,0)/total*100, 1),
                "小": round(bs_counts.get(0,0)/total*100, 1)
            },
            "hot_top3": [f["digit"] for f in freq_list[:3]],
            "cold_bottom3": [f["digit"] for f in freq_list[-3:]]
        }
    
    return result

def analyze_sums(data, num_count=3):
    """和值分析"""
    sums = []
    for d in data:
        nums = d.get("n", d.get("r", []))
        sums.append(sum(nums[:num_count]))
    
    dist = Counter(sums)
    total = len(sums)
    return {
        "avg": round(sum(sums)/total, 1),
        "min": min(sums), "max": max(sums),
        "current": sums[0],
        "recent_10": sums[:10],
        "hot": [{"sum": s, "count": c, "pct": round(c/total*100,1)}
                for s, c in dist.most_common(8)]
    }

def analyze_cross_pos(data, num_count=3):
    """跨位关联：当某位出特定数字时，其他位常出什么"""
    total = len(data)
    pairs = {}
    
    for p1 in range(num_count):
        for p2 in range(num_count):
            if p1 >= p2: continue
            key = f"{p1}-{p2}"
            pair_data = defaultdict(lambda: Counter())
            for d in data:
                nums = d.get("n", d.get("r", []))
                if p1 < len(nums) and p2 < len(nums):
                    pair_data[nums[p1]][nums[p2]] += 1
            
            # 取最显著的关联
            significant = []
            for d1, c in pair_data.items():
                top = c.most_common(2)
                for d2, cnt in top:
                    pct = round(cnt / max(total//10, 1) * 100, 1)
                    if cnt >= 3:  # 出现3次以上才认为有意义
                        significant.append({
                            "when": d1, "then": d2,
                            "count": cnt, "pct": pct
                        })
            significant.sort(key=lambda x: -x["count"])
            pairs[key] = significant[:6]
    
    # 相邻位同号出现频率（如3D中百位=十位）
    same_count = 0
    for d in data:
        nums = d.get("n", d.get("r", []))
        if len(nums) >= 2 and nums[0] == nums[1]:
            same_count += 1
    
    return {
        "cross_pairs": pairs,
        "pos0_eq_pos1_rate": round(same_count/total*100, 1)
    }

def generate_recommendation(pos_analysis, sum_analysis):
    """基于多维度分析的智能选号"""
    recs = []
    
    # 策略1: 追热（每位取Top3热号交叉）
    hot_picks = [pos_analysis[f"pos{p}"]["hot_top3"] for p in range(3)]
    for h0 in hot_picks[0][:2]:
        for h1 in hot_picks[1][:2]:
            for h2 in hot_picks[2][:2]:
                recs.append({
                    "nums": [h0, h1, h2],
                    "method": "追热",
                    "reason": f"百位{h0}热+十位{h1}热+个位{h2}热"
                })
    
    # 策略2: 冷热搭配（百位用冷号，十位个位用热号）
    cold_picks = [pos_analysis[f"pos{p}"]["cold_bottom3"] for p in range(3)]
    for c0 in cold_picks[0][:1]:
        for h1 in hot_picks[1][:1]:
            for h2 in hot_picks[2][:1]:
                recs.append({
                    "nums": [c0, h1, h2],
                    "method": "冷热搭",
                    "reason": f"百位{c0}冷+十位{h1}热+个位{h2}热"
                })
    
    # 策略3: 012路均衡（每位尽量选不同路的号）
    for r0 in range(3):
        for r1 in range(3):
            for r2 in range(3):
                if len({r0, r1, r2}) >= 2:  # 至少两路不同
                    # 从每路中选最热的号
                    nums = []
                    for pos, r in enumerate([r0, r1, r2]):
                        candidates = [f for f in pos_analysis[f"pos{pos}"]["freq"] 
                                      if int(f["route"][0]) == r]
                        if candidates:
                            nums.append(candidates[0]["digit"])
                    if len(nums) == 3:
                        recs.append({
                            "nums": nums,
                            "method": "012均衡",
                            "reason": f"{r0}路+{r1}路+{r2}路"
                        })
    
    # 去重取前8组
    seen = set()
    unique_recs = []
    for r in recs:
        key = tuple(r["nums"])
        if key not in seen:
            seen.add(key)
            unique_recs.append(r)
    
    return unique_recs[:8]

def main():
    ld = load_html_data()
    
    for dtype, num_count in [("fc3d", 3), ("pl3", 3), ("pl5", 5)]:
        data = ld.get(dtype, [])
        if len(data) < 10:
            print(f"{dtype}: 数据不足 ({len(data)}条)")
            continue
        
        print(f"\n{'='*50}")
        print(f"{dtype} ({len(data)}期)")
        print('='*50)
        
        pos_analysis = analyze_positions(data, num_count)
        sum_analysis = analyze_sums(data, num_count)
        cross = analyze_cross_pos(data, num_count)
        recs = generate_recommendation(pos_analysis, sum_analysis)
        
        # 每位top
        for p in range(min(3, num_count)):
            name = ["百位","十位","个位","四位","五位"][p]
            pa = pos_analysis[f"pos{p}"]
            hot_str = ",".join(str(h) for h in pa["hot_top3"])
            cold_str = ",".join(str(c) for c in pa["cold_bottom3"])
            print(f"  {name}: 热[{hot_str}] 冷[{cold_str}]")
            print(f"    012路: {pa['route_012']}  奇偶: {pa['odd_even']}  大小: {pa['big_small']}")
        
        print(f"  和值: 均{sum_analysis['avg']} 当期{sum_analysis['current']}")
        print(f"  同号率(百=十): {cross['pos0_eq_pos1_rate']}%")
        
        # 推荐
        print(f"  推荐Top5:")
        for r in recs[:5]:
            nums_str = "".join(str(n) for n in r["nums"])
            print(f"    {nums_str} ({r['method']})")
        
        # 保存
        output = {
            "date": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(data),
            "positions": pos_analysis,
            "sums": sum_analysis,
            "cross_pos": cross,
            "recommendations": recs
        }
        out_path = os.path.join(PROJECT_ROOT, "data", f"{dtype}_analysis.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  ✅ 保存到 {out_path}")

if __name__ == "__main__":
    main()
