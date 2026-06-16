"""
双色球/大乐透 4年回测：大复试推荐的各等奖次数和总回报
SSQ: 9红+3蓝 = 252注/504元/期
DLT: 8红+3蓝 = 168注/336元/期
"""
import json, urllib.request
from math import comb
from collections import Counter

API = "http://api.huiniao.top/interface/home/lotteryHistory"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

def fetch(type_name, limit=500):
    url = f"{API}?type={type_name}&page=1&limit={limit}"
    r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    resp = urllib.request.urlopen(r, timeout=30)
    data = json.loads(resp.read().decode("utf-8"))
    return data["data"]["data"]["list"]

def parse_ssq(items):
    result = []
    for item in items:
        nums = []
        for f in FIELDS:
            v = item.get(f)
            if v is not None:
                try: nums.append(int(v))
                except: pass
        result.append({"p": str(item.get("code","")), "d": str(item.get("day","")),
                       "r": sorted(nums[:6]), "b": nums[6] if len(nums) > 6 else None})
    return result

def parse_dlt(items):
    result = []
    for item in items:
        nums = []
        for f in FIELDS:
            v = item.get(f)
            if v is not None:
                try: nums.append(int(v))
                except: pass
        result.append({"p": str(item.get("code","")), "d": str(item.get("day","")),
                       "r": sorted(nums[:5]), "b": sorted(nums[5:7]) if len(nums) > 5 else []})
    return result

# ===== 评分函数 =====
def score_ssq_red(train):
    freq = {n: 0 for n in range(1, 34)}
    miss = {n: len(train) for n in range(1, 34)}
    for i, d in enumerate(train):
        for n in d["r"]:
            if 1 <= n <= 33: freq[n] += 1; miss[n] = min(miss[n], i)
    recent = [0]*34
    for d in train[:10]:
        for n in d["r"]:
            if 1 <= n <= 33: recent[n] += 1
    # EMA
    ema = {}
    for n in range(1, 34):
        seq = [1 if n in d["r"] else 0 for d in train]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e = 0.5*v + 0.5*e
        ema[n] = e
    scores = {}
    for n in range(1, 34):
        emaW = (ema[n] or 0) * 5.0
        freqW = (freq[n] or 0)/len(train) * 3.0
        recentW = recent[n] * 3.0
        scores[n] = emaW + freqW + recentW
    return scores

def score_ssq_blue(train):
    bfreq = {n: 0 for n in range(1, 17)}
    bmiss = {n: len(train) for n in range(1, 17)}
    for i, d in enumerate(train):
        b = d.get("b")
        if b is not None and 1 <= b <= 16: bfreq[b] += 1; bmiss[b] = min(bmiss[b], i)
    brecent = {n: 0 for n in range(1, 17)}
    for d in train[:10]:
        b = d.get("b")
        if b is not None and 1 <= b <= 16: brecent[b] += 1
    scores = {n: bfreq[n]*0.3 + brecent[n]*3.0 + (len(train)-bmiss[n])*0.2 for n in range(1, 17)}
    return scores

def score_dlt_red(train):
    """旧3因子+三区均衡"""
    freq = {n: 0 for n in range(1, 36)}
    miss = {n: len(train) for n in range(1, 36)}
    for i, d in enumerate(train):
        for n in d["r"]:
            if 1 <= n <= 35: freq[n] += 1; miss[n] = min(miss[n], i)
    recent = [0]*36
    for d in train[:10]:
        for n in d["r"]:
            if 1 <= n <= 35: recent[n] += 1
    scores = {n: (freq[n] or 0)*1.0 + (miss.get(n, len(train)) or 0)*0.3 + (recent[n] or 0)*3.0 for n in range(1, 36)}
    return scores

def score_dlt_blue(train):
    bfreq = {n: 0 for n in range(1, 13)}
    for d in train:
        for b in d["b"]:
            if 1 <= b <= 12: bfreq[b] += 1
    brecent = {n: 0 for n in range(1, 13)}
    for d in train[:10]:
        for b in d["b"]:
            if 1 <= b <= 12: brecent[b] += 1
    scores = {n: bfreq[n]*0.5 + brecent[n]*3.0 for n in range(1, 13)}
    return scores

