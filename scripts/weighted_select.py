#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""选号逻辑改为「按权重抽样」（可复现），11 月起生效，10 月数据保持不变"""
import io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["index.html", "deploy/index.html", "index_modified.html"]

HELPER = r'''      /* ===== 按权重选号（可复现）=====
         与"取评分最高 N 个"的区别：每个号按 exp((score-min)/T) 的比例获得被选中概率，
         同月同卡用固定种子 → 月内号码不变，但每月自然分散，不会长期锁死在同一批号。
         T 越小越接近"取最高分"；T=0.35 时评分最高的号也只有约 30~40% 概率被选。 */
      var _KL8_WT = 0.35;            /* 抽样温度（调小=更集中，调大=更分散） */
      var _KL8_WFROM = '2026-11';    /* 从该月起启用；改成 '2026-10' 可立即生效 */
      function _kl8CurYm() {
        var t = new Date();
        return t.getFullYear() + '-' + String(t.getMonth() + 1).padStart(2, '0');
      }
      function _kl8UseWeighted() { return _kl8CurYm() >= _KL8_WFROM; }
      function _kl8Rng(seed) {
        var h = 2166136261;
        for (var i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
        var a = h >>> 0;
        return function () {
          a = a + 0x6D2B79F5 | 0;
          var t = Math.imul(a ^ a >>> 15, 1 | a);
          t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
          return ((t ^ t >>> 14) >>> 0) / 4294967296;
        };
      }
      /* 按权重"不放回"抽样：每次按 w 占比抽一个，抽出后移出池子 */
      function _kl8WeightedPick(scores, size, seed) {
        var minS = Infinity, n;
        for (n = 1; n <= 80; n++) { var s0 = scores[n] || 0; if (s0 < minS) minS = s0; }
        var w = {}, pool = [];
        for (n = 1; n <= 80; n++) { w[n] = Math.exp(((scores[n] || 0) - minS) / _KL8_WT); pool.push(n); }
        var rnd = _kl8Rng(seed), out = [];
        while (out.length < size && pool.length) {
          var tot = 0, i;
          for (i = 0; i < pool.length; i++) { tot += w[pool[i]]; }
          var r = rnd() * tot, acc = 0, idx = pool.length - 1;
          for (i = 0; i < pool.length; i++) { acc += w[pool[i]]; if (r <= acc) { idx = i; break; } }
          out.push(pool[idx]);
          pool.splice(idx, 1);
        }
        return out.sort(function (a, b) { return a - b; });
      }
      window._kl8WeightedPick = _kl8WeightedPick;

'''

ANCHOR_HELPER = "      /* ===== 覆盖模式（3 注不重叠号码）· 三张追号卡共用 =====\n"

# 卡片 -> (锚点行, 覆盖语句)
OVERRIDES = [
    ("        _x3Picks.push(_x3best);\n      }",
     "      if (_kl8UseWeighted()) { _x3Picks = _kl8WeightedPick(_x3Score, 3, 'x3|' + _kl8CurYm()); }"),
    ("      _x6Picks = _x6Picks.slice(0, 6).sort(function(a,b){ return a-b; });",
     "      if (_kl8UseWeighted()) { _x6Picks = _kl8WeightedPick(_x6Score, 6, 'x6|' + _kl8CurYm()); }"),
    ("      _x2Picks.sort(function(a,b){return a-b;});",
     "      if (_kl8UseWeighted()) { _x2Picks = _kl8WeightedPick(_x2Score, 2, 'x2|' + _kl8CurYm()); }"),
    ("      _x4Picks.sort(function(a, b) { return a - b; });",
     "      if (_kl8UseWeighted()) { _x4Picks = _kl8WeightedPick(_x4Score, 4, 'x4|' + _kl8CurYm()); }"),
]

SUB_OLD_A = "基于EMA评分+动量+频率 | 每30天重算换号 | 追号请量力而行</div>';"
SUB_NEW_A = "基于EMA评分+动量+频率 | 每30天重算换号 | 追号请量力而行' + (_kl8UseWeighted() ? ' · 按权重抽样' : '') + '</div>';"
SUB_OLD_B = "基于EMA评分+动量+频率（总分Top6）| 每30天重算换号 | 追号请量力而行</div>';"
SUB_NEW_B = "基于EMA评分+动量+频率（总分Top6）| 每30天重算换号 | 追号请量力而行' + (_kl8UseWeighted() ? ' · 按权重抽样' : '') + '</div>';"

for f in FILES:
    p = os.path.join(ROOT, f)
    h = io.open(p, encoding="utf-8", newline="").read()
    if "_kl8WeightedPick" in h:
        print(f, "已存在, 跳过"); continue
    nl = "\r\n" if "\r\n" in h else "\n"
    n0 = len(h)

    a = ANCHOR_HELPER.replace("\n", nl)
    assert h.count(a) == 1, (f, "helper 锚点", h.count(a))
    h = h.replace(a, HELPER.replace("\n", nl) + a, 1)

    for old, call in OVERRIDES:
        o = old.replace("\n", nl)
        assert h.count(o) == 1, (f, "选号锚点", old[:30], h.count(o))
        h = h.replace(o, o + nl + call.replace("\n", nl), 1)

    for so, sn in [(SUB_OLD_A, SUB_NEW_A), (SUB_OLD_B, SUB_NEW_B)]:
        cnt = h.count(so)
        assert cnt >= 1, (f, "副标题锚点", so[:20])
        h = h.replace(so, sn)

    io.open(p, "w", encoding="utf-8", newline="").write(h)
    print(f, "已改为按权重选号 ✓ +", len(h) - n0, "字节")
