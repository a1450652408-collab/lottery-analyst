"""排列五 五不同+二同 滚动回测（测试全部5组推荐）"""
import json, urllib.request, time, sys
from math import comb

API = "http://api.huiniao.top/interface/home/lotteryHistory"

def fetch_pl5(limit=1200):
    all_items = []
    page = 1
    while len(all_items) < limit:
        r = urllib.request.Request(
            f"{API}?type=plw&page={page}&limit=100",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(r, timeout=30) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        if d.get("code") != 1: break
        items = d["data"]["data"]["list"]
        if not items: break
        fields = ["one","two","three","four","five","six","seven",
                  "eight","nine","ten","eleven","twelve","thirteen",
                  "fourteen","fifteen","sixteen","seventeen","eighteen",
                  "nineteen","twenty"]
        parsed = []
        for item in items:
            nums = []
            for f in fields:
                v = item.get(f)
                if v is not None:
                    try: nums.append(int(v))
                    except: pass
            parsed.append({
                "p": str(item.get("code","")),
                "d": str(item.get("day","")),
                "n": [int(x) for x in nums[:5]]
            })
        all_items.extend(parsed)
        page += 1
        time.sleep(1.5)
        if len(parsed) < 100: break
    return all_items[:limit]

def get_nums(item):
    return item["n"]

# === 算法 ===
def pl_dyn_range(data, morph, attr):
    vals = []
    for item in data:
        nd = get_nums(item); ct = {}
        for k in nd: ct[k] = ct.get(k, 0) + 1
        ok = all(v==1 for v in ct.values()) if morph=="wb" else any(v==2 for v in ct.values())
        if not ok: continue
        v = 0
        if attr=='odd': v=sum(1 for x in nd if x%2==1)
        elif attr=='big': v=sum(1 for x in nd if x>=5)
        elif attr=='lu0': v=sum(1 for x in nd if x%3==0)
        elif attr=='prime': v=sum(1 for x in nd if x in (2,3,5,7))
        elif attr=='sum': v=sum(nd)
        elif attr=='span': v=max(nd)-min(nd)
        vals.append(v)
    if len(vals)<5: return None
    freq={}
    for v in vals: freq[v]=freq.get(v,0)+1
    items=sorted(freq.items(), key=lambda x:-x[1])
    acc=0; r=[]; cov=0.85 if attr not in ('sum','span') else 0.80
    for v,c in items:
        r.append(v); acc+=c
        if acc/len(vals)>=cov: break
    return r

def pl_kill(data):
    ks=set()
    last5=get_nums(data[0])
    ks.add((last5[4]*2+3)%10); ks.add((last5[0]+last5[1])%10)
    n=len(data)
    r5={i:0 for i in range(10)}
    for j in range(min(5,n)):
        for k in get_nums(data[j]): r5[int(k)]=r5.get(int(k),0)+1
    miss={i:n for i in range(10)}
    for j in range(n):
        for k in get_nums(data[j]):
            ik=int(k)
            if ik in miss and miss[ik]>j: miss[ik]=j
    coldest,coldest_s=-1,999
    for i in range(10):
        if i in ks: continue
        s=r5[i]*2+miss[i]*0.5
        if s<coldest_s: coldest_s=s; coldest=i
    if coldest>=0: ks.add(coldest)
    return ks

def pl_danma(data, mfreq):
    fq={}
    for j in range(len(data)):
        for k in get_nums(data[j]): fq[k]=fq.get(k,0)+1+(5 if j<15 else 0)
    sc=[(i,(fq.get(i,0) or 0)*0.3+(mfreq.get(i,0) or 0)*2.0) for i in range(10)]
    sc.sort(key=lambda x:-x[1])
    return [sc[0][0], sc[1][0]]

def pl_pair_score(com):
    pairs=[(0,5),(1,6),(2,7),(3,8),(4,9)]; s=0
    for a in range(len(com)):
        for b in range(a+1,len(com)):
            for p in pairs:
                if (com[a]==p[0] and com[b]==p[1]) or (com[a]==p[1] and com[b]==p[0]): s+=1
    return s

def comb_n(arr, n):
    if n==0: return [[]]
    if len(arr)<n: return []
    r=[]; f=arr[0]; rest=arr[1:]
    for c in comb_n(rest,n-1): r.append([f]+c)
    for c in comb_n(rest,n): r.append(c)
    return r

def pl_build(data, morph):
    mf={i:0 for i in range(10)}; pf={}; rf={}; n=0
    for item in data:
        nd=get_nums(item); ct={}
        for k in nd: ct[k]=ct.get(k,0)+1
        ok=all(v==1 for v in ct.values()) if morph=="wb" else any(v==2 for v in ct.values())
        if not ok: continue
        n+=1; s=set(nd)
        for k in s: mf[k]=mf.get(k,0)+1
        keys=list(s)
        for a in range(len(keys)):
            for b in range(a+1,len(keys)):
                pk=f"{min(keys[a],keys[b])},{max(keys[a],keys[b])}"
                pf[pk]=pf.get(pk,0)+1
        if morph!="wb":
            for k,v in ct.items():
                if v==2: rf[k]=rf.get(k,0)+1
    return {"mf":mf,"pf":pf,"rf":rf,"n":n}

# === 主回测 ===
print("获取排列五数据 ...")
pl5_data = fetch_pl5(1200)
print(f"获取完成: {len(pl5_data)}期 | {pl5_data[-1]['d']} ~ {pl5_data[0]['d']}")

WINDOW = 80
GROUPS = 5

# 五不同: 每期5组, 每组5个不同数字
wb_all = []    # [(期号, 日期, 开奖号, 命中的组数, 各组的命中数)]
wb_total_trials = 0
wb_hit_dist = {i:0 for i in range(6)}  # 各组命中数分布

# 二同: 每期5组, 每组4个不同数字+1个重复数字
et_all = []
et_total_trials = 0
et_hit_dist = {i:0 for i in range(6)}

for i in range(WINDOW, len(pl5_data)):
    train = pl5_data[i-WINDOW:i]
    test = pl5_data[i]
    test_nums = get_nums(test)
    test_set = set(test_nums)
    
    # === 五不同 (V2: 杀1个+W80+EMA评分) ===
    train_wb = pl5_data[max(0,i-WINDOW):i]
    wb_eng = pl_build(train_wb, "wb")
    if wb_eng["n"] >= 10:
        # V2: EMA评分替代6约束过滤
        def score_digits(data, digit=10):
            n=len(data)
            if n<15: return {i:0 for i in range(digit)}
            freq_all={i:0 for i in range(digit)}
            recent10={i:0 for i in range(digit)}
            pos_freq={i:{p:0 for p in range(5)} for i in range(digit)}
            recent5={i:0 for i in range(digit)}
            prev5={i:0 for i in range(digit)}
            for jj in range(n):
                nd2=get_nums(data[jj])
                for pp,kk in enumerate(nd2):
                    try:
                        ik=int(kk)
                        if ik<0 or ik>9: continue
                        freq_all[ik]+=1
                        if jj<5: recent5[ik]+=1
                        elif jj<10: prev5[ik]+=1
                        if jj<10: recent10[ik]+=1
                        pos_freq[ik][pp]+=1
                    except: pass
            scores={}
            for i in range(digit):
                if freq_all[i]==0: scores[i]=0; continue
                ema_hot=recent10[i]/10.0*3.0
                mid_freq=freq_all[i]/n*1.5
                momentum=(recent5[i]-prev5[i])/max(prev5[i],1)*2.0
                momentum=max(-3,min(3,momentum))
                pos_counts=[pos_freq[i][p] for p in range(5)]
                max_pos=max(pos_counts)
                avg_pos=sum(pos_counts)/5.0 if sum(pos_counts)>0 else 0
                uniformity=(avg_pos/max_pos)*1.0 if max_pos>0 else 0
                scores[i]=ema_hot+mid_freq+momentum+uniformity
            return scores
        
        # V2: 杀1个
        def pl_kill_v2(data):
            ks=set()
            last5_nums=get_nums(data[0])
            ks.add((last5_nums[4]*2+3)%10)
            return ks
        
        kk=pl_kill_v2(train_wb)
        cand=[i for i in range(10) if i not in kk]
        if len(cand)<7:
            for jj in range(10):
                if jj not in cand: cand.append(jj)
                if len(cand)>=7: break
        
        scores=score_digits(train_wb)
        ranked=sorted(scores.items(), key=lambda x:-x[1])
        dm=[ranked[0][0], ranked[1][0]]
        if dm[0] not in cand: cand.append(dm[0])
        if dm[1] not in cand: cand.append(dm[1])
        
        all5=comb_n(cand,5)
        scored=[]
        for c in all5:
            if dm[0] not in c: continue
            combo_score=sum(scores.get(k,0) for k in c)
            combo_score+=pl_pair_score(c)*2
            scored.append({"combo":c,"score":combo_score})
        
        if scored:
            scored.sort(key=lambda x:-x["score"])
            seen=set(); groups=[]
            for s in scored:
                k=str(sorted(s["combo"]))
                if k not in seen:
                    seen.add(k); groups.append(s["combo"])
                    if len(groups)>=GROUPS: break
            if groups:
                wb_total_trials+=1
                hits=[sum(1 for x in g if x in test_set) for g in groups]
                max_hit=max(hits)
                for h in hits: wb_hit_dist[h]=wb_hit_dist.get(h,0)+1
                wb_all.append((test["p"],test["d"],test_nums,groups,hits,max_hit))
    
    # === 二同 ===
    et_eng = pl_build(train, "et")
    if et_eng["n"] >= 10:
        odd_r2=pl_dyn_range(train,"et","odd"); big_r2=pl_dyn_range(train,"et","big")
        lu_r2=pl_dyn_range(train,"et","lu0"); prime_r2=pl_dyn_range(train,"et","prime")
        sum_r2=pl_dyn_range(train,"et","sum"); span_r2=pl_dyn_range(train,"et","span")
        kk2=pl_kill(train); dm2=pl_danma(train,et_eng["mf"])
        cand2=[i for i in range(10) if i not in kk2]
        if dm2[0] not in cand2: cand2.append(dm2[0])
        if dm2[1] not in cand2: cand2.append(dm2[1])
        all4=comb_n(cand2,4)
        fq2={}
        for item in train:
            for k in get_nums(item): fq2[k]=fq2.get(k,0)+1
        scored2=[]
        for c in all4:
            if dm2[0] not in c: continue
            for pr in range(4):
                rp=c[pr]; n5=c+[rp]
                o=sum(1 for x in n5 if x%2==1); b=sum(1 for x in n5 if x>=5)
                l=sum(1 for x in n5 if x%3==0); p=sum(1 for x in n5 if x in (2,3,5,7))
                su=sum(n5); sp=max(n5)-min(n5)
                if odd_r2 and o not in odd_r2: continue
                if big_r2 and b not in big_r2: continue
                if lu_r2 and l not in lu_r2: continue
                if prime_r2 and p not in prime_r2: continue
                if sum_r2 and su not in sum_r2: continue
                if span_r2 and sp not in span_r2: continue
                heat=sum(fq2.get(k,0) for k in c)
                spec=sum(et_eng["mf"].get(k,0)*1.5 for k in c)
                follow=0
                for pa in range(4):
                    for pb in range(pa+1,4):
                        pv=f"{min(c[pa],c[pb])},{max(c[pa],c[pb])}"
                        follow+=et_eng["pf"].get(pv,0)/max(et_eng["n"],1)
                rp_bonus=et_eng["rf"].get(rp,0)*2
                scored2.append({"combo":c,"repeat":rp,"score":heat+spec+follow*20+rp_bonus+pl_pair_score(c)*3})
        if scored2:
            scored2.sort(key=lambda x:-x["score"])
            seen2=set(); groups2=[]
            for s in scored2:
                k=str(sorted(s["combo"]))
                if k not in seen2:
                    seen2.add(k)
                    groups2.append((s["combo"],s["repeat"]))
                    if len(groups2)>=GROUPS: break
            if groups2:
                et_total_trials+=1
                hits2=[]
                # 验证开奖号是否是真正的二同走势图（有重复数字）
                test_ct={}
                for k in test_nums: test_ct[k]=test_ct.get(k,0)+1
                draw_is_et = any(v==2 for v in test_ct.values())
                sorted_draw = sorted(test_nums)
                for g,rp in groups2:
                    sorted_combo5 = sorted(sorted(g)+[rp])
                    # 用多重集比较替代 set 包含关系
                    hc = sum(1 for i in range(5) if sorted_combo5[i]==sorted_draw[i])
                    # 开奖号不是二同（如五不同），不能算二同全中
                    if hc==5 and not draw_is_et:
                        hc=4
                    hits2.append(hc)
                max_hit2=max(hits2)
                for h in hits2: et_hit_dist[h]=et_hit_dist.get(h,0)+1
                et_all.append((test["p"],test["d"],test_nums,groups2,hits2,max_hit2))

    if i%100==0:
        print(f"\r  回测: {i-WINDOW}/{len(pl5_data)-WINDOW} ({int((i-WINDOW)/(len(pl5_data)-WINDOW)*100)}%)", end="", flush=True)

print(f"\r  回测完成!                           ")

# ===== 报告 =====
wb_total_groups = sum(5 for _ in wb_all)
et_total_groups = sum(5 for _ in et_all)

print(f"\n{'='*85}")
print(f"排列五 五不同+二同 滚动回测报告（每期5组）")
print(f"{'='*85}")
print(f"数据范围: {pl5_data[-1]['d']} ~ {pl5_data[0]['d']} ({len(pl5_data)}期)")
print(f"回测窗口: 每期用前{WINDOW}期训练, 测试下1期")
print(f"测试期数: {len(pl5_data)-WINDOW}")
print()

# 五不同
print(f"{'─'*65}")
print(f"【五不同推荐】— 每期{GROUPS}组×120注=600注/1200元")
print(f"{'─'*65}")
if wb_total_trials > 0:
    total_groups_wb = wb_total_trials * GROUPS
    print(f"  产生推荐: {wb_total_trials}期 ({wb_total_trials/(len(pl5_data)-WINDOW)*100:.1f}%)")
    print(f"  测试组数: {total_groups_wb}组")
    print()
    # 按"每期最好一组"统计
    best_wb = {}
    for r in wb_all:
        k = r[5]  # max_hit
        best_wb[k] = best_wb.get(k, 0) + 1
    print(f"  每期最佳组命中:")
    for hn in [5,4,3,2,1,0]:
        actual = best_wb.get(hn, 0)
        if actual==0 and hn==0: continue
        print(f"    最高中{hn}个: {actual}期 ({actual/wb_total_trials*100:.1f}%)")
    print()
    # 各组总体命中分布
    print(f"  全部{total_groups_wb}组命中分布:")
    for hn in [5,4,3,2,1,0]:
        actual = wb_hit_dist.get(hn, 0)
        if actual==0 and hn==0: continue
        prob = comb(5, hn) * comb(5, 5-hn) / comb(10, 5) if hn <=5 else 0
        expected = total_groups_wb * prob
        ratio = actual/expected if expected>0 else 0
        print(f"    中{hn}个: {actual:>5}次 {actual/total_groups_wb*100:>6.1f}% | 期望{expected:>5.0f} | 实际/期望={ratio:>5.2f}x")
    print()
    # 奖金（保守：任选1组买=120注=240元/期）
    print(f"  奖金估算（每期选1组买, 120注=240元）:")
    wb_tier5 = best_wb.get(5,0); wb_tier4 = best_wb.get(4,0); wb_tier3 = best_wb.get(3,0)
    wb_cost = wb_total_trials * 240
    wb_prize = wb_tier5*100000 + wb_tier4*1000 + wb_tier3*50
    print(f"    总投入: {wb_cost}元 ({wb_total_trials}期×240元)")
    print(f"    总奖金: {wb_prize}元")
    print(f"    净盈亏: {wb_prize-wb_cost:+,}元")
    print(f"    返奖率: {wb_prize/wb_cost*100:.1f}%" if wb_cost>0 else "")
    # Top
    print(f"\n  Top10 最佳命中:")
    sorted_wb=sorted(wb_all, key=lambda x:-x[5])
    for r in sorted_wb[:10]:
        print(f"    {r[0]} {r[1]} | 开奖:{r[2]} | 5组命中:{r[4]} | 最高中{r[5]}个")
else:
    print("  (无推荐)")

print()

# 二同
print(f"{'─'*65}")
print(f"【二同推荐】— 每期{GROUPS}组×60注=300注/600元")
print(f"{'─'*65}")
if et_total_trials > 0:
    total_groups_et = et_total_trials * GROUPS
    print(f"  产生推荐: {et_total_trials}期 ({et_total_trials/(len(pl5_data)-WINDOW)*100:.1f}%)")
    print(f"  测试组数: {total_groups_et}组")
    print()
    best_et = {}
    for r in et_all:
        k = r[5]
        best_et[k] = best_et.get(k, 0) + 1
    print(f"  每期最佳组命中:")
    for hn in [5,4,3,2,1,0]:
        actual = best_et.get(hn, 0)
        if actual==0 and hn==0: continue
        print(f"    最高中{hn}个: {actual}期 ({actual/et_total_trials*100:.1f}%)")
    print()
    print(f"  全部{total_groups_et}组命中分布:")
    for hn in [5,4,3,2,1,0]:
        actual = et_hit_dist.get(hn, 0)
        if actual==0 and hn==0: continue
        print(f"    中{hn}个: {actual:>5}次 {actual/total_groups_et*100:>6.1f}%")
    print()
    print(f"  奖金估算（每期选1组买, 60注=120元）:")
    et_tier5 = best_et.get(5,0); et_tier4 = best_et.get(4,0); et_tier3 = best_et.get(3,0)
    et_cost = et_total_trials * 120
    et_prize = et_tier5*100000 + et_tier4*1000 + et_tier3*50
    print(f"    总投入: {et_cost}元 ({et_total_trials}期×120元)")
    print(f"    总奖金: {et_prize}元")
    print(f"    净盈亏: {et_prize-et_cost:+,}元")
    print(f"    返奖率: {et_prize/et_cost*100:.1f}%" if et_cost>0 else "")
    print(f"\n  Top10 最佳命中:")
    sorted_et=sorted(et_all, key=lambda x:-x[5])
    for r in sorted_et[:10]:
        groups_str = "; ".join([f"[{sorted(g)}+{rp}]={h}" for (g,rp),h in zip(r[3],r[4])])
        print(f"    {r[0]} {r[1]} | 开奖:{r[2]} | {groups_str} | 最高{r[5]}个")
else:
    print("  (无推荐)")

print()
print(f"{'='*85}")
print(f"关键结论（注意：回测检验的是数字匹配，不是位置匹配）")
print(f"{'='*85}")
print(f"• 五不同每期5组: 最佳组中5个 {best_wb.get(5,0)}期 | 中4个 {best_wb.get(4,0)}期")
print(f"• 二同每期5组:   最佳组中5个 {best_et.get(5,0)}期 | 中4个 {best_et.get(4,0)}期")
print(f"• 排列五需位置全对才能中10万, 目前算法只产出数字集合")
print(f"• 建议把5组推荐全部展示在页面上供用户参考")
