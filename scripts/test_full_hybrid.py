"""
完整综合方案: 动量+重号/回补/热号+分区+尾数+奇偶+连号
"""
import json, urllib.request
from collections import Counter

URL = 'http://api.huiniao.top/interface/home/lotteryHistory?type=klb&page=1&limit=500'
FIELDS = ['one','two','three','four','five','six','seven','eight','nine','ten',
          'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty']
req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
resp = urllib.request.urlopen(req, timeout=30)
d = json.loads(resp.read().decode('utf-8'))
items = d['data']['data']['list']
data = []
for item in items:
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    data.append({'n': sorted(nums)})
def gn(d): return d.get('n', [])

def get_dantuo(data, dc):
    """综合方案选胆: 动量+重号/回补/热号+分区+尾数+奇偶"""
    idx_in_data = data['_idx']
    past = data['_past']
    recent = past[:30]
    pool35 = data['_pool35']
    freq = data['_freq']
    ema_s = data['_ema_s']
    miss = data['_miss']
    mom = data['_mom']
    
    prev_draw = set(gn(data['_all'][idx_in_data-1])) if idx_in_data > 30 else set()
    
    # 1) 重号/回补/热号 约束
    repeats = [n for n in pool35 if n in prev_draw]
    rebound = [n for n in pool35 if 6 <= miss.get(n, 100) <= 12]
    hot5 = [n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2)) >= 2]
    must = list(set(repeats[:3] + rebound[:3] + hot5[:3]))
    
    # 从动量top dc开始
    top = sorted(pool35, key=lambda n: -mom[n])[:dc]
    selected = list(top)
    
    # 强制补入约束号
    for n in must:
        if n not in selected:
            selected[-1] = n
            selected.sort(key=lambda n: -mom[n])
    
    # 2) 分区均衡矫正
    for _ in range(5):
        zc = {}
        for n in selected:
            z = (n - 1) // 20
            zc[z] = zc.get(z, 0) + 1
        overload = [z for z, c in zc.items() if c > max(3, dc // 4)]
        if not overload:
            break
        for oz in overload:
            onums = [n for n in selected if (n - 1) // 20 == oz]
            other = [n for n in pool35 if (n - 1) // 20 != oz and n not in selected]
            other.sort(key=lambda n: -mom[n])
            if other:
                to_go = min(onums, key=lambda n: mom[n])
                selected.remove(to_go)
                selected.append(other[0])
    
    # 3) 尾数热度矫正
    tail_hot = {}
    for t in range(10):
        tail_hot[t] = sum(1 for d2 in recent[:10] for nn in gn(d2) if nn % 10 == t)
    # 尽量保证选中的号覆盖至少5个不同尾数
    for _ in range(3):
        tails_in_sel = set(n % 10 for n in selected)
        if len(tails_in_sel) >= min(5, dc):
            break
        # 找一个未覆盖的热尾中的号替换最后一名
        cold_tails = [t for t in range(10) if t not in tails_in_sel]
        if cold_tails:
            best_tail = max(cold_tails, key=lambda t: tail_hot[t])
            candidates = [n for n in pool35 if n % 10 == best_tail and n not in selected]
            if candidates:
                candidates.sort(key=lambda n: -mom[n])
                selected[-1] = candidates[0]
                selected.sort(key=lambda n: -mom[n])
    
    # 4) 奇偶矫正
    odd_c = sum(1 for n in selected if n % 2 == 1)
    target_odd = max(dc // 2 - 1, 0)
    if odd_c > target_odd + 2:
        extra = [n for n in selected if n % 2 == 1]
        extra.sort(key=lambda n: mom[n])
        for n in extra:
            if odd_c <= target_odd + 2: break
            evens = [x for x in pool35 if x % 2 == 0 and x not in selected]
            evens.sort(key=lambda n: -mom[n])
            if evens:
                selected.remove(n)
                selected.append(evens[0])
                odd_c -= 1
    
    return selected[:dc]

print('=== 完整综合方案（动量+重号/回补/热号+分区+尾数+奇偶）===')
print()

for dc in [9, 11, 13, 15, 17, 19]:
    total = 0
    hits = []
    
    for idx in range(30, len(data)):
        past = data[idx-30:idx]
        draw = data[idx]
        drawn_set = set(gn(draw))
        recent = past[:30]
        total += 1
        
        # 6投票→35码池
        freq = {n: 0 for n in range(1, 81)}
        for d2 in recent:
            for nn in gn(d2):
                if 1 <= nn <= 80: freq[nn] += 1
        for ri in range(min(5, len(recent))):
            for nn in gn(recent[ri]):
                if 1 <= nn <= 80: freq[nn] += 2
        hot = sorted(range(1, 81), key=lambda nn: -freq[nn])
        fm = sum(freq.values()) / 80
        ema_s = {}
        for nn in range(1, 81):
            seq = [1 if nn in gn(d2) else 0 for d2 in recent]
            seq_rev = seq[::-1]
            e = seq_rev[0]
            for v in seq[1:]: e = 0.5*v+0.5*e; ema_s[nn] = e
        miss = {}
        for nn in range(1, 81):
            for i2, d2 in enumerate(recent):
                if nn in gn(d2): miss[nn] = i2; break
            else: miss[nn] = len(recent)
        s1 = set(hot[:20]); s2 = set()
        for si in range(0, len(hot), 3): s2.add(hot[si])
        if len(s2) < 20:
            for si in range(1, len(hot), 3): s2.add(hot[si])
        s3 = set()
        for zmin, zmax in [[1, 20], [21, 40], [41, 60], [61, 80]]:
            c = 0
            for nn in hot:
                if zmin <= nn <= zmax: s3.add(nn); c += 1
                if c >= 5: break
        s4 = set()
        fs = {nn: (freq[nn]/fm*10 if fm > 0 else 0) + miss[nn]/len(recent)*8 + ema_s[nn]*12 for nn in range(1, 81)}
        fl = sorted(range(1, 81), key=lambda nn: -fs[nn])
        for fi in range(20): s4.add(fl[fi])
        s5 = set(hot[:60]); cold = sorted(range(1, 81), key=lambda nn: -miss[nn])
        for nn in cold[:40]: s5.add(nn)
        s6 = set(s1)
        for nn in hot: s6.add(nn)
        votes = {nn: sum(1 for s in [s1, s2, s3, s4, s5, s6] if nn in s) for nn in range(1, 81)}
        pool35 = sorted(range(1, 81), key=lambda nn: (-votes[nn], -freq[nn]))[:35]
        
        mom = {n: sum(1 for d2 in recent[:5] if n in gn(d2))*3 + ema_s.get(n, 0)*12 + freq.get(n, 0)*0.5 for n in pool35}
        
        # 综合选胆
        prev_draw = set(gn(data[idx-1]))
        repeats = [n for n in pool35 if n in prev_draw]
        rebound = [n for n in pool35 if 6 <= miss.get(n, 100) <= 12]
        hot5 = [n for n in pool35 if sum(1 for d2 in recent[:5] if n in gn(d2)) >= 2]
        must = list(set(repeats[:3] + rebound[:3] + hot5[:3]))
        
        top = sorted(pool35, key=lambda n: -mom[n])[:dc]
        selected = list(top)
        for n in must:
            if n not in selected:
                selected[-1] = n
                selected.sort(key=lambda n: -mom[n])
        
        # 分区矫正
        for _ in range(5):
            zc = {}
            for n in selected:
                z = (n - 1) // 20
                zc[z] = zc.get(z, 0) + 1
            overload = [z for z, c in zc.items() if c > max(3, dc // 4)]
            if not overload: break
            for oz in overload:
                onums = [n for n in selected if (n - 1) // 20 == oz]
                other = [n for n in pool35 if (n - 1) // 20 != oz and n not in selected]
                other.sort(key=lambda n: -mom[n])
                if other:
                    to_go = min(onums, key=lambda n: mom[n])
                    selected.remove(to_go)
                    selected.append(other[0])
        
        # 尾数矫正
        tail_hot = {}
        for t in range(10):
            tail_hot[t] = sum(1 for d2 in recent[:10] for nn in gn(d2) if nn % 10 == t)
        for _ in range(3):
            tails_in = set(n % 10 for n in selected)
            if len(tails_in) >= min(5, dc): break
            cold_ts = [t for t in range(10) if t not in tails_in]
            if cold_ts:
                bt = max(cold_ts, key=lambda t: tail_hot[t])
                cands = [n for n in pool35 if n % 10 == bt and n not in selected]
                if cands:
                    cands.sort(key=lambda n: -mom[n])
                    selected[-1] = cands[0]
                    selected.sort(key=lambda n: -mom[n])
        
        # 奇偶矫正
        oc = sum(1 for n in selected if n % 2 == 1)
        target = max(dc // 2 - 1, 0)
        if oc > target + 2:
            extra = [n for n in selected if n % 2 == 1]
            extra.sort(key=lambda n: mom[n])
            for n in extra:
                if oc <= target + 2: break
                evens = [x for x in pool35 if x % 2 == 0 and x not in selected]
                evens.sort(key=lambda n: -mom[n])
                if evens:
                    selected.remove(n)
                    selected.append(evens[0])
                    oc -= 1
        
        h = sum(1 for n in selected[:dc] if n in drawn_set)
        hits.append(h)
    
    avg = sum(hits) / total
    mx = max(hits)
    g8 = sum(1 for h in hits if h >= 8)
    g9 = sum(1 for h in hits if h >= 9)
    g10 = sum(1 for h in hits if h >= 10)
    print(f'{dc:>2}胆: 均{avg:.2f}个 | 最高{mx:>2}个 | ≥8:{g8:>2}期 | ≥9:{g9:>2}期 | ≥10:{g10:>2}期')
