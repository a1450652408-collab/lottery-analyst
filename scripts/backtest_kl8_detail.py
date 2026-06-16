"""
快乐8详细回测分析
"""
import json, urllib.request, time, math
from collections import Counter

API = "http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=300"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

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

def recommend_20(data):
    """复刻JS的多策略融合推荐"""
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
    
    hot = sorted(range(1,81), key=lambda n: -(
        freq[n]*2 + ema_scores[n]*15 + (2 if 1<=miss.get(n,100)<=6 else 0) +
        (3 if n not in kill_set and sorted(range(1,81), key=lambda x: -freq[x]).index(n) < 15 else 0) +
        (2 if any(n in get_nums(recent[r]) for r in range(min(5,len(recent)))) else 0)
    ))
    
    return hot

# ===== 奖金计算 =====
# 选十玩法奖金（每注2元）
PRIZE_SHI = {10: 5000000, 9: 8000, 8: 800, 7: 80, 6: 5, 5: 3, 0: 2}

# 选六复式奖金（守号策略 C(10,6)=210注）
# 中6: C(6,6)*C(4,0)*3000, 中5: C(6,5)*C(4,1)*30, 中4: C(6,4)*C(4,2)*10, 中3: C(6,3)*C(4,3)*3
def prize_xuan6(match):
    from math import comb
    return comb(match,6)*3000 + comb(match,5)*comb(10-match,1)*30 + comb(match,4)*comb(10-match,2)*10 + comb(match,3)*comb(10-match,3)*3

