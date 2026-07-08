import json, urllib.request, time

FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

def fetch_page(page):
    r = urllib.request.Request(f'http://api.huiniao.top/interface/home/lotteryHistory?type=fcsd&page={page}&limit=500',
        headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(r, timeout=30) as resp:
        d = json.loads(resp.read().decode('utf-8'))
    if d.get('code') == 1: return d['data']['data']['list']
    return []

def parse_item(item):
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    return {"p": str(item.get("code","")), "d": str(item.get("day","")), "n": nums[:3]}

all_data = []
for page in [1, 2, 3]:
    items = fetch_page(page)
    if items:
        for item in items: all_data.append(parse_item(item))
    time.sleep(1)

seen = set()
deduped = []
for item in all_data:
    if item['p'] not in seen:
        seen.add(item['p']); deduped.append(item)

# 三期融合评分
def _window_score(data_pool, window_size, pos_count=3):
    win = min(window_size, len(data_pool[1:31]))
    ws = data_pool[1:1+win]
    n = len(ws)
    sc = {d:0 for d in range(10)}
    for pos in range(pos_count):
        for d in range(10):
            s = []
            for i in range(n):
                ns = ws[i]['n']
                s.append(1 if len(ns) > pos and ns[pos] == d else 0)
            s_rev = s[::-1]
            e = s_rev[0]
            for v in s[1:]: e = 0.5*v + 0.5*e
            shortE = s[0] if s else 0
            longE = s[0] if s else 0
            for v in s[1:]:
                shortE = 0.5*v + 0.5*shortE
                longE = 0.15*v + 0.85*longE
            macd = shortE - longE
            burst = sum(s[:3])
            miss = n
            for j in range(n):
                if s[j] == 1: miss=j; break
            missScore = 1.0 - miss/max(n,1)
            freq = sum(s)
            freqScore = freq/max(n,1)
            sc[d] += e*0.20 + max(-0.3,min(0.3,macd))*0.10 + (burst/3)*0.10 + missScore*0.30 + freqScore*0.30
    return sc

def get_scores_K(data_pool):
    s10 = _window_score(data_pool, 10)
    s20 = _window_score(data_pool, 20)
    s40 = _window_score(data_pool, 40)
    scores = {}
    for d in range(10):
        scores[d] = s10[d]*0.3 + s20[d]*0.4 + s40[d]*0.3
    # 冷号兜底
    use_data = data_pool[1:31]
    for pos in range(3):
        for d in range(10):
            appeared = False
            for r in use_data:
                if len(r['n']) > pos and r['n'][pos] == d:
                    appeared = True
                    break
            if not appeared: scores[d] += 0.5
    return scores

def algo_6(data_pool):
    scores = get_scores_K(data_pool)
    cooc = {d:{dd:0 for dd in range(10)} for d in range(10)}
    win = min(31, len(data_pool))
    for ci in range(win):
        cn = data_pool[ci]['n']
        for a in range(len(cn)):
            for b in range(a+1, len(cn)):
                cooc[cn[a]][cn[b]] += 1; cooc[cn[b]][cn[a]] += 1
    ranked = sorted(range(10), key=lambda n:-scores[n])
    g = [ranked[0]]; u = {ranked[0]}
    while len(g) < 6:
        bestN=-1; bestS=-999
        for dn in ranked:
            if dn in u: continue
            cs = sum(cooc[dn][m] for m in g)
            sc = cs*0.4 + scores[dn]*0.5
            if sc > bestS: bestS=sc; bestN=dn
        if bestN >= 0: g.append(bestN); u.add(bestN)
        else: break
    return sorted(g)

print('===== 6码（三期融合评分）最长连失分析 =====')
print()

for label, date_cut in [('全部4年', None), ('最近2年', '2024-06-01'), ('最近1年', '2025-06-01')]:
    hit3 = total = 0; streak = 0; max_streak = 0
    max_start = None; max_end = None; cur_start = None
    streaks = []
    for i in range(0, len(deduped)-30):
        test_date = deduped[i]['d']
        if date_cut and test_date < date_cut: continue
        total += 1
        dp = deduped[i:i+31]
        draw_set = set(deduped[i]['n'])
        group = algo_6(dp)
        h = len(draw_set & set(group))
        if h < 3:
            if streak == 0: cur_start = test_date
            streak += 1
            if streak > max_streak:
                max_streak = streak; max_start = cur_start; max_end = test_date
        else:
            hit3 += 1
            if streak > 0: streaks.append(streak)
            streak = 0
    if streak > 0: streaks.append(streak)
    streaks.sort(reverse=True)
    pct = hit3/total*100 if total else 0
    print(f'【{label}】')
    print(f'  期数: {total}, 中3: {hit3}次 ({pct:.1f}%) 约{total/max(hit3,1):.1f}期/次')
    print(f'  最长连失: {max_streak}期 ({max_start} ~ {max_end})')
    print(f'  连失TOP5: {streaks[:5]}')
    dist = {"1-4期":0,"5-9期":0,"10-14期":0,"15-19期":0,"20+期":0}
    for s in streaks:
        if s <= 4: dist["1-4期"]+=1
        elif s <= 9: dist["5-9期"]+=1
        elif s <= 14: dist["10-14期"]+=1
        elif s <= 19: dist["15-19期"]+=1
        else: dist["20+期"]+=1
    print(f'  连失分布: {dist}')
    print()

print('===== 最近2年 · 只看组六开奖 =====')
hit3 = 0; zuliu_total = 0; streak = 0; max_streak = 0; max_start = None; max_end = None; cur_start = None
for i in range(0, len(deduped)-30):
    test_date = deduped[i]['d']
    if test_date < '2024-06-01': continue
    dp = deduped[i:i+31]
    draw_set = set(deduped[i]['n'])
    if len(draw_set) < 3: continue
    zuliu_total += 1
    group = algo_6(dp)
    h = len(draw_set & set(group))
    if h < 3:
        if streak == 0: cur_start = test_date
        streak += 1
        if streak > max_streak:
            max_streak = streak; max_start = cur_start; max_end = test_date
    else:
        hit3 += 1; streak = 0

print(f'  组六开奖: {zuliu_total}期')
print(f'  中3: {hit3}次 ({hit3/zuliu_total*100:.1f}%) 约{zuliu_total/max(hit3,1):.1f}期/次')
print(f'  最长连失: {max_streak}期 ({max_start} ~ {max_end})')

today = algo_6(deduped[:31])
print()
print(f'今日推荐6码: {"".join(str(n) for n in today)}')