def pick_ssq_9(train):
    red_scores = score_ssq_red(train)
    red_ranked = sorted(range(1, 34), key=lambda n: -red_scores[n])
    # 三区均衡
    zones = [[1, 11], [12, 22], [23, 33]]
    picked = []
    for zn in zones:
        for n in red_ranked:
            if len([x for x in picked if zn[0] <= x <= zn[1]]) >= 3: break
            if zn[0] <= n <= zn[1] and n not in picked: picked.append(n)
    for n in red_ranked:
        if len(picked) >= 9: break
        if n not in picked: picked.append(n)
    
    blue_scores = score_ssq_blue(train)
    blues = sorted(range(1, 17), key=lambda n: -blue_scores[n])[:3]
    return picked, blues

def pick_dlt_8(train):
    red_scores = score_dlt_red(train)
    red_ranked = sorted(range(1, 36), key=lambda n: -red_scores[n])
    zones = [[1, 12], [13, 23], [24, 35]]
    picked = []
    for zn in zones:
        for n in red_ranked:
            if len([x for x in picked if zn[0] <= x <= zn[1]]) >= 3: break
            if zn[0] <= n <= zn[1] and n not in picked: picked.append(n)
    for n in red_ranked:
        if len(picked) >= 8: break
        if n not in picked: picked.append(n)
    
    blue_scores = score_dlt_blue(train)
    blues = sorted(range(1, 13), key=lambda n: -blue_scores[n])[:3]
    return picked, blues

# ===== SSQ奖金表 =====
def ssq_prize(red_hit, blue_hit):
    if red_hit == 6 and blue_hit == 1: return "一等奖", "浮动(约500万)"
    if red_hit == 6 and blue_hit == 0: return "二等奖", "浮动(约20万)"
    if red_hit == 5 and blue_hit == 1: return "三等奖", "3000"
    if red_hit == 5 and blue_hit == 0: return "四等奖", "200"
    if red_hit == 4 and blue_hit == 1: return "四等奖", "200"
    if red_hit == 4 and blue_hit == 0: return "五等奖", "10"
    if red_hit == 3 and blue_hit == 1: return "五等奖", "10"
    if red_hit == 2 and blue_hit == 1: return "六等奖", "5"
    if red_hit == 1 and blue_hit == 1: return "六等奖", "5"
    if red_hit == 0 and blue_hit == 1: return "六等奖", "5"
    return None, None

def dlt_prize(red_hit, blue_hit):
    if red_hit == 5 and blue_hit == 2: return "一等奖", "浮动(约1000万)"
    if red_hit == 5 and blue_hit == 1: return "二等奖", "浮动(约20万)"
    if red_hit == 5 and blue_hit == 0: return "三等奖", "10000"
    if red_hit == 4 and blue_hit == 2: return "四等奖", "3000"
    if red_hit == 4 and blue_hit == 1: return "五等奖", "300"
    if red_hit == 3 and blue_hit == 2: return "五等奖", "300"
    if red_hit == 4 and blue_hit == 0: return "六等奖", "100"
    if red_hit == 3 and blue_hit == 1: return "六等奖", "100"
    if red_hit == 2 and blue_hit == 2: return "六等奖", "100"
    if red_hit == 3 and blue_hit == 0: return "七等奖", "10"
    if red_hit == 1 and blue_hit == 2: return "七等奖", "10"
    if red_hit == 2 and blue_hit == 1: return "七等奖", "10"
    if red_hit == 0 and blue_hit == 2: return "八等奖", "5"
    return None, None

def fixed_prize_amount(prize_str):
    if prize_str is None: return 0
    if "浮动" in prize_str: return 0  # 浮动奖不算入固定回报
    try: return int(prize_str)
    except: return 0

