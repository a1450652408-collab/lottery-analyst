#!/usr/bin/env python3
import json, re, os, time

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

m = re.search(r'window\.__LOTTERY_DATA\s*=\s*(\{.*?\});\s*\n</script>', html, re.DOTALL)
data = json.loads(m.group(1))

def get_nums(d): return d.get("n", d.get("r", []))
def get_blue(d):
    b = d.get("b", [])
    if not isinstance(b, list): b = [b]
    return b
def sort_by_freq(freq, nmin, nmax):
    items = [(n, freq.get(n, 0)) for n in range(nmin, nmax+1)]
    items.sort(key=lambda x: (-x[1], x[0]))
    return [x[0] for x in items]

def recommend_kl8(recent, rMax=80, rC=20):
    total = len(recent)
    freq = {n: 0 for n in range(1, rMax+1)}
    last_seen = {n: -1 for n in range(1, rMax+1)}
    for i, d in enumerate(recent):
        ns = get_nums(d)
        for n in ns:
            if 1 <= n <= rMax: freq[n] += 1; last_seen[n] = i
    miss = {n: total-1-last_seen[n] for n in range(1, rMax+1)}
    hot_nums = sort_by_freq(freq, 1, rMax)
    freq_mean = sum(freq.values()) / rMax
    ema_score = {}
    for n in range(1, rMax+1):
        seq = [1 if n in get_nums(d) else 0 for d in recent]
        ema = seq[0] if seq else 0
        for v in seq[1:]: ema = 0.5*v+0.5*ema
        ema_score[n] = ema
    s1 = set(hot_nums[:rC])
    s2 = set()
    for si in range(0, len(hot_nums), 3):
        s2.add(hot_nums[si])
        if len(s2)>=rC: break
    if len(s2)<rC:
        for si in range(1, len(hot_nums), 3):
            s2.add(hot_nums[si])
            if len(s2)>=rC: break
    s3 = set()
    for zmin,zmax in [[1,20],[21,40],[41,60],[61,80]]:
        c=0
        for n in hot_nums:
            if zmin<=n<=zmax: s3.add(n); c+=1
            if c>=5: break
    s4 = set()
    fscores = {}
    for n in range(1, rMax+1):
        if freq[n]==0 and miss[n]>=15: fscores[n] = -999
        elif miss[n]>=12: fscores[n] = -999
        else: fscores[n] = (freq[n]/freq_mean*10 if freq_mean>0 else 0) + miss[n]/total*8 + ema_score[n]*12
    fusion_list = sorted(range(1, rMax+1), key=lambda n: -fscores[n])
    for fi in range(rC): s4.add(fusion_list[fi])
    vote_count = {n: sum(1 for s in [s1,s2,s3,s4] if n in s) for n in range(1, rMax+1)}
    voted_list = sorted(range(1, rMax+1), key=lambda n: (-vote_count[n], -freq[n]))
    return sorted(voted_list[:rC]), voted_list

