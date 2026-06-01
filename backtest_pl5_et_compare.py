"""排列五二同 多方案对比回测"""
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

# ============ V1 原版二同 ============
def run_v1(pl5_data, WINDOW=50, GROUPS=5):
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
            for k in get_nums(data[j]): 
                ik=int(k)
                if 0<=ik<=9: r5[ik]=r5.get(ik,0)+1
        miss={i:n for i in range(10)}
        for j in range(n):
            for k in get_nums(data[j]):
                ik=int(k)
                if 0<=ik<=9 and miss[ik]>j: miss[ik]=j
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
    
    trials=0; best={}; hit_dist={i:0 for i in range(6)}
    for i in range(WINDOW, len(pl5_data)):
        train=pl5_data[i-WINDOW:i]; test=pl5_data[i]
        test_nums=get_nums(test)
        et_eng=pl_build(train,"et")
        if et_eng["n"]<10: continue
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
                trials+=1
                hits2=[]
                test_ct={}
                for k in test_nums: test_ct[k]=test_ct.get(k,0)+1
                draw_is_et=any(v==2 for v in test_ct.values())
                sorted_draw=sorted(test_nums)
                for g,rp in groups2:
                    sorted_combo5=sorted(sorted(g)+[rp])
                    hc=sum(1 for i2 in range(5) if sorted_combo5[i2]==sorted_draw[i2])
                    if hc==5 and not draw_is_et: hc=4
                    hits2.append(hc)
                mh2=max(hits2)
                best[mh2]=best.get(mh2,0)+1
                for h in hits2: hit_dist[h]=hit_dist.get(h,0)+1
    return trials, best, hit_dist

