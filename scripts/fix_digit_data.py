#!/usr/bin/env python3
"""
修复数字彩数据：手动补拉FC3D/PL5/PL3缺失的期号
"""
import sys, json, urllib.request, re, os, time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from auto_update import parse_digit_entry, extract_basic_info, fetch_page

def fetch_and_parse(base, period, num_count):
    url = f"https://sports.163.com/caipiao/lottery/{base}/{period}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        _, date_str = extract_basic_info(html)
        entry = parse_digit_entry(html, period, date_str or "", num_count)
        return entry
    except Exception as e:
        return None

def add_periods(base, num_count, file_name, start_period, end_period_str):
    path = os.path.join(DATA_DIR, file_name)
    with open(path) as f:
        data = json.load(f)
    existing = {item.get('p') for item in data}
    print(f"{base}: {len(data)} periods, latest={max(existing) if existing else 'empty'}")

    # Generate period list
    prefix = start_period[:-3]
    start_num = int(start_period[-3:])
    end_num = int(end_period_str[-3:])
    
    added = 0
    for num in range(start_num, end_num + 1):
        p = prefix + str(num).zfill(3)
        if p in existing:
            continue
        time.sleep(0.25)
        entry = fetch_and_parse(base, p, num_count)
        if entry and entry.get('n'):
            data.insert(0, entry)
            added += 1
            print(f"  ✅ {p}: {entry['n']}")
        else:
            print(f"  ⚠️ {p}: failed")

    if added > 0:
        data.sort(key=lambda x: int(x.get('p','0').replace('20','')), reverse=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(f"  → {base}: +{added}, total {len(data)}")

# === FC3D: missing 2026167-2026170 ===
add_periods("fc3d", 3, "fc3d_full.json", "2026167", "2026170")

# === PL5: missing 26150-26170 ===  
add_periods("pl5", 5, "pl5_full.json", "26150", "26170")

# === PL3: initialize ===
pl3_path = os.path.join(DATA_DIR, "pl3_full.json")
with open(pl3_path) as f:
    pl3_data = json.load(f)
print(f"\npl3: {len(pl3_data)} periods")

if len(pl3_data) == 0:
    print("PL3 is empty, fetching latest...")
    html = fetch_page("pl3")
    if html:
        period, date_str = extract_basic_info(html)
        print(f"  Latest PL3: {period} ({date_str})")
        # Also try fetching individual periods
        latest_num = int(period[-3:]) if len(period) > 3 else int(period)
        prefix = period[:-3]
        for num in range(max(1, latest_num - 500), latest_num + 1):
            p = prefix + str(num).zfill(3)
            time.sleep(0.15)
            entry = fetch_and_parse("pl3", p, 3)
            if entry and entry.get('n'):
                pl3_data.append(entry)
            if len(pl3_data) >= 500:
                break
        if pl3_data:
            pl3_data.sort(key=lambda x: int(x.get('p','0').replace('20','')), reverse=True)
            with open(pl3_path, 'w', encoding='utf-8') as f:
                json.dump(pl3_data, f, ensure_ascii=False, separators=(',', ':'))
            print(f"  ✅ PL3: {len(pl3_data)} periods saved")
        else:
            print("  ❌ PL3: no data fetched")

print("\n✅ Data fix complete!")
