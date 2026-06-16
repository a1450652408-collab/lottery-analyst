import json, re
from collections import Counter
from math import comb

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()
m = re.search(r'window\.__LOTTERY_DATA\s*=\s*(\{.*?\});\s*\n</script>', html, re.DOTALL)
data = json.loads(m.group(1))

def get_nums(d): return d.get("n", d.get("r", []))
def get_blues(d):
    b = d.get("b", [])
    if not isinstance(b, list): b = [b]
    return b

def stddev(vals):
    m = sum(vals)/len(vals)
    return (sum((x-m)**2 for x in vals)/len(vals))**0.5

# ===== 旧版 =====
def old_score(data_slice, rMax, bMax):
    freq = {n: 0 for n in range(1, rMax+1)}
    miss = {n: len(data_slice) for n in range(1, rMax+1)}
    for i, d in enumerate(data_slice):
        for n in get_nums(d):
            if n in freq: freq[n] += 1; miss[n] = min(miss[n], i)
    recent = [0]*(rMax+1)
    for d in data_slice[:10]:
        for n in get_nums(d):
            if 1 <= n <= rMax: recent[n] += 1
    scores = {n: (freq[n] or 0)*1.0 + (miss.get(n, len(data_slice)) or 0)*0.3 + (recent[n] or 0)*3.0 for n in range(1, rMax+1)}
    ranked = sorted(range(1, rMax+1), key=lambda n: -scores[n])
    top9 = ranked[:9]
    bfreq = {n: 0 for n in range(1, bMax+1)}
    for d in data_slice:
        for b in get_blues(d):
            if b in bfreq: bfreq[b] += 1
    brecent = {n: 0 for n in range(1, bMax+1)}
    for d in data_slice[:10]:
        for b in get_blues(d):
            if 1 <= b <= bMax: brecent[b] += 1
    bscores = {n: bfreq[n]*0.5 + brecent[n]*3.0 for n in range(1, bMax+1)}
    branked = sorted(range(1, bMax+1), key=lambda n: -bscores[n])
    return top9, branked[:3]

# ===== 新版 =====
def new_score(data_slice, rMax, bMax):
    freq = {n: 0 for n in range(1, rMax+1)}
    miss = {n: len(data_slice) for n in range(1, rMax+1)}
    for i, d in enumerate(data_slice):
        for n in get_nums(d):
            if n in freq: freq[n] += 1; miss[n] = min(miss[n], i)
    freq_mean = sum(freq.values())/rMax
    freq_sd = stddev(list(freq.values()))
    ema = {}
    for n in range(1, rMax+1):
        seq = [1 if n in get_nums(d) else 0 for d in data_slice]
        seq_rev = seq[::-1]
        e = seq_rev[0]
        for v in seq[1:]: e = 0.5*v + 0.5*e
        ema[n] = e
    # 简化趋势
    trend = {}
    for n in range(1, rMax+1):
        seq = [1 if n in get_nums(d) else 0 for d in data_slice[:20]]
        if len(seq) < 5: trend[n] = 0; continue
        xs = list(range(len(seq)))
        mx = sum(xs)/len(xs); my = sum(seq)/len(seq)
        num = sum((xs[i]-mx)*(seq[i]-my) for i in range(len(seq)))
        den = sum((x-mx)**2 for x in xs)
        slope = num/den if den > 0 else 0
        r2 = (num**2/(den*sum((y-my)**2 for y in seq)+0.001)) if den > 0 else 0
        trend[n] = slope * r2 * 3
    scores = {}
    for n in range(1, rMax+1):
        emaW = (ema[n] or 0) * 0.50
        zW = stddev([freq[n]]) * 0 if len([freq[n]]) < 2 else zscore(freq[n] or 0, freq_mean, freq_sd) * 0.15
        trendW = trend.get(n, 0)
        scores[n] = emaW + trendW
    
    if rMax == 33: zones = [[1, 11], [12, 22], [23, 33]]
    elif rMax == 35: zones = [[1, 12], [13, 23], [24, 35]]
    else: zones = [[1, rMax//3], [rMax//3+1, rMax*2//3], [rMax*2//3+1, rMax]]
    
    ranked = sorted(range(1, rMax+1), key=lambda n: -scores[n])
    picked = []
    for zn in zones:
        for n in ranked:
            if len(picked) >= 9: break
            if zn[0] <= n <= zn[1] and n not in picked: picked.append(n)
    for n in ranked:
        if len(picked) >= 9: break
        if n not in picked: picked.append(n)
    
    bfreq = {n: 0 for n in range(1, bMax+1)}
    bmiss = {n: len(data_slice) for n in range(1, bMax+1)}
    for i, d in enumerate(data_slice):
        for b in get_blues(d):
            if 1 <= b <= bMax: bfreq[b] += 1; bmiss[b] = min(bmiss[b], i)
    brecent = {n: 0 for n in range(1, bMax+1)}
    for d in data_slice[:10]:
        for b in get_blues(d):
            if 1 <= b <= bMax: brecent[b] += 1
    bscores = {n: bfreq[n]*0.3 + brecent[n]*3.0 + (len(data_slice)-bmiss[n])*0.2 for n in range(1, bMax+1)}
    branked = sorted(range(1, bMax+1), key=lambda n: -bscores[n])
    return picked, branked[:3]

for lot_type in ['ssq', 'dlt']:
    raw = data.get(lot_type, [])
    if len(raw) < 15: continue
    rMax = 33 if lot_type == 'ssq' else 35
    bMax = 16 if lot_type == 'ssq' else 12
    old_rh, new_rh = [], []
    old_bh, new_bh = [], []
    for idx in range(len(raw)-20):
        train = raw[idx+1:idx+16]
        if len(train) < 10: continue
        actual = set(get_nums(raw[idx]))
        ab = set(get_blues(raw[idx]))
        o9, o3b = old_score(train, rMax, bMax)
        n9, n3b = new_score(train, rMax, bMax)
        old_rh.append(len(set(o9) & actual))
        new_rh.append(len(set(n9) & actual))
        old_bh.append(1 if set(o3b) & ab else 0)
        new_bh.append(1 if set(n3b) & ab else 0)
    n = len(old_rh)
    print(f"\n--- {lot_type.upper()} (n={n}) ---")
    print(f"红球均命中: 旧{sum(old_rh)/n:.2f} -> 新{sum(new_rh)/n:.2f}")
    for thr in [3,4,5]:
        op = sum(1 for h in old_rh if h>=thr)/n*100
        np = sum(1 for h in new_rh if h>=thr)/n*100
        arrow = "+" if np > op else ""
        print(f"  >= {thr}红: {op:.0f}% -> {np:.0f}% ({arrow}{np-op:.0f}%)")
    print(f"蓝球中: 旧{sum(old_bh)/n*100:.0f}% -> 新{sum(new_bh)/n*100:.0f}%")
