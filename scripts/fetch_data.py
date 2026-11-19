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

修复记录 2026-11-18:
  5. huiniao 的 klb 接口滞后(11-18 时最新只到 11-14, 落后 3 期), 导致站点看起来"几天没更新"。
     新增中国福彩网官方接口兜底(福彩 4 种: ssq / fc3d / qlc / kl8), 官方条目优先入库;
     官方接口失败时静默回退 huiniao, 不影响原有流程。
"""
import json, urllib.request, time, sys, os, re

API = "http://api.huiniao.top/interface/home/lotteryHistory"
CWL = "https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice"
# 中国福彩网只覆盖福彩系; name 参数是官方的彩种代号
CWL_NAME = {"ssq": "ssq", "fc3d": "3d", "qlc": "qlc", "kl8": "kl8"}
CWL_COUNT = 30
# 中国体彩网官方历史接口(体彩 4 种), 同样比 huiniao 及时
SPORTTERY = "https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry"
SPORTTERY_GAME = {"dlt": "85", "pl3": "35", "pl5": "350133", "qxc": "04"}
SPORTTERY_COUNT = 30
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


def fetch_official(name, count=CWL_COUNT):
    """中国福彩网官方开奖公告(福彩 4 种)。比 huiniao 更及时。"""
    req = urllib.request.Request(
        f"{CWL}?name={name}&issueCount={count}",
        headers={"User-Agent": "Mozilla/5.0",
                 "Referer": "https://www.cwl.gov.cn/ygkj/wqkjgg/kl8/"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        j = json.loads(resp.read().decode("utf-8"))
    if j.get("state") != 0:
        raise RuntimeError(f"state={j.get('state')} msg={j.get('message')}")
    return j.get("result", [])


def parse_official(t, item):
    """把官方条目转成与 parse() 一致的结构"""
    red = [int(x) for x in str(item.get("red", "")).split(",") if x.strip() != ""]
    blue = [int(x) for x in str(item.get("blue", "")).split(",") if x.strip() != ""]
    e = {"p": str(item.get("code", "")), "d": str(item.get("date", ""))[:10]}
    if t == "ssq":
        e["r"] = sorted(red[:6]); e["b"] = blue[0] if blue else None
    elif t == "qlc":
        e["r"] = sorted(red[:7])
    elif t == "fc3d":
        e["n"] = red[:3]          # 3D 是位序号, 不能排序
    else:                          # kl8
        e["n"] = sorted(red)
    return e


def fetch_sporttery(game_no, size=SPORTTERY_COUNT):
    """中国体彩网官方历史开奖(大乐透/排列3/排列5/七星彩)"""
    url = (f"{SPORTTERY}?gameNo={game_no}&provinceId=0&pageSize={size}"
           "&isVerify=1&pageNo=1")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://static.sporttery.cn/"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        j = json.loads(resp.read().decode("utf-8"))
    lst = (j.get("value") or {}).get("list") or []
    if not lst:
        raise RuntimeError("empty list")
    return lst


def parse_sporttery(t, item):
    """lotteryDrawResult 是空格分隔的号码串, 与 huiniao 结构对齐"""
    nums = [int(x) for x in str(item.get("lotteryDrawResult", "")).split() if x]
    e = {"p": str(item.get("lotteryDrawNum", "")),
         "d": str(item.get("lotteryDrawTime", ""))[:10]}
    if t == "dlt":
        e["r"] = sorted(nums[:5]); e["b"] = sorted(nums[5:7])
    else:                          # pl3 / pl5 / qxc: 位序号, 不能排序
        e["n"] = nums
    return e


def _prepend_official(out, t, items, src):
    """官方条目排在前面 → union_merge 时官方版本优先"""
    items = [i for i in items if i.get("p")]
    if not items:
        return
    old = out.get(t, [])
    old_latest = old[0]["p"] if old else ""
    new_latest = items[0]["p"]
    out[t] = items + old
    tag = "补" if old_latest < new_latest else "校"
    print(f"  {t}: {src} {new_latest} ({items[0]['d']}) {len(items)}条 [{old_latest or '无'} → {tag}]")


def fetch_all():
    """抓取所有彩种; 返回 {type_key: [条目]}(官方条目排在前面, 优先入库)"""
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

    # --- 官方兜底 1: 福彩系用中国福彩网校正, 解决 huiniao 滞后 ---
    for t, name in CWL_NAME.items():
        try:
            _prepend_official(out, t, [parse_official(t, i) for i in fetch_official(name)], "福彩网")
        except Exception as e:
            print(f"  {t}: 福彩网兜底跳过 ({e})")
        time.sleep(1)

    # --- 官方兜底 2: 体彩系用中国体彩网校正 ---
    for t, g in SPORTTERY_GAME.items():
        try:
            _prepend_official(out, t, [parse_sporttery(t, i) for i in fetch_sporttery(g)], "体彩网")
        except Exception as e:
            print(f"  {t}: 体彩网兜底跳过 ({e})")
        time.sleep(1)
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
