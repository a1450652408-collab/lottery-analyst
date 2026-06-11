"""
福彩3D 位置包号算法回测与改进
- 对比 V1（现有） vs V2（六因子优化）
- 滚动回测：每次用最近N期预测下一期
"""
import json, math

with open('data/fc3d_data.json', encoding='utf-8') as f:
    raw = json.load(f)

# 数据按时间升序（最旧→最新）
data = list(reversed(raw))
print(f'总期数: {len(data)}')
print(f'最近一期: {data[-1]["p"]} {data[-1]["d"]} -> {data[-1]["n"]}')

def extract_nums(d):
    return d['n']  # list of 3 digits

# ============ V1 算法（现有） ============
def v1_predict(train_data, pos_keep=5):
    """复制现有JS算法逻辑"""
    n = len(train_data)
    pos_count = 3
    result = []
    for pos in range(pos_count):
        scores = {}
        for d in range(0, 10):
            pf = 0  # frequency
            pm = n  # recency (default = furthest)
            pr = 0  # last 10 hot
            for j, rec in enumerate(train_data):
                nums = extract_nums(rec)
                if len(nums) <= pos:
                    continue
                if nums[pos] == d:
                    pf += 1
                    if pm == n:
                        pm = j
            for ri in range(min(10, n)):
                nums = extract_nums(train_data[ri])
                if len(nums) > pos and nums[pos] == d:
                    pr += 1
            scores[d] = pf * 0.5 + pm * 0.2 + pr * 3.0
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        top = sorted([x[0] for x in ranked[:pos_keep]])
        result.append(top)
    return result

# ============ V2 算法（六因子优化） ============
def v2_predict(train_data, pos_keep=5):
    """
    六因子评分:
    1. EMA热度 (α=0.3) — 指数衰减，越近权重越高
    2. 中期频率 (总次数 * 0.5)
    3. 动量因子 (近5 vs 前5)
    4. 遗漏回归 (long-miss bonus)
    5. 位置特异性 (各位置独立评分)
    """
    n = len(train_data)
    pos_count = 3
    result = []
    
    for pos in range(pos_count):
        scores = {}
        for d in range(0, 10):
            # 1. EMA热度 (α=0.3)
            ema = 0.0
            hits = 0
            for j in range(n):
                nums = extract_nums(train_data[j])
                val = 1.0 if (len(nums) > pos and nums[pos] == d) else 0.0
                ema = 0.3 * val + 0.7 * ema
                hits += val
            
            # 2. 中期频率 (总频率 * weight)
            mid_freq = hits / n
            
            # 3. 动量: 近5期 vs 前5期
            recent5_hits = 0
            prev5_hits = 0
            for j in range(min(5, n)):
                nums = extract_nums(train_data[j])
                if len(nums) > pos and nums[pos] == d:
                    recent5_hits += 1
            for j in range(5, min(10, n)):
                nums = extract_nums(train_data[j])
                if len(nums) > pos and nums[pos] == d:
                    prev5_hits += 1
            momentum = (recent5_hits - prev5_hits) * 1.0
            momentum = max(-5, min(5, momentum))  # clamp
            
            # 4. 遗漏回归: 出现间隔越长→回补概率↑ 
            # 但非线性，用 logistic 风格
            last_seen = n  # default = never seen
            for j, rec in enumerate(train_data):
                nums = extract_nums(rec)
                if len(nums) > pos and nums[pos] == d:
                    last_seen = j
                    break
            miss_len = last_seen  # 已经多久没出现（期数）
            # 如果遗漏 > 期望间隔(10期/10个数字)，加分
            expected_gap = 10 / (mid_freq * 10 + 0.1)  # 期望出现间隔
            miss_bonus = max(0, (miss_len - expected_gap) * 0.3)
            
            # 5. 位置修正: 有些数字在某些位置更稳定
            # 不做人工修正，但通过EMA保留位置特征
            
            # 综合评分
            score = (ema * 5.0 +          # EMA热度为主
                     mid_freq * 2.0 +      # 中期频率
                     momentum * 1.5 +      # 动量
                     miss_bonus * 0.8)     # 遗漏回补
            
            scores[d] = round(score, 3)
        
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        top = sorted([x[0] for x in ranked[:pos_keep]])
        result.append(top)
    return result


