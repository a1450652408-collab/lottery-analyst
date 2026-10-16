#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数字彩开奖数据抓取与写入（GitHub Actions 每日流水线调用）

修复记录 2026-10-15:
  1. 数据块定位原用 `";\\n</script>"`, 但 index.html 为 CRLF 换行 → 永远找不到 → 流水线空操作。
     改为 json.JSONDecoder().raw_decode 精确定位(与换行符无关)。
  2. 原来整体覆盖 __LOTTERY_DATA, 会把接口不覆盖的彩种(ttcx4 / sh15x5)从页面里删掉。
     改为"按彩种合并"(保留其他彩种 + 新旧按期号并集)。
  3. 原来用 indent=2 写入 → 内嵌 JSON 变成多行, 文件体积膨胀; 改为紧凑格式(与文件现状一致)。
  4. 原来只写 HTML, 不同步 data/*.json → 与独立数据文件脱节; 现在同步(支持 --no-json 关闭)。
"""
import json, urllib.request, time, sys, os, re

API = "http://api.huiniao.top/interface/home/lotteryHistory"
TYPES = [("ssq", "ssq", 50), ("dlt", "dlt", 50), ("qlc", "qlc", 50),
         ("kl8", "klb", 300), ("fc3d", "fcsd", 100), ("pl3", "pls", 100),
         ("pl5", "plw", 100), ("qxc", "qxc", 100)]
FIELDS = ["one", "two", "three", "four", "five", "six", "seven",
          "eight", "nine", "ten", "eleven", "twelve", "thirteen",
          "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
          "nineteen", "twenty"]

HTML_FILES = ["index.html", "deploy/index.html", "index_modified.html"]
INDIVIDUAL_FILES = {"ssq": "ssq_data.json", "dlt": "dlt_data.json", "qlc": "qlc_data.json",
                    "kl8": "kl8_500.json", "fc3d": "fc3d_data.json", "pl3": "pl3_data.json",
                    "pl5": "pl5_data.json", "qxc": "qxc_data.json"}
CAPS = {"kl8": 1500}          # 其余彩种上限
DEFAULT_CAP = 150


def fetch(a, l):
    r = urllib.request.Request(f"{API}?type={a}&page=1&limit={l}",
                               headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse(api, item):
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try:
                nums.append(int(v))
            except ValueError:
                pass
    e = {"p": str(item.get("code", "")), "d": str(item.get("day", ""))}
    if api == "ssq":
        e["r"] = sorted(nums[:6]); e["b"] = nums[6] if len(nums) > 6 else None
    elif api == "dlt":
        e["r"] = sorted(nums[:5]); e["b"] = sorted(nums[5:7]) if len(nums) > 5 else []
    elif api in ("fcsd", "pls"):
        e["n"] = nums[:3]
    elif api == "plw":
        e["n"] = nums[:5]
    elif api == "qxc":
        e["n"] = nums[:7]
    elif api == "qlc":
        e["r"] = sorted(nums[:7])
    else:
        e["n"] = sorted(nums)
    return e


def fetch_all():
    """抓取所有彩种; 返回 {type_key: [条目]}"""
    out = {}
    for t, a, l in TYPES:
        try:
            d = fetch(a, l)
            if d.get("code") == 1:
                out[t] = [parse(a, i) for i in d["data"]["data"]["list"]]
                print(f"  {t}: {out[t][0]['p']} ({out[t][0]['d']}) {len(out[t])}条")
            else:
                print(f"  {t}: API error")
        except Exception as e:
            print(f"  {t}: FAIL {e}")
        time.sleep(2)
    return out


def find_embedded(html):
    """定位 window.__LOTTERY_DATA 的 JSON 区间(与 CRLF/LF 无关)。返回 (obj, start, end) 或 (None, -1, -1)"""
    m = re.search(r"window\.__LOTTERY_DATA\s*=\s*", html)
    if not m:
        return None, -1, -1
    start = m.end()
    try:
        obj, n = json.JSONDecoder().raw_decode(html[start:])
    except Exception as e:
        print(f"  解析内嵌数据失败: {e}")
        return None, -1, -1
    return obj, start, start + n


def _cap_of(t):
    return CAPS.get(t, DEFAULT_CAP)


def _period_key(it):
    p = str(it.get("p", ""))
    return int(p) if p.isdigit() else -1


def union_merge(old_items, new_items, cap):
    """按期号并集, 新数据优先; 按期号降序; 截断到 cap"""
    by_p = {}
    for it in list(new_items) + list(old_items):
        p = str(it.get("p", ""))
        if p and p not in by_p:
            by_p[p] = it
    items = sorted(by_p.values(), key=_period_key, reverse=True)
    return items[:cap]


def main(write_json=True):
    print("--- Fetch ---")
    fetched = fetch_all()
    if not fetched:
        print("未抓到任何数据, 中止(不改动文件)")
        return 1

    # 以 index.html 为基准读取现有数据并合并
    with open(HTML_FILES[0], "r", encoding="utf-8") as f:
        base_html = f.read()
    old, s, e = find_embedded(base_html)
    if old is None:
        print(f"!! 未能在 {HTML_FILES[0]} 定位 __LOTTERY_DATA, 中止")
        return 1

    merged = dict(old)                      # 保留已有全部彩种(含 ttcx4 / sh15x5)
    for t, items in fetched.items():
        merged[t] = union_merge(old.get(t, []), items, _cap_of(t))
    missing = [k for k in ("ssq", "dlt", "qlc", "kl8", "fc3d", "pl3", "pl5", "qxc",
                           "ttcx4", "sh15x5") if k not in merged or not merged[k]]
    if missing:
        print("!! 警告: 页面缺少彩种 " + ",".join(missing))

    js = json.dumps(merged, ensure_ascii=False, separators=(",", ":"))
    print("--- Write HTML ---")
    for fn in HTML_FILES:
        if not os.path.exists(fn):
            print(f"  {fn}: not found, skip")
            continue
        with open(fn, "r", encoding="utf-8") as f:
            h = f.read()
        obj, s2, e2 = find_embedded(h)
        if obj is None:
            print(f"  {fn}: data block not found")
            continue
        with open(fn, "w", encoding="utf-8") as f:
            f.write(h[:s2] + js + h[e2:])
        print(f"  {fn}: updated (彩种 {len(merged)}, kl8 {len(merged.get('kl8', []))}条, 最新 {merged.get('kl8', [{}])[0].get('p', '?')})")

    if write_json:
        print("--- Sync data/*.json ---")
        os.makedirs("data", exist_ok=True)
        for t, items in fetched.items():
            fn = INDIVIDUAL_FILES.get(t)
            if not fn:
                continue
            path = os.path.join("data", fn)
            old_items = []
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        old_items = json.load(f)
                except Exception:
                    old_items = []
            save = union_merge(old_items, items, _cap_of(t))
            with open(path, "w", encoding="utf-8") as f:
                json.dump(save, f, ensure_ascii=False, separators=(",", ":"))
            print(f"  data/{fn}: {len(save)}条, 最新 {save[0].get('p', '?')} ({save[0].get('d', '?')})")
    return 0


if __name__ == "__main__":
    sys.exit(main(write_json="--no-json" not in sys.argv))
