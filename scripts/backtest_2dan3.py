"""
快乐8 2胆拖选三 真实收益模拟
数据来源: api.huiniao.top
胆码: 置信度筛选(低方差优先)
"""
import json, urllib.request, math
from collections import Counter
from math import comb

API = "http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=300"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

PRIZE3 = {0:0,1:0,2:3,3:53}
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

def score_all_numbers(data):
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
    return ranked, freq

def select_dantuo_stable(ranked, data, dc):
    """置信度筛选: 从20码中选dc个稳定胆码"""
    top20 = ranked[:20]
    recent = data[:30]
    win = min(30, len(recent))
    stability = {}
    for n in top20:
        pat = [1 if n in get_nums(d) else 0 for d in recent[:win]]
        avg = sum(pat) / win if win > 0 else 0
        var = sum((v - avg)**2 for v in pat) / win if win > 0 else 0
        f = sum(pat)
        if var > 0 and f > 0:
            stability[n] = f / math.sqrt(var)
        elif var == 0 and f > 0:
            stability[n] = f * 100
        else:
            stability[n] = 0
    # 按稳定度降序, 相同则按原始排名
    stable_ranked = sorted(top20, key=lambda n: (-stability[n], ranked.index(n)))
    return stable_ranked[:dc]

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

def main():
    print("=" * 80)
    print("🎯 快乐8 2胆拖 三种玩法对比: 选三 vs 选五 vs 选六")
    print("   胆码: 置信度筛选(低方差优先)")
    print("=" * 80)
    
    print("\n📡 正在从灰鸟API获取实时数据...")
    d = fetch()
    items = d["data"]["data"]["list"]
    data = parse(items)
    print(f"  ✅ 获取成功: {len(data)} 期数据")
    print(f"  📅 最新: 第{data[0]['p']}期 ({data[0]['d']})")
    
    total = 0
    all_hits = []  # [(d_hit, t_hit)]
    
    for i in range(30, len(data)):
        past = data[i-30:i]
        draw = data[i]
        drawn = set(get_nums(draw))
        ranked, freq = score_all_numbers(past)
        dan = select_dantuo_stable(ranked, past, 2)
        tuo = [n for n in ranked[:20] if n not in dan]
        d_hit = sum(1 for n in dan if n in drawn)
        t_hit = sum(1 for n in tuo if n in drawn)
        all_hits.append((d_hit, t_hit))
        total += 1
    
    print(f"\n  📊 回测期数: {total} 期")
    
    # ---- 2胆命中分布 ----
    print(f"\n  📍 2胆(置信度筛选)命中分布:")
    dh_dist = Counter(h[0] for h in all_hits)
    print(f"  {'胆中':>5} | {'期数':>6} | {'占比':>8} | 柱状图")
    print(f"  {'─'*50}")
    for h in range(2, -1, -1):
        cnt = dh_dist.get(h, 0)
        bar = "█" * max(1, int(cnt / total * 60))
        print(f"  {h:>5}个 | {cnt:>6} | {cnt/total*100:>7.2f}% | {bar}")
    
    # 按胆码命中分组的拖码平均命中
    print(f"\n  📍 拖码命中(按胆码分组):")
    print(f"  {'胆中':>5} | {'期数':>6} | {'平均拖中':>8} | {'常见范围':>10}")
    print(f"  {'─'*40}")
    for h in range(2, -1, -1):
        items = [h2[1] for h2 in all_hits if h2[0] == h]
        if items:
            avg_t = sum(items) / len(items)
            # 25th-75th percentile
            s_items = sorted(items)
            lo = s_items[len(items)//4] if items else 0
            hi = s_items[len(items)*3//4] if items else 0
            print(f"  {h:>5}个 | {len(items):>6} | {avg_t:>7.2f}个 | {lo}-{hi}")
    
    # =========================================
    # 三种玩法对比
    # =========================================
    configs = [
        ("选三", 3, PRIZE3),
        ("选五", 5, PRIZE5),
        ("选六", 6, PRIZE6),
    ]
    
    print(f"\n{'='*80}")
    print(f"📊 2胆拖 三种玩法收益对比 (2胆+18拖, 置信度胆码)")
    print(f"{'='*80}")
    
    print(f"\n{'─'*80}")
    header = f"{'玩法':>6} | {'每期注数':>8} | {'每期成本':>8} | {'总投入':>10} | {'总奖金':>10} | {'净盈亏':>10} | {'回报率':>8} | {'盈利期数':>10} | {'每期亏':>8}"
    print(f"  {header}")
    print(f"  {'─'*80}")
    
    results = {}
    for play_name, need, prize_tbl in configs:
        tuo_pick = need - 2
        tuo_total = 18
        bets_per = comb(tuo_total, tuo_pick)
        cost_per = bets_per * 2
        
        total_prize = 0
        win_cnt = 0
        prizes = []
        for d_hit, t_hit in all_hits:
            p = calc_dantuo(d_hit, t_hit, 2, need, prize_tbl)
            total_prize += p
            prizes.append(p)
            if p > 0: win_cnt += 1
        
        total_cost = total * cost_per
        net = total_prize - total_cost
        roi = total_prize / total_cost * 100 if total_cost > 0 else 0
        loss_per = total_cost/total - total_prize/total
        
        results[need] = {
            "bets": bets_per, "cost_per": cost_per,
            "total_cost": total_cost, "total_prize": total_prize,
            "net": net, "roi": roi, "win_cnt": win_cnt,
            "loss_per": loss_per, "prizes": prizes
        }
        
        scheme = f"C({tuo_total},{tuo_pick})={bets_per}注"
        print(f"  {play_name:>6} | {scheme:>8} | {cost_per:>7}元 | {total_cost:>9,} | {total_prize:>9,} | {'+' if net>=0 else ''}{net:>9,} | {roi:>7.2f}% | {win_cnt:>3}/{total} | {loss_per:>7.2f}元")
    
    print(f"  {'─'*80}")
    
    # =========================================
    # 选三详细明细
    # =========================================
    print(f"\n{'='*80}")
    print(f"📊 2胆拖选三 详细奖金结构 (18注/期, 36元/期)")
    print(f"{'='*80}")
    
    # 胆码中2个的不同拖码情况
    print(f"\n  📋 当胆码中2个时:")
    print(f"  {'拖中':>4} | {'奖金':>6} | {'利润':>8} | {''  :>20}")
    print(f"  {'─'*40}")
    for t in range(0, 9):
        p = calc_dantuo(2, t, 2, 3, PRIZE3)
        profit = p - 36
        print(f"  {t:>4}个 | {p:>5}元 | {'+' if profit>=0 else ''}{profit:>6}元")
    
    print(f"\n  📋 当胆码中1个时:")
    print(f"  {'拖中':>4} | {'奖金':>6} | {'利润':>8}")
    print(f"  {'─'*30}")
    for t in range(0, 5):
        p = calc_dantuo(1, t, 2, 3, PRIZE3)
        profit = p - 36
        print(f"  {t:>4}个 | {p:>5}元 | {'+' if profit>=0 else ''}{profit:>6}元")
    
    # =========================================
    # 选三回测明细
    # =========================================
    print(f"\n  📋 选三 中奖明细(270期):")
    prize3_dist = Counter()
    for d_hit, t_hit in all_hits:
        p = calc_dantuo(d_hit, t_hit, 2, 3, PRIZE3)
        if p > 0:
            prize3_dist[(d_hit, t_hit)] += 1
    
    print(f"  {'胆码中':>6} | {'拖码中':>6} | {'单期奖金':>8} | {'中奖期数':>8} | {'小计':>10}")
    print(f"  {'─'*50}")
    for (d, t), cnt in sorted(prize3_dist.items(), key=lambda x:-x[0][0]):
        p = calc_dantuo(d, t, 2, 3, PRIZE3)
        print(f"  {d:>6} | {t:>6} | {p:>8} | {cnt:>8} | {p*cnt:>10,}")
    print(f"  {'合计':>14} | {'':>6} | {'':>8} | {'':>8} | {results[3]['total_prize']:>10,}")
    
    win3 = results[3]["win_cnt"]
    print(f"\n  盈利期数: {win3}/{total} ({win3/total*100:.1f}%)")
    print(f"  亏损期数: {total-win3}/{total} ({(total-win3)/total*100:.1f}%)")
    
    # =========================================
    # 全部玩法扫一遍 (2-4胆 × 选三/选五/选六)
    # =========================================
    print(f"\n{'='*80}")
    print(f"📊 全部玩法扫一遍 (2胆/3胆/4胆 × 选三/选五/选六)")
    print(f"{'='*80}")
    
    print(f"\n{'─'*90}")
    h = f"{'胆数':>4} | {'玩法':>4} | {'方案':>16} | {'每期成本':>8} | {'总投入':>10} | {'总奖金':>10} | {'净盈亏':>10} | {'回报率':>8} | {'盈利':>8}"
    print(f"  {h}")
    print(f"  {'─'*90}")
    
    for dc in [2, 3, 4]:
        for need in [3, 5, 6]:
            if need <= dc: continue  # 胆码数不能大于需要选的号码数
            
            # 重新取胆
            d_hits_run = []
            for i in range(30, len(data)):
                past = data[i-30:i]
                draw = data[i]
                drawn = set(get_nums(draw))
                ranked, freq = score_all_numbers(past)
                dan = select_dantuo_stable(ranked, past, dc)
                tuo = [n for n in ranked[:20] if n not in dan]
                d_hit = sum(1 for n in dan if n in drawn)
                t_hit = sum(1 for n in tuo if n in drawn)
                d_hits_run.append((d_hit, t_hit))
            
            prize_tbl = {3: PRIZE3, 5: PRIZE5, 6: PRIZE6}[need]
            tuo_pick = need - dc
            bets = comb(20-dc, tuo_pick)
            cost_p = bets * 2
            
            tp = sum(calc_dantuo(d, t, dc, need, prize_tbl) for d, t in d_hits_run)
            tc = total * cost_p
            net = tp - tc
            roi = tp / tc * 100 if tc > 0 else 0
            wc = sum(1 for d, t in d_hits_run if calc_dantuo(d, t, dc, need, prize_tbl) > 0)
            
            scheme = f"{dc}胆+{20-dc}拖"
            play_n = {3:"选三",5:"选五",6:"选六"}[need]
            print(f"  {dc:>4} | {play_n:>4} | {scheme:>16} | {cost_p:>7}元 | {tc:>9,} | {tp:>9,} | {'+' if net>=0 else ''}{net:>9,} | {roi:>7.2f}% | {wc:>3}/{total}")
    
    print(f"  {'─'*90}")
    
    # =========================================
    # 结论
    # =========================================
    print(f"\n{'='*80}")
    r3 = results[3]
    r5 = results[5]
    r6 = results[6]
    print(f"📌 2胆拖三种玩法结论:")
    print(f"  选三: 每期{r3['cost_per']}元 | 净亏{r3['net']:,}元 | 回报率{r3['roi']:.1f}% | 盈利{r3['win_cnt']}/{total}期")
    print(f"  选五: 每期{r5['cost_per']}元 | 净亏{r5['net']:,}元 | 回报率{r5['roi']:.1f}% | 盈利{r5['win_cnt']}/{total}期")
    print(f"  选六: 每期{r6['cost_per']}元 | 净亏{r6['net']:,}元 | 回报率{r6['roi']:.1f}% | 盈利{r6['win_cnt']}/{total}期")
    
    # 找最优组合
    all_combos = []
    for dc in [2, 3, 4]:
        d_hits_run = []
        for i in range(30, len(data)):
            past = data[i-30:i]
            draw = data[i]
            drawn = set(get_nums(draw))
            ranked, freq = score_all_numbers(past)
            dan = select_dantuo_stable(ranked, past, dc)
            tuo = [n for n in ranked[:20] if n not in dan]
            d_hit = sum(1 for n in dan if n in drawn)
            t_hit = sum(1 for n in tuo if n in drawn)
            d_hits_run.append((d_hit, t_hit))
        for need in [3, 5, 6]:
            if need <= dc: continue
            prize_tbl = {3: PRIZE3, 5: PRIZE5, 6: PRIZE6}[need]
            tp = sum(calc_dantuo(d, t, dc, need, prize_tbl) for d, t in d_hits_run)
            tc = total * comb(20-dc, need-dc) * 2
            roi = tp / tc * 100 if tc > 0 else 0
            loss_per = tc/total - tp/total
            all_combos.append((roi, loss_per, dc, need, tp, tc))
    
    all_combos.sort(key=lambda x: -x[0])  # 按回报率降序
    print(f"\n🏆 回报率Top3组合:")
    for i, (roi, loss, dc, need, tp, tc) in enumerate(all_combos[:3]):
        play_n = {3:"选三",5:"选五",6:"选六"}[need]
        print(f"   {i+1}. {dc}胆+{20-dc}拖 {play_n}: 回报率{roi:.1f}% | 每期亏{loss:.2f}元 | 总投入{tc:,}元 总奖金{tp:,}元")
    
    all_combos.sort(key=lambda x: x[1])  # 按每期亏损升序
    print(f"\n🏆 每期亏损最小Top3:")
    for i, (roi, loss, dc, need, tp, tc) in enumerate(all_combos[:3]):
        play_n = {3:"选三",5:"选五",6:"选六"}[need]
        print(f"   {i+1}. {dc}胆+{20-dc}拖 {play_n}: 每期亏{loss:.2f}元 | 回报率{roi:.1f}% | 总投入{tc:,}元 总奖金{tp:,}元")

if __name__ == "__main__":
    main()