# ============ V2: 杀N个+EMA评分二同 ============
def run_v2(pl5_data, WINDOW=50, GROUPS=5, KILL_N=2):
    """二同 V2: EMA评分替代部分约束, 调整杀号数"""
    def pl_kill_n(data, kill_n):
        ks=set()
        last5=get_nums(data[0])
        ks.add(int(last5[4]*2+3)%10)
        if kill_n<=1: return ks
        n=len(data)
        r5={i:0 for i in range(10)}
        for j in range(min(5,n)):
            for k in get_nums(data[j]): 
                ik=int(k)
                if 0<=ik<=9: r5[ik]=r5.get(ik,0)+1
        miss={i:n for i in range(10)}
        for j in range(n):
            for k in get_nums(data[j]):
                ik=int(k)
                if 0<=ik<=9 and miss[ik]>j: miss[ik]=j
        kill_cands=[]
        for i in range(10):
            if i in ks: continue
            s=r5[i]*2+miss[i]*0.5
            kill_cands.append((i,s))
        kill_cands.sort(key=lambda x:x[1])
        needed=kill_n-len(ks)
        for idx in range(min(needed, len(kill_cands))):
            ks.add(kill_cands[idx][0])
        return ks
    
    def build_et_stats(data):
        """二同专属统计：数字频率+配对频率+重号频率+EMA热度"""
        n=len(data)
        if n<10: return None
        mf={i:0 for i in range(10)}; pf={}; rf={}; et_n=0
        # EMA热度
        ema_hot={i:0.0 for i in range(10)}
        recent5={i:0 for i in range(10)}
        prev5={i:0 for i in range(10)}
        
        for j in range(n):
            nd=get_nums(data[j]); ct={}
            for k in nd: ct[k]=ct.get(k,0)+1
            ok=any(v==2 for v in ct.values())
            if not ok: continue
            et_n+=1; s=set(nd)
            for k in s: mf[k]=mf.get(k,0)+1
            keys=list(s)
            for a in range(len(keys)):
                for b in range(a+1,len(keys)):
                    pk=f"{min(keys[a],keys[b])},{max(keys[a],keys[b])}"
                    pf[pk]=pf.get(pk,0)+1
            for k,v in ct.items():
                if v==2: rf[k]=rf.get(k,0)+1
            # EMA: 每个数字出现
            for k in range(10):
                if k in s:
                    if j<5: recent5[k]+=1
                    elif j<10: prev5[k]+=1
                    ema_hot[k]=ema_hot.get(k,0)*0.7+1.0*0.3
                else:
                    ema_hot[k]=ema_hot.get(k,0)*0.7+0.0*0.3
        
        return {"mf":mf,"pf":pf,"rf":rf,"n":et_n,"ema":ema_hot,"mom5":recent5,"mom10_prev":prev5}
    
    def pair_score(com):
        pairs=[(0,5),(1,6),(2,7),(3,8),(4,9)]; s=0
        for a in range(len(com)):
            for b in range(a+1,len(com)):
                for p in pairs:
                    if (com[a]==p[0] and com[b]==p[1]) or (com[a]==p[1] and com[b]==p[0]): s+=1
        return s
    
    trials=0; best={}; hit_dist={i:0 for i in range(6)}
    for i in range(WINDOW, len(pl5_data)):
        train=pl5_data[i-WINDOW:i]; test=pl5_data[i]
        test_nums=get_nums(test)
        
        stats=build_et_stats(train)
        if not stats or stats["n"]<10: continue
        
        kk=pl_kill_n(train, KILL_N)
        cand=[i for i in range(10) if i not in kk]
        if len(cand)<7:
            for jj in range(10):
                if jj not in cand: cand.append(jj)
                if len(cand)>=7: break
        
        # EMA评分：频率+EMA热度+动量
        digit_scores={}
        for d in range(10):
            freq=stats["mf"].get(d,0)/max(stats["n"],1)*2.0
            ema=stats["ema"].get(d,0)*3.0
            mom=(stats["mom5"].get(d,0)-stats["mom10_prev"].get(d,0))/max(stats["mom10_prev"].get(d,0),1)*1.5
            mom=max(-2,min(2,mom))
            digit_scores[d]=freq+ema+mom
        
        # 胆码: 最高分2个
        ranked=sorted(digit_scores.items(), key=lambda x:-x[1])
        dm=[ranked[0][0], ranked[1][0]]
        if dm[0] not in cand: cand.append(dm[0])
        if dm[1] not in cand: cand.append(dm[1])
        
        all4=comb_n(cand,4)
        scored=[]
        for c in all4:
            if dm[0] not in c: continue
            for pr in range(4):
                rp=c[pr]
                # 组合评分
                cs=sum(digit_scores.get(k,0) for k in c)
                # 配对跟随
                follow=0
                for pa in range(4):
                    for pb in range(pa+1,4):
                        pv=f"{min(c[pa],c[pb])},{max(c[pa],c[pb])}"
                        follow+=stats["pf"].get(pv,0)/max(stats["n"],1)
                # 重号频率
                rp_bonus=stats["rf"].get(rp,0)*2
                # 互补对
                ps=pair_score(c)*2
                scored.append({"combo":c,"repeat":rp,"score":cs+follow*15+rp_bonus+ps})
        
        if scored:
            scored.sort(key=lambda x:-x["score"])
            seen=set(); groups=[]
            for s in scored:
                k=str(sorted(s["combo"]))
                if k not in seen:
                    seen.add(k); groups.append((s["combo"],s["repeat"]))
                    if len(groups)>=GROUPS: break
            if groups:
                trials+=1
                hits2=[]
                test_ct={}
                for k in test_nums: test_ct[k]=test_ct.get(k,0)+1
                draw_is_et=any(v==2 for v in test_ct.values())
                sorted_draw=sorted(test_nums)
                for g,rp in groups:
                    sorted_combo5=sorted(sorted(g)+[rp])
                    hc=sum(1 for i2 in range(5) if sorted_combo5[i2]==sorted_draw[i2])
                    if hc==5 and not draw_is_et: hc=4
                    hits2.append(hc)
                mh2=max(hits2)
                best[mh2]=best.get(mh2,0)+1
                for h in hits2: hit_dist[h]=hit_dist.get(h,0)+1
    return trials, best, hit_dist

