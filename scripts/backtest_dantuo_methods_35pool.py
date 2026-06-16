#!/usr/bin/env python3
"""
回测35码池内胆码筛选方法——哪种二次筛选命中率最高
"""
import json, sys, math, statistics
from collections import Counter

with open('data/kl8_500.json', 'r', encoding='utf-8') as f:
    RAW = json.load(f)

def get_nums(d):
    return d.get("n", d.get("r", []))

class DataWindow:
    """模拟网站数据窗口"""
    def __init__(self, data, window=50):
        self.raw = data
        self.window = window

    def compute_ema_scores(self, recs, alpha=0.5):
        knEma = {}
        for i in range(1, 81):
            seq = [1 if i in get_nums(d) else 0 for d in recs]
            if not seq:
                knEma[i] = 0
                continue
            seq_rev = seq[::-1]
            e = seq_rev[0]
            for v in seq[1:]:
                e = alpha * v + (1 - alpha) * e
            knEma[i] = e
        return knEma

    def compute_kill_set(self, recs):
        nMin, nMax = 1, 80
        freq = {i: 0 for i in range(nMin, nMax + 1)}
        last = {i: -1 for i in range(nMin, nMax + 1)}
        for rdi, d in enumerate(recs):
            for n in get_nums(d):
                if nMin <= n <= nMax:
                    freq[n] += 1
                    last[n] = rdi
        miss = {i: len(recs) - 1 - last[i] for i in range(nMin, nMax + 1)}
        kills = set()
        for i in range(nMin, nMax + 1):
            if freq[i] == 0 and miss[i] >= 15:
                kills.add(i)
            elif miss[i] >= 12:
                kills.add(i)
        return kills, miss

    def get_top35(self, recs, alpha=0.5):
        """返回35码池（基于EMA评分）"""
        nMin, nMax = 1, 80
        win30 = min(30, len(recs))
        kills, miss = self.compute_kill_set(recs)
        ema = self.compute_ema_scores(recs, alpha)
        freq30 = {i: 0 for i in range(nMin, nMax + 1)}
        for j in range(win30):
            for n in get_nums(recs[j]):
                if nMin <= n <= nMax:
                    freq30[n] += 1
        r5, p5 = {i: 0 for i in range(nMin, nMax + 1)}, {i: 0 for i in range(nMin, nMax + 1)}
        for j in range(min(10, len(recs))):
            for n in get_nums(recs[j]):
                if j < 5:
                    r5[n] += 1
                else:
                    p5[n] += 1
        mom = {}
        for i in range(nMin, nMax + 1):
            mom[i] = max(-2, min(2, (r5[i] - p5[i]) / max(p5[i], 1)))
        prev = set(get_nums(recs[1])) if len(recs) > 1 else set()
        scores = {}
        for i in range(nMin, nMax + 1):
            s = (ema[i] or 0) * 5.0 + (freq30[i] / win30) * 3.0 + (mom[i] or 0) * 2.0
            if i in prev:
                s += 3.0
            if i in kills:
                s = -999
            s += max(0, 10 - (miss.get(i, 50))) * 0.5
            scores[i] = s
        ranked = sorted(range(nMin, nMax + 1), key=lambda n: -scores[n])
        return ranked[:35], ranked, scores, freq30, mom, prev

    def method_ema(self, top35, ranked, scores, freq30, mom, prev):
        """方法1（现有）：直接取排序前N"""
        return top35  # 35码池本身就是EMA排序

    def method_vote(self, top35, ranked, scores, freq30, mom, prev):
        """方法2：多因子投票
        EMA评分排名 + 动量排名 + 30期频率排名，三票总分"""
        nMin, nMax = 1, 80
        votes = {n: 0 for n in top35}
        # EMA排名分
        for rank, n in enumerate(ranked):
            if n in votes:
                votes[n] += max(0, 35 - rank)
        # 动量排名分
        mom_ranked = sorted(top35, key=lambda n: -mom.get(n, -999))
        for rank, n in enumerate(mom_ranked):
            votes[n] += max(0, 35 - rank)
        # 频率排名分
        freq_ranked = sorted(top35, key=lambda n: -freq30.get(n, -999))
        for rank, n in enumerate(freq_ranked):
            votes[n] += max(0, 35 - rank)
        sorted_votes = sorted(top35, key=lambda n: -votes[n])
        return sorted_votes

    def method_zone(self, top35, ranked, scores, freq30, mom, prev):
        """方法3：四区均衡 + EMA排序
        每区至少选x个，然后按评分补满"""
        zones = [(1, 20), (21, 40), (41, 60), (61, 80)]
        result = []
        used = set()
        for zmin, zmax in zones:
            zone_nums = [n for n in top35 if zmin <= n <= zmax]
            # 每区先拿最好的2个
            for n in zone_nums[:2]:
                if n not in used:
                    result.append(n)
                    used.add(n)
        # 剩余按评分补满到35
        for n in top35:
            if n not in used:
                result.append(n)
                used.add(n)
        return result

    def method_cool_mix(self, top35, ranked, scores, freq30, mom, prev):
        """方法4：EMA + 动量 + 频率混合评分（已有）"""
        return top35  # 同方法1

    def method_antihot(self, top35, ranked, scores, freq30, mom, prev):
        """方法5：排除过热号（近5期≥3次降权）
        热度太高容易回调"""
        hot_penalty = {}
        for n in top35:
            r5_count = 0
            # 直接用mom里的r5数据
            hot_penalty[n] = 0
        return top35  # 和现有一样，但筛选胆码时会考虑


