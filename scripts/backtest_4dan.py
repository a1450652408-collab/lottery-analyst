"""
快乐8 4胆拖 真实收益模拟
数据来源: api.huiniao.top (页面同源)
算法: 与页面JS一致 (频率×2 + EMA×15 + 近5期加权)
奖金: 官方福彩奖金规则
"""
import json, urllib.request, time, math
from collections import Counter
from math import comb

API = "http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=300"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

# =========================================
# 数据获取
# =========================================
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

# =========================================
# 评分算法（与页面JS一致）
# =========================================
def ema(seq, alpha=0.5):
    if not seq: return 0
    seq_rev = seq[::-1]
    e = seq_rev[0]
    for v in seq[1:]: e = alpha * v + (1-alpha) * e
    return e

def score_top20(data):
    """返回20个评分最高的号码"""
    recent = data[:30]
    freq = {n:0 for n in range(1, 81)}
    for d in recent:
        for n in get_nums(d):
            if 1 <= n <= 80: freq[n] += 1
    # 近5期双倍
    for ri in range(min(5, len(recent))):
        for n in get_nums(recent[ri]):
            if 1 <= n <= 80: freq[n] += 2
    
    # EMA
    ema_scores = {}
    for n in range(1, 81):
        seq = [1 if n in get_nums(d) else 0 for d in recent]
        ema_scores[n] = ema(seq, 0.5)
    
    # 遗漏
    miss = {}
    for n in range(1, 81):
        for i, d in enumerate(recent):
            if n in get_nums(d): miss[n] = i; break
        else: miss[n] = len(recent)
    
    # 杀号
    kills = sorted((n for n in range(1,81) if freq[n]==0 and miss[n]>=15), key=lambda n: -miss[n])[:5]
    kill_set = set(kills)
    
    # 热号
    hot = sorted(range(1,81), key=lambda n: -freq[n])
    clean_hots = [n for n in hot if n not in kill_set]
    
    # 综合评分
    scores = {}
    for n in range(1, 81):
        if n in kill_set: continue
        s = freq[n] * 2 + ema_scores[n] * 15
        if 1 <= miss.get(n,100) <= 6: s += 2
        if n in clean_hots and clean_hots.index(n) < min(15, len(clean_hots)): s += 3
        for ri in range(min(5, len(recent))):
            if n in get_nums(recent[ri]): s += 2; break
        if n % 2 == 1: s += 1  # 奇数加分
        scores[n] = s
    
    ranked = sorted(scores, key=lambda n: -scores[n])[:20]
    return ranked

# =========================================
# 奖金计算
# =========================================
# 选五胆拖 (4胆 + 16拖): C(16,1) = 16注, 32元/期
# 选六胆拖 (4胆 + 16拖): C(16,2) = 120注, 240元/期

PRIZE5 = {0:0, 1:0, 2:0, 3:3, 4:21, 5:1000}  # 选五奖金
PRIZE6 = {0:0, 1:0, 2:0, 3:3, 4:10, 5:30, 6:3000}  # 选六奖金

def calc_xuan5_4dan(d_hit, t_hit):
    """
    选五胆拖 4胆+16拖
    每注 = 4胆 + 1拖, 共16注
    选到中奖拖码的注数: C(t_hit,1) -> 中 d_hit+1 个
    选到未中奖拖码的注数: 16-t_hit -> 中 d_hit 个
    """
    win_5 = t_hit * PRIZE5.get(d_hit + 1, 0)       # d_hit+1个
    win_4 = (16 - t_hit) * PRIZE5.get(d_hit, 0)    # d_hit个
    return win_5 + win_4

def calc_xuan6_4dan(d_hit, t_hit):
    """
    选六胆拖 4胆+16拖
    每注 = 4胆 + 2拖, 共 C(16,2) = 120注
    k=0: 2个拖码都没中 -> C(t_hit,0)×C(16-t_hit,2) 注 -> 中 d_hit 个
    k=1: 1个拖码中了 -> C(t_hit,1)×C(16-t_hit,1) 注 -> 中 d_hit+1 个
    k=2: 2个拖码都中 -> C(t_hit,2)×C(16-t_hit,0) 注 -> 中 d_hit+2 个
    """
    total = 0
    for k in range(3):  # k = 拖码中奖个数
        ways = comb(t_hit, k) * comb(16 - t_hit, 2 - k)
        prize = PRIZE6.get(d_hit + k, 0)
        total += ways * prize
    return total

