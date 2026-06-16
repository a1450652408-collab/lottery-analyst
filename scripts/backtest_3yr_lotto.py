"""
SSQ/DLT 3年回测：旧3因子评分 vs 新7因子评分
直接从API拉取500期数据
"""
import json, urllib.request, sys, os
from collections import Counter
from math import comb

def fetch(type_name, limit=500):
    url = f'http://api.huiniao.top/interface/home/lotteryHistory?type={type_name}&page=1&limit={limit}'
    r = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    resp = urllib.request.urlopen(r, timeout=30)
    data = json.loads(resp.read().decode('utf-8'))
    if data.get('code') != 1:
        raise Exception(f'API error: {data}')
    return data['data']['data']['list']

FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

def parse_ssq(items):
    result = []
    for item in items:
        nums = []
        for f in FIELDS:
            v = item.get(f)
            if v is not None:
                try: nums.append(int(v))
                except: pass
        result.append({
            "p": str(item.get("code","")),
            "d": str(item.get("day","")),
            "r": sorted(nums[:6]),
            "b": nums[6] if len(nums) > 6 else None
        })
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
        result.append({
            "p": str(item.get("code","")),
            "d": str(item.get("day","")),
            "r": sorted(nums[:5]),
            "b": sorted(nums[5:7]) if len(nums) > 5 else []
        })
    return result

def get_nums(d): return d.get("r", []) if "r" in d else d.get("n", [])
def get_blues(d):
    b = d.get("b", [])
    if not isinstance(b, list): b = [b]
    return b

# ===== 旧版：3因子评分 =====
def old_pick9(data_slice, rMax, bMax):
    freq = {n: 0 for n in range(1, rMax+1)}
    miss = {n: len(data_slice) for n in range(1, rMax+1)}
    for i, d in enumerate(data_slice):
        for n in get_nums(d):
            if n in freq: freq[n] += 1; miss[n] = min(miss[n], i)
    recent = [0]*(rMax+1)
    for d in data_slice[:10]:
        for n in get_nums(d):
            if 1 <= n <= rMax: recent[n] += 1
    scores = {n: (freq[n] or 0)*1.0 + (miss.get(n, len(data_slice)) or 0)*0.3 + (recent[n] or 0)*3.0 for n in range(1, rMax+1)}
    ranked = sorted(range(1, rMax+1), key=lambda n: -scores[n])
    # 蓝球
    bfreq = {n: 0 for n in range(1, bMax+1)}
    for d in data_slice:
        for b in get_blues(d):
            if b in bfreq: bfreq[b] += 1
    brecent = {n: 0 for n in range(1, bMax+1)}
    for d in data_slice[:10]:
        for b in get_blues(d):
            if 1 <= b <= bMax: brecent[b] += 1
    bscores = {n: bfreq[n]*0.5 + brecent[n]*3.0 for n in range(1, bMax+1)}
    branked = sorted(range(1, bMax+1), key=lambda n: -bscores[n])
    return ranked[:9], branked[:3]