def backtest(alpha=0.5, total_periods=470, window=50):
    """滚动回测所有方法"""
    dw = DataWindow(RAW, window)

    methods = {
        "A_EMA现方案": lambda t35, r, s, f, m, p: t35,
        "B_多因子投票": dw.method_vote,
        "C_四区均衡": dw.method_zone,
    }

    results = {name: {dc: {"hits": 0, "total": 0} for dc in [2, 3, 4, 5, 6]}
               for name in methods}

    for start in range(0, total_periods - window):
        recs = RAW[start:start + window]
        draw = RAW[start]  # 最新一期作为开奖
        draw_set = set(get_nums(draw))

        top35_list, ranked, scores, freq30, mom, prev = dw.get_top35(recs, alpha)

        for mname, mfunc in methods.items():
            ordered = mfunc(top35_list, ranked, scores, freq30, mom, prev)
            for dc in [2, 3, 4, 5, 6]:
                dans = ordered[:dc]
                hits = sum(1 for n in dans if n in draw_set)
                results[mname][dc]["hits"] += hits
                results[mname][dc]["total"] += dc

        if start % 100 == 0:
            print(f"  进度: {start}/{total_periods - window}", file=sys.stderr)

    return results


def print_results(results):
    print(f"\n{'='*70}")
    print(f"回测: {len(RAW)}期数据, 50期滚动窗口, EMA系数={0.5}")
    print(f"{'='*70}")
    print(f"{'方法':<20} {'胆数':<6} {'命中率':<10} {'命中/总':<15}")
    print(f"{'-'*55}")

    for mname, dc_data in results.items():
        for dc in [2, 3, 4, 5, 6]:
            d = dc_data[dc]
            rate = d["hits"] / d["total"] * 100 if d["total"] > 0 else 0
            print(f"{mname:<20} {dc:<6} {rate:>6.2f}%   {d['hits']}/{d['total']}")


def print_comparison(results, top_n=8):
    """对比每种方法在2胆/4胆上的排名"""
    print(f"\n{'='*70}")
    print(f"各方法在35码池选胆命中率对比（仅排序，非覆盖数）")
    print(f"{'='*70}")

    for dc in [2, 3, 4, 5, 6]:
        print(f"\n--- {dc}胆命中率排名 ---")
        items = []
        for mname, dc_data in results.items():
            d = dc_data[dc]
            rate = d["hits"] / d["total"] * 100 if d["total"] > 0 else 0
            items.append((rate, mname, d["hits"], d["total"]))
        items.sort(reverse=True)
        for rank, (rate, mname, hits, total) in enumerate(items, 1):
            print(f"  #{rank} {mname:<20} {rate:.2f}% ({hits}/{total})")


if __name__ == "__main__":
    print("运行回测中...（约470期 × 3种方法）")
    results = backtest(alpha=0.5, total_periods=470, window=50)
    print_results(results)
    print_comparison(results)