# ===== 回测 =====
for name, parse_fn, rMax, bC, big_red, cost_per_period, pick_fn, prize_fn in [
    ("双色球", parse_ssq, 33, 6, 9, 504, pick_ssq_9, ssq_prize),
    ("大乐透", parse_dlt, 35, 5, 8, 336, pick_dlt_8, dlt_prize),
]:
    print(f"\n{'='*70}")
    print(f"  {name} 大复试推荐回测")
    print(f"  {'='*70}")
    
    api_type = "ssq" if "双色球" in name else "dlt"
    raw = fetch(api_type, 500)
    data = parse_fn(raw)
    print(f"  数据: {len(data)} 期 ({data[-1]['p']} ~ {data[0]['p']})")
    
    prize_counts = Counter()
    total_won = 0
    total_cost = 0
    winning_periods = 0
    best_period = ""
    best_prize = ""
    
    # 用于组合枚举
    from itertools import combinations
    
    for idx in range(len(data)-105):
        train = data[idx+1:idx+101]
        if len(train) < 80: continue
        actual_reds = set(data[idx]["r"])
        actual_blues = data[idx]["b"]
        if not isinstance(actual_blues, list):
            actual_blues_set = {actual_blues}
        else:
            actual_blues_set = set(actual_blues)
        
        picks_red, picks_blue = pick_fn(train)
        
        total_cost += cost_per_period
        
        # 枚举所有组合
        period_won = 0
        period_prizes = Counter()
        
        for red_combo in combinations(picks_red, bC):
            rh = len(set(red_combo) & actual_reds)
            for blue in picks_blue:
                bh = 1 if blue in actual_blues_set else 0
                if not isinstance(data[idx]["b"], list):
                    # SSQ: 1 blue
                    prize_name, prize_amount = prize_fn(rh, bh)
                else:
                    # DLT: need to check if blue is in the 2 drawn blues
                    bh = 1 if blue in actual_blues_set else 0
                    prize_name, prize_amount = prize_fn(rh, bh)
                
                if prize_name:
                    period_prizes[prize_name] += 1
                    amt = fixed_prize_amount(prize_amount)
                    period_won += amt
        
        # 记录该期的情况
        if period_prizes:
            winning_periods += 1
            total_won += period_won
            for pn, cnt in period_prizes.items():
                prize_counts[pn] += cnt
            
            # 检查是否有一二等
            top_prizes = [p for p in period_prizes if "一等" in p or "二等" in p]
            if top_prizes:
                best_period = data[idx].get("p", "?")
                best_prize = ", ".join(top_prizes)
    
    total_draws = len(data) - 105
    
    print(f"\n  回测期数: {total_draws} 期")
    print(f"  总投入: {total_cost}元 ({cost_per_period}元/期 × {total_draws}期)")
    print(f"  总回报(固定奖): {total_won}元")
    print(f"  ROI(仅固定奖): {total_won/total_cost*100:.1f}%")
    print(f"  中奖期数: {winning_periods}/{total_draws} ({winning_periods/total_draws*100:.1f}%)")
    
    print(f"\n  各等奖中奖次数:")
    prize_order = ["一等奖", "二等奖", "三等奖", "四等奖", "五等奖", "六等奖", "七等奖", "八等奖"]
    for p in prize_order:
        if prize_counts[p] > 0:
            print(f"    {p}: {prize_counts[p]} 次")
    if best_prize:
        print(f"\n  最优成绩: 期号 {best_period} → {best_prize}")
    
    print(f"\n  红球命中统计:")
    # 只要看9红中有几个在开奖号中
    rh_dist = Counter()
    for idx in range(len(data)-105):
        train = data[idx+1:idx+101]
        if len(train) < 80: continue
        picks_red, _ = pick_fn(train)
        actual_reds = set(data[idx]["r"])
        rh = len(set(picks_red) & actual_reds)
        rh_dist[rh] += 1
    print(f"    {'红球命中':>6} | {'期数':>6} | {'占比':>6}")
    print(f"    {'-'*22}")
    for h in range(0, 10):
        if rh_dist[h] > 0:
            print(f"    {h:>4}个  | {rh_dist[h]:>4}期 | {rh_dist[h]/total_draws*100:>5.1f}%")

print(f"\n{'='*70}")
print(f"  注：一二等奖为浮动奖金，以上仅统计固定奖金额。")
print(f"      若中一二等奖，实际回报远高于固定奖统计。")