def main():
    print("=" * 70)
    print("🎯 快乐8 详细回测分析")
    print("=" * 70)
    
    # 获取数据
    print("\n📡 获取数据...")
    d = fetch()
    items = d["data"]["data"]["list"]
    data = parse(items)
    print(f"  共 {len(data)} 期数据")
    print(f"  最新: 第{data[0]['p']}期 ({data[0]['d']})")
    print(f"  最旧: 第{data[-1]['p']}期 ({data[-1]['d']})")
    
    # =========================================
    # 1. 多策略融合20码回测
    # =========================================
    print("\n" + "=" * 70)
    print("📊 一、多策略融合20码回测（30期窗口）")
    print("=" * 70)
    
    all_hits = []       # 20码命中数
    top10_hits = []     # 前10码命中数
    top6_hits = []      # 前6码命中数（选六）
    dan_hits = {2:[],3:[],4:[],5:[],6:[],7:[],8:[],9:[]}
    tuo_hits = {2:[],3:[],4:[],5:[],6:[],7:[],8:[],9:[]}
    
    hit_dist_20 = Counter()
    hit_dist_10 = Counter()
    hit_dist_6 = Counter()
    
    for i in range(30, len(data)):
        past = data[i-30:i]
        draw = data[i]
        drawn = set(get_nums(draw))
        
        ranked = recommend_20(past)
        top20 = ranked[:20]
        top10 = ranked[:10]
        top6 = ranked[:6]
        
        h20 = sum(1 for n in top20 if n in drawn)
        h10 = sum(1 for n in top10 if n in drawn)
        h6 = sum(1 for n in top6 if n in drawn)
        
        all_hits.append(h20)
        top10_hits.append(h10)
        top6_hits.append(h6)
        hit_dist_20[min(h20, 20)] += 1
        hit_dist_10[min(h10, 10)] += 1
        hit_dist_6[min(h6, 6)] += 1
        
        # 胆拖
        for dc in range(2, 10):
            dan = ranked[:dc]
            tuo = [n for n in top20 if n not in dan]
            d_hit = sum(1 for n in dan if n in drawn)
            t_hit = sum(1 for n in tuo if n in drawn)
            dan_hits[dc].append(d_hit)
            tuo_hits[dc].append(t_hit)
    
    total = len(all_hits)
    print(f"\n  回测期数: {total} 期")
    
    # 20码分布
    print(f"\n  📍 20码命中分布:")
    print(f"  {'命中':>5} | {'期数':>5} | {'占比':>6} | 柱状图")
    print(f"  {'-'*45}")
    for h in range(20, -1, -1):
        cnt = hit_dist_20.get(h, 0)
        if cnt > 0:
            bar = "█" * int(cnt / max(1, total) * 100)
            pct = cnt / total * 100
            print(f"  {h:>5} | {cnt:>5} | {pct:>5.1f}% | {bar}")
    
    avg20 = sum(all_hits) / total
    max20 = max(all_hits)
    print(f"\n  📊 统计: 平均 {avg20:.2f} 个 | 最高 {max20} 个")
    print(f"         中≥5: {sum(1 for h in all_hits if h>=5)}期 ({sum(1 for h in all_hits if h>=5)/total*100:.1f}%)")
    print(f"         中≥8: {sum(1 for h in all_hits if h>=8)}期 ({sum(1 for h in all_hits if h>=8)/total*100:.1f}%)")
    print(f"         中≥10: {sum(1 for h in all_hits if h>=10)}期 ({sum(1 for h in all_hits if h>=10)/total*100:.1f}%)")
    
    # 前10码分布
    print(f"\n  📍 前10码命中分布（选十）:")
    print(f"  {'命中':>5} | {'期数':>5} | {'占比':>6} | 柱状图")
    print(f"  {'-'*45}")
    for h in range(10, -1, -1):
        cnt = hit_dist_10.get(h, 0)
        if cnt > 0:
            bar = "█" * int(cnt / max(1, total) * 100)
            pct = cnt / total * 100
            print(f"  {h:>5} | {cnt:>5} | {pct:>5.1f}% | {bar}")
    
    avg10 = sum(top10_hits) / total
    max10 = max(top10_hits)
    print(f"\n  📊 统计: 平均 {avg10:.2f} 个 | 最高 {max10} 个")
    print(f"         中≥6: {sum(1 for h in top10_hits if h>=6)}期 ({sum(1 for h in top10_hits if h>=6)/total*100:.1f}%)")
    print(f"         中≥8: {sum(1 for h in top10_hits if h>=8)}期 ({sum(1 for h in top10_hits if h>=8)/total*100:.1f}%)")
    
    # 前6码分布（选六复式）
    print(f"\n  📍 前6码命中分布（选六复式）:")
    print(f"  {'命中':>5} | {'期数':>5} | {'占比':>6} | 柱状图")
    print(f"  {'-'*45}")
    for h in range(6, -1, -1):
        cnt = hit_dist_6.get(h, 0)
        if cnt > 0:
            bar = "█" * int(cnt / max(1, total) * 100)
            pct = cnt / total * 100
            print(f"  {h:>5} | {cnt:>5} | {pct:>5.1f}% | {bar}")
    
    avg6 = sum(top6_hits) / total
    max6 = max(top6_hits)
    print(f"\n  📊 统计: 平均 {avg6:.2f} 个 | 最高 {max6} 个")
    print(f"         中≥3: {sum(1 for h in top6_hits if h>=3)}期 ({sum(1 for h in top6_hits if h>=3)/total*100:.1f}%)")
    print(f"         中≥4: {sum(1 for h in top6_hits if h>=4)}期 ({sum(1 for h in top6_hits if h>=4)/total*100:.1f}%)")
    
    # =========================================
    # 2. 胆拖分析
    # =========================================
    print("\n" + "=" * 70)
    print("📊 二、胆拖回测分析（20码内取胆+拖）")
    print("=" * 70)
    
    print(f"\n  {'胆数':>4} | {'胆平均':>6} | {'胆最高':>6} | {'拖平均':>6} | {'拖最高':>6} | {'胆≥1占比':>8}")
    print(f"  {'-'*55}")
    for dc in range(2, 10):
        da = sum(dan_hits[dc]) / len(dan_hits[dc])
        ta = sum(tuo_hits[dc]) / len(tuo_hits[dc])
        dm = max(dan_hits[dc])
        tm = max(tuo_hits[dc])
        d1_pct = sum(1 for h in dan_hits[dc] if h >= 1) / len(dan_hits[dc]) * 100
        print(f"  {dc:>4}胆 | {da:>6.2f} | {dm:>6} | {ta:>6.2f} | {tm:>6} | {d1_pct:>7.1f}%")
    
    # =========================================
    # 3. 选十奖金模拟
    # =========================================
    print("\n" + "=" * 70)
    print("📊 三、选十奖金模拟（前10码投注）")
    print("=" * 70)
    
    total_cost = total * 2  # 每期2元
    total_prize = 0
    prize_dist = Counter()
    for h in top10_hits:
        p = PRIZE_SHI.get(h, 0)
        total_prize += p
        prize_dist[min(h, 10)] += 1
    
    net = total_prize - total_cost
    print(f"\n  投注方式: 选十单注（前10码）")
    print(f"  每期成本: 2元")
    print(f"  总投入: {total_cost}元")
    print(f"  总奖金: {total_prize}元")
    print(f"  净盈亏: {'+' if net>=0 else ''}{net}元")
    print(f"  回报率: {total_prize/total_cost*100:.1f}%")
    
    print(f"\n  {'中奖等级':>8} | {'奖金':>8} | {'中奖期数':>8} | {'总奖金':>10}")
    print(f"  {'-'*45}")
    for h in [10,9,8,7,6,5,0]:
        cnt = prize_dist.get(h, 0)
        if cnt > 0:
            p = PRIZE_SHI.get(h, 0)
            print(f"  {'选十中'+str(h):>8} | {p:>8} | {cnt:>8} | {p*cnt:>10}")
    print(f"  {'合计':>8} | {'':>8} | {'':>8} | {total_prize:>10}")
    
    # =========================================
    # 4. 选六复式奖金模拟
    # =========================================
    print("\n" + "=" * 70)
    print("📊 四、选六复式奖金模拟（前10码 C(10,6)=210注 420元/期）")
    print("=" * 70)
    
    cost_per = 420
    total_cost2 = total * cost_per
    total_prize2 = 0
    prize2_dist = Counter()
    
    for h in top10_hits:
        p = prize_xuan6(h)
        total_prize2 += p
        prize2_dist[min(h, 10)] += 1
    
    net2 = total_prize2 - total_cost2
    print(f"\n  投注方式: 选六复式 C(10,6)=210注")
    print(f"  每期成本: {cost_per}元")
    print(f"  总投入: {total_cost2}元")
    print(f"  总奖金: {total_prize2}元")
    print(f"  净盈亏: {'+' if net2>=0 else ''}{net2}元")
    print(f"  回报率: {total_prize2/total_cost2*100:.1f}%")
    
    print(f"\n  {'命中':>5} | {'奖金':>8} | {'期数':>5} | {'小计':>10}")
    print(f"  {'-'*35}")
    for h in range(10, 2, -1):
        cnt = prize2_dist.get(h, 0)
        if cnt > 0:
            p = prize_xuan6(h)
            print(f"  {h:>5}中 | {p:>8} | {cnt:>5} | {p*cnt:>10}")
    print(f"  {'合计':>8} | {'':>8} | {'':>8} | {total_prize2:>10}")
    
    # =========================================
    # 5. 最佳胆拖组合分析
    # =========================================
    print("\n" + "=" * 70)
    print("📊 五、胆拖投注建议（基于回测数据）")
    print("=" * 70)
    print(f"\n  {'胆数':>4} | {'胆≥1概率':>8} | {'拖均值':>6} | {'建议':>20}")
    print(f"  {'-'*45}")
    recommendations = {
        2: "推荐，胆易中1个",
        3: "推荐，胆较稳",
        4: "可选，胆风险适中",
        5: "谨慎，胆可能0个",
        6: "谨慎，胆要求偏高",
    }
    for dc in range(2, 7):
        d1 = sum(1 for h in dan_hits[dc] if h >= 1) / len(dan_hits[dc]) * 100
        ta = sum(tuo_hits[dc]) / len(tuo_hits[dc])
        rec = recommendations.get(dc, "")
        print(f"  {dc:>4}胆 | {d1:>7.1f}% | {ta:>6.2f} | {rec:>20}")

if __name__ == "__main__":
    main()
