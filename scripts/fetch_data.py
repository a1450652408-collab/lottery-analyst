import json, urllib.request, time, sys, os

API = "http://api.huiniao.top/interface/home/lotteryHistory"
TYPES = [("ssq","ssq",50),("dlt","dlt",50),("qlc","qlc",50),
         ("kl8","klb",300),("fc3d","fcsd",100),("pl3","pls",100),
         ("pl5","plw",100),("qxc","qxc",100)]
FIELDS = ["one","two","three","four","five","six","seven",
          "eight","nine","ten","eleven","twelve","thirteen",
          "fourteen","fifteen","sixteen","seventeen","eighteen",
          "nineteen","twenty"]

def fetch(a, l):
    r = urllib.request.Request(f"{API}?type={a}&page=1&limit={l}",
        headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def parse(api, item):
    nums = []
    for f in FIELDS:
        v = item.get(f)
        if v is not None:
            try: nums.append(int(v))
            except: pass
    e = {"p": str(item.get("code","")), "d": str(item.get("day",""))}
    if api=="ssq": e["r"]=sorted(nums[:6]); e["b"]=nums[6] if len(nums)>6 else None
    elif api=="dlt": e["r"]=sorted(nums[:5]); e["b"]=sorted(nums[5:7]) if len(nums)>5 else []
    elif api in ("fcsd","pls"): e["n"]=nums[:3]
    elif api=="plw": e["n"]=nums[:5]
    elif api=="qxc": e["n"]=nums[:7]
    elif api=="qlc": e["r"]=sorted(nums[:7])
    else: e["n"]=sorted(nums)
    return e

all_data = {}
for t, a, l in TYPES:
    try:
        d = fetch(a, l)
        if d.get("code") == 1:
            items = d["data"]["data"]["list"]
            all_data[t] = [parse(a,i) for i in items]
            print(f"{t}: {all_data[t][0]['p']} ({all_data[t][0]['d']})")
        else: print(f"{t}: API error")
    except Exception as e: print(f"{t}: FAIL {e}")
    time.sleep(2)

js = "/* 开奖数据 - auto */\n"
js += "window.__LOTTERY_DATA = " + json.dumps(all_data, ensure_ascii=False, indent=2) + ";"

for fn in ["index.html", "deploy/index.html", "index_modified.html"]:
    if not os.path.exists(fn):
        print(f"{fn}: not found, skip")
        continue
    with open(fn, "r", encoding="utf-8") as f:
        h = f.read()
    ds = h.find("window.__LOTTERY_DATA = ")
    de = h.find(";\n</script>", ds)
    if ds > 0 and de > 0:
        ss = h.rfind("<script>", 0, ds)
        nc = h.find("</script>", de)
        nh = h[:ss] + "<script>\n" + js + "\n" + h[nc:]
        with open(fn, "w", encoding="utf-8") as f:
            f.write(nh)
        print(f"{fn}: updated")
    else:
        print(f"{fn}: data block not found")
