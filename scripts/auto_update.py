#!/usr/bin/env python3
"""
每日彩票数据自动更新脚本

从 163.com 自动抓取最新开奖数据（无需硬编码期号）：
1. 访问各彩种首页 → 自动解析最新开奖号码、期号、日期
2. 更新 index_modified.html 中嵌入的 __LOTTERY_DATA
3. 同步 data/*.json 独立数据文件
4. 提交到 GitHub（可选）

调用方式: python scripts/auto_update.py
"""

import re, json, sys, os, time, urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(PROJECT_ROOT, "index_modified.html")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
KL8_FILE = os.path.join(DATA_DIR, "kl8_500.json")

# 所有彩种配置
# type_key -> (163_base_url, parser_method, max_records)
LOTTERY_CONFIG = {
    "ssq": {"base": "ssq", "parser": "ssq"},    # 双色球: 6红+1蓝
    "dlt": {"base": "dlt", "parser": "dlt"},    # 大乐透: 5前+2后
    "qlc": {"base": "qlc", "parser": "ssq"},    # 七乐彩: 7个标准号
    "kl8": {"base": "kl8", "parser": "kl8"},    # 快乐8: 20个号
    "fc3d": {"base": "fc3d", "parser": "digit"}, # 福彩3D: 3个号
    "pl3": {"base": "pl3", "parser": "digit"},   # 排列三: 3个号
    "pl5": {"base": "pl5", "parser": "digit"},   # 排列五: 5个号
    "qxc": {"base": "qxc", "parser": "digit"},   # 七星彩: 7个号
}

# 各彩种数据文件独立同步映射
INDIVIDUAL_FILES = {
    "ssq": "ssq_data.json",
    "dlt": "dlt_data.json",
    "qlc": "qlc_data.json",
    "kl8": "kl8_500.json",
    "fc3d": "fc3d_data.json",
    "pl3": "pl3_data.json",
    "pl5": "pl5_data.json",
    "qxc": "qxc_data.json",
}

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def fetch_page(ltype_base):
    """访问彩票首页，返回 HTML"""
    url = f"https://sports.163.com/caipiao/lottery/{ltype_base}/"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        html = resp.read().decode("utf-8", errors="replace")
        if "404" in html[:500] or len(html) < 1000:
            return None
        return html
    except Exception as e:
        print(f"  FETCH FAIL: {e}")
        return None


def extract_basic_info(html):
    """从HTML中提取期号和日期"""
    # 期号: <span>2026151期</span>
    m = re.search(r'<span[^>]*>(\d+?)期</span>', html)
    period = m.group(1) if m else None

    # 日期: <span>开奖日期: 2026-06-10</span>
    m = re.search(r'开奖日期:\s*(\d{4}-\d{2}-\d{2})', html)
    date_str = m.group(1) if m else None

    return period, date_str


def parse_balls_by_class(html):
    """按CSS class提取号码球"""
    # 所有 lottery-ball
    all_balls = re.findall(r'lottery-ball[^>]*>(\d+)</span>', html)
    # 红色球 (ssq红球/dlt前区)
    red_balls = re.findall(r'lottery-ball\s+bg-red-\d+[^>]*>(\d+)</span>', html)
    # 蓝色球 (ssq蓝球/dlt后区)
    blue_balls = re.findall(r'lottery-ball\s+bg-blue[^>]*>(\d+)</span>', html)

    return {
        "all": [int(n) for n in all_balls] if all_balls else [],
        "red": [int(n) for n in red_balls] if red_balls else [],
        "blue": [int(n) for n in blue_balls] if blue_balls else [],
    }


def parse_entry(html, period, date_str, parser_type):
    """按彩种解析开奖条目"""
    if not period or not date_str:
        return None

    balls = parse_balls_by_class(html)

    if parser_type == "ssq":
        # 6红+1蓝
        if len(balls["red"]) >= 6 and len(balls["blue"]) >= 1:
            return {
                "p": period,
                "d": date_str,
                "r": sorted(balls["red"][:6]),
                "b": balls["blue"][0],
            }
        # fallback: 按顺序前6个是红，最后1个是蓝
        if len(balls["all"]) >= 7:
            return {
                "p": period,
                "d": date_str,
                "r": sorted(balls["all"][:6]),
                "b": balls["all"][6],
            }

    elif parser_type == "dlt":
        # 5前+2后
        if len(balls["red"]) >= 5 and len(balls["blue"]) >= 2:
            return {
                "p": period,
                "d": date_str,
                "r": sorted(balls["red"][:5]),
                "b": sorted(balls["blue"][:2]),
            }
        # fallback: 前5前区，后2后区
        if len(balls["all"]) >= 7:
            return {
                "p": period,
                "d": date_str,
                "r": sorted(balls["all"][:5]),
                "b": sorted(balls["all"][5:7]),
            }

    elif parser_type == "kl8":
        # 20个号（快乐8没有红蓝之分）
        if len(balls["all"]) >= 20:
            return {
                "p": period,
                "d": date_str,
                "n": sorted(balls["all"][:20]),
            }
        # 有些页面 class 可能不带 bg 前缀
        all_nums = re.findall(r'lottery-ball[^>]*>(\d+)</span>', html)
        nums = [int(n) for n in all_nums]
        if len(nums) >= 20:
            return {
                "p": period,
                "d": date_str,
                "n": sorted(nums[:20]),
            }

    elif parser_type == "digit":
        # 数字彩：fc3d(3), pl3(3), pl5(5), qxc(7)
        counts = {"fc3d": 3, "pl3": 3, "pl5": 5, "qxc": 7}
        count = counts.get("fc3d", 3)  # fallback

    return None


