"""
快乐8 胆码精选优化方案测试
从20码池中选取胆码的不同数学方法对比

测试方法:
1. Baseline: 当前评分总分Top-N
2. EMA重加权: 提高EMA权重(降低频率权重)
3. 动量筛选: 近5期趋势上升的号码
4. 互斥分散: 从不同"群落"中选胆,减少冗余
5. 置信度筛选: 低方差/高稳定性的号码
"""
import json, urllib.request, time, math
from collections import Counter
from math import comb

API = "http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=300"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

PRIZE5 = {0:0,1:0,2:0,3:3,4:21,5:1000}
PRIZE6 = {0:0,1:0,2:0,3:3,4:10,5:30,6:3000}

def fetch():
    req = urllib.request.Request(API, headers={"User-Agent":"Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode("utf-8"))
def parse(items):
    data = []
    for item in items:
        nums = []
        for f in FIELDS:
            v = item.get(f)
            if v is not None:
                try: nums.append(int(v))
                except: pass
        data.append({"n": sorted(nums), "p": str(item.get("code","")), "d": str(item.get("day",""))})
    return data
def get_nums(d): return d.get("n", [])
def ema(seq, alpha=0.5):
    if not seq: return 0
    seq_rev = seq[::-1]
    e = seq_rev[0]
    for v in seq[1:]: e = alpha * v + (1-alpha) * e
    return e

# =========================================
# 基础评分（与页面一致）
# =========================================
def score_all_numbers(data):
    """返回80个号的评分"""
    recent = data[:30]
    freq = {n:0 for n in range(1, 81)}
    for d in recent:
        for n in get_nums(d):
            if 1 <= n <= 80: freq[n] += 1
    for ri in range(min(5, len(recent))):
        for n in get_nums(recent[ri]):
            if 1 <= n <= 80: freq[n] += 2
    ema_scores = {}
    for n in range(1, 81):
        seq = [1 if n in get_nums(d) else 0 for d in recent]
        ema_scores[n] = ema(seq, 0.5)
    miss = {}
    for n in range(1, 81):
        for i, d in enumerate(recent):
            if n in get_nums(d): miss[n] = i; break
        else: miss[n] = len(recent)
    kills = sorted((n for n in range(1,81) if freq[n]==0 and miss[n]>=15), key=lambda n: -miss[n])[:5]
    kill_set = set(kills)
    hot = sorted(range(1,81), key=lambda n: -freq[n])
    clean_hots = [n for n in hot if n not in kill_set]
    scores = {}
    for n in range(1, 81):
        if n in kill_set: continue
        s = freq[n] * 2 + ema_scores[n] * 15
        if 1 <= miss.get(n,100) <= 6: s += 2
        if n in clean_hots and clean_hots.index(n) < min(15, len(clean_hots)): s += 3
        for ri in range(min(5, len(recent))):
            if n in get_nums(recent[ri]): s += 2; break
        if n % 2 == 1: s += 1
        scores[n] = s
    ranked = sorted(scores, key=lambda n: -scores[n])
    return ranked, scores, freq, ema_scores, miss

# =========================================
# 方法1: Baseline — 总分Top-N
# =========================================
def method_baseline(ranked, scores, freq, ema_scores, miss, dc, data):
    return ranked[:dc]

# =========================================
# 方法2: EMA重加权（胆码专用评分）
# EMA权重从15提高到25, 频率从2降到1
# 胆码更看重近期趋势
# =========================================
def method_ema_weighted(ranked, scores, freq, ema_scores, miss, dc, data):
    recent = data[:30]
    kills = sorted((n for n in range(1,81) if freq[n]==0 and miss.get(n,100)>=15), key=lambda n: -miss[n])[:5]
    kill_set = set(kills)
    hot = sorted(range(1,81), key=lambda n: -freq[n])
    clean_hots = [n for n in hot if n not in kill_set]
    
    dan_scores = {}
    for n in range(1, 81):
        if n in kill_set: continue
        # EMA加权更重（25 vs 15），频率降低（1 vs 2）
        s = freq[n] * 1 + ema_scores[n] * 25
        if 1 <= miss.get(n,100) <= 6: s += 3  # 遗漏加分也提高
        if n in clean_hots and clean_hots.index(n) < min(15, len(clean_hots)): s += 3
        for ri in range(min(5, len(recent))):
            if n in get_nums(recent[ri]): s += 3; break  # 近5期加更多
        if n % 2 == 1: s += 1
        dan_scores[n] = s
    dan_ranked = sorted(dan_scores, key=lambda n: -dan_scores[n])
    return dan_ranked[:dc]

# =========================================
# 方法3: 动量筛选（近期趋势上升）
# 比较近5期 vs 前10期的出现率
# =========================================
def method_momentum(ranked, scores, freq, ema_scores, miss, dc, data):
    recent = data[:30]
    top20 = ranked[:20]
    
    # 每号码在近5期 vs 中间10期(6-15)的出现次数
    momentum = {}
    for n in top20:
        recent_5 = sum(1 for d in recent[:5] if n in get_nums(d))
        mid_10 = sum(1 for d in recent[5:15] if n in get_nums(d))
        # 动量 = 近5期出现率 - 中间10期出现率 (正值=上升)
        m = recent_5/5 - mid_10/10
        momentum[n] = m
    
    # 先按动量降序排，再按总分降序排
    ranked_by_momentum = sorted(top20, key=lambda n: (-momentum[n], -scores[n]))
    
    # 取前dc个，但保证至少有1个来自评分Top3
    result = []
    picked = set()
    
    # 先确保评分最高的号码可能被包含
    for n in ranked[:3]:
        if len(result) < dc and n in top20:
            result.append(n)
            picked.add(n)
    
    # 再从动量最高的补充
    for n in ranked_by_momentum:
        if len(result) >= dc: break
        if n not in picked:
            result.append(n)
            picked.add(n)
    
    return result[:dc]

# =========================================
# 方法4: 互斥分散（群落分析）
# 从不同"热区"选胆,避免高度相关的号码
# =========================================
def method_diversified(ranked, scores, freq, ema_scores, miss, dc, data):
    recent = data[:30]
    top20 = ranked[:20]
    
    # 计算每对号码的互斥度
    # 如果两个号码经常同时出现或同时不出现,它们高度相关
    # 如果两个号码的出现模式相反,它们互斥
    # 我们想要: 独立性强、互不依赖的号码
    n_groups = {}  # number -> group id
    
    if dc <= 2:
        # 2胆: 选评分最高的2个就行
        return ranked[:dc]
    
    # 按号码整除10粗略分群(0-9,10-19,20-29,...,70-79)
    for n in top20:
        n_groups[n] = n // 10
    
    # 从不同群中选评分最高的
    groups = {}
    for n in top20:
        g = n_groups[n]
        if g not in groups:
            groups[g] = []
        groups[g].append(n)
    
    result = []
    picked = set()
    
    # 按群评分总和排序
    group_scores = {}
    for g, nums in groups.items():
        group_scores[g] = sum(scores[n] for n in nums)
    
    for g in sorted(group_scores, key=lambda g: -group_scores[g]):
        for n in groups[g]:
            if len(result) >= dc: break
            if n not in picked:
                result.append(n)
                picked.add(n)
        if len(result) >= dc: break
    
    # 如果还不够,补评分最高的
    for n in top20:
        if len(result) >= dc: break
        if n not in picked:
            result.append(n)
            picked.add(n)
    
    return result[:dc]

# =========================================
# 方法5: 置信度筛选（低方差优先）
# 出现模式稳定的号码更适合做胆
# =========================================
def method_confidence(ranked, scores, freq, ema_scores, miss, dc, data):
    recent = data[:30]
    top20 = ranked[:20]
    
    # 对每个号码,计算近30期出现模式的方差
    # 方差低 = 出现模式稳定 = 更适合做胆
    stabilities = {}
    for n in top20:
        pattern = [1 if n in get_nums(d) else 0 for d in recent]
        avg = sum(pattern) / len(pattern)
        variance = sum((v - avg)**2 for v in pattern) / len(pattern)
        # 稳定度 = 1 / variance (方差越小越稳定)
        # 但如果号码几乎从不出,方差也低但不是好胆码
        # 所以结合出现频率: stable_score = freq * (1 / sqrt(variance))
        if variance > 0:
            stable_score = (freq[n]) / math.sqrt(variance)
        else:
            stable_score = freq[n] * 100  # 完美稳定
        stabilities[n] = stable_score
    
    # 按稳定度排序选胆
    result = sorted(top20, key=lambda n: -stabilities[n])[:dc]
    return result

# =========================================
# 方法6: 综合优化
# EMA重加权 + 动量 + 互斥分散 + 置信度
# =========================================
def method_hybrid(ranked, scores, freq, ema_scores, miss, dc, data):
    recent = data[:30]
    kills = sorted((n for n in range(1,81) if freq[n]==0 and miss.get(n,100)>=15), key=lambda n: -miss[n])[:5]
    kill_set = set(kills)
    hot = sorted(range(1,81), key=lambda n: -freq[n])
    clean_hots = [n for n in hot if n not in kill_set]
    
    # 综合评分: 兼顾近期趋势、动量、稳定度、分散度
    dan_scores = {}
    for n in range(1, 81):
        if n in kill_set: continue
        s = freq[n] * 0.5 + ema_scores[n] * 25
        if 1 <= miss.get(n,100) <= 6: s += 3
        if n in clean_hots and clean_hots.index(n) < min(15, len(clean_hots)): s += 3
        for ri in range(min(5, len(recent))):
            if n in get_nums(recent[ri]): s += 4; break
        if n % 2 == 1: s += 1
        
        # 动量加分
        recent_5 = sum(1 for d in recent[:5] if n in get_nums(d))
        mid_10 = sum(1 for d in recent[5:15] if n in get_nums(d))
        momentum = recent_5/5 - mid_10/10
        if momentum > 0: s += momentum * 5
        
        # 稳定度加分 (方差)
        pattern = [1 if n in get_nums(d) else 0 for d in recent]
        avg = sum(pattern) / len(pattern)
        variance = sum((v - avg)**2 for v in pattern) / len(pattern)
        if variance > 0 and freq[n] > 0:
            stability = freq[n] / math.sqrt(variance)
            s += stability * 2
        
        dan_scores[n] = s
    
    dan_ranked = sorted(dan_scores, key=lambda n: -dan_scores[n])
    
    # 从不同群中选（分散优化）
    top30_dan = dan_ranked[:30]
    groups = {}
    for n in top30_dan:
        g = n // 10
        if g not in groups: groups[g] = []
        groups[g].append(n)
    
    result = []
    picked = set()
    for g in sorted(groups, key=lambda g: -sum(dan_scores[n] for n in groups[g])):
        for n in groups[g]:
            if len(result) >= dc: break
            if n not in picked:
                result.append(n)
                picked.add(n)
        if len(result) >= dc: break
    
    for n in top30_dan:
        if len(result) >= dc: break
        if n not in picked:
            result.append(n)
            picked.add(n)
    
    return result[:dc]

# =========================================
# 通用胆拖奖金计算
# =========================================
def calc_dantuo(d_hit, t_hit, dan_cnt, need, prize_table):
    tuo_pick = need - dan_cnt
    tuo_total = 20 - dan_cnt
    total = 0
    for k in range(tuo_pick + 1):
        if k > t_hit: break
        if tuo_pick - k > tuo_total - t_hit: continue
        ways = comb(t_hit, k) * comb(tuo_total - t_hit, tuo_pick - k)
        prize = prize_table.get(min(d_hit + k, max(prize_table.keys())), 0)
        total += ways * prize
    return total

# =========================================
# 测试
# =========================================
def test_method(data, method_fn, method_name, dc, need, prize_table):
    """测试一种方法在给定胆数和玩法下的表现"""
    total = 0
    total_prize = 0
    d_hits = []
    win_cnt = 0
    
    for i in range(30, len(data)):
        past = data[i-30:i]
        draw = data[i]
        drawn = set(get_nums(draw))
        
        ranked, scores, freq, ema_s, miss = score_all_numbers(past)
        dan = method_fn(ranked, scores, freq, ema_s, miss, dc, past)
        tuo = [n for n in ranked[:20] if n not in dan]
        
        d_hit = sum(1 for n in dan if n in drawn)
        t_hit = sum(1 for n in tuo if n in drawn)
        
        d_hits.append(d_hit)
        
        if need > 0:
            prize = calc_dantuo(d_hit, t_hit, dc, need, prize_table)
            total_prize += prize
            if prize > 0: win_cnt += 1
        
        total += 1
    
    avg_d = sum(d_hits) / total if total > 0 else 0
    ge1 = sum(1 for h in d_hits if h >= 1) / total * 100 if total > 0 else 0
    ge2 = sum(1 for h in d_hits if h >= 2) / total * 100 if total > 0 else 0
    ge3 = sum(1 for h in d_hits if h >= 3) / total * 100 if total > 0 else 0
    max_d = max(d_hits) if d_hits else 0
    
    bet_count = comb(20-dc, need-dc)
    cost_per = bet_count * 2
    total_cost = total * cost_per
    net = total_prize - total_cost
    roi = total_prize / total_cost * 100 if total_cost > 0 else 0
    
    return {
        "name": method_name,
        "dc": dc, "need": need,
        "avg_d": avg_d, "ge1": ge1, "ge2": ge2, "ge3": ge3, "max_d": max_d,
        "total_prize": total_prize, "total_cost": total_cost,
        "net": net, "roi": roi, "win_cnt": win_cnt, "total": total,
        "cost_per": cost_per, "bets": bet_count
    }

def main():
    print("=" * 90)
    print("🧪 快乐8 胆码精选数学方法对比测试")
    print("=" * 90)
    
    # 获取数据
    print("\n📡 正在从灰鸟API获取实时数据...")
    d = fetch()
    items = d["data"]["data"]["list"]
    data = parse(items)
    print(f"  ✅ 获取成功: {len(data)} 期数据")
    print(f"  📅 最新: 第{data[0]['p']}期 ({data[0]['d']})")
    print(f"  📅 最旧: 第{data[-1]['p']}期 ({data[-1]['d']})")
    
    methods = [
        ("Baseline(当前)", method_baseline),
        ("EMA重加权", method_ema_weighted),
        ("动量筛选", method_momentum),
        ("互斥分散", method_diversified),
        ("置信度筛选", method_confidence),
        ("综合优化", method_hybrid),
    ]
    
    # 测试 2胆/3胆/4胆 + 选五
    for dc in [2, 3, 4]:
        print(f"\n{'='*90}")
        print(f"📊 测试: {dc}胆 选五胆拖")
        print(f"{'='*90}")
        
        results = []
        for name, fn in methods:
            r = test_method(data, fn, name, dc, 5, PRIZE5)
            results.append(r)
        
        # 胆码命中对比
        print(f"\n  📍 胆码命中对比:")
        print(f"  {'方法':>16} | {'平均胆中':>8} | {'≥1':>6} | {'≥2':>6} | {'≥3':>6} | {'最高':>4} | {'净盈亏':>10} | {'回报率':>8} | {'盈利':>10}")
        print(f"  {'─'*90}")
        
        for r in sorted(results, key=lambda x: -x["net"]):
            print(f"  {r['name']:>16} | {r['avg_d']:>8.2f} | {r['ge1']:>5.1f}% | {r['ge2']:>5.1f}% | {r['ge3']:>5.1f}% | {r['max_d']:>4} | {'+' if r['net']>=0 else ''}{r['net']:>9,} | {r['roi']:>7.2f}% | {r['win_cnt']:>3}/{r['total']}")
        
        # 找出最优
        best = max(results, key=lambda x: x["net"])
        baseline = [r for r in results if r["name"] == "Baseline(当前)"][0]
        improvement = best["net"] - baseline["net"]
        print(f"\n  🏆 最优: {best['name']} | 净亏{best['net']:,}元 | 回报率{best['roi']:.1f}%")
        print(f"     Baseline: 净亏{baseline['net']:,}元 | 回报率{baseline['roi']:.1f}%")
        print(f"     改善: {'+' if improvement>=0 else ''}{improvement:,}元 ({improvement/baseline['net']*100 if baseline['net']!=0 else 0:+.1f}%)")
    
    # 最优方案详细数据
    print(f"\n{'='*90}")
    print(f"🏆 最终建议方案（综合看）")
    print(f"{'='*90}")
    
    print(f"\n  各方法在2胆/3胆/4胆下的净盈亏总和（越大越好）:")
    method_totals = {}
    for name, fn in methods:
        total_net = 0
        for dc in [2, 3, 4]:
            r = test_method(data, fn, name, dc, 5, PRIZE5)
            total_net += r["net"]
        method_totals[name] = total_net
    
    for name, total_net in sorted(method_totals.items(), key=lambda x: -x[1]):
        print(f"    {name:>16}: 合计净亏 {total_net:,} 元")

if __name__ == "__main__":
    main()
