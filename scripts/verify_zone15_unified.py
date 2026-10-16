#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证 calc_zone15_dantuo (已修复口径) 与前端 index.html 是否完全一致。
方法: 从 scripts/backup_all_recs.py 源码中用 AST 提取函数本体并执行(测试真实源码);
     对 2026-09-01~2026-10-15 每期, 用"目标期之前50期"作 training, 输出 胆|拖 供对比。"""
import ast, io, json, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = io.open(os.path.join(ROOT, "scripts", "backup_all_recs.py"), encoding="utf-8").read()
tree = ast.parse(src)
fn = next(n for n in tree.body if getattr(n, "name", None) == "calc_zone15_dantuo")
ns = {"Counter": Counter, "from collections import Counter": None}
# 执行函数定义(仅需 collections.Counter)
exec("from collections import Counter\n" + ast.get_source_segment(src, fn), ns)
calc = ns["calc_zone15_dantuo"]

# 数据: index.html 嵌入(最新在前) + zhcw 补齐的 10-09~10-15
html = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
import re
m = re.search(r"window\.__LOTTERY_DATA\s*=\s*(\{.*?\});\s*</script>", html, re.S)
data = json.loads(m.group(1))["kl8"]           # newest-first
NEW = [
 ["2026268","2026-10-09",[1,2,6,7,16,19,26,31,35,40,45,46,48,49,52,59,62,68,73,79]],
 ["2026269","2026-10-10",[1,2,3,7,11,13,15,18,25,27,30,35,44,46,55,57,60,63,70,73]],
 ["2026270","2026-10-11",[3,6,7,8,9,16,21,22,23,27,39,40,41,44,48,54,60,65,68,75]],
 ["2026271","2026-10-12",[10,17,20,22,30,31,37,40,41,43,44,45,50,52,56,58,59,63,71,76]],
 ["2026272","2026-10-13",[11,14,19,20,39,40,41,43,47,51,57,62,64,66,67,68,72,76,77,80]],
 ["2026273","2026-10-14",[9,10,12,14,23,24,27,31,35,38,49,51,52,54,55,58,61,63,65,76]],
 ["2026274","2026-10-15",[8,9,15,17,27,29,35,38,43,44,45,46,47,48,54,56,63,64,70,78]],
]
have = {d["p"] for d in data}
for p, dt, n in NEW:
    if p not in have:
        data.insert(0, {"p": p, "d": dt, "n": n})
data.sort(key=lambda x: int(x["p"]), reverse=True)      # newest-first

# oldest-first, 逐期算 (training = 目标期之前50期)
old = list(reversed(data))
out = {}
for idx in range(len(old)):
    d = old[idx]["d"]
    if not (d >= "2026-09-01" and d <= "2026-10-15"):
        continue
    training = old[max(0, idx - 50):idx]
    if len(training) < 10:
        continue
    r = calc(training, old[idx])
    out[d] = {"dan": r["dan"], "tuo": r["tuo"]}
io.open(os.path.join(ROOT, "scripts", "_zone15_py.json"), "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False))
print("Python 侧生成 %d 期 → scripts/_zone15_py.json" % len(out))
