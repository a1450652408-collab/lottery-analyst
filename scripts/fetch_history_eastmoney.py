#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""东方财富历史页补齐本地彩种数据（支持翻页），用于 ttcx4 / sh15x5 等。

背景:
  - 天天彩选4(ttcx4): 500.com 停更于 2026171(06-30)，本库数据在 06-30 后中断；
    东财 /Result/History/ttcx4?page=N 每页 50 期，可翻页回补。
  - 华东15选5(sh15x5): 本库仅 31 期(<recPeriod 50)，东财 /Result/History/hd15x5 可补齐。

用法:
  python scripts/fetch_history_eastmoney.py ttcx4
  python scripts/fetch_history_eastmoney.py sh15x5 [--dry-run]
"""
import re, json, sys, os, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_FILES = ["index.html", "deploy/index.html", "index_modified.html"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0"

# type_key: (东财历史页路径, 每期号码个数, 是否升序排序号码, 独立数据文件)
GAMES = {
    "ttcx4": ("ttcx4", 4, False, "ttcx4_data.json"),
    "sh15x5": ("hd15x5", 5, True, "sh15x5_data.json"),
}


def fetch_page(game_path, digits, page):
    url = f"https://caipiao.eastmoney.com/Result/History/{game_path}?page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as resp:
        h = resp.read().decode("utf-8", errors="replace")
    recs = []
    for row in re.findall(r"<tr>.*?</tr>", h, re.DOTALL):
        pm = re.search(r'id=(\d{7})"[^>]*>(\d{7})</a>', row)
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", row)
        ns = re.findall(r'class="pellet pellet-primary pellet-sm [^"]*">(\d{1,2})</span>', row)
        if pm and dm and len(ns) == digits:
            recs.append({"p": pm.group(1), "d": dm.group(1), "n": [int(x) for x in ns]})
    return recs


def find_embedded(html):
    m = re.search(r"window\.__LOTTERY_DATA\s*=\s*", html)
    if not m:
        return None, -1, -1
    start = m.end()
    obj, n = json.JSONDecoder().raw_decode(html[start:])
    return obj, start, start + n


def main(type_key, dry_run=False):
    if type_key not in GAMES:
        print("未知彩种:", type_key, "可选:", ",".join(GAMES)); return 1
    game_path, digits, do_sort, json_name = GAMES[type_key]

    with open(os.path.join(ROOT, "index.html"), "r", encoding="utf-8", newline="") as f:
        base = f.read()
    obj, s, e = find_embedded(base)
    if obj is None:
        print("!! 无法定位嵌入数据"); return 1
    have = {x["p"]: x for x in obj.get(type_key, [])}
    if not have:
        print(f"!! 无 {type_key} 数据"); return 1
    oldest, newest = min(have, key=int), max(have, key=int)
    print(f"[{type_key}] 现有 {len(have)} 期, {oldest} ~ {newest}")

    fetched, page = {}, 1
    while page <= 12:
        try:
            recs = fetch_page(game_path, digits, page)
        except Exception as ex:
            print(f"  第{page}页抓取失败: {ex}"); break
        if not recs:
            print(f"  第{page}页无数据, 停止"); break
        lo, hi = min(r["p"] for r in recs), max(r["p"] for r in recs)
        print(f"  第{page}页: {len(recs)}期 {lo}~{hi}")
        for r in recs:
            fetched.setdefault(r["p"], r)
        if lo <= oldest:
            break
        page += 1
        time.sleep(2)

    overlap = sorted(set(fetched) & set(have), key=int)
    mism = [p for p in overlap if fetched[p]["n"] != have[p]["n"]]
    print(f"重叠校验: {len(overlap)} 期, 不一致 {len(mism)}")
    for p in mism[:10]:
        print(f"   ✗ {p} 接口 {fetched[p]['n']} vs 本库 {have[p]['n']}")
    if mism:
        print("!! 存在不一致, 中止(避免污染数据)"); return 1

    add = sorted([p for p in fetched if p not in have], key=int)
    print(f"缺失待补: {len(add)} 期" + (f"  {add[0]}~{add[-1]}" if add else ""))
    if not add:
        print("无需补数据"); return 0

    merged = list(have.values()) + [fetched[p] for p in add]
    for it in merged:
        if do_sort:
            it["n"] = sorted(it["n"])
    merged.sort(key=lambda x: int(x["p"]), reverse=True)
    ps = [int(x["p"]) for x in merged]
    gaps = [(ps[i], ps[i + 1]) for i in range(len(ps) - 1) if ps[i] - ps[i + 1] != 1]
    print(f"合并后: {len(merged)} 期 {ps[-1]} ~ {ps[0]}; 期号断点 {len(gaps)}" + (f" {gaps[:5]}" if gaps else ""))

    if dry_run:
        print("--dry-run, 不写文件"); return 0

    for fn in HTML_FILES:
        p = os.path.join(ROOT, fn)
        with open(p, "r", encoding="utf-8", newline="") as f:
            h = f.read()
        o, s2, e2 = find_embedded(h)
        if o is None:
            print(f"  {fn}: 定位失败, 跳过"); continue
        o[type_key] = merged
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(h[:s2] + json.dumps(o, ensure_ascii=False, separators=(",", ":")) + h[e2:])
        print(f"  {fn}: {type_key} → {len(merged)} 期")
    jp = os.path.join(ROOT, "data", json_name)
    with open(jp, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(merged, ensure_ascii=False, separators=(",", ":")))
    print(f"  data/{json_name}: {len(merged)} 期")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(1)
    sys.exit(main(args[0], dry_run="--dry-run" in sys.argv))
