"""
世界杯比赛数据采集器 (V2)
=======================
从 football-data.org API 拉取世界杯2026完整赛果

用法: python scripts/jc_results.py
输出: data/jc_results.json
"""

import json, os, sys
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
API_KEY = "1163986726a345ffb7093db9e34a5e3f"
COMPETITION_ID = 2000  # FIFA World Cup

def api_get(path):
    """调用 football-data.org API"""
    url = f"https://api.football-data.org/v4/{path}"
    req = Request(url, headers={
        "X-Auth-Token": API_KEY,
        "User-Agent": "lottery-analyst/1.0"
    })
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all_matches():
    """获取所有世界杯比赛"""
    data = api_get(f"competitions/{COMPETITION_ID}/matches")
    return data.get("matches", [])


def parse_match(m):
    """将 API 比赛数据转为统一格式"""
    status = m.get("status", "")
    sc = m.get("score", {})
    fs = sc.get("fullTime", {})
    home_score = fs.get("home")
    away_score = fs.get("away")

    home = m["homeTeam"].get("name") or ""
    away = m["awayTeam"].get("name") or ""

    utc = m.get("utcDate", "")
    match_date = utc[:10] if utc else ""

    result = {
        "date": match_date,
        "home": home,
        "away": away,
    }

    if status == "FINISHED" and home_score is not None and away_score is not None:
        result["score"] = f"{home_score}-{away_score}"
        result["home_score"] = int(home_score)
        result["away_score"] = int(away_score)
        result["status"] = "finished"
    else:
        result["score"] = None
        result["home_score"] = 0
        result["away_score"] = 0
        result["status"] = "scheduled"

    return result


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, "jc_results.json")

    print("🔍 正在从 football-data.org 拉取世界杯比赛数据...")

    try:
        matches = fetch_all_matches()
    except URLError as e:
        print(f"❌ API 请求失败: {e}")
        return

    print(f"✅ API 返回 {len(matches)} 场比赛")

    results = []
    finished = 0
    scheduled = 0
    for m in matches:
        r = parse_match(m)
        results.append(r)
        if r["status"] == "finished":
            finished += 1
        else:
            scheduled += 1

    # 按日期倒序排序
    results.sort(key=lambda x: x["date"], reverse=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✅ 已保存: {len(results)} 场比赛 ({finished} 场已完场, {scheduled} 场未赛)")
    print(f"\n📊 最近 10 场赛果:")
    count = 0
    for r in results:
        if r["status"] == "finished":
            print(f"  {r['date']}  {r['home']} {r['score']} {r['away']}")
            count += 1
            if count >= 10:
                break

    return results


if __name__ == "__main__":
    main()
