"""
快乐8 多形态走势组合推荐算法
策略: 看最近5期, 从1-20+60-80区间取号
综合: 单热号 + 二连号 + 三连号 + 对子号(同尾)
输出: 选九11码复式 + 选十12码复式
"""
import json, math, os, sys
from collections import Counter

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'kl8_1500.json')
ZONE = list(range(1, 21)) + list(range(60, 81))
ZONE_SET = set(ZONE)

def load_data():
    with open(DATA_FILE) as f:
        data = json.load(f)
    return sorted(data, key=lambda x: x['p'], reverse=True)  # 最新在前

def get_zone_nums(item):
    """获取落在1-20+60-80区间内的号码"""
    nums = item.get('n', item.get('r', []))
    return sorted([n for n in nums if n in ZONE_SET])

def recommend(recent, pick_n):
    """
    从最近几期中按多形态组合选出pick_n个号码
    recent: 数据列表(最新在前)
    """
    recent5 = recent[:min(5, len(recent))]
    if len(recent5) < 3:
        return None
    
    # 统计各种形态
    single_freq = Counter()
    pair2_freq = Counter()
    pair3_freq = Counter()
    duizi_freq = Counter()
    
    for item in recent5:
        nums = get_zone_nums(item)
        # 单号
        for n in nums:
            single_freq[n] += 1
        # 二连号
        for j in range(len(nums) - 1):
            if nums[j + 1] == nums[j] + 1:
                pair2_freq[(nums[j], nums[j + 1])] += 1
        # 三连号
        for j in range(len(nums) - 2):
            if nums[j + 2] == nums[j] + 2 and nums[j + 1] == nums[j] + 1:
                pair3_freq[(nums[j], nums[j] + 1, nums[j] + 2)] += 1
        # 对子号(同尾数)
        for a in range(len(nums)):
            for b in range(a + 1, len(nums)):
                if nums[a] % 10 == nums[b] % 10:
                    duizi_freq[(nums[a], nums[b])] += 1
    
    # 构建选号池
    pool = set()
    
    # 最热二连号(最多2组)
    for pair, _ in pair2_freq.most_common(2):
        pool |= set(pair)
    
    # 最热三连号(最多1组,不跟已有重叠)
    for triple, _ in pair3_freq.most_common(3):
        if not any(n in pool for n in triple):
            pool |= set(triple)
            break
    
    # 对子号(最多2组,不跟已有重叠)
    dz_count = 0
    for pair, _ in duizi_freq.most_common(8):
        if dz_count >= 2:
            break
        if not any(n in pool for n in pair):
            pool |= set(pair)
            dz_count += 1
    
    # 补单热号
    for n, _ in single_freq.most_common(25):
        if len(pool) >= pick_n:
            break
        pool.add(n)
    
    # 不够从ZONE补
    if len(pool) < pick_n:
        for n in ZONE:
            if len(pool) >= pick_n:
                break
            pool.add(n)
    
    return sorted(pool)[:pick_n]


def main():
    data = load_data()
    print(f"数据: {len(data)}条")
    print(f"范围: {data[-1]['d']} ~ {data[0]['d']}")
    print()
    
    # 选九11码
    picks9 = recommend(data, 11)
    if picks9:
        print(f"选九11码复式 (110元/天):")
        print(f"  号码: {' '.join(str(n).zfill(2) for n in picks9)}")
        # 区间分布
        z1 = [n for n in picks9 if n <= 20]
        z2 = [n for n in picks9 if n >= 60]
        print(f"  1-20: {len(z1)}个 {' '.join(str(n).zfill(2) for n in z1)}")
        print(f"  60-80: {len(z2)}个 {' '.join(str(n).zfill(2) for n in z2)}")
        # 形态统计
        print(f"  C(11,9)=55注=110元/天")
        print()
    
    # 选十12码
    picks10 = recommend(data, 12)
    if picks10:
        print(f"选十12码复式 (132元/天):")
        print(f"  号码: {' '.join(str(n).zfill(2) for n in picks10)}")
        z1 = [n for n in picks10 if n <= 20]
        z2 = [n for n in picks10 if n >= 60]
        print(f"  1-20: {len(z1)}个 {' '.join(str(n).zfill(2) for n in z1)}")
        print(f"  60-80: {len(z2)}个 {' '.join(str(n).zfill(2) for n in z2)}")
        print(f"  C(12,10)=66注=132元/天")
        print()
    
    print(f"合计: 242元/天")
    
    # 输出JSON供网站使用
    result = {
        "date": data[0]['d'],
        "picks9": picks9 or [],
        "picks10": picks10 or [],
    }
    output_path = os.path.join(os.path.dirname(__file__), '..', 'kl8_recommend.json')
    with open(output_path, 'w') as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"已保存到 {output_path}")


if __name__ == '__main__':
    main()
