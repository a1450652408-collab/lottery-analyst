"""
批量拉取双色球/大乐透历史数据（多页）
"""
import json, urllib.request, time, sys

API = "http://api.huiniao.top/interface/home/lotteryHistory"
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

def fetch_page(api, page, limit=100):
    url = f"{API}?type={api}&page={page}&limit={limit}"
    r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def parse_item(api, item):
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    e = {"p": str(item.get("code","")), "d": str(item.get("day",""))}
    if api=="ssq":
        e["r"]=sorted(nums[:6])
        e["b"]=nums[6] if len(nums)>6 else None
    elif api=="dlt":
        e["r"]=sorted(nums[:5])
        e["b"]=sorted(nums[5:7]) if len(nums)>5 else []
    return e

for api_name, file_name in [("ssq","ssq"), ("dlt","dlt")]:
    all_items = []
    page = 1
    empty_count = 0
    
    print(f"\n=== 拉取{api_name.upper()}数据 ===")
    while len(all_items) < 1000 and empty_count < 3:
        try:
            d = fetch_page(api_name, page)
            if d.get("code") != 1:
                print(f"  page {page}: API error")
                empty_count += 1
                page += 1
                time.sleep(2)
                continue
            
            items = d["data"]["data"]["list"]
            if not items:
                empty_count += 1
                page += 1
                time.sleep(2)
                continue
            
            parsed = [parse_item(api_name, i) for i in items]
            all_items.extend(parsed)
            first = parsed[0]
            last = parsed[-1]
            print(f"  page {page}: {len(parsed)}条 {first['d']}~{last['d']} (累计{len(all_items)})")
            
            empty_count = 0
            page += 1
            time.sleep(1.5)
        except Exception as e:
            print(f"  page {page}: FAIL {e}")
            empty_count += 1
            page += 1
            time.sleep(3)
    
    # 去重
    seen = set()
    unique = []
    for item in all_items:
        key = item["p"]
        if key not in seen:
            seen.add(key)
            unique.append(item)
    
    print(f"\n{api_name.upper()} 总计: {len(all_items)}条, 去重后: {len(unique)}条")
    print(f"  最早: {unique[-1]['d']} 最晚: {unique[0]['d']}")
    
    # 保存
    out_path = f'C:/Users/14506/WorkBuddy/Claw/data/{file_name}_full.json'
    with open(out_path, 'w') as f:
        json.dump(unique, f)
    print(f"  已保存: {out_path}")

print("\n完成!")
