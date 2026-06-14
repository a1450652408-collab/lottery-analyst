#!/usr/bin/env python3
"""
选一单注 五期阶梯方案 按月回测（2025-2026）
方案: 第1~5期每期x2, 第6~10期每期x2.5
选号: 每周期随机生成1个号码（1-80）
"""

import json
import random
from collections import defaultdict

# 加载数据
data = json.load(open(r'C:\Users\14506\WorkBuddy\Claw\data\kl8_1500.json'))
print(f"总数据: {len(data)}条")
print(f"最新: {data[0]['d']} | 最旧: {data[-1]['d']}")
print()

# 按年月分组
by_month = defaultdict(list)
for draw in data:
    date_str = draw['d']
    ym = date_str[:7]  # 2025-03
    by_month[ym].append(draw)

print(f"覆盖月份: {len(by_month)}个月")
for ym in sorted(by_month.keys()):
    print(f"  {ym}: {len(by_month[ym])}期")
print()

# 参数
BASE = 2          # 基础投注 2元
PRIZE = 4.6       # 中奖 4.6元

def run_cycle(data_chunk):
    """在 data_chunk 上跑一个完整的策略循环，返回每日净收益列表"""
    results = []       # 每个周期的结果
    pos_in_cycle = 0   # 当前是周期第几期 (0-based)
    mult = 1.0         # 当前倍数
    cycle_cost = 0     # 当前周期的已投入
    
    # 每周期随机选一个号
    current_pick = random.randint(1, 80)
    
    for draw in data_chunk:
        nums = draw['n']  # 开奖号码列表
        
        if pos_in_cycle == 0:
            # 新周期开始
            current_pick = random.randint(1, 80)
            mult = 1.0
            cycle_cost = 0
        
        # 确定当前期倍数和成本
        if pos_in_cycle == 0:
            mult = 1.0
        elif pos_in_cycle < 5:
            mult *= 2
        else:
            mult *= 2.5
        
        cost = round(BASE * mult)
        cycle_cost += cost
        
        # 检查是否中奖
        won = current_pick in nums
        
        if won:
            prize = PRIZE * mult
            net = prize - cycle_cost  # 净赚 = 中奖 - 本周期全部投入（含当期）
            results.append({
                'date': draw['d'],
                'period': draw['p'],
                'pick': current_pick,
                'period_in_cycle': pos_in_cycle + 1,
                'cost': cost,
                'cycle_cost': cycle_cost,
                'prize': round(prize, 1),
                'net': round(net, 1)
            })
            # 重置周期
            pos_in_cycle = 0
            cycle_cost = 0
            mult = 1.0
        else:
            pos_in_cycle += 1
            if pos_in_cycle >= 10:
                # 10期全不中，止损
                results.append({
                    'date': draw['d'],
                    'period': draw['p'],
                    'pick': current_pick,
                    'period_in_cycle': pos_in_cycle,
                    'cost': cost,
                    'cycle_cost': cycle_cost,
                    'prize': 0,
                    'net': -cycle_cost
                })
                # 重置
                pos_in_cycle = 0
                cycle_cost = 0
                mult = 1.0
    
    # 处理未完成的周期
    if pos_in_cycle > 0:
        # 不记录未结束的周期
        pass
    
    return results


# 由于随机性，跑多次取平均
NUM_RUNS = 50
all_monthly = defaultdict(list)

print(f"正在回测... 每次随机选号，跑 {NUM_RUNS} 轮取平均")
print()

for run in range(NUM_RUNS):
    random.seed(run)  # 可复现
    results = run_cycle(data)
    
    # 按月份统计
    monthly = defaultdict(lambda: {'cycles': 0, 'wins': 0, 'losses': 0, 'total_net': 0, 'total_cost': 0, 'total_prize': 0})
    
    for r in results:
        ym = r['date'][:7]
        m = monthly[ym]
        m['cycles'] += 1
        m['total_cost'] += r['cycle_cost']
        m['total_prize'] += r.get('prize', 0)
        m['total_net'] += r.get('net', 0)
        if r['net'] > 0:
            m['wins'] += 1
        else:
            m['losses'] += 1
    
    for ym, m in monthly.items():
        all_monthly[ym].append(m)


# 输出结果
print("=" * 80)
print(f"五期阶梯方案 月度回测（{NUM_RUNS}轮平均）")
print(f"选号方式: 每周期随机1个号（1-80）")
print(f"方案: 第1~5期每期x2, 第6~10期每期x2.5")
print("=" * 80)
print(f"{'月份':8s} | {'期数':5s} | {'轮数':5s} | {'中奖':4s} | {'止损':4s} | {'胜率':6s} | {'总投入':8s} | {'总奖金':8s} | {'净收益':10s} | {'平均每轮':10s}")
print("-" * 80)

total_net = 0
total_wins = 0
total_losses = 0

for ym in sorted(all_monthly.keys()):
    stats_list = all_monthly[ym]
    avg = {}
    for key in ['cycles', 'wins', 'losses', 'total_net', 'total_cost', 'total_prize']:
        avg[key] = round(sum(s[key] for s in stats_list) / len(stats_list), 1)
    
    total_net += avg['total_net']
    total_wins += avg['wins']
    total_losses += avg['losses']
    
    win_rate = avg['wins'] / avg['cycles'] * 100 if avg['cycles'] > 0 else 0
    avg_per_cycle = avg['total_net'] / avg['cycles'] if avg['cycles'] > 0 else 0
    draws = len(by_month[ym])
    
    print(f"{ym:8s} | {draws:4d}期 | {avg['cycles']:5.0f} | {avg['wins']:4.0f} | {avg['losses']:4.0f} | {win_rate:5.1f}% | {avg['total_cost']:>7.0f}元 | {avg['total_prize']:>7.1f}元 | {avg['total_net']:>+8.1f}元 | {avg_per_cycle:>+8.2f}元")

print("-" * 80)
total_cycles = total_wins + total_losses
overall_win_rate = total_wins / total_cycles * 100 if total_cycles > 0 else 0
print(f"{'合计':8s} | {'-':4s} | {total_cycles:5.0f} | {total_wins:4.0f} | {total_losses:4.0f} | {overall_win_rate:5.1f}% | {'-':>7s} | {'-':>7s} | {total_net:>+8.1f}元 | {'-':>8s}")

print()
print(f"总净收益: {total_net:+.1f}元")
print(f"总周期数: {total_cycles:.0f}")
print(f"总胜率: {overall_win_rate:.1f}%")
