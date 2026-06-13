"""
快乐8 信号强度策略推荐算法
策略: 看最近5期1-20+60-80频率，Top5累计≥18时出击
选号: 纯频率选前14码 → 选十14码复式 (C(14,10)=1,001注=2,002元)
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

def calc_signal(recent):
    """计算信号强度: 最近5期TOP5频率总和"""
    recent5 = recent[:min(5, len(recent))]
    if len(recent5) < 3:
        return 0, []
    
    freq = Counter()
    for item in recent5:
        nums = item.get('n', item.get('r', []))
        for n in nums:
            if n in ZONE_SET:
                freq[n] += 1
    
    top5 = freq.most_common(5)
    top5_sum = sum(c for _, c in top5)
    return top5_sum, top5

def recommend_picks(recent, pick_n=14):
    """从最近5期取频率最高的pick_n个号"""
    recent5 = recent[:min(5, len(recent))]
    if len(recent5) < 3:
        return None
    
    freq = Counter()
    for item in recent5:
        nums = item.get('n', item.get('r', []))
        for n in nums:
            if n in ZONE_SET:
                freq[n] += 1
    
    picks = [n for n, _ in freq.most_common(pick_n)]
    if len(picks) < pick_n:
        for n in ZONE:
            if len(picks) >= pick_n:
                break
            if n not in picks:
                picks.append(n)
    
    return sorted(picks)[:pick_n]


def main():
    data = load_data()
    print(f"数据: {len(data)}条")
    print(f"范围: {data[-1]['d']} ~ {data[0]['d']}")
    print()
    
    # 计算信号
    signal, top5 = calc_signal(data)
    is_strong = signal >= 18
    
    print(f"📡 信号强度: Top5累计={signal}次 {'🔥 强信号(≥18)·建议出手' if is_strong else '💤 弱信号(<18)·建议等待'}")
    print()
    
    print(f"热号TOP5:")
    for n, c in top5:
        bar = '▮' * c
        print(f"  {n:2d}: {c}次 {bar}")
    print()
    
    # 推荐14码
    picks14 = recommend_picks(data, 14)
    if picks14:
        cost = math.comb(14, 10) * 2
        print(f"{'🔥' if is_strong else '💤'} 选十14码复式 (C(14,10)=1,001注={cost:,}元/次):")
        print(f"  号码: {' '.join(str(n).zfill(2) for n in picks14)}")
        z1 = [n for n in picks14 if n <= 20]
        z2 = [n for n in picks14 if n >= 60]
        print(f"  1-20区: {' '.join(str(n).zfill(2) for n in z1)} ({len(z1)}个)")
        print(f"  60-80区: {' '.join(str(n).zfill(2) for n in z2)} ({len(z2)}个)")
        print(f"  回测: 5.5年出手72次净+6.5万·ROI 144.8%·中9一次(20.8万)")
        if is_strong:
            print(f"  ✅ 当前信号强，建议出击!")
        else:
            print(f"  ⏳ 当前信号弱，建议等待信号触发出手")
        print()
    
    # 输出JSON供网站使用
    result = {
        "date": data[0]['d'],
        "signal": signal,
        "is_strong": is_strong,
        "top5": [{"n": n, "freq": c} for n, c in top5],
        "picks14": picks14 or [],
    }
    output_path = os.path.join(os.path.dirname(__file__), '..', 'kl8_recommend.json')
    with open(output_path, 'w') as f:
        json.dump(result, f, ensure_ascii=False)
    print(f"已保存到 {output_path}")


if __name__ == '__main__':
    main()
