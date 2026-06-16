"""
全彩种回测脚本 (Python版)
直接从API拉数据，用和JS一致的算法做回测
"""
import json, urllib.request, time, math
from collections import Counter

API = "http://api.huiniao.top/interface/home/lotteryHistory"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

TYPES = [
    ("ssq","ssq",50,"lotto",15,33,6,16,1),
    ("dlt","dlt",50,"lotto",15,35,5,12,2),
    ("qlc","qlc",50,"lotto",15,30,7,0,0),
    ("kl8","klb",300,"keno",30,80,20,0,0),
    ("fc3d","fcsd",100,"digit",30,9,3,0,0),
    ("pl3","pls",100,"digit",30,9,3,0,0),
    ("pl5","plw",100,"digit",30,9,5,0,0),
    ("qxc","qxc",100,"digit",30,9,7,0,0),
]

def fetch(api_type, limit):
    url = f"{API}?type={api_type}&page=1&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read().decode("utf-8"))

def parse(api, item):
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    if api=="ssq": return {"r":sorted(nums[:6]), "b":nums[6] if len(nums)>6 else None}
    elif api=="dlt": return {"r":sorted(nums[:5]), "b":sorted(nums[5:7]) if len(nums)>5 else []}
    elif api in ("fcsd","pls"): return {"n":nums[:3]}
    elif api=="plw": return {"n":nums[:5]}
    elif api=="qxc": return {"n":nums[:7]}
    elif api=="qlc": return {"r":sorted(nums[:7])}
    else: return {"n":sorted(nums)}

def get_nums(d):
    return d.get("r") or d.get("n") or []

def get_blues(d):
    b = d.get("b")
    if b is None: return []
    if isinstance(b, list): return b
    return [b]

def ema(seq, alpha=0.5):
    """从旧到新计算EMA，让近期数据权重更高"""
    if not seq: return 0
    # seq[0]=最新, seq[-1]=最旧 → 反转后从旧到新计算
    seq_rev = seq[::-1]  # seq_rev[0]=最旧, seq_rev[-1]=最新
    e = seq_rev[0]
    for v in seq_rev[1:]: e = alpha * v + (1-alpha) * e
    return e

# ========== 推荐算法 ==========

def recommend_lotto(data, rMax, rC, bMax, bC):
    if len(data) < 5: return None
    recent = data[:15]
    freq = {n:0 for n in range(1, rMax+1)}
    last_seen = {}
    for i, d in enumerate(recent):
        for n in get_nums(d):
            if 1 <= n <= rMax: freq[n] += 1; last_seen[n] = i
    
    miss = {n: len(recent)-1-last_seen.get(n, -1) for n in range(1, rMax+1)}
    
    # EMA评分
    ema_scores = {}
    for n in range(1, rMax+1):
        seq = [1 if n in get_nums(d) else 0 for d in recent]
        ema_scores[n] = ema(seq, 0.5)
    
    # 综合评分
    scores = {}
    for n in range(1, rMax+1):
        s = freq[n] * 2 + ema_scores[n] * 15
        if 1 <= miss[n] <= 6: s += 2
        # 近5期
        for ri in range(min(5, len(recent))):
            if n in get_nums(recent[ri]): s += 2; break
        scores[n] = s
    
    ranked = sorted(scores, key=lambda n: -scores[n])
    
    # 蓝球
    blue_freq = Counter()
    for d in recent:
        for b in get_blues(d):
            if 1 <= b <= bMax: blue_freq[b] += 1
    blue_ema = {}
    for b in range(1, bMax+1):
        seq = [1 if b in get_blues(d) else 0 for d in recent]
        blue_ema[b] = ema(seq, 0.5)
    blue_scores = {b: blue_freq[b]*2 + blue_ema[b]*15 for b in range(1, bMax+1)}
    blue_ranked = sorted(blue_scores, key=lambda b: -blue_scores[b])
    
    # 胆拖
    dantuo = []
    for dc in range(2, 5):
        dan = ranked[:dc]
        tuo = [n for n in ranked if n not in dan][:14]
        dantuo.append({"dan":dan, "tuo":tuo})
    
    # 基本推荐
    basic = [
        {"nums": ranked[:rC], "blues": blue_ranked[:bC]},
        {"nums": miss_based(data, rMax, rC), "blues": blue_ranked[:bC]},
        {"nums": ranked[1:1+rC], "blues": blue_ranked[:bC]},
    ]
    
    return {"basic": basic, "dantuo": dantuo, "analysis": {
        "hotReds": ranked, "hotBlues": blue_ranked,
        "emaScores": ema_scores
    }}