def recommend_kl8_enhanced(recent, rMax=80, rC=20):
    """6策略融合增强推荐（快乐8）"""
    total = len(recent)
    freq = {n: 0 for n in range(1, rMax+1)}
    last_seen = {n: -1 for n in range(1, rMax+1)}
    for i, d in enumerate(recent):
        ns = get_nums(d)
        for n in ns:
            if 1 <= n <= rMax: freq[n] += 1; last_seen[n] = i
    miss = {n: total-1-last_seen[n] for n in range(1, rMax+1)}
    hot_nums = sort_by_freq(freq, 1, rMax)
    freq_mean = sum(freq.values()) / rMax
    ema_score = {}
    for n in range(1, rMax+1):
        seq = [1 if n in get_nums(d) else 0 for d in recent]
        ema = seq[0] if seq else 0
        for v in seq[1:]: ema = 0.5*v+0.5*ema
        ema_score[n] = ema
    s1 = set(hot_nums[:rC])
    s2 = set()
    for si in range(0, len(hot_nums), 3):
        s2.add(hot_nums[si])
        if len(s2)>=rC: break
    if len(s2)<rC:
        for si in range(1, len(hot_nums), 3):
            s2.add(hot_nums[si])
            if len(s2)>=rC: break
    s3 = set()
    for zmin,zmax in [[1,20],[21,40],[41,60],[61,80]]:
        c=0
        for n in hot_nums:
            if zmin<=n<=zmax: s3.add(n); c+=1
            if c>=5: break
    s4 = set()
    fscores = {}
    for n in range(1, rMax+1):
        if freq[n]==0 and miss[n]>=15: fscores[n] = -999
        elif miss[n]>=12: fscores[n] = -999
        else: fscores[n] = (freq[n]/freq_mean*10 if freq_mean>0 else 0) + miss[n]/total*8 + ema_score[n]*12
    fl = sorted(range(1, rMax+1), key=lambda n: -fscores[n])
    for fi in range(rC): s4.add(fl[fi])
    s5 = set()
    for n in hot_nums[:60]: s5.add(n)
    cold_by_miss = sorted(range(1, rMax+1), key=lambda n: -miss[n])
    for n in cold_by_miss[:40]: s5.add(n)
    s6 = set(s1)
    for n in hot_nums:
        s6.add(n)
        if len(s6)>=rC: break
    vote6 = {n: sum(1 for s in [s1,s2,s3,s4,s5,s6] if n in s) for n in range(1, rMax+1)}
    enhanced_list = sorted(range(1, rMax+1), key=lambda n: (-vote6[n], -freq[n]))
    return sorted(enhanced_list[:rC]), enhanced_list

def kl8_dantuo(vl, recent=None, rC=20):
    cards = []
    # 置信度筛选: 按稳定度重排序(低方差号码优先做胆)
    dan_pool = list(vl[:rC])
    if recent and len(recent) > 5:
        import math
        win = min(30, len(recent))
        stability = {}
        for n in dan_pool:
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
        dan_pool = sorted(dan_pool, key=lambda n: (-stability[n], vl.index(n)))
    for dc in range(2,10):
        dan = sorted(dan_pool[:dc])
        ds = set(dan)
        tuo = sorted([n for n in vl[:rC] if n not in ds])
        cards.append({"dan":dan,"tuo":tuo})
    return cards

def recommend_lotto_blue(recent, bMax, bC):
    """蓝球多因素评分"""
    if bC<=0: return []
    total=len(recent)
    freq_b={n:0 for n in range(1,bMax+1)}
    last_seen_b={n:-1 for n in range(1,bMax+1)}
    for i,d in enumerate(recent):
        bs=get_blue(d)
        for n in bs:
            if 1<=n<=bMax: freq_b[n]+=1; last_seen_b[n]=i
    miss_b={n:total-1-last_seen_b[n] for n in range(1,bMax+1)}
    freq_b_mean=sum(freq_b.values())/bMax if bMax>0 else 0
    ema_b={}
    for n in range(1,bMax+1):
        seq=[1 if n in get_blue(d) else 0 for d in recent]
        e=seq[0] if seq else 0
        for v in seq[1:]: e=0.5*v+0.5*e; ema_b[n]=e
    b_scores={}
    for n in range(1,bMax+1):
        b_scores[n]=(freq_b[n]/freq_b_mean*10 if freq_b_mean>0 else 0)+miss_b[n]/total*8+ema_b[n]*12
    blue_list=sorted(range(1,bMax+1),key=lambda n:-b_scores[n])
    return sorted(blue_list[:bC])

