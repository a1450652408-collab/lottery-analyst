"""
快乐8 6胆/7胆 命中概率 & 收益分析
"""
import json, urllib.request, math
from collections import Counter
from math import comb

API = "http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=300"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

PRIZE5 = {0:0,1:0,2:0,3:3,4:21,5:1000}
PRIZE6 = {0:0,1:0,2:0,3:3,4:10,5:30,6:3000}
PRIZE7 = {0:2,1:0,2:0,3:2,4:4,5:28,6:288,7:10000}
PRIZE8 = {0:2,1:0,2:0,3:2,4:4,5:10,6:66,7:550,8:50000}
PRIZE9 = {0:2,1:0,2:0,3:2,4:4,5:5,6:20,7:200,8:2000,9:300000}
PRIZE10 = {0:2,1:0,2:0,3:0,4:4,5:5,6:6,7:80,8:800,9:8000,10:5000000}

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
        data.append({"n": sorted(nums)})
    return data
def gn(d): return d.get("n", [])
def ema(s,a=0.5):
    if not s: return 0
    s_rev = s[::-1]
    e = s_rev[0]
    for v in s[1:]: e=a*v+(1-a)*e
    return e

def score_confidence(data):
    """页面一致的评分+置信度"""
    recent = data[:30]
    freq = {n:0 for n in range(1,81)}
    for d in recent:
        for n in gn(d):
            if 1<=n<=80: freq[n]+=1
    for ri in range(min(5, len(recent))):
        for n in gn(recent[ri]):
            if 1<=n<=80: freq[n]+=2
    ema_s = {}
    for n in range(1,81):
        seq = [1 if n in gn(d) else 0 for d in recent]
        ema_s[n] = ema(seq,0.5)
    miss = {}
    for n in range(1,81):
        for i,d in enumerate(recent):
            if n in gn(d): miss[n]=i; break
        else: miss[n]=len(recent)
    kills = sorted((n for n in range(1,81) if freq[n]==0 and miss.get(n,100)>=15), key=lambda n:-miss[n])[:5]
    ks = set(kills)
    hot = sorted(range(1,81), key=lambda n:-freq[n])
    ch = [n for n in hot if n not in ks]
    scores = {}
    for n in range(1,81):
        if n in ks: continue
        s = freq[n]*2 + ema_s[n]*15
        if 1<=miss.get(n,100)<=6: s+=2
        if n in ch and ch.index(n)<min(15,len(ch)): s+=3
        for ri in range(min(5,len(recent))):
            if n in gn(recent[ri]): s+=2; break
        if n%2==1: s+=1
        scores[n]=s
    ranked = sorted(scores, key=lambda n:-scores[n])[:20]
    # 置信度重排序
    win = min(30, len(recent))
    stab = {}
    for n in ranked:
        pat = [1 if n in gn(d) else 0 for d in recent[:win]]
        avg = sum(pat)/win if win>0 else 0
        var = sum((v-avg)**2 for v in pat)/win if win>0 else 0
        f = freq.get(n,0)
        if var>0 and f>0: stab[n]=f/math.sqrt(var)
        elif var==0 and f>0: stab[n]=f*100
        else: stab[n]=0
    stable = sorted(ranked, key=lambda n:(-stab[n], ranked.index(n)))
    return ranked, stable, freq