def miss_based(data, rMax, rC):
    """冷号回补"""
    recent = data[:15]
    last_seen = {}
    for i, d in enumerate(recent):
        for n in get_nums(d):
            if 1 <= n <= rMax: last_seen[n] = i
    miss = {n: len(recent)-1-last_seen.get(n, -1) for n in range(1, rMax+1)}
    return sorted(miss, key=lambda n: -miss[n])[:rC]

def recommend_keno(data):
    if len(data) < 10: return None
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
    
    scores = {n: freq[n]*2 + ema_scores[n]*15 for n in range(1, 81)}
    ranked = sorted(scores, key=lambda n: -scores[n])
    
    dantuo = []
    for dc in range(2, 10):
        dan = ranked[:dc]
        tuo = [n for n in ranked[:20] if n not in dan]
        if tuo: dantuo.append({"dan":dan, "tuo":tuo})
    
    return {"basic": [{"nums": ranked[:20]}], "dantuo": dantuo,
            "analysis": {"hotReds": ranked, "emaScores": ema_scores}}

def recommend_digit(data, pos):
    if len(data) < 5: return None
    recent = data[:30]
    pos_scores = []
    for p in range(pos):
        freq = {n:0 for n in range(10)}
        for d in recent:
            ns = get_nums(d)
            if len(ns) > p:
                v = ns[p]
                if 0 <= v <= 9: freq[v] += 1
        for ri in range(min(5, len(recent))):
            ns = get_nums(recent[ri])
            if len(ns) > p:
                v = ns[p]
                if 0 <= v <= 9: freq[v] += 2
        
        ema_scores = {}
        for n in range(10):
            seq = [1 if len(get_nums(d))>p and get_nums(d)[p]==n else 0 for d in recent]
            ema_scores[n] = ema(seq, 0.5)
        
        scores = {n: freq[n]*2 + ema_scores[n]*15 for n in range(10)}
        ranked = sorted(scores, key=lambda n: -scores[n])
        pos_scores.append(ranked)
    
    basic = [{"nums": [pos_scores[p][0] for p in range(pos)]}]
    return {"basic": basic, "analysis": {"posScores": pos_scores}}

def generate_recommend(data, cfg_type, rMax, rC, bMax, bC):
    if len(data) < 5: return None
    if cfg_type == "lotto": return recommend_lotto(data, rMax, rC, bMax, bC)
    elif cfg_type == "keno": return recommend_keno(data)
    elif cfg_type == "digit": return recommend_digit(data, rC)
    return None

# ========== 回测 ==========