def recommend_lotto(recent, rMax, rC, bMax, bC):
    """4策略投票推荐（乐透型）"""
    total = len(recent)
    freq_r={n:0 for n in range(1,rMax+1)}
    last_seen={n:-1 for n in range(1,rMax+1)}
    for i,d in enumerate(recent):
        for n in get_nums(d):
            if 1<=n<=rMax: freq_r[n]+=1; last_seen[n]=i
    miss_r={n:total-1-last_seen[n] for n in range(1,rMax+1)}
    hot_r=sort_by_freq(freq_r,1,rMax)
    freq_mean=sum(freq_r.values())/rMax
    ema_r={}
    for n in range(1,rMax+1):
        seq=[1 if n in get_nums(d) else 0 for d in recent]
        e=seq[0] if seq else 0
        for v in seq[1:]: e=0.5*v+0.5*e; ema_r[n]=e
    s1=set(hot_r[:rC])
    s2=set()
    for si in range(0,len(hot_r),2):
        s2.add(hot_r[si])
        if len(s2)>=rC: break
    if len(s2)<rC:
        for si in range(1,len(hot_r),2):
            s2.add(hot_r[si])
            if len(s2)>=rC: break
    s3=set()
    if rMax==33: zones=[[1,11],[12,22],[23,33]]
    elif rMax==35: zones=[[1,7],[8,14],[15,21],[22,28],[29,35]]
    else: zones=[[1,rMax//3],[rMax//3+1,rMax*2//3],[rMax*2//3+1,rMax]]
    per_zone=max(1,rC//len(zones))
    for zmin,zmax in zones:
        c=0
        for n in hot_r:
            if zmin<=n<=zmax: s3.add(n); c+=1
            if c>=per_zone: break
    s4=set()
    fscores={}
    for n in range(1,rMax+1):
        if freq_r[n]==0 and miss_r[n]>=total*0.3: fscores[n]=-999
        elif miss_r[n]>=total*0.25: fscores[n]=-999
        else: fscores[n]=(freq_r[n]/freq_mean*10 if freq_mean>0 else 0)+miss_r[n]/total*8+ema_r[n]*12
    fusion_list=sorted(range(1,rMax+1),key=lambda n:-fscores[n])
    for fi in range(rC): s4.add(fusion_list[fi])
    vote_count={n:sum(1 for s in [s1,s2,s3,s4] if n in s) for n in range(1,rMax+1)}
    scored=sorted(range(1,rMax+1),key=lambda n:(-vote_count[n],-freq_r[n]))
    # 奇偶修正
    final=[]; oc=sum(1 for n in scored[:rC] if n%2==1)
    if oc<2 or oc>4:
        odds=[n for n in scored if n%2==1]; evens=[n for n in scored if n%2==0]
        to=max(2,min(4,round(rC/2)))
        final=odds[:to]+evens[:rC-to]
    else: final=list(scored[:rC])
    basic_r=sorted(final[:rC])
    basic_b=recommend_lotto_blue(recent, bMax, bC)
    dantuo=[]
    for dr in range(2,min(rC,5)):
        dan=sorted(scored[:dr]); ds=set(dan)
        tuo=[n for n in scored if n not in ds][:rC-dr+4]
        bd=[basic_b[0]] if basic_b else []; bt=basic_b[1:] if len(basic_b)>1 else []
        dantuo.append({"dan":dan,"tuo":tuo,"blueDan":bd,"blueTuo":bt})
    return {"reds":basic_r,"blues":basic_b,"dantuo":dantuo}

def recommend_lotto_enhanced(recent, rMax, rC, bMax, bC):
    """6策略融合增强推荐（乐透型）"""
    total=len(recent)
    freq_r={n:0 for n in range(1,rMax+1)}
    last_seen={n:-1 for n in range(1,rMax+1)}
    for i,d in enumerate(recent):
        for n in get_nums(d):
            if 1<=n<=rMax: freq_r[n]+=1; last_seen[n]=i
    miss_r={n:total-1-last_seen[n] for n in range(1,rMax+1)}
    hot_r=sort_by_freq(freq_r,1,rMax)
    freq_mean=sum(freq_r.values())/rMax
    ema_r={}
    for n in range(1,rMax+1):
        seq=[1 if n in get_nums(d) else 0 for d in recent]
        e=seq[0] if seq else 0
        for v in seq[1:]: e=0.5*v+0.5*e; ema_r[n]=e
    # 质数
    primes=set()
    for n in range(2,rMax+1):
        for d in range(2,int(n**0.5)+1):
            if n%d==0: break
        else: primes.add(n)
    s1=set(hot_r[:rC])
    s2=set()
    for si in range(0,len(hot_r),2):
        s2.add(hot_r[si])
        if len(s2)>=rC: break
    if len(s2)<rC:
        for si in range(1,len(hot_r),2):
            s2.add(hot_r[si])
            if len(s2)>=rC: break
    s3=set()
    if rMax==33: zones=[[1,11],[12,22],[23,33]]
    elif rMax==35: zones=[[1,7],[8,14],[15,21],[22,28],[29,35]]
    else: zones=[[1,rMax//3],[rMax//3+1,rMax*2//3],[rMax*2//3+1,rMax]]
    pz=max(1,rC//len(zones))
    for zmin,zmax in zones:
        c=0
        for n in hot_r:
            if zmin<=n<=zmax: s3.add(n); c+=1
            if c>=pz: break
    s4=set()
    fs={}
    for n in range(1,rMax+1):
        if freq_r[n]==0 and miss_r[n]>=total*0.3: fs[n]=-999
        elif miss_r[n]>=total*0.25: fs[n]=-999
        else: fs[n]=(freq_r[n]/freq_mean*10 if freq_mean>0 else 0)+miss_r[n]/total*8+ema_r[n]*12
    fl=sorted(range(1,rMax+1),key=lambda n:-fs[n])
    for fi in range(rC): s4.add(fl[fi])
    # 策略5: 质数精选
    s5=set()
    for n in sorted([n for n in hot_r if n in primes])[:rC]: s5.add(n)
    for n in hot_r:
        s5.add(n)
        if len(s5)>=rC: break
    # 策略6: 隔期重现
    s6=set()
    if len(recent)>10:
        for n in get_nums(recent[10]):
            if 1<=n<=rMax: s6.add(n)
    for n in hot_r:
        s6.add(n)
        if len(s6)>=rC: break
    vote6={n:sum(1 for s in [s1,s2,s3,s4,s5,s6] if n in s) for n in range(1,rMax+1)}
    scored=sorted(range(1,rMax+1),key=lambda n:(-vote6[n],-freq_r[n]))
    # 奇偶修正
    final=[]; oc=sum(1 for n in scored[:rC] if n%2==1)
    if oc<2 or oc>4:
        odds=[n for n in scored if n%2==1]; evens=[n for n in scored if n%2==0]
        to=max(2,min(4,round(rC/2)))
        final=odds[:to]+evens[:rC-to]
    else: final=list(scored[:rC])
    er=sorted(final[:rC])
    bb=recommend_lotto_blue(recent, bMax, bC)
    dantuo=[]
    for dr in range(2,min(rC,5)):
        dan=sorted(scored[:dr]); ds=set(dan)
        tuo=[n for n in scored if n not in ds][:rC-dr+4]
        bd=[bb[0]] if bb else []; bt=bb[1:] if len(bb)>1 else []
        dantuo.append({"dan":dan,"tuo":tuo,"blueDan":bd,"blueTuo":bt})
    return {"reds":er,"blues":bb,"dantuo":dantuo}

def recommend_digit(recent, pos):
    """多策略数字彩推荐（3D/排列三/排列五/七星彩）"""
    total = len(recent)
    pfreq=[{n:0 for n in range(10)} for _ in range(pos)]
    plast=[{n:-1 for n in range(10)} for _ in range(pos)]
    for i, d in enumerate(recent):
        ns=get_nums(d)
        for pi in range(min(len(ns),pos)):
            n=ns[pi]
            if 0<=n<=9: pfreq[pi][n]+=1; plast[pi][n]=i
    pmiss=[{n:total-1-plast[pi][n] for n in range(10)} for pi in range(pos)]
    pmean=[sum(pfreq[pi].values())/10 for pi in range(pos)]
    pema=[[0]*10 for _ in range(pos)]
    for pi in range(pos):
        for n in range(10):
            seq=[1 if len(get_nums(d))>pi and get_nums(d)[pi]==n else 0 for d in recent]
            e=seq[0] if seq else 0
            for v in seq[1:]: e=0.4*v+0.6*e
            pema[pi][n]=e
    scored_pos=[]
    for pi in range(pos):
        scores={}
        for n in range(10):
            fs=(pfreq[pi][n]/pmean[pi]*10 if pmean[pi]>0 else 0)+pmiss[pi][n]/total*8+pema[pi][n]*12
            scores[n]=fs
        scored=sorted(range(10), key=lambda n:-scores[n])
        scored_pos.append(scored)
    basic=[]; dantuo=[]
    for pi in range(pos):
        hot=scored_pos[pi]; basic.append(hot[:3])
        dan=[hot[0]]; tuo=hot[1:6]; dantuo.append({"dan":dan,"tuo":tuo})
    z1=[scored_pos[pi][0] for pi in range(pos)]
    z2=[scored_pos[pi][1] for pi in range(pos)]
    z3=[scored_pos[pi][2] for pi in range(pos)]
    z4=[]
    for pi in range(pos):
        if pi%2==0: z4.append(scored_pos[pi][0])
        else: z4.append(scored_pos[pi][1])
    return {"basic":basic,"dantuo":dantuo,"multi":[z1,z2,z3,z4],"scored_pos":scored_pos}

now = int(time.time())
recs = []

def add_rec(t, period, date, basic_items, dantuo_data, multi=None, enhanced=None):
    r={"id":t+"_"+period+"_"+str(now),"type":t,"period":period,"date":date,
       "basic":basic_items,"dantuo":dantuo_data}
    if multi: r["multi"]=multi
    if enhanced: r["enhanced"]=enhanced
    recs.append(r)

kl8d=data.get("kl8",[])
if len(kl8d)>50:
    b20,vl=recommend_kl8(kl8d[:30])
    dt=kl8_dantuo(vl, kl8d[:30])
    e20,evl=recommend_kl8_enhanced(kl8d[:30])
    edt=kl8_dantuo(evl, kl8d[:30])
    add_rec("kl8",kl8d[0]["p"],kl8d[0]["d"],[{"nums":b20,"blues":[]}],dt,
            enhanced={"nums":e20,"dantuo":edt})
    print(f"kl8({kl8d[0]['p']}): 普通{len(b20)}码+{len(dt)}组胆拖 增强{len(e20)}码+{len(edt)}组胆拖")

ssqd=data.get("ssq",[])
if len(ssqd)>5:
    r=recommend_lotto(ssqd[:15],33,6,16,1)
    er=recommend_lotto_enhanced(ssqd[:15],33,6,16,1)
    add_rec("ssq",ssqd[0]["p"],ssqd[0]["d"],[{"nums":r["reds"],"blues":r["blues"]}],r["dantuo"],
            enhanced={"nums":er["reds"],"blues":er["blues"],"dantuo":er["dantuo"]})
    print(f"ssq({ssqd[0]['p']}): {r['reds']}+{r['blues']}, {len(r['dantuo'])}组胆拖")

dltd=data.get("dlt",[])
if len(dltd)>5:
    r=recommend_lotto(dltd[:15],35,5,12,2)
    er=recommend_lotto_enhanced(dltd[:15],35,5,12,2)
    add_rec("dlt",dltd[0]["p"],dltd[0]["d"],[{"nums":r["reds"],"blues":r["blues"]}],r["dantuo"],
            enhanced={"nums":er["reds"],"blues":er["blues"],"dantuo":er["dantuo"]})
    print(f"dlt({dltd[0]['p']}): {r['reds']}+{r['blues']}, {len(r['dantuo'])}组胆拖")

qlcd=data.get("qlc",[])
if len(qlcd)>5:
    r=recommend_lotto(qlcd[:15],30,7,1,0)
    er=recommend_lotto_enhanced(qlcd[:15],30,7,1,0)
    add_rec("qlc",qlcd[0]["p"],qlcd[0]["d"],[{"nums":r["reds"],"blues":[]}],r["dantuo"],
            enhanced={"nums":er["reds"],"dantuo":er["dantuo"]})
    print(f"qlc({qlcd[0]['p']}): {r['reds']}, {len(r['dantuo'])}组胆拖")

fc3d=data.get("fc3d",[])
if len(fc3d)>5:
    r=recommend_digit(fc3d[:30],3)
    add_rec("fc3d",fc3d[0]["p"],fc3d[0]["d"],
        [{"nums":[r["basic"][0][0],r["basic"][1][0],r["basic"][2][0]],"blues":[]},
         {"nums":[r["basic"][0][1],r["basic"][1][1],r["basic"][2][1]],"blues":[]},
         {"nums":[r["basic"][0][2],r["basic"][1][2],r["basic"][2][2]],"blues":[]}],
        [{"dan":[c["dan"][0]],"tuo":c["tuo"],"pos":i} for i,c in enumerate(r["dantuo"])],
        multi=r["multi"],
        enhanced={"pos":[sorted(r["scored_pos"][pi])[:5] for pi in range(3)],
                  "names":["百位","十位","个位"]})

pl3d=data.get("pl3",[])
if len(pl3d)>5:
    r=recommend_digit(pl3d[:30],3)
    add_rec("pl3",pl3d[0]["p"],pl3d[0]["d"],
        [{"nums":[r["basic"][0][0],r["basic"][1][0],r["basic"][2][0]],"blues":[]},
         {"nums":[r["basic"][0][1],r["basic"][1][1],r["basic"][2][1]],"blues":[]},
         {"nums":[r["basic"][0][2],r["basic"][1][2],r["basic"][2][2]],"blues":[]}],
        [{"dan":[c["dan"][0]],"tuo":c["tuo"],"pos":i} for i,c in enumerate(r["dantuo"])],
        multi=r["multi"],
        enhanced={"pos":[sorted(r["scored_pos"][pi])[:5] for pi in range(3)],
                  "names":["百位","十位","个位"]})

pl5d=data.get("pl5",[])
if len(pl5d)>5:
    r=recommend_digit(pl5d[:30],5)
    add_rec("pl5",pl5d[0]["p"],pl5d[0]["d"],
        [{"nums":[r["basic"][i][0] for i in range(5)],"blues":[]}],
        [{"dan":[c["dan"][0]],"tuo":c["tuo"],"pos":i} for i,c in enumerate(r["dantuo"])],
        multi=r["multi"],
        enhanced={"pos":[sorted(r["scored_pos"][pi])[:5] for pi in range(5)],
                  "names":["万位","千位","百位","十位","个位"]})

qxcd=data.get("qxc",[])
if len(qxcd)>5:
    r=recommend_digit(qxcd[:30],7)
    add_rec("qxc",qxcd[0]["p"],qxcd[0]["d"],
        [{"nums":[r["basic"][i][0] for i in range(7)],"blues":[]}],
        [{"dan":[c["dan"][0]],"tuo":c["tuo"],"pos":i} for i,c in enumerate(r["dantuo"])],
        multi=r["multi"],
        enhanced={"pos":[sorted(r["scored_pos"][pi])[:5] for pi in range(7)],
                  "names":["第1位","第2位","第3位","第4位","第5位","第6位","第7位"]})

saved_path = 'data/saved_recs.json'
existing = []
if os.path.exists(saved_path):
    try:
        with open(saved_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
    except: pass

by_key = {}
for r in existing:
    by_key[r.get("type","")+"_"+r.get("period","")] = r
for rec in recs:
    by_key[rec["type"]+"_"+rec["period"]] = rec

merged = sorted(by_key.values(), key=lambda r: r.get("id",""), reverse=True)

os.makedirs(os.path.dirname(saved_path), exist_ok=True)
with open(saved_path, 'w', encoding='utf-8') as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)

print(f"\nTotal: {len(merged)} records saved")
