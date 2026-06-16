"""
快乐8 胆拖对比: 2胆 vs 3胆 vs 4胆 真实收益模拟
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

PRIZE5 = {0:0,1:0,2:0,3:3,4:21,5:1000}
PRIZE6 = {0:0,1:0,2:0,3:3,4:10,5:30,6:3000}

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
def ema(seq, alpha=0.5):
    if not seq: return 0
    seq_rev = seq[::-1]
    e = seq_rev[0]
    for v in seq[1:]: e = alpha * v + (1-alpha) * e
    return e

def score_top20(data):
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
    ranked = sorted(scores, key=lambda n: -scores[n])[:20]
    return ranked

# =========================================
# 通用胆拖奖金计算
# d_hit = 胆码中奖数, t_hit = 拖码中奖数
# dan_cnt = 胆码数量, need = 每注需要选几个号码(5或6)
# =========================================
def calc_dantuo(d_hit, t_hit, dan_cnt, need, prize_table):
    """
    胆拖奖金计算:
    dan_cnt个胆码 + (need-dan_cnt)个拖码 组成一注
    拖码池大小 = 20 - dan_cnt
    每注从拖码池选 need-dan_cnt 个
    k = 选到的拖码中中奖的个数
    中奖号码数 = d_hit + k
    """
    tuo_pick = need - dan_cnt  # 每注选几个拖码
    tuo_total = 20 - dan_cnt   # 拖码池大小
    total = 0
    for k in range(tuo_pick + 1):
        if k > t_hit: break  # 不可能选到比实际中奖更多的拖码
        if tuo_pick - k > tuo_total - t_hit: continue  # 没有足够的未中奖拖码可填
        ways = comb(t_hit, k) * comb(tuo_total - t_hit, tuo_pick - k)
        prize = prize_table.get(min(d_hit + k, max(prize_table.keys())), 0)
        total += ways * prize
    return total

# =========================================
def main():
    print("=" * 80)
    print("🎯 快乐8 胆拖对比: 2胆 vs 3胆 vs 4胆 | 选五/选六 真实收益模拟")
    print("=" * 80)
    
    # 获取数据
    print("\n📡 正在从灰鸟API获取实时数据...")
    d = fetch()
    items = d["data"]["data"]["list"]
    data = parse(items)
    print(f"  ✅ 获取成功: {len(data)} 期数据")
    print(f"  📅 最新: 第{data[0]['p']}期 ({data[0]['d']})")
    print(f"  📅 最旧: 第{data[-1]['p']}期 ({data[-1]['d']})")
    
    total = 0
    # 对于每种胆数，存储 [(d_hit, t_hit)] 列表
    all_hits = {dc: [] for dc in [2, 3, 4]}
    
    for i in range(30, len(data)):
        past = data[i-30:i]
        draw = data[i]
        drawn = set(get_nums(draw))
        top20 = score_top20(past)
        
        for dc in [2, 3, 4]:
            dan = top20[:dc]
            tuo = [n for n in top20 if n not in dan]
            d_hit = sum(1 for n in dan if n in drawn)
            t_hit = sum(1 for n in tuo if n in drawn)
            all_hits[dc].append((d_hit, t_hit))
        
        total += 1
    
    print(f"\n  📊 回测期数: {total} 期")
    
    # =========================================
    # 各胆数命中分布
    # =========================================
    for dc in [2, 3, 4]:
        print(f"\n  {'─'*60}")
        print(f"  📍 {dc}胆 命中分布:")
        hits = [h[0] for h in all_hits[dc]]
        dist = Counter(hits)
        print(f"  {'胆中':>5} | {'期数':>6} | {'占比':>8} | 柱状图")
        print(f"  {'─'*50}")
        for h in range(dc, -1, -1):
            cnt = dist.get(h, 0)
            bar = "█" * max(1, int(cnt / total * 60))
            print(f"  {h:>5}个 | {cnt:>6} | {cnt/total*100:>7.2f}% | {bar}")
        avg = sum(hits) / total
        print(f"  📈 平均: {avg:.2f}个 | ≥1: {sum(1 for h in hits if h>=1)/total*100:.1f}% | ≥{dc-1}: {sum(1 for h in hits if h>=dc-1)/total*100:.1f}% | ={dc}: {sum(1 for h in hits if h==dc)/total*100:.2f}%")
    
    # =========================================
    # 收益对比表
    # =========================================
    print("\n" + "=" * 80)
    print("📊 胆拖收益对比总表")
    print("=" * 80)
    
    # 表头
    header = f"{'胆数':>4} | {'玩法':>4} | {'方案':>18} | {'每期成本':>8} | {'总投入':>10} | {'总奖金':>10} | {'净盈亏':>10} | {'回报率':>8} | {'盈利期数':>8}"
    sep = "─" * len(header)
    print(f"\n  {sep}")
    print(f"  {header}")
    print(f"  {sep}")
    
    results = {}
    for dc in [2, 3, 4]:
        configs = [(5, "选五", PRIZE5), (6, "选六", PRIZE6)]
        for need, play_name, prize_tbl in configs:
            tuo_cnt = 20 - dc
            tuo_pick = need - dc
            bets_per = comb(tuo_cnt, tuo_pick)
            cost_per = bets_per * 2
            
            total_prize = 0
            win_cnt = 0
            for d_hit, t_hit in all_hits[dc]:
                p = calc_dantuo(d_hit, t_hit, dc, need, prize_tbl)
                total_prize += p
                if p > 0: win_cnt += 1
            
            total_cost = total * cost_per
            net = total_prize - total_cost
            roi = total_prize / total_cost * 100 if total_cost > 0 else 0
            
            results[(dc, need)] = {
                "cost_per": cost_per, "bets": bets_per,
                "total_cost": total_cost, "total_prize": total_prize,
                "net": net, "roi": roi, "win_cnt": win_cnt
            }
            
            scheme = f"{dc}胆+{tuo_cnt}拖 C({tuo_cnt},{tuo_pick})={bets_per}注"
            print(f"  {dc:>4} | {play_name:>4} | {scheme:>18} | {cost_per:>7}元 | {total_cost:>9,} | {total_prize:>9,} | {'+' if net>=0 else ''}{net:>9,} | {roi:>7.2f}% | {win_cnt:>4}/{total}")
    
    print(f"  {sep}")
    
    # =========================================
    # 各胆数最佳玩法推荐
    # =========================================
    print(f"\n  {'─'*80}")
    print(f"  📋 各胆数推荐玩法:")
    
    for dc in [2, 3, 4]:
        # 找到这个胆数下回报率最高的玩法
        best_need = max([5, 6], key=lambda n: results[(dc, n)]["roi"])
        r = results[(dc, best_need)]
        play_name = "选五" if best_need == 5 else "选六"
        print(f"    {dc}胆 → {play_name}: 每期{r['cost_per']}元 | 净亏{r['net']:,}元 | 回报率{r['roi']:.1f}% | 盈利{r['win_cnt']}/{total}期")
    
    # =========================================
    # 选出最优方案
    # =========================================
    print(f"\n  {'─'*80}")
    # 按每期预期亏损排序（越小越好）
    sorted_by_net = sorted(results.values(), key=lambda r: r["net"])
    best = sorted_by_net[-1]  # 亏损最小（即净盈亏最大）
    best_pair = None
    for k, v in results.items():
        if v["total_prize"] == best["total_prize"] and v["cost_per"] == best["cost_per"]:
            best_pair = k
            break
    
    if best_pair:
        dc, need = best_pair
        play_name = "选五" if need == 5 else "选六"
        r = results[best_pair]
        print(f"  🏆 相对最优: {dc}胆+{20-dc}拖 {play_name}")
        print(f"     每期{r['bets']}注/{r['cost_per']}元 | 净亏{r['net']:,}元 | 回报率{r['roi']:.1f}%")
        print(f"     但注意: 这只是亏损最小化，没有一种方案长期盈利")
    
    # 每期平均亏损对比
    print(f"\n  {'─'*80}")
    print(f"  📊 每期预期亏损对比（越低越好）:")
    print(f"  {'胆数':>4} | {'选五亏/期':>10} | {'选五回报率':>10} | {'选六亏/期':>10} | {'选六回报率':>10}")
    print(f"  {'─'*55}")
    for dc in [2, 3, 4]:
        r5 = results[(dc, 5)]
        r6 = results[(dc, 6)]
        loss5 = r5["cost_per"] - r5["total_prize"] / total
        loss6 = r6["cost_per"] - r6["total_prize"] / total
        print(f"  {dc:>4}胆 | {loss5:>9.2f}元 | {r5['roi']:>9.2f}% | {loss6:>9.2f}元 | {r6['roi']:>9.2f}%")
    
    # =========================================
    # 结论
    # =========================================
    print(f"\n  {'='*80}")
    print(f"  📌 结论（基于{total}期真实数据）:")
    
    # 找出最不亏损的方案
    best_net = max(r["net"] for r in results.values())  # 最大净盈亏
    best_roi = max(r["roi"] for r in results.values())  # 最高回报率
    best_win_rate = max(r["win_cnt"] / total * 100 for r in results.values())
    
    print(f"    1. 所有方案长期均亏损，无一能盈利")
    best_overall = max(results.keys(), key=lambda k: results[k]["roi"])
    dc, need = best_overall
    r = results[best_overall]
    play_name = "选五" if need == 5 else "选六"
    print(f"    2. 回报率最高: {dc}胆+{20-dc}拖 {play_name} ({r['roi']:.1f}%)")
    
    min_loss_dc = min([2,3,4], key=lambda dc: results[(dc,5)]["cost_per"] - results[(dc,5)]["total_prize"]/total)
    min_loss = results[(min_loss_dc,5)]["cost_per"] - results[(min_loss_dc,5)]["total_prize"]/total
    print(f"    3. 每期亏损最小: {min_loss_dc}胆 选五胆拖（每期亏{min_loss:.2f}元）")
    print(f"    4. 核心瓶颈: 算法从80个号中预测20个尚可(平均{sum(h[0] for h in all_hits[4])/total:.2f}个/4胆)，")
    print(f"       但要从20个号中精准选出前{min_loss_dc}个做胆码，命中率不足以覆盖投注成本")
    print(f"  {'='*80}")

if __name__ == "__main__":
    main()