# =========================================
# 主流程
# =========================================
def main():
    print("=" * 70)
    print("🎯 快乐8 4胆拖 真实收益模拟（从API拉数据）")
    print("=" * 70)
    
    # 获取数据
    print("\n📡 正在从灰鸟API获取实时数据...")
    d = fetch()
    items = d["data"]["data"]["list"]
    data = parse(items)
    print(f"  ✅ 获取成功: {len(data)} 期数据")
    print(f"  📅 最新: 第{data[0]['p']}期 ({data[0]['d']})")
    print(f"  📅 最旧: 第{data[-1]['p']}期 ({data[-1]['d']})")
    
    # =========================================
    # 回测
    # =========================================
    print("\n" + "=" * 70)
    print("📊 一、4胆拖回测（30期滑动窗口, 20码池中取前4做胆, 剩16做拖）")
    print("=" * 70)
    
    total = 0
    dantuo_hits = []    # (d_hit, t_hit) 列表
    all_20_hits = []    # 20码命中数
    
    for i in range(30, len(data)):
        past = data[i-30:i]
        draw = data[i]
        drawn = set(get_nums(draw))
        
        top20 = score_top20(past)
        dan = top20[:4]
        tuo = [n for n in top20 if n not in dan]  # 16个拖码
        
        d_hit = sum(1 for n in dan if n in drawn)
        t_hit = sum(1 for n in tuo if n in drawn)
        
        dantuo_hits.append((d_hit, t_hit))
        all_20_hits.append(sum(1 for n in top20 if n in drawn))
        total += 1
    
    print(f"\n  📊 回测期数: {total} 期")
    
    # ---- 胆码命中分布 ----
    print(f"\n  📍 胆码(前4)命中分布:")
    dh_dist = Counter(h[0] for h in dantuo_hits)
    print(f"  {'胆中':>5} | {'期数':>6} | {'占比':>8} | 柱状图")
    print(f"  {'-'*55}")
    for h in range(4, -1, -1):
        cnt = dh_dist.get(h, 0)
        if cnt > 0:
            bar = "█" * max(1, int(cnt / total * 80))
            print(f"  {h:>5}个 | {cnt:>6} | {cnt/total*100:>7.2f}% | {bar}")
    
    d_avg = sum(h[0] for h in dantuo_hits) / total
    d_ge1 = sum(1 for h in dantuo_hits if h[0] >= 1) / total * 100
    d_ge2 = sum(1 for h in dantuo_hits if h[0] >= 2) / total * 100
    d_ge3 = sum(1 for h in dantuo_hits if h[0] >= 3) / total * 100
    d_eq4 = sum(1 for h in dantuo_hits if h[0] == 4) / total * 100
    print(f"\n  📈 统计: 平均胆中 {d_avg:.2f} 个")
    print(f"         ≥1个: {d_ge1:.1f}%")
    print(f"         ≥2个: {d_ge2:.1f}%")
    print(f"         ≥3个: {d_ge3:.1f}%")
    print(f"         =4个: {d_eq4:.4f}%")
    
    # ---- 20码命中分布 ----
    print(f"\n  📍 20码池命中分布:")
    h20_dist = Counter(min(h, 20) for h in all_20_hits)
    print(f"  {'命中':>5} | {'期数':>6} | {'占比':>8} | 柱状图")
    print(f"  {'-'*55}")
    for h in range(20, -1, -1):
        cnt = h20_dist.get(h, 0)
        if cnt > 0:
            bar = "█" * max(1, int(cnt / total * 80))
            print(f"  {h:>5}个 | {cnt:>6} | {cnt/total*100:>7.2f}% | {bar}")
    
    h20_avg = sum(all_20_hits) / total
    h20_max = max(all_20_hits)
    print(f"\n  📈 20码池: 平均 {h20_avg:.2f} 个 | 最高 {h20_max} 个")
    
    # =========================================
    # 二、选五胆拖收益模拟
    # =========================================
    print("\n" + "=" * 70)
    print("📊 二、选五胆拖（4胆+16拖）收益模拟")
    print("   每期 C(16,1)=16注 | 每注2元 | 每期成本32元")
    print("=" * 70)
    
    cost5 = 32  # 每期
    total_cost5 = total * cost5
    total_prize5 = 0
    prize5_detail = []  # (期号, d_hit, t_hit, 奖金, 累计)
    period_prizes = []
    
    for idx, (d_hit, t_hit) in enumerate(dantuo_hits):
        prize = calc_xuan5_4dan(d_hit, t_hit)
        period_prizes.append(prize)
        total_prize5 += prize
    
    net5 = total_prize5 - total_cost5
    roi5 = total_prize5 / total_cost5 * 100 if total_cost5 > 0 else 0
    
    print(f"\n  投注方案: 4胆+16拖 选五胆拖")
    print(f"  每期注数: 16注 | 每期成本: 32元")
    print(f"  回测期数: {total}期")
    print(f"  ─────────────────────────────────")
    print(f"  总投入:      {total_cost5:>8,.0f} 元")
    print(f"  总奖金:      {total_prize5:>8,.0f} 元")
    print(f"  净盈亏:      {'+' if net5>=0 else ''}{net5:>8,.0f} 元")
    print(f"  回报率:      {roi5:>7.2f}%")
    print(f"  年均回报率:  {roi5*total/365:.1f}%（按{total}期≈{total/365:.1f}年）")
    
    # 中奖明细
    print(f"\n  📋 选五中奖明细:")
    prize5_dist = Counter()
    for d_hit, t_hit in dantuo_hits:
        p = calc_xuan5_4dan(d_hit, t_hit)
        if p > 0:
            prize5_dist[(d_hit, t_hit)] += 1
    
    print(f"  {'胆码中':>6} | {'拖码中':>6} | {'单期奖金':>8} | {'中奖期数':>8} | {'小计':>10}")
    print(f"  {'-'*55}")
    total_win_5 = 0
    for (d, t), cnt in sorted(prize5_dist.items(), key=lambda x:-x[0][0]):
        p = calc_xuan5_4dan(d, t)
        total_win_5 += p * cnt
        print(f"  {d:>6} | {t:>6} | {p:>8,} | {cnt:>8} | {p*cnt:>10,}")
    print(f"  {'合计':>14} | {'':>6} | {'':>8} | {'':>8} | {total_prize5:>10,}")
    
    win5_cnt = sum(1 for p in period_prizes if p > 0)
    lose5_cnt = total - win5_cnt
    print(f"\n  盈利期数: {win5_cnt}/{total} ({win5_cnt/total*100:.1f}%)")
    print(f"  亏损期数: {lose5_cnt}/{total} ({lose5_cnt/total*100:.1f}%)")
    
    # =========================================
    # 三、选六胆拖收益模拟
    # =========================================
    print("\n" + "=" * 70)
    print("📊 三、选六胆拖（4胆+16拖）收益模拟")
    print("   每期 C(16,2)=120注 | 每注2元 | 每期成本240元")
    print("=" * 70)
    
    cost6 = 240  # 每期
    total_cost6 = total * cost6
    total_prize6 = 0
    period_prizes6 = []
    
    for d_hit, t_hit in dantuo_hits:
        prize = calc_xuan6_4dan(d_hit, t_hit)
        period_prizes6.append(prize)
        total_prize6 += prize
    
    net6 = total_prize6 - total_cost6
    roi6 = total_prize6 / total_cost6 * 100 if total_cost6 > 0 else 0
    
    print(f"\n  投注方案: 4胆+16拖 选六胆拖")
    print(f"  每期注数: 120注 | 每期成本: 240元")
    print(f"  回测期数: {total}期")
    print(f"  ─────────────────────────────────")
    print(f"  总投入:      {total_cost6:>8,.0f} 元")
    print(f"  总奖金:      {total_prize6:>8,.0f} 元")
    print(f"  净盈亏:      {'+' if net6>=0 else ''}{net6:>8,.0f} 元")
    print(f"  回报率:      {roi6:>7.2f}%")
    
    # 中奖明细
    print(f"\n  📋 选六中奖明细:")
    prize6_dist = Counter()
    for d_hit, t_hit in dantuo_hits:
        p = calc_xuan6_4dan(d_hit, t_hit)
        if p > 0:
            prize6_dist[(d_hit, t_hit)] += 1
    
    print(f"  {'胆码中':>6} | {'拖码中':>6} | {'单期奖金':>10} | {'中奖期数':>8} | {'小计':>12}")
    print(f"  {'-'*60}")
    for (d, t), cnt in sorted(prize6_dist.items(), key=lambda x:-x[0][0]):
        p = calc_xuan6_4dan(d, t)
        print(f"  {d:>6} | {t:>6} | {p:>10,} | {cnt:>8} | {p*cnt:>12,}")
    print(f"  {'合计':>14} | {'':>6} | {'':>10} | {'':>8} | {total_prize6:>12,}")
    
    win6_cnt = sum(1 for p in period_prizes6 if p > 0)
    lose6_cnt = total - win6_cnt
    print(f"\n  盈利期数: {win6_cnt}/{total} ({win6_cnt/total*100:.1f}%)")
    print(f"  亏损期数: {lose6_cnt}/{total} ({lose6_cnt/total*100:.1f}%)")
    
    # =========================================
    # 四、对比总结
    # =========================================
    print("\n" + "=" * 70)
    print("📊 四、选五 vs 选六 4胆拖对比")
    print("=" * 70)
    
    print(f"\n  {'项目':>20} | {'选五4胆拖':>15} | {'选六4胆拖':>15}")
    print(f"  {'-'*55}")
    print(f"  {'每期注数':>20} | {'16注':>15} | {'120注':>15}")
    print(f"  {'每期成本':>20} | {'32元':>15} | {'240元':>15}")
    print(f"  {'回测期数':>20} | {total:>15} | {total:>15}")
    print(f"  {'总投入':>20} | {total_cost5:>15,} | {total_cost6:>15,}")
    print(f"  {'总奖金':>20} | {total_prize5:>15,} | {total_prize6:>15,}")
    print(f"  {'净盈亏':>20} | {'+' if net5>=0 else ''}{net5:>14,} | {'+' if net6>=0 else ''}{net6:>14,}")
    print(f"  {'回报率':>20} | {roi5:>14.2f}% | {roi6:>14.2f}%")
    print(f"  {'盈利期数占比':>20} | {win5_cnt/total*100:>14.1f}% | {win6_cnt/total*100:>14.1f}%")
    print(f"  {'平均每期奖金':>20} | {total_prize5/total:>14.2f} | {total_prize6/total:>14.2f}")
    print(f"  {'平均每期亏损':>20} | {total_cost5/total - total_prize5/total:>14.2f} | {total_cost6/total - total_prize6/total:>14.2f}")
    
    # =========================================
    # 五、真实案例分析（取最近5期）
    # =========================================
    print("\n" + "=" * 70)
    print("📊 五、最近5期实战明细（验证计算结果）")
    print("=" * 70)
    
    print(f"\n  {'期号':>10} | {'胆码(前4)':>24} | {'开奖号码':>50} | {'胆中':>4} | {'拖中':>4} | {'选五奖金':>8} | {'选六奖金':>8}")
    print(f"  {'-'*120}")
    for i in range(total-5, total):
        idx = i + 30  # data索引偏移
        draw = data[idx]
        drawn = set(get_nums(draw))
        top20 = score_top20(data[idx-30:idx])
        dan = top20[:4]
        tuo = [n for n in top20 if n not in dan]
        d_hit, t_hit = dantuo_hits[i]
        
        dan_str = " ".join(f"{n:02d}" for n in dan)
        draw_str = " ".join(f"{n:02d}" for n in sorted(drawn)[:20])
        p5 = calc_xuan5_4dan(d_hit, t_hit)
        p6 = calc_xuan6_4dan(d_hit, t_hit)
        print(f"  {draw['p']:>10} | {dan_str:>24} | {draw_str:>50} | {d_hit:>4} | {t_hit:>4} | {p5:>8,} | {p6:>8,}")
    
    print("\n" + "=" * 70)
    if net5 >= 0:
        print(f"  📌 结论: 选五4胆拖 {'盈利' if net5>0 else '保本'}，净盈亏 {'+'+str(net5) if net5>0 else str(net5)}元")
    else:
        print(f"  📌 结论: 选五4胆拖 亏损，净盈亏 {net5}元（平均每期亏 {total_cost5/total - total_prize5/total:.2f}元）")
    if net6 >= 0:
        print(f"  📌 结论: 选六4胆拖 {'盈利' if net6>0 else '保本'}，净盈亏 {'+'+str(net6) if net6>0 else str(net6)}元")
    else:
        print(f"  📌 结论: 选六4胆拖 亏损，净盈亏 {net6}元（平均每期亏 {total_cost6/total - total_prize6/total:.2f}元）")
    print(f"  ⚠️  以上数据完全基于灰鸟API真实历史数据，算法与页面一致")
    print("=" * 70)

if __name__ == "__main__":
    main()