# ============ V3: 不杀号+EMA评分+6约束过滤 ============
def run_v3(pl5_data, WINDOW=50, GROUPS=5, KILL_N=0):
    """二同 V3: 不杀号或少杀号, EMA评分, 但保留6约束过滤"""
    def pl_kill_n(data, kill_n):
        ks=set()
        last5=get_nums(data[0])
        ks.add(int(last5[4]*2+3)%10)
        if kill_n<=1: return ks
        n=len(data)
        r5={i:0 for i in range(10)}
        for j in range(min(5,n)):
            for k in get_nums(data[j]): 
                ik=int(k)
                if 0<=ik<=9: r5[ik]=r5.get(ik,0)+1
        miss={i:n for i in range(10)}
        for j in range(n):
            for k in get_nums(data[j]):
                ik=int(k)
                if 0<=ik<=9 and miss[ik]>j: miss[ik]=j
        kill_cands=[]
        for i in range(10):
            if i in ks: continue
            s=r5[i]*2+miss[i]*0.5
            kill_cands.append((i,s))
        kill_cands.sort(key=lambda x:x[1])
        needed=kill_n-len(ks)
        for idx in range(min(needed, len(kill_cands))):
            ks.add(kill_cands[idx][0])
        return ks
    
    def dyn_range(data, attr):
        vals=[]
        for item in data:
            nd=get_nums(item); ct={}
            for k in nd: ct[k]=ct.get(k,0)+1
            if not any(v==2 for v in ct.values()): continue
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
    
    def build_et_stats(data):
        n=len(data)
        if n<10: return None
        mf={i:0 for i in range(10)}; pf={}; rf={}; et_n=0
        ema_hot={i:0.0 for i in range(10)}
        recent5={i:0 for i in range(10)}
        prev5={i:0 for i in range(10)}
        for j in range(n):
            nd=get_nums(data[j]); ct={}
            for k in nd: ct[k]=ct.get(k,0)+1
            ok=any(v==2 for v in ct.values())
            if not ok: continue
            et_n+=1; s=set(nd)
            for k in s: mf[k]=mf.get(k,0)+1
            keys=list(s)
            for a in range(len(keys)):
                for b in range(a+1,len(keys)):
                    pk=f"{min(keys[a],keys[b])},{max(keys[a],keys[b])}"
                    pf[pk]=pf.get(pk,0)+1
            for k,v in ct.items():
                if v==2: rf[k]=rf.get(k,0)+1
            for k in range(10):
                if k in s: ema_hot[k]=ema_hot.get(k,0)*0.7+1.0*0.3
                else: ema_hot[k]=ema_hot.get(k,0)*0.7+0.0*0.3
                if j<5 and k in s: recent5[k]+=1
                elif 5<=j<10 and k in s: prev5[k]+=1
        return {"mf":mf,"pf":pf,"rf":rf,"n":et_n,"ema":ema_hot,"mom5":recent5,"mom10_prev":prev5}
    
    def pair_score(com):
        pairs=[(0,5),(1,6),(2,7),(3,8),(4,9)]; s=0
        for a in range(len(com)):
            for b in range(a+1,len(com)):
                for p in pairs:
                    if (com[a]==p[0] and com[b]==p[1]) or (com[a]==p[1] and com[b]==p[0]): s+=1
        return s
    
    trials=0; best={}; hit_dist={i:0 for i in range(6)}
    for i in range(WINDOW, len(pl5_data)):
        train=pl5_data[i-WINDOW:i]; test=pl5_data[i]
        test_nums=get_nums(test)
        
        stats=build_et_stats(train)
        if not stats or stats["n"]<10: continue
        
        kk=pl_kill_n(train, KILL_N)
        cand=[i for i in range(10) if i not in kk]
        if len(cand)<7:
            for jj in range(10):
                if jj not in cand: cand.append(jj)
                if len(cand)>=7: break
        
        odd_r2=dyn_range(train,"odd"); big_r2=dyn_range(train,"big")
        lu_r2=dyn_range(train,"lu0"); prime_r2=dyn_range(train,"prime")
        sum_r2=dyn_range(train,"sum"); span_r2=dyn_range(train,"span")
        
        digit_scores={}
        for d in range(10):
            freq=stats["mf"].get(d,0)/max(stats["n"],1)*2.0
            ema=stats["ema"].get(d,0)*3.0
            mom=(stats["mom5"].get(d,0)-stats["mom10_prev"].get(d,0))/max(stats["mom10_prev"].get(d,0),1)*1.5
            mom=max(-2,min(2,mom))
            digit_scores[d]=freq+ema+mom
        
        ranked=sorted(digit_scores.items(), key=lambda x:-x[1])
        dm=[ranked[0][0], ranked[1][0]]
        if dm[0] not in cand: cand.append(dm[0])
        if dm[1] not in cand: cand.append(dm[1])
        
        all4=comb_n(cand,4)
        scored=[]
        for c in all4:
            if dm[0] not in c: continue
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
                cs=sum(digit_scores.get(k,0) for k in c)
                follow=0
                for pa in range(4):
                    for pb in range(pa+1,4):
                        pv=f"{min(c[pa],c[pb])},{max(c[pa],c[pb])}"
                        follow+=stats["pf"].get(pv,0)/max(stats["n"],1)
                rp_bonus=stats["rf"].get(rp,0)*2
                ps=pair_score(c)*2
                scored.append({"combo":c,"repeat":rp,"score":cs+follow*15+rp_bonus+ps})
        
        if scored:
            scored.sort(key=lambda x:-x["score"])
            seen=set(); groups=[]
            for s in scored:
                k=str(sorted(s["combo"]))
                if k not in seen:
                    seen.add(k); groups.append((s["combo"],s["repeat"]))
                    if len(groups)>=GROUPS: break
            if groups:
                trials+=1
                hits2=[]
                test_ct={}
                for k in test_nums: test_ct[k]=test_ct.get(k,0)+1
                draw_is_et=any(v==2 for v in test_ct.values())
                sorted_draw=sorted(test_nums)
                for g,rp in groups:
                    sorted_combo5=sorted(sorted(g)+[rp])
                    hc=sum(1 for i2 in range(5) if sorted_combo5[i2]==sorted_draw[i2])
                    if hc==5 and not draw_is_et: hc=4
                    hits2.append(hc)
                mh2=max(hits2)
                best[mh2]=best.get(mh2,0)+1
                for h in hits2: hit_dist[h]=hit_dist.get(h,0)+1
    return trials, best, hit_dist

