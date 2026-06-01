"""排列五 五不同+二同 近1年回测"""
import json, urllib.request, time, sys
from math import comb
from datetime import datetime, timedelta

API = "http://api.huiniao.top/interface/home/lotteryHistory"

def fetch_pl5(limit=400):
    all_items = []; page = 1
    while len(all_items) < limit:
        r = urllib.request.Request(f"{API}?type=plw&page={page}&limit=100", headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(r, timeout=30) as resp: d = json.loads(resp.read().decode("utf-8"))
        if d.get("code")!=1: break
        items = d["data"]["data"]["list"]
        if not items: break
        fields = ["one","two","three","four","five","six","seven","eight","nine","ten",
                  "eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen","eighteen","nineteen","twenty"]
        parsed = []
        for item in items:
            nums = []
            for f in fields:
                v = item.get(f)
                if v is not None:
                    try: nums.append(int(v))
                    except: pass
            parsed.append({"p":str(item.get("code","")), "d":str(item.get("day","")), "n":[int(x) for x in nums[:5]]})
        all_items.extend(parsed); page+=1; time.sleep(1.5)
        if len(parsed)<100: break
    return all_items[:limit]

def get_nums(item): return item["n"]

def pl_dyn_range(data, morph, attr):
    vals=[]
    for item in data:
        nd=get_nums(item); ct={}
        for k in nd: ct[k]=ct.get(k,0)+1
        ok=all(v==1 for v in ct.values()) if morph=="wb" else any(v==2 for v in ct.values())
        if not ok: continue
        v=0
        if attr=="odd": v=sum(1 for x in nd if x%2==1)
        elif attr=="big": v=sum(1 for x in nd if x>=5)
        elif attr=="lu0": v=sum(1 for x in nd if x%3==0)
        elif attr=="prime": v=sum(1 for x in nd if x in (2,3,5,7))
        elif attr=="sum": v=sum(nd)
        elif attr=="span": v=max(nd)-min(nd)
        vals.append(v)
    if len(vals)<5: return None
    freq={}
    for v in vals: freq[v]=freq.get(v,0)+1
    items=sorted(freq.items(), key=lambda x:-x[1])
    acc=0; r=[]; cov=0.85 if attr not in ("sum","span") else 0.80
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

print("获取排列五数据(近1年)..."); sys.stdout.flush()
pl5_data = fetch_pl5(400)
latest = pl5_data[0]
cutoff = datetime.strptime(latest["d"],"%Y-%m-%d") - timedelta(days=365)
pl5_data = [d for d in pl5_data if datetime.strptime(d["d"],"%Y-%m-%d") >= cutoff]
print(f"获取完成: {len(pl5_data)}期 | {pl5_data[-1]['d']} ~ {pl5_data[0]['d']}")

WINDOW=80; GROUPS=5
wb_all=[]; et_all=[]
wb_trials=0; et_trials=0
best_wb={}; best_et={}

for i in range(WINDOW, len(pl5_data)):
    train=pl5_data[i-WINDOW:i]; test=pl5_data[i]
    test_nums=get_nums(test); test_set=set(test_nums)

    # 五不同 (V2: 杀1个+W80+EMA评分)
    train_wb=train
    wb_eng=pl_build(train_wb,"wb")
    if wb_eng["n"]>=10:
        # V2: EMA评分
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
            l5=get_nums(data[0])
            ks.add((l5[4]*2+3)%10)
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
                wb_trials+=1
                hits=[sum(1 for x in g if x in test_set) for g in groups]
                mh=max(hits)
                best_wb[mh]=best_wb.get(mh,0)+1
                wb_all.append((test["p"],test["d"],test_nums,groups,hits,mh))

    # 二同
    et_eng=pl_build(train,"et")
    if et_eng["n"]>=10:
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
                    seen2.add(k); groups2.append((s["combo"],s["repeat"]))
                    if len(groups2)>=GROUPS: break
            if groups2:
                et_trials+=1
                hits2=[]
                # 验证开奖号是否是真正的二同走势图（有重复数字）
                test_ct={}
                for k in test_nums: test_ct[k]=test_ct.get(k,0)+1
                draw_is_et = any(v==2 for v in test_ct.values())
                sorted_draw = sorted(test_nums)
                for g,rp in groups2:
                    sorted_combo5 = sorted(sorted(g)+[rp])
                    hc = sum(1 for i in range(5) if sorted_combo5[i]==sorted_draw[i])
                    if hc==5 and not draw_is_et:
                        hc=4
                    hits2.append(hc)
                mh2=max(hits2)
                best_et[mh2]=best_et.get(mh2,0)+1
                et_all.append((test["p"],test["d"],test_nums,groups2,hits2,mh2))

    if i%50==0:
        print(f"  进度: {i-WINDOW}/{len(pl5_data)-WINDOW}", end="\r", flush=True)

print(f"\n回测完成!                           \n")

print("="*80)
print("排列五 近1年回测报告（2025-06 ~ 2026-05）")
print("="*80)
print(f"测试期数: {len(pl5_data)-WINDOW}")
print()

print(f"【五不同】每期5组x120注=240元")
print(f"  {'─'*50}")
print(f"  产生推荐: {wb_trials}期")
wb5=best_wb.get(5,0)
wb_cost=wb_trials*240
wb_prize=wb5*100000
print(f"  中5个(10万): {wb5}次 ({wb5/max(wb_trials,1)*100:.1f}%)")
print(f"  投入: {wb_cost}元 | 奖金: {wb_prize}元 | 盈亏: {wb_prize-wb_cost:+,}元")
print(f"  返奖率: {wb_prize/wb_cost*100:.1f}%" if wb_cost>0 else "")
print()
if wb5>0:
    print(f"  中5个明细:")
    for r in wb_all:
        if r[5]!=5: continue
        det=""
        for idx,h in enumerate(r[4]):
            if h==5: det+=f" 第{idx+1}组:{sorted(r[3][idx])}"
        print(f"    {r[0]} {r[1]} | 开奖:{r[2]} |{det}")

print()
print(f"【二同】每期5组x60注=120元")
print(f"  {'─'*50}")
et5=best_et.get(5,0)
et_cost=et_trials*120
et_prize=et5*100000
print(f"  产生推荐: {et_trials}期")
print(f"  中5个(10万): {et5}次 ({et5/max(et_trials,1)*100:.1f}%)")
print(f"  投入: {et_cost}元 | 奖金: {et_prize}元 | 盈亏: {et_prize-et_cost:+,}元")
print(f"  返奖率: {et_prize/et_cost*100:.1f}%" if et_cost>0 else "")
print()
if et5>0:
    print(f"  中5个明细:")
    for r in et_all:
        if r[5]!=5: continue
        det=""
        for idx,h in enumerate(r[4]):
            if h==5:
                g,rp=r[3][idx]
                det+=f" 第{idx+1}组:{sorted(g)}+重{rp}"
        print(f"    {r[0]} {r[1]} | 开奖:{r[2]} |{det}")

print()
print("="*80)
print("说明: 排列五直选全组合中奖条件为5码全对(不考虑顺序)")
print("      只有一等奖10万, 中4码及以下不算中奖")
print("="*80)