# ============ V2.1 算法（增强版：自适应冷号槽位+权重调优）============
def v2_1_predict(train_data, pos_keep=5, cold_slot=1):
    """
    V2.1 增强:
    - 保留(pos_keep - cold_slot)个热号 + cold_slot个冷号槽位
    - 冷号选择：遗漏最长且长期频率不低的数字
    - 权重进一步调优
    """
    n = len(train_data)
    pos_count = 3
    result = []
    hot_slots = pos_keep - cold_slot
    
    for pos in range(pos_count):
        scores = {}
        cold_scores = {}
        
        for d in range(0, 10):
            ema = 0.0
            hits = 0
            last_seen = n
            for j, rec in enumerate(train_data):
                nums = extract_nums(rec)
                hit = 1.0 if (len(nums) > pos and nums[pos] == d) else 0.0
                ema = 0.3 * hit + 0.7 * ema
                hits += hit
                if hit and j < last_seen:
                    last_seen = j
            
            mid_freq = hits / n
            
            recent5_hits = 0
            prev5_hits = 0
            for j in range(min(5, n)):
                nums = extract_nums(train_data[j])
                if len(nums) > pos and nums[pos] == d:
                    recent5_hits += 1
            for j in range(5, min(10, n)):
                nums = extract_nums(train_data[j])
                if len(nums) > pos and nums[pos] == d:
                    prev5_hits += 1
            momentum = (recent5_hits - prev5_hits) * 1.5
            momentum = max(-5, min(5, momentum))
            
            miss_len = last_seen
            expected_gap = 10 / (mid_freq * 10 + 0.5)
            miss_bonus = max(0, (miss_len - expected_gap) * 0.5)
            
            # 热号评分
            score = ema * 5.0 + mid_freq * 2.0 + momentum * 2.0
            
            # 冷号专用评分：只考虑遗漏和长期频率
            cold_score = miss_len * 0.8 + hits * 0.3
            
            scores[d] = round(score, 3)
            cold_scores[d] = round(cold_score, 2)
        
        # 选热号: 按评分降序，剔除评分最低的位置
        ranked_hot = sorted(scores.items(), key=lambda x: -x[1])
        
        # 选冷号: 排除已选的热号，按cold_score选
        hot_picks = [x[0] for x in ranked_hot[:hot_slots]]
        
        cold_candidates = [(d, cold_scores[d]) for d in range(10) if d not in hot_picks]
        cold_candidates.sort(key=lambda x: -x[1])
        cold_picks = [x[0] for x in cold_candidates[:cold_slot]]
        
        top = sorted(hot_picks + cold_picks)
        result.append(top)
    
    return result


# ============ 回测评估 ============
def backtest_algorithm(alg_func, name, train_window=50, pos_keep=5, **kwargs):
    """滚动回测"""
    per_pos_hits = [0, 0, 0]
    total_tests = 0
    all_pos_hit = 0  # 三位全中
    
    for i in range(train_window, len(data)):
        train = data[i-train_window:i]
        actual = extract_nums(data[i])
        
        if alg_func.__name__ == 'v1_predict':
            pred = alg_func(train, pos_keep)
        elif alg_func.__name__ == 'v2_1_predict':
            pred = alg_func(train, pos_keep, kwargs.get('cold_slot', 1))
        else:
            pred = alg_func(train, pos_keep)
        
        all_match = True
        for pos in range(3):
            if actual[pos] in pred[pos]:
                per_pos_hits[pos] += 1
            else:
                all_match = False
        if all_match:
            all_pos_hit += 1
        total_tests += 1
    
    total_combo = pos_keep ** 3
    results = {
        'name': name,
        'tests': total_tests,
        'pos_hits': [f'{h/total_tests*100:.1f}% ({h}/{total_tests})' for h in per_pos_hits],
        'pos_hits_raw': per_pos_hits,
        'all_pos_hit': f'{all_pos_hit/total_tests*100:.2f}% ({all_pos_hit}/{total_tests})',
        'all_pos_hit_raw': all_pos_hit,
        'combos': total_combo,
        'cost_per_day': total_combo * 2,
    }
    return results


results = []

# 跑回测
results.append(backtest_algorithm(v1_predict, 'V1 (现有: 3因子评分)'))
results.append(backtest_algorithm(v2_predict, 'V2 (六因子: EMA+动量+遗漏)'))

# V2.1 不同冷号槽位
for cs in [0, 1, 2]:
    r = backtest_algorithm(v2_1_predict, f'V2.1 (热{5-cs}+冷{cs}槽)', cold_slot=cs)
    results.append(r)

# 打印结果
print('\n' + '='*80)
print('福彩3D 位置包号算法回测 (滚动窗口50期)')
print('='*80)
print(f'总测试期数: {results[0]["tests"]}')
print()

print(f'{"算法":<25} {"百位命中":<16} {"十位命中":<16} {"个位命中":<16} {"三位全中":<16} {"每期成本":<10}')
print('-'*100)
for r in results:
    cost_str = f'{r["cost_per_day"]}元'
    print(f'{r["name"]:<25} {r["pos_hits"][0]:<16} {r["pos_hits"][1]:<16} {r["pos_hits"][2]:<16} {r["all_pos_hit"]:<16} {cost_str:<10}')

print('\n--- 三位全中期望值对比 ---')
for r in results:
    exp_all = (r['pos_hits_raw'][0]/r['tests']) * (r['pos_hits_raw'][1]/r['tests']) * (r['pos_hits_raw'][2]/r['tests']) * 100
    print(f'{r["name"]:<25} 理论全中率: {exp_all:.2f}% | 实际全中率: {r["all_pos_hit"]}')

# 计算随机基准
print('\n--- 随机基准 ---')
rand_per_pos = 5/10 * 100
rand_all = (5/10)**3 * 100
print(f'随机(5/10)单位置: {rand_per_pos:.0f}% | 三位全中: {rand_all:.2f}%')

# 找出最佳
best_all = max(results, key=lambda r: r['all_pos_hit_raw'])
best_per_pos = max(results, key=lambda r: sum(r['pos_hits_raw']))
print(f'\n🏆 三位全中最优: {best_all["name"]} ({best_all["all_pos_hit"]})')
print(f'🏆 单位置总命中最优: {best_per_pos["name"]} ({sum(best_per_pos["pos_hits_raw"])}/{3*best_per_pos["tests"]})')
