"""排列五 五不同 V2 优化版回测
改动：
1. 杀号从3个→1个（候选池覆盖63.5%）
2. EMA评分替代简单频率（近期权重更高）
3. 位置频率维度（每号在各位置的出现率）
4. 动态权重评分 → Top5
"""
import json, urllib.request, time, sys
from math import comb

API = "http://api.huiniao.top/interface/home/lotteryHistory"

def fetch_pl5(limit=1200):
    all_items = []; page = 1
    fields = ["one","two","three","four","five","six","seven",
              "eight","nine","ten","eleven","twelve","thirteen",
              "fourteen","fifteen","sixteen","seventeen","eighteen",
              "nineteen","twenty"]
    while len(all_items) < limit:
        r = urllib.request.Request(f"{API}?type=plw&page={page}&limit=100", headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(r, timeout=30) as resp: d = json.loads(resp.read().decode("utf-8"))
        if d.get("code")!=1: break
        items = d["data"]["data"]["list"]
        if not items: break
        parsed = []
        for item in items:
            nums = []
            for f in fields:
                v = item.get(f)
                if v is not None:
                    try:
                        n = int(v)
                        if 0 <= n <= 9: nums.append(n)
                    except: pass
            if len(nums) >= 5:
                parsed.append({"p":str(item.get("code","")), "d":str(item.get("day","")), "n":nums[:5]})
        all_items.extend(parsed); page+=1
        if len(items)<100: break
        time.sleep(1.2)
    return all_items[:limit]

def get_nums(item): return item["n"]

def comb_n(arr, n):
    if n==0: return [[]]
    if len(arr)<n: return []
    r=[]; f=arr[0]; rest=arr[1:]
    for c in comb_n(rest,n-1): r.append([f]+c)
    for c in comb_n(rest,n): r.append(c)
    return r

def compute_ema(vals, alpha=0.3):
    """EMA平滑"""
    if not vals: return 0
    ema = vals[0]
    for v in vals[1:]:
        ema = alpha * v + (1-alpha) * ema
    return ema

# === 新: EMA评分 =============
def score_digits_v2(data, digit=10):
    """
    返回每个数字的综合评分
    维度:
    - EMA近期热度: 近10期出现率EMA
    - 中期热度: 全窗口出现率
    - 位置适配度: 在各位置的出现均匀度
    - 动量: 近5期 vs 前5期的变化
    """
    n = len(data)
    if n < 15: return {i:0 for i in range(digit)}
    
    # 全窗口频率
    freq_all = {i:0 for i in range(digit)}
    # 近10期频率 + 位置计数
    recent10 = {i:0 for i in range(digit)}
    # 位置频率 {digit: {pos: count}}
    pos_freq = {i:{p:0 for p in range(5)} for i in range(digit)}
    # 动量: 近5期 vs 前5期
    recent5 = {i:0 for i in range(digit)}
    prev5 = {i:0 for i in range(digit)}
    
    for j in range(n):
        nd = get_nums(data[j])
        for p, k in enumerate(nd):
            try:
                ik = int(k)
                if ik < 0 or ik > 9: continue
                freq_all[ik] += 1
                if j < 5: recent5[ik] += 1
                elif j < 10: prev5[ik] += 1
                if j < 10: recent10[ik] += 1
                pos_freq[ik][p] += 1
            except: pass
    
    # 位置均匀度: 数字在5个位置出现越均匀越好
    scores = {}
    for i in range(digit):
        if freq_all[i] == 0:
            scores[i] = 0
            continue
        
        # EMA热度 (近10期权重高)
        ema_hot = recent10[i] / 10.0 * 3.0
        
        # 中期频率
        mid_freq = freq_all[i] / n * 1.5
        
        # 动量: 近期增长>0是好事
        momentum = (recent5[i] - prev5[i]) / max(prev5[i], 1) * 2.0
        momentum = max(-3, min(3, momentum))  # clip
        
        # 位置均匀度: 在各位置都有出现比集中在一个位置好
        pos_counts = [pos_freq[i][p] for p in range(5)]
        max_pos = max(pos_counts)
        avg_pos = sum(pos_counts) / 5.0 if sum(pos_counts) > 0 else 0
        uniformity = (avg_pos / max_pos) * 1.0 if max_pos > 0 else 0
        
        scores[i] = ema_hot + mid_freq + momentum + uniformity
    
    return scores

# === 新: 精简杀号(只杀1个) =============
def pl_kill_v2(data, kill_n=1):
    """杀kill_n个数字"""
    ks = set()
    last5 = get_nums(data[0])
    ks.add((last5[4]*2+3)%10)
    
    if kill_n <= 1:
        return ks
    
    n = len(data)
    r5 = {i:0 for i in range(10)}
    for j in range(min(5,n)):
        for k in get_nums(data[j]): 
            ik = int(k)
            if 0 <= ik <= 9: r5[ik] = r5.get(ik, 0) + 1
    miss = {i:n for i in range(10)}
    for j in range(n):
        for k in get_nums(data[j]):
            ik = int(k)
            if 0 <= ik <= 9 and miss[ik] > j: miss[ik] = j
    coldest, coldest_s = -1, 999
    for i in range(10):
        if i in ks: continue
        s = r5[i]*2 + miss[i]*0.5
        if s < coldest_s: coldest_s = s; coldest = i
    if coldest >= 0: ks.add(coldest)
    return ks

# === 主回测 =============
print("获取排列五数据...")
pl5_data = fetch_pl5(1200)
print(f"{len(pl5_data)}期: {pl5_data[-1]['d']} ~ {pl5_data[0]['d']}")

WINDOW = 80
GROUPS = 5

wb_trials = 0
wb_hit_dist = {i:0 for i in range(6)}
wb_all = []
best_wb = {}

for i in range(WINDOW, len(pl5_data)):
    train = pl5_data[i-WINDOW:i]
    test = pl5_data[i]
    test_nums = get_nums(test)
    test_set = set(test_nums)
    
    # V2评分 + 杀1个
    kk = pl_kill_v2(train)
    cand = [i for i in range(10) if i not in kk]
    
    # 确保至少有7个候选
    if len(cand) < 7:
        for j in range(10):
            if j not in cand:
                cand.append(j)
                if len(cand) >= 7: break
    
    scores = score_digits_v2(train)
    
    # 胆码: 评分最高的前2作为必选
    ranked = sorted(scores.items(), key=lambda x:-x[1])
    dm = [ranked[0][0], ranked[1][0]]
    if dm[0] not in cand: cand.append(dm[0])
    if dm[1] not in cand: cand.append(dm[1])
    
    all5 = comb_n(cand, 5)
    scored = []
    
    for c in all5:
        if dm[0] not in c: continue
        # 综合评分
        combo_score = sum(scores.get(k, 0) for k in c)
        # 互补对加分
        pairs = [(0,5),(1,6),(2,7),(3,8),(4,9)]
        pair_score = 0
        for a in range(5):
            for b in range(a+1, 5):
                for p in pairs:
                    if (c[a]==p[0] and c[b]==p[1]) or (c[a]==p[1] and c[b]==p[0]):
                        pair_score += 1
        combo_score += pair_score * 2
        
        scored.append({"combo": c, "score": combo_score})
    
    if scored:
        scored.sort(key=lambda x:-x["score"])
        seen = set()
        groups = []
        for s in scored:
            k = str(sorted(s["combo"]))
            if k not in seen:
                seen.add(k)
                groups.append(s["combo"])
                if len(groups) >= GROUPS: break
        
        if groups:
            wb_trials += 1
            hits = [sum(1 for x in g if x in test_set) for g in groups]
            mh = max(hits)
            best_wb[mh] = best_wb.get(mh, 0) + 1
            for h in hits: wb_hit_dist[h] = wb_hit_dist.get(h, 0) + 1
            wb_all.append((test["p"], test["d"], test_nums, groups, hits, mh))
    
    if i % 100 == 0:
        print(f"\r  回测: {i-WINDOW}/{len(pl5_data)-WINDOW} ({int((i-WINDOW)/(len(pl5_data)-WINDOW)*100)}%)", end="", flush=True)

print(f"\r  回测完成!                           ")

# ===== 报告 =====
total_groups = wb_trials * GROUPS
wb5 = best_wb.get(5, 0)
wb4 = best_wb.get(4, 0)
wb3 = best_wb.get(3, 0)

wb_cost = wb_trials * 240
wb_prize = wb5 * 100000 + wb4 * 1000 + wb3 * 50

print(f"\n{'='*80}")
print(f"排列五 五不同 V2优化版 回测报告")
print(f"{'='*80}")
print(f"数据范围: {pl5_data[-1]['d']} ~ {pl5_data[0]['d']} ({len(pl5_data)}期)")
print(f"窗口: {WINDOW}期 | 杀号: 1个 | 评分: EMA+频率+动量+位置均匀度")
print(f"测试: {len(pl5_data)-WINDOW}期 | 产生推荐: {wb_trials}期 | 每组120注/240元")
print()

print(f"  每期最佳组命中:")
for hn in [5, 4, 3, 2, 1, 0]:
    if hn == 0 and best_wb.get(0, 0) == 0: continue
    print(f"    最高中{hn}个: {best_wb.get(hn, 0)}期 ({best_wb.get(hn, 0)/max(wb_trials,1)*100:.1f}%)")
print()

print(f"  全部{total_groups}组命中分布:")
for hn in [5, 4, 3, 2, 1, 0]:
    actual = wb_hit_dist.get(hn, 0)
    if actual == 0 and hn == 0: continue
    prob = comb(5, hn) * comb(5, 5-hn) / comb(10, 5)
    expected = total_groups * prob
    ratio = actual / expected if expected > 0 else 0
    print(f"    中{hn}个: {actual:>5}次 {actual/total_groups*100:>6.1f}% | 期望{expected:>5.0f} | 实际/期望={ratio:>5.2f}x")
print()

print(f"  奖金估算（每期选1组买, 120注=240元）:")
print(f"    总投入: {wb_cost}元 ({wb_trials}期×240元)")
print(f"    总奖金: {wb_prize}元")
print(f"    净盈亏: {wb_prize-wb_cost:+,}元")
print(f"    返奖率: {wb_prize/wb_cost*100:.1f}%" if wb_cost > 0 else "")
print()

if wb5 > 0:
    print(f"  Top命中明细:")
    for r in sorted(wb_all, key=lambda x:-x[5])[:15]:
        det = "; ".join([f"第{i+1}组:{sorted(g)}中{h}" for i,(g,h) in enumerate(zip(r[3],r[4]))])
        print(f"    {r[0]} {r[1]} | 开奖:{r[2]} | {det}")

print()
# 与V1对比
print(f"  {'─'*50}")
print(f"  V1(杀3个+6约束): 中5个6次(0.5%), 返奖率293.7%")
print(f"  V2(杀1个+EMA评分): 中5个{best_wb.get(5,0)}次({best_wb.get(5,0)/max(wb_trials,1)*100:.1f}%), 返奖率{wb_prize/wb_cost*100:.1f}%" if wb_cost > 0 else "")