def parse_digit_entry(html, period, date_str, num_count):
    """解析数字彩（fc3d/pl3/pl5/qxc）"""
    balls = parse_balls_by_class(html)
    all_nums = balls["all"]
    
    # 尝试用所有 lottery-ball
    if len(all_nums) >= num_count:
        return {
            "p": period,
            "d": date_str,
            "n": all_nums[:num_count],
        }
    
    # fallback: 重新抓一遍
    all_fallback = re.findall(r'lottery-ball[^>]*>(\d+)</span>', html)
    nums = [int(n) for n in all_fallback]
    if len(nums) >= num_count:
        return {
            "p": period,
            "d": date_str,
            "n": nums[:num_count],
        }
    
    return None


def read_existing_data():
    """从 index_modified.html 读取现有数据"""
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    m = re.search(r"window\.__LOTTERY_DATA\s*=\s*(\{.+?\});", html, re.DOTALL)
    if not m:
        print("ERROR: Cannot find __LOTTERY_DATA in HTML")
        sys.exit(1)

    data = json.loads(m.group(1))
    return html, data, m.start(), m.end()


def write_html(html, data, data_start, data_end):
    """写回 HTML"""
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    new_html = html[:data_start] + "window.__LOTTERY_DATA = " + json_str + ";" + html[data_end:]

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)
    print(f"  ✅ HTML written: {HTML_PATH}")


def sync_individual_file(data, type_key):
    """将某彩种数据同步到独立 data/*.json 文件"""
    items = data.get(type_key, [])
    if not items:
        return

    filename = INDIVIDUAL_FILES.get(type_key)
    if not filename:
        return

    filepath = os.path.join(DATA_DIR, filename)
    os.makedirs(DATA_DIR, exist_ok=True)

    # 保持 KL8 最多 1500 条，其他最多 100 条
    if type_key == "kl8":
        save = items[:1500]
    else:
        save = items[:150]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(save, f, ensure_ascii=False, separators=(",", ":"))
    
    latest = save[0]
    print(f"  ✅ {filename}: {len(save)}条, 最新={latest.get('p','?')} ({latest.get('d','?')})")


def sync_all_data_files(data):
    """同步所有彩种的独立文件"""
    print("\n--- Sync data files ---")
    for type_key in INDIVIDUAL_FILES:
        sync_individual_file(data, type_key)


def main():
    print("=" * 55)
    print("  Lottery Data Auto-Update (auto-detect periods)")
    print("=" * 55)

    # 读取现有数据
    html, data, ds, de = read_existing_data()

    updated_types = []
    skipped_types = []
    failed_types = []

    num_count_map = {"fc3d": 3, "pl3": 3, "pl5": 5, "qxc": 7}

    for type_key, config in LOTTERY_CONFIG.items():
        base = config["base"]
        parser = config["parser"]

        print(f"\n--- {type_key} ---")

        if type_key not in data:
            print(f"  SKIP: not in data config")
            continue

        # 1. 获取最新开奖页
        print(f"  Fetching {base}/ ...")
        page_html = fetch_page(base)
        if not page_html:
            print(f"  FAIL: Cannot fetch")
            failed_types.append(type_key)
            continue

        time.sleep(0.2)  # 礼貌间隔

        # 2. 提取期号和日期
        period, date_str = extract_basic_info(page_html)
        if not period or not date_str:
            print(f"  FAIL: Cannot extract period/date from HTML")
            failed_types.append(type_key)
            continue

        print(f"  最新: {period}期 ({date_str})")

        # 3. 检查是否已存在
        existing = data[type_key]
        existing_periods = {item.get("p") for item in existing}
        if period in existing_periods:
            print(f"  ✅ ALREADY EXISTS")
            skipped_types.append(type_key)
            continue

        # 4. 解析号码
        if parser == "digit":
            num_count = num_count_map.get(type_key, 3)
            entry = parse_digit_entry(page_html, period, date_str, num_count)
        elif parser == "kl8":
            entry = parse_entry(page_html, period, date_str, "kl8")
        elif parser == "dlt":
            entry = parse_entry(page_html, period, date_str, "dlt")
        else:  # ssq (ssq / qlc)
            entry = parse_entry(page_html, period, date_str, "ssq")

        if not entry:
            print(f"  FAIL: Cannot parse numbers")
            failed_types.append(type_key)
            continue

        # 5. 输出号码
        if "r" in entry and "b" in entry:
            print(f"  红:{entry['r']} 蓝:{entry['b']}")
        elif "n" in entry:
            print(f"  号: {entry['n']}")

        # 6. 插入最新
        existing.insert(0, entry)
        updated_types.append(type_key)
        print(f"  ✅ UPDATED: {period} ({date_str})")

    # 写回 HTML
    if updated_types:
        write_html(html, data, ds, de)
    else:
        print("\n⚠️ No new data to update.")

    # 同步独立数据文件
    sync_all_data_files(data)

    # 汇总
    print("\n" + "=" * 55)
    if updated_types:
        print(f"✅ UPDATED: {', '.join(updated_types)}")
    if skipped_types:
        print(f"⏭️  SKIP (已有): {', '.join(skipped_types)}")
    if failed_types:
        print(f"❌ FAILED: {', '.join(failed_types)}")
    print("=" * 55)

    return len(updated_types) > 0


if __name__ == "__main__":
    main()
