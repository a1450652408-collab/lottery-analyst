# -*- coding: utf-8 -*-
"""网格搜索：预警期 × 倍率 × 止损期，10个月真实回测找最优方案"""
import json
from itertools import combinations

with open('data/kl8_500.json', encoding='utf-8') as f:
    kl8 = json.load(f)

def compute_x3_picks(data, ym):
    x3Data = []
    for it in data:
        if not it or not it.get('d'): continue
        if it['d'][:7] < ym: x3Data.append(it)
        if len(x3Data) >= 50: break
    if len(x3Data) < 10: x3Data = data[:min(50,len(data))]
    period = len(x3Data)
    ema = {}
    for n in range(1,81):
        seq = [1 if n in it['n'] else 0 for it in x3Data]
        if not seq: ema[n]=0; continue
        e = seq[-1]
        for j in range(len(seq)-2,-1,-1): e = 0.5*seq[j]+0.5*e
        ema[n]=e
    R5,P5 = {n:0 for n in range(1,81)},{n:0 for n in range(1,81)}
    for j in range(min(10,period)):
        for n in x3Data[j]['n']:
            if j<5: R5[n]+=1
            else: P5[n]+=1
    mom = {n: max(-2,min(2,(R5[n]-P5[n])/max(P5[n],1))) for n in range(1,81)}
    freq30 = {n:0 for n in range(1,81)}
    for j in range(min(30,period)):
        for n in x3Data[j]['n']: freq30[n]+=1
    zones = [(1,20),(21,40),(41,60),(61,80)]
    win = min(30,len(x3Data))
    score = {n: ema[n]*5 + (min(freq30[n],win)/win)*3 + mom[n]*2 for n in range(1,81)}
    za = []
    for i,(a,b) in enumerate(zones):
        za.append({'i':i,'a':sum(score[n] for n in range(a,b+1))/20})
    za.sort(key=lambda x:-x['a'])
    picks = []
    for z in za[:3]:
        zr = zones[z['i']]
        best = zr[0]; bs=-999
        for n in range(zr[0],zr[1]+1):
            if score[n]>bs: bs=score[n]; best=n
        picks.append(best)
    return picks

def day_notes(draw_set, bets):
    return sum(1 for b in bets if all(n in draw_set for n in b))

def sim(triple, days, warm, mult, in_stop):
    bets = list(combinations(triple,2))
    miss = 0; investing = False; stage = 1; in_miss = 0
    cum_inv = 0; cum_prize = 0; peak = 0; wins = 0; busts = 0
    for d in days:
        notes = day_notes(set(d['n']), bets)
        if investing:
            inv = 6 * (mult ** (stage - 1))
            prize = 19*notes*(mult ** (stage - 1)) if notes > 0 else 0
            cum_inv += inv; cum_prize += prize
            peak = max(peak, inv)
            if prize > 0:
                wins += 1; investing = False; miss = 0; stage = 1; in_miss = 0
            else:
                stage += 1; in_miss += 1; miss += 1
                if in_miss >= in_stop:
                    busts += 1; investing = False; miss = 0; stage = 1; in_miss = 0
        else:
            if notes > 0: miss = 0
            else:
                miss += 1
                if miss >= warm:
                    investing = True; stage = 1; in_miss = 0
    return cum_inv, cum_prize, peak, busts

months = ['2025-11','2025-12','2026-01','2026-02','2026-03','2026-04','2026-05','2026-06','2026-07','2026-08']

# 预生成每月号码
month_picks = {}
for ym in months:
    days = sorted([d for d in kl8 if d['d'].startswith(ym)], key=lambda x: x['d'])
    if days:
        month_picks[ym] = (compute_x3_picks(kl8, ym), days)

# ============ 网格扫描 ============
print("===== 网格搜索：预警期×倍率×止损期（10个月）=====\n")
results = []
for warm in [3,4,5,6,7]:
    for mult in [1.5, 2.0]:
        for in_stop in [5,6,7,8,9,10,11,12,15,99]:
            tot_inv=0; tot_prize=0; max_peak=0; busts=0; loss_months=0
            for ym,(triple,days) in month_picks.items():
                ci,cp,pk,b = sim(triple, days, warm, mult, in_stop)
                tot_inv += ci; tot_prize += cp; max_peak = max(max_peak, pk); busts += b
                if cp - ci < 0: loss_months += 1
            net = tot_prize - tot_inv
            roi = net/tot_inv*100 if tot_inv else 0
            results.append({'warm':warm,'mult':mult,'stop':in_stop,'net':net,'roi':roi,
                            'peak':max_peak,'inv':tot_inv,'busts':busts,'loss_m':loss_months})

# 排序：先按净>0，再按峰值小（风险低），再按ROI
pos = [r for r in results if r['net'] > 0]
neg = [r for r in results if r['net'] <= 0]
pos.sort(key=lambda r: (-r['net'], r['peak']))
neg.sort(key=lambda r: (r['net']))

print("--- 盈利方案 TOP10（净>0）---")
print(f"{'预警':<5} {'倍率':<5} {'止损':<6} {'净':>10} {'ROI':>7} {'峰值':>8} {'投入':>8} {'止损次':>5} {'亏月数':>5}")
for r in pos[:10]:
    print(f"{r['warm']:<5} {r['mult']:<5} {r['stop']:<6} {r['net']:>+10,} {r['roi']:>+6.1f}% {r['peak']:>8,} {r['inv']:>8,} {r['busts']:>5} {r['loss_m']:>5}")

print("\n--- 亏损最少的方案 TOP5 ---")
for r in neg[:5]:
    print(f"{r['warm']:<5} {r['mult']:<5} {r['stop']:<6} {r['net']:>+10,} {r['roi']:>+6.1f}% {r['peak']:>8,} {r['inv']:>8,} {r['busts']:>5} {r['loss_m']:>5}")

print(f"\n盈利方案总数: {len(pos)}/{len(results)}")