# ============ 主程序 ============
print("获取排列五数据..."); sys.stdout.flush()
pl5_data = fetch_pl5(1200)
print(f"{len(pl5_data)}期: {pl5_data[-1]['d']} ~ {pl5_data[0]['d']}"); sys.stdout.flush()

results = []

# V1 原版
print("\n[V1] 原版(杀3+6约束+W50)...")
t,b,h = run_v1(pl5_data, 50, 5)
results.append((f"V1 原版(杀3+约束+W50)", t, b, h))
roi = (b.get(5,0)*100000+b.get(4,0)*1000)/(max(t,1)*120)*100
print(f"  试{t}期 | 中5:{b.get(5,0)} 中4:{b.get(4,0)} | 返奖:{roi:.1f}%"); sys.stdout.flush()

# V2: 杀0,1,2 + W50
for kill_n in [0, 1, 2]:
    print(f"\n[V2] EMA评分+杀{kill_n}+W50...")
    t,b,h = run_v2(pl5_data, 50, 5, kill_n)
    label = f"V2 EMA(杀{kill_n}+W50)"
    results.append((label, t, b, h))
    roi = (b.get(5,0)*100000+b.get(4,0)*1000)/(max(t,1)*120)*100
    print(f"  试{t}期 | 中5:{b.get(5,0)} 中4:{b.get(4,0)} | 返奖:{roi:.1f}%"); sys.stdout.flush()

# V2: 杀1 + W30, W80
for w in [30, 80]:
    print(f"\n[V2] EMA评分+杀1+W{w}...")
    t,b,h = run_v2(pl5_data, w, 5, 1)
    label = f"V2 EMA(杀1+W{w})"
    results.append((label, t, b, h))
    roi = (b.get(5,0)*100000+b.get(4,0)*1000)/(max(t,1)*120)*100
    print(f"  试{t}期 | 中5:{b.get(5,0)} 中4:{b.get(4,0)} | 返奖:{roi:.1f}%"); sys.stdout.flush()

# V3: EMA+约束+杀0,1 + W50
for kill_n in [0, 1]:
    print(f"\n[V3] EMA+约束+杀{kill_n}+W50...")
    t,b,h = run_v3(pl5_data, 50, 5, kill_n)
    label = f"V3 EMA+约束(杀{kill_n}+W50)"
    results.append((label, t, b, h))
    roi = (b.get(5,0)*100000+b.get(4,0)*1000)/(max(t,1)*120)*100
    print(f"  试{t}期 | 中5:{b.get(5,0)} 中4:{b.get(4,0)} | 返奖:{roi:.1f}%"); sys.stdout.flush()

# V2: 杀1 + W80 (already done, but let's also try V2 杀2+W80)
print(f"\n[V2] EMA评分+杀2+W80...")
t,b,h = run_v2(pl5_data, 80, 5, 2)
label = "V2 EMA(杀2+W80)"
results.append((label, t, b, h))
roi = (b.get(5,0)*100000+b.get(4,0)*1000)/(max(t,1)*120)*100
print(f"  试{t}期 | 中5:{b.get(5,0)} 中4:{b.get(4,0)} | 返奖:{roi:.1f}%"); sys.stdout.flush()

# ===== 综合对比 =====
print(f"\n{'='*100}")
print(f"{'方案':<35} {'期数':>5} {'中5':>6} {'中4':>6} {'中3':>6} {'中2':>6} {'命中率':>8} {'返奖率':>8} {'投入/期':>8}")
print(f"{'─'*100}")
for label, trials, best, _ in results:
    w5 = best.get(5,0)
    w4 = best.get(4,0)
    w3 = best.get(3,0)
    w2 = best.get(2,0)
    hit_rate = (w5+w4)/max(trials,1)*100
    roi = (w5*100000+w4*1000+w3*50)/(max(trials,1)*120)*100
    print(f"{label:<35} {trials:>5} {w5:>6} {w4:>6} {w3:>6} {w2:>6} {hit_rate:>7.2f}% {roi:>7.1f}% {'120元':>8}")

print(f"{'='*100}")
print(f"说明: 中5=10万, 中4=2000元(二同), 中3=50元 | 每组60注=120元")
print(f"注意: 二同需开奖号有重复数字才有效")