def calc_dantuo(d_hit, t_hit, dan_cnt, need, prize_table):
    tuo_pick = need - dan_cnt
    if tuo_pick <= 0:
        # 胆码已经够了, 不需要拖码
        return prize_table.get(min(d_hit, max(prize_table.keys())), 0)
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
    print("🎯 快乐8 6胆/7胆 命中概率 & 收益分析")
    print("   胆码: 置信度筛选")
    print("=" * 80)
    
    d = fetch(); items = d["data"]["data"]["list"]; data = parse(items)
    print(f"\n📡 数据: {len(data)}期")
    
    total = 0
    hits = {dc: [] for dc in [2,3,4,5,6,7,8,9]}
    for i in range(30, len(data)):
        past = data[i-30:i]; draw = data[i]; drawn = set(gn(draw))
        ranked, stable, freq = score_confidence(past)
        for dc in range(2,10):
            dan = stable[:dc]
            tuo = [n for n in ranked[:20] if n not in dan]
            d_hit = sum(1 for n in dan if n in drawn)
            t_hit = sum(1 for n in tuo if n in drawn)
            hits[dc].append((d_hit, t_hit))
        total += 1
    
    print(f"\n{'='*80}")
    
    for dc in [6, 7]:
        print(f"\n{'─'*80}")
        print(f"📊 {dc}胆 命中分布:")
        dh = Counter(h[0] for h in hits[dc])
        print(f"  {'胆中':>5} | {'期数':>6} | {'占比':>8}")
        print(f"  {'─'*30}")
        for h in range(dc, -1, -1):
            cnt = dh.get(h, 0)
            if cnt > 0:
                print(f"  {h:>5}个 | {cnt:>6} | {cnt/total*100:>7.2f}%")
        avg_d = sum(h[0] for h in hits[dc]) / total
        ge3 = sum(1 for h in hits[dc] if h[0] >= 3)
        ge4 = sum(1 for h in hits[dc] if h[0] >= 4)
        ge5 = sum(1 for h in hits[dc] if h[0] >= 5)
        print(f"\n  平均胆中: {avg_d:.2f}个")
        print(f"  ≥3个: {ge3/total*100:.1f}%")
        print(f"  ≥4个: {ge4/total*100:.1f}%")
        print(f"  ≥5个: {ge5/total*100:.1f}%")
        
        # 推荐玩法
        print(f"\n  📋 推荐玩法:")
        if dc == 6:
            configs = [
                ("选六(1注)", 6, PRIZE6, 0),
                ("选七(14注/28元)", 7, PRIZE7, 1),
                ("选八(91注/182元)", 8, PRIZE8, 2),
                ("选九(364注/728元)", 9, PRIZE9, 3),
                ("选十(1001注/2002元)", 10, PRIZE10, 4),
            ]
        elif dc == 7:
            configs = [
                ("选七(1注)", 7, PRIZE7, 0),
                ("选八(13注/26元)", 8, PRIZE8, 1),
                ("选九(78注/156元)", 9, PRIZE9, 2),
                ("选十(286注/572元)", 10, PRIZE10, 3),
            ]
        
        for name, need, pt, tuo_pick in configs[:3]:  # 只显示前3种
            if tuo_pick <= 0:
                bets = 1; cost_p = 2
            else:
                bets = comb(20-dc, tuo_pick); cost_p = bets * 2
            
            tp = sum(calc_dantuo(d,t,dc,need,pt) for d,t in hits[dc])
            tc = total * cost_p
            net = tp - tc
            roi = tp/tc*100 if tc>0 else 0
            win = sum(1 for d,t in hits[dc] if calc_dantuo(d,t,dc,need,pt) > 0)
            
            print(f"    {name}: 每期{cost_p}元 | 净亏{net:,}元 | 回报率{roi:.1f}% | 盈利{win}/{total}期")
            
            # 特定场景的奖金
            if dc == 6:
                # 6胆中4时的奖金
                for d_check in [4, 5, 6]:
                    items = [(t, calc_dantuo(d_check, t, dc, need, pt)) for d,t in hits[dc] if d == d_check]
                    if items:
                        avg_p = sum(p for _,p in items)/len(items)
                        max_p = max(p for _,p in items)
                        print(f"      其中{d_check}胆中: {len(items)}期, 平均奖金{avg_p:.0f}元, 最高{max_p}元")
            elif dc == 7:
                for d_check in [5, 6, 7]:
                    items = [(t, calc_dantuo(d_check, t, dc, need, pt)) for d,t in hits[dc] if d == d_check]
                    if items:
                        avg_p = sum(p for _,p in items)/len(items)
                        max_p = max(p for _,p in items)
                        print(f"      其中{d_check}胆中: {len(items)}期, 平均奖金{avg_p:.0f}元, 最高{max_p}元")

    print(f"\n{'='*80}")
    print("📌 结论:")
    for dc in [6, 7]:
        cnt4 = sum(1 for h in hits[dc] if h[0] >= 4)
        cnt5 = sum(1 for h in hits[dc] if h[0] >= 5)
        print(f"  {dc}胆中≥4: {cnt4/total*100:.1f}% (约{total//cnt4 if cnt4>0 else '--'}期/次)")
        print(f"  {dc}胆中≥5: {cnt5/total*100:.1f}% (约{total//cnt5 if cnt5>0 else '--'}期/次)")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()
