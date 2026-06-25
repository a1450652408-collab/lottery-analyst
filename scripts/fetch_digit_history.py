#!/usr/bin/env python3
"""
数字彩历史数据扩充脚本
从163.com批量拉取福彩3D/排列三/排列五的全年历史数据
输出: data/fc3d_full.json, data/pl3_full.json, data/pl5_full.json
"""

import urllib.request, re, json, os, sys, time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

LOTTERY_BASE = {
    "fc3d": "fc3d",
    "pl3": "pl3",
    "pl5": "pl5",
}

def fetch_period(ltype, period):
    """抓取单期数据"""
    url = f"https://sports.163.com/caipiao/lottery/{ltype}/{period}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        resp = urllib.request.urlopen(req, timeout=8)
        html = resp.read().decode("utf-8", errors="replace")
        
        balls = re.findall(r'lottery-ball[^>]*>(\d+)</span>', html)
        date_m = re.search(r'开奖日期:\s*(\d{4}-\d{2}-\d{2})', html)
        
        if balls and date_m:
            return {"p": period, "d": date_m.group(1), "n": [int(b) for b in balls]}
    except:
        pass
    return None

def merge_with_existing(new_data, existing_path):
    """与已有数据合并去重"""
    existing = []
    if os.path.exists(existing_path):
        with open(existing_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    
    seen = {item["p"] for item in existing}
    for item in new_data:
        if item["p"] not in seen:
            seen.add(item["p"])
            existing.append(item)
    
    existing.sort(key=lambda x: -int(x["p"]))
    return existing

def main():
    for ltype_key, ltype_base in LOTTERY_BASE.items():
        out_path = os.path.join(DATA_DIR, f"{ltype_key}_full.json")
        
        # 先检查已有的数量
        existing_count = 0
        if os.path.exists(out_path):
            with open(out_path, "r") as f:
                existing_count = len(json.load(f))
        
        print(f"\n{ltype_key}: 已有{existing_count}期")
        
        new_records = []
        years = ["2025", "2026"]
        failed_streak = 0
        
        for year in years:
            for base in range(1, 200):
                period = f"{year}{base:03d}"
                result = fetch_period(ltype_base, period)
                if result:
                    new_records.append(result)
                    failed_streak = 0
                    if len(new_records) % 50 == 0:
                        print(f"  已抓取{len(new_records)}期...")
                else:
                    failed_streak += 1
                    if failed_streak >= 15:
                        break  # 连续15期无数据就跳过该年
                time.sleep(0.2)
        
        merged = merge_with_existing(new_records, out_path)
        
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, separators=(",", ":"))
        
        print(f"  {'✅' if len(new_records) > 0 else '⏭️'} 新增{len(new_records)}期, 总计{len(merged)}期")
        if merged:
            print(f"  最新: {merged[0]['p']} {merged[0]['d']} {merged[0]['n']}")

if __name__ == "__main__":
    main()