def backtest(recs, cfg_type, rMax, rC, bMax, bC, rec_period, name):
    print(f"\n🔍 {name} ({rec_period}期窗口)")
    
    results = {"total":0, "basic_hits":[], "dantuo_hits":[], "enhanced_hits":[]}
    
    for i in range(rec_period, len(recs)):
        past = recs[i-rec_period:i]
        draw = recs[i]
        drawn = get_nums(draw)
        blues = get_blues(draw)
        
        rec = generate_recommend(past, cfg_type, rMax, rC, bMax, bC)
        if not rec: continue
        
        results["total"] += 1
        
        # 基本推荐
        for idx, item in enumerate(rec["basic"]):
            nums = item.get("nums", [])
            b = item.get("blues", [])
            hits = sum(1 for n in nums if n in drawn)
            b_hits = sum(1 for n in b if n in blues)
            if len(results["basic_hits"]) <= idx:
                results["basic_hits"].append({"label":f"注{idx+1}","hits":[],"blues":[]})
            results["basic_hits"][idx]["hits"].append(hits)
            results["basic_hits"][idx]["blues"].append(b_hits)
        
        # 胆拖
        for idx, dt in enumerate(rec.get("dantuo", [])):
            d_hit = sum(1 for n in dt.get("dan",[]) if n in drawn)
            t_hit = sum(1 for n in dt.get("tuo",[]) if n in drawn)
            if len(results["dantuo_hits"]) <= idx:
                results["dantuo_hits"].append({"dan":[],"tuo":[]})
            results["dantuo_hits"][idx]["dan"].append(d_hit)
            results["dantuo_hits"][idx]["tuo"].append(t_hit)
        
        # 增强推荐
        an = rec.get("analysis",{})
        if cfg_type == "lotto":
            hot = an.get("hotReds",[])
            hot_b = an.get("hotBlues",[])
            ec = 8 if rMax == 35 else 9
            er = hot[:ec]
            eb = hot_b[:3]
            results["enhanced_hits"].append({
                "reds": sum(1 for n in er if n in drawn),
                "blues": sum(1 for n in eb if n in blues)
            })
        elif cfg_type == "keno":
            hot = an.get("hotReds",[])
            e20 = hot[:20]
            results["enhanced_hits"].append(sum(1 for n in e20 if n in drawn))
        elif cfg_type == "digit":
            pos = an.get("posScores",[])
            hits_per_pos = []
            for p in range(min(len(pos), rC)):
                top5 = pos[p][:5]
                if len(drawn) > p:
                    hits_per_pos.append(1 if drawn[p] in top5 else 0)
            results["enhanced_hits"].append(sum(hits_per_pos) if hits_per_pos else 0)
    
    # 打印
    print(f"  共回测 {results['total']} 期")
    
    print(f"  📋 基本推荐:")
    for idx, bh in enumerate(results["basic_hits"]):
        avg = sum(bh["hits"])/len(bh["hits"]) if bh["hits"] else 0
        mx = max(bh["hits"]) if bh["hits"] else 0
        dist = Counter(min(h, 9) for h in bh["hits"])
        top = " | ".join(f"中{k}:{v}期" for k,v in sorted(dist.items(), reverse=True)[:4])
        print(f"    {bh['label']} 平均{avg:.2f}个 最高{mx}个 {top}")
    
    if results["dantuo_hits"]:
        print(f"  📋 胆拖推荐:")
        for idx, dh in enumerate(results["dantuo_hits"][:4]):
            da = sum(dh["dan"])/len(dh["dan"]) if dh["dan"] else 0
            ta = sum(dh["tuo"])/len(dh["tuo"]) if dh["tuo"] else 0
            dm = max(dh["dan"]) if dh["dan"] else 0
            tm = max(dh["tuo"]) if dh["tuo"] else 0
            print(f"    胆拖{idx+1}: 胆平均{da:.2f}(最高{dm}) 拖平均{ta:.2f}(最高{tm})")
    
    if results["enhanced_hits"]:
        if cfg_type == "lotto":
            vals = [h["reds"] for h in results["enhanced_hits"]]
            avg = sum(vals)/len(vals)
            mx = max(vals)
            dist = Counter(min(v, 9) for v in vals)
            top = " | ".join(f"中{k}:{v}期" for k,v in sorted(dist.items(), reverse=True)[:6])
            ec = "8红+3蓝" if rMax == 35 else "9红+3蓝"
            print(f"  🏆 大复试({ec}): 平均{avg:.2f}个 最高{mx}个 {top}")
        elif cfg_type == "keno":
            vals = results["enhanced_hits"]
            avg = sum(vals)/len(vals)
            mx = max(vals)
            dist = Counter(min(v, 20) for v in vals)
            top = " | ".join(f"中{k}:{v}期" for k,v in sorted(dist.items(), reverse=True)[:6])
            print(f"  🏆 多策略20码: 平均{avg:.2f}个 最高{mx}个 {top}")
        elif cfg_type == "digit":
            vals = results["enhanced_hits"]
            avg = sum(vals)/len(vals)
            mx = max(vals)
            dist = Counter(vals)
            top = " | ".join(f"中{k}:{v}期" for k,v in sorted(dist.items(), reverse=True)[:5])
            print(f"  🏆 大底: 平均{avg:.2f}位 最高{mx}位 {top}")
    
    return results

# ========== 主流程 ==========

def main():
    print("=" * 60)
    print("📊 全彩种回测 (Python版)")
    print(f"  算法逻辑与JS推荐一致: 频率×2 + EMA×15 + 近5期加权")
    print("=" * 60)
    
    all_data = {}
    for t, api_type, limit, cfg_type, rec_period, rMax, rC, bMax, bC in TYPES:
        try:
            d = fetch(api_type, limit)
            if d.get("code") == 1:
                items = d["data"]["data"]["list"]
                parsed = [parse(api_type, item) for item in items]
                all_data[t] = parsed
                print(f"  {t}: {len(parsed)}期")
            else:
                print(f"  {t}: API错误")
        except Exception as e:
            print(f"  {t}: 失败 {e}")
        time.sleep(0.5)
    
    results = {}
    for t, api_type, limit, cfg_type, rec_period, rMax, rC, bMax, bC in TYPES:
        data = all_data.get(t, [])
        if len(data) < rec_period + 5:
            print(f"\n⚠ {t}: 数据不足 ({len(data)}期)")
            continue
        results[t] = backtest(data, cfg_type, rMax, rC, bMax, bC, rec_period, t)
    
    # 保存
    with open("data/backtest_result.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n✅ 结果已保存到 data/backtest_result.json")

if __name__ == "__main__":
    main()