# ===== 新版：EMA综合评分 + 区间均衡 =====
def new_pick9(data_slice, rMax, bMax):
    freq = {n: 0 for n in range(1, rMax+1)}
    for d in data_slice:
        for n in get_nums(d):
            if 1 <= n <= rMax: freq[n] += 1
    freq_mean = sum(freq.values())/rMax
    freq_sd = (sum((freq[n]-freq_mean)**2 for n in range(1, rMax+1))/rMax)**0.5
    
    ema = {}
    for n in range(1, rMax+1):
        seq = [1 if n in get_nums(d) else 0 for d in data_slice]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e = 0.5*v + 0.5*e
        ema[n] = e
    
    scores = {}
    for n in range(1, rMax+1):
        emaW = (ema[n] or 0) * 5.0
        freqW = (freq[n] or 0) / freq_mean * 0.5 if freq_mean > 0 else 0
        zW = ((freq[n] or 0) - freq_mean) / (freq_sd + 0.001) * 0.15
        scores[n] = emaW + freqW + max(zW, -1)
    
    if rMax == 33: zones = [[1, 11], [12, 22], [23, 33]]
    elif rMax == 35: zones = [[1, 12], [13, 23], [24, 35]]
    else: zones = [[1, rMax//3], [rMax//3+1, rMax*2//3], [rMax*2//3+1, rMax]]
    
    ranked = sorted(range(1, rMax+1), key=lambda n: -scores[n])
    picked = []
    per = 9 // len(zones)
    for zn in zones:
        for n in ranked:
            if len([x for x in picked if zn[0] <= x <= zn[1]]) >= per: break
            if zn[0] <= n <= zn[1] and n not in picked: picked.append(n)
    for n in ranked:
        if len(picked) >= 9: break
        if n not in picked: picked.append(n)
    
    # 蓝球：3因子
    bfreq = {n: 0 for n in range(1, bMax+1)}
    bmiss = {n: len(data_slice) for n in range(1, bMax+1)}
    for i, d in enumerate(data_slice):
        for b in get_blues(d):
            if 1 <= b <= bMax: bfreq[b] += 1; bmiss[b] = min(bmiss[b], i)
    brecent = {n: 0 for n in range(1, bMax+1)}
    for d in data_slice[:10]:
        for b in get_blues(d):
            if 1 <= b <= bMax: brecent[b] += 1
    bscores = {n: bfreq[n]*0.3 + brecent[n]*3.0 + (len(data_slice)-bmiss[n])*0.2 for n in range(1, bMax+1)}
    branked = sorted(range(1, bMax+1), key=lambda n: -bscores[n])
    return picked, branked[:3]

# ===== 回测 =====
for lot_type, parse_fn, rMax, bMax in [
    ('双色球(SSQ)', parse_ssq, 33, 16),
    ('大乐透(DLT)', parse_dlt, 35, 12),
]:
    print(f"\n{'='*70}")
    print(f"  {lot_type} - 从API拉取数据...")
    raw_items = fetch('ssq' if 'SSQ' in lot_type else 'dlt', 500)
    data = parse_fn(raw_items)
    print(f"  获取 {len(data)} 期: {data[0]['p']}({data[0]['d']}) ~ {data[-1]['p']}({data[-1]['d']})")
    
    # 滚动回测：训练窗口15期，预测下一期
    old_rh, new_rh = [], []
    old_bh, new_bh = [], []
    old_ge3, new_ge3 = 0, 0
    old_ge4, new_ge4 = 0, 0
    old_ge5, new_ge5 = 0, 0
    n_tests = 0
    
    for idx in range(len(data)-20, -1, -1):
        train = data[idx+1:idx+16]  # 前15期训练
        if len(train) < 10: continue
        actual = set(get_nums(data[idx]))
        ablue = set(get_blues(data[idx]))
        
        o9, o3b = old_pick9(train, rMax, bMax)
        n9, n3b = new_pick9(train, rMax, bMax)
        
        oh = len(set(o9) & actual)
        nh = len(set(n9) & actual)
        old_rh.append(oh); new_rh.append(nh)
        old_bh.append(1 if set(o3b) & ablue else 0)
        new_bh.append(1 if set(n3b) & ablue else 0)
        
        if oh >= 3: old_ge3 += 1
        if oh >= 4: old_ge4 += 1
        if oh >= 5: old_ge5 += 1
        if nh >= 3: new_ge3 += 1
        if nh >= 4: new_ge4 += 1
        if nh >= 5: new_ge5 += 1
        n_tests += 1
    
    print(f"\n  回测期数: {n_tests}")
    print(f"\n  {'指标':>12} | {'旧3因子':>10} | {'新7因子+区':>10} | {'变化':>8}")
    print(f"  {'-'*46}")
    print(f"  {'红球均命中':>12} | {sum(old_rh)/n_tests:>8.3f}个 | {sum(new_rh)/n_tests:>8.3f}个 | {sum(new_rh)/n_tests - sum(old_rh)/n_tests:>+7.3f}")
    print(f"  {'≥3红':>12} | {old_ge3/n_tests*100:>8.1f}% | {new_ge3/n_tests*100:>8.1f}% | {new_ge3/n_tests*100 - old_ge3/n_tests*100:>+7.1f}%")
    print(f"  {'≥4红':>12} | {old_ge4/n_tests*100:>8.1f}% | {new_ge4/n_tests*100:>8.1f}% | {new_ge4/n_tests*100 - old_ge4/n_tests*100:>+7.1f}%")
    print(f"  {'≥5红':>12} | {old_ge5/n_tests*100:>8.1f}% | {new_ge5/n_tests*100:>8.1f}% | {new_ge5/n_tests*100 - old_ge5/n_tests*100:>+7.1f}%")
    print(f"  {'蓝球中':>12} | {sum(old_bh)/n_tests*100:>8.1f}% | {sum(new_bh)/n_tests*100:>8.1f}% | {sum(new_bh)/n_tests*100 - sum(old_bh)/n_tests*100:>+7.1f}%")
    
    # 期望值对比（随机）
    from math import comb as c
    random_expect = 9 * rMax / (rMax * 6)  # simplified
    print(f"\n  随机期望: {9*6/rMax:.3f}个/期 (纯随机选9红)")
    
    verdict = "新版更好" if (sum(new_rh) > sum(old_rh)) else "旧版更好" if (sum(old_rh) > sum(new_rh)) else "持平"
    print(f"\n  >>> 结论: {verdict}")
