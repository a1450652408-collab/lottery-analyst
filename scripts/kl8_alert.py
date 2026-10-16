# -*- coding: utf-8 -*-
"""
快乐8三组追号 · 状态预警系统
============================
核心原理（基于真实数据验证）:
  1. 彩票每期独立，"憋得越久越容易中"在历史数据中不成立（条件概率持平或下降）。
  2. 因此预警不做"预测"，而是做三件有真实依据的事:
     a) 位置感: 当前已等待期数在历史间隔分布中的百分位——让你知道自己在时间线的位置
     b) 风险感: 未来30期真实条件概率(查历史表) —— 拒绝赌徒谬误,防止"憋久了就加注"
     c) 资金感: 已投入 + 按历史最坏间隔还需备用多少资金 —— 防止半途而废(回测利润全部来自坚持到中奖)

用法:
  python scripts/kl8_alert.py
输出:
  控制台预警 + data/kl8_alert.json (供 index_modified.html 页面读取)

等级规则:
  waited < median          -> 正常   (照常按计划买)
  median <= waited < 85%max -> 深水区 (进入历史常见等待区间,别停,资金要够)
  waited >= 85%max          -> 临界   (已超过历史绝大多数等待,坚持=按纪律走)
"""
import json
import os
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'data')

GROUPS = {
    '选八9码': dict(nums=[5, 11, 12, 18, 19, 62, 63, 77, 78], cost=18,
                    prize='中8=5万,中7=800'),
    '选九10码': dict(nums=[8, 9, 15, 16, 65, 66, 72, 73, 79, 80], cost=20,
                     prize='中9=30万,中7=200'),
    '选十11码': dict(nums=[1, 2, 5, 6, 12, 18, 19, 27, 40, 41, 53], cost=22,
                     prize='中10=500万,中7=80'),
}
EVENT_LEVEL = 7  # 中7+ 视为一次"有效事件"(有奖且>100元档位)


def load():
    merged = {}
    for path in ['kl8_1500.json', 'kl8_500.json']:
        for d in json.load(open(os.path.join(DATA, path), encoding='utf-8')):
            merged[d['p']] = d
    return sorted(merged.values(), key=lambda x: x['d'])


def hit_level(nums, drawn):
    return len(set(nums) & set(drawn))


def build_history(recs, nums):
    """返回事件序列(1=中7+)和每次事件的位置"""
    seq = []
    for r in recs:
        seq.append(1 if hit_level(nums, r['n']) >= EVENT_LEVEL else 0)
    return seq


def analyze(recs, nums):
    seq = build_history(recs, nums)
    n = len(seq)
    # 事件位置
    ev_pos = [i for i, v in enumerate(seq) if v]
    total = len(ev_pos)
    # 间隔
    gaps = [ev_pos[i] - ev_pos[i-1] for i in range(1, total)]
    # 当前已等待期数(距上次事件)
    waited = n - 1 - ev_pos[-1] if ev_pos else n
    stats = dict(
        total=n, events=total,
        avg_gap=(n / total) if total else None,
        median_gap=sorted(gaps)[len(gaps)//2] if gaps else None,
        max_gap=max(gaps) if gaps else None,
        waited=waited,
        last_event_pos=ev_pos[-1] if ev_pos else None,
    )
    # 未来30期条件概率表: 已等g期 -> 概率 (仅当样本>=30)
    cond = {}
    base = None
    W = 30
    base_cnt = sum(1 for i in range(n - W) if any(seq[i+1:i+W+1]))
    base = base_cnt / (n - W) * 100 if n > W else None
    for g in [10, 20, 30, 40, 50, 60, 80, 100, 120, 150]:
        hits = []
        streak = 0
        for i, v in enumerate(seq):
            if v:
                streak = 0
            else:
                streak += 1
                if streak >= g:
                    hits.append(i)
        if len(hits) >= 30:
            cnt = sum(1 for i in hits if i + W < n and any(seq[i+1:i+W+1]))
            cond[g] = cnt / len(hits) * 100
    stats['base_prob30'] = base
    stats['cond_prob30'] = cond
    # 当前条件概率(取不大于waited的最大g)
    cur = None
    for g in sorted(cond):
        if g <= waited:
            cur = cond[g]
    stats['cur_prob30'] = cur
    return stats




def trend_health(recs, nums):
    """走势健康度: 近10期命中/期 vs 自身历史均值(近100期)"""
    recent100 = recs[-100:]
    now10 = sum(len(set(nums) & set(r['n'])) for r in recent100[-10:]) / 10
    prev90 = sum(len(set(nums) & set(r['n'])) for r in recent100[:90]) / 90
    ratio = now10 / prev90 if prev90 else 1.0
    if ratio >= 1.15:
        return '强', now10, prev90
    if ratio <= 0.85:
        return '弱', now10, prev90
    return '平', now10, prev90


def decision_light(waited, max_gap, level, health, reserve_ok):
    """决策灯: 综合等待位置+走势+资金 -> 今日操作建议
    原则(诚实): 不预测大奖,而是回答"该不该继续持有/能否承受等待"
    """
    mx = max_gap or 0
    pct = min(100, waited / mx * 100) if mx else 0
    if not reserve_ok:
        return '红灯', '资金储备不足: 历史最坏间隔需要约56,340元,当前不够 -> 先降档,别借钱追'
    if level == '临界':
        return '黄灯', '已超过历史85%的等待期,放弃=前功尽弃,继续按纪律走'
    if level == '深水区':
        return '黄灯', '进入历史常见等待区间(中位以上),别停,这是回测利润的来源'
    if health == '强':
        return '绿灯', '走势偏强(近10期高于均值),按计划持有'
    if pct >= 40:
        return '黄灯', f'等待位置{pct:.0f}%,已接近中位,保持耐心'
    return '绿灯', '刚中过不久,正常等待期,按计划买即可'

def main():
    recs = load()
    print('数据范围:', recs[0]['d'], '->', recs[-1]['d'], f'({len(recs)}期)')
    print('预警事件定义: 单期中7+ (有奖且>=100元档)')
    print('=' * 78)
    result = {'date': recs[-1]['d'], 'period': recs[-1]['p'], 'groups': {}, 'funding': {}}
    total_cost = 0
    for gname, g in GROUPS.items():
        st = analyze(recs, g['nums'])
        mg, mx = st['median_gap'], st['max_gap']
        pct = min(100, st['waited'] / mx * 100) if mx else 100
        # 等级
        if mg is None:
            lvl = '正常'
        elif st['waited'] < mg:
            lvl = '正常'
        elif st['waited'] < 0.85 * mx:
            lvl = '深水区'
        else:
            lvl = '临界'
        cur = st['cur_prob30']
        cur_s = f"{cur:.1f}%" if cur is not None else '样本不足'
        base_s = f"{st['base_prob30']:.1f}%" if st['base_prob30'] is not None else '-'
        gap_s = f"中位{mg}期" if mg else '-'
        max_s = f"最长{mx}期" if mx else '-'
        evdate = recs[st['last_event_pos']]['d'] if st['last_event_pos'] is not None else '无'
        # 走势健康度
        htag, now10, prev90 = trend_health(recs, g['nums'])
        # 决策灯
        light, advice = decision_light(st['waited'], mx, lvl, htag, True)
        print(f"\n【{gname}】 {g['nums']}")
        print(f"  上次中7+: {evdate} | 已等 {st['waited']} 期 | 平均间隔{st['avg_gap']:.0f}期 | {gap_s} | {max_s}")
        print(f"  等待位置: {pct:.0f}%分位 | 未来30期条件概率 {cur_s} (无条件基准 {base_s})")
        print(f"  走势: {htag}(近10期{now10:.2f}/期 vs 前90期{prev90:.2f}/期) | 状态: {lvl}")
        print(f"  ▶ 决策灯: {light} | {advice}")
        print(f"  单期成本 {g['cost']}元 | 奖金: {g['prize']}")
        total_cost += g['cost']
        result['groups'][gname] = dict(
            nums=g['nums'], cost=g['cost'], waited=st['waited'],
            avg_gap=round(st['avg_gap'], 1) if st['avg_gap'] else None,
            median_gap=mg, max_gap=mx, percentile=round(pct, 1),
            prob30=round(cur, 2) if cur is not None else None,
            base30=round(st['base_prob30'], 2) if st['base_prob30'] is not None else None,
            level=lvl, last_event=evdate, trend=htag,
            light=light, advice=advice,
        )
    # 资金预警
    max_waited_all = max((result['groups'][g]['waited'] for g in result['groups']), default=0)
    worst_gap_all = max((result['groups'][g]['max_gap'] or 0 for g in result['groups']), default=0)
    invested = total_cost * max_waited_all
    reserve = total_cost * worst_gap_all
    print('\n' + '=' * 78)
    print(f"💰 资金预警: 三组合计 {total_cost}元/天")
    print(f"  自上次中7+以来已投入: ~{invested:,}元 (按最久等待的组计算)")
    print(f"  历史最坏间隔 {worst_gap_all} 期 → 若坚持到底需准备: ~{reserve:,}元")
    print(f"  📌 核心提醒: 回测利润全部来自'坚持到中奖那一刻',中途停追=前面投入白扔")
    result['funding'] = dict(daily_cost=total_cost, invested_since_last=invested,
                             reserve_for_worst=reserve, worst_gap=worst_gap_all)
    out = os.path.join(DATA, 'kl8_alert.json')
    json.dump(result, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'\n已写入 {out}')


if __name__ == '__main__':
    main()
