#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给三张追号卡加「覆盖模式(3注不重叠)」开关
- 默认关闭：卡片行为完全不变
- 打开后：按评分再取 2 组不重叠号码，共 3 注/期（成本 6 元），任一注中奖即算命中
- 独立 localStorage：kl8_cover_x2 / x3 / x6 + *_recs
"""
import io, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["index.html", "deploy/index.html", "index_modified.html"]

HELPER = """      /* ===== 覆盖模式（3 注不重叠号码）· 三张追号卡共用 =====
         数学依据: 同一玩法下"有奖率"只由每注号码数决定, 与选哪几个号无关;
         想提高命中率只能增加覆盖号码数(成本线性上涨)。 */
      function _kl8CoverOn(key) { try { return localStorage.getItem(key) === '1'; } catch (e) { return false; } }
      function _kl8CoverToggle(key) {
        try { localStorage.setItem(key, _kl8CoverOn(key) ? '0' : '1'); } catch (e) {}
        if (window._kl8ReRender) window._kl8ReRender();
      }
      function _kl8CoverGroups(scores, size, n) {
        var ranked = Object.keys(scores).map(Number).sort(function (a, b) { return (scores[b] || 0) - (scores[a] || 0) || a - b; });
        var used = {}, out = [];
        for (var g = 0; g < n; g++) {
          var grp = [];
          for (var i = 0; i < ranked.length && grp.length < size; i++) {
            if (used[ranked[i]]) continue;
            used[ranked[i]] = 1; grp.push(ranked[i]);
          }
          if (grp.length < size) break;
          out.push(grp.sort(function (a, b) { return a - b; }));
        }
        return out;
      }
      function _kl8CoverBlock(opt) {
        var on = _kl8CoverOn(opt.key);
        var h = '<div style="margin-top:6px;border-top:1px dashed #b0bec5;padding-top:5px">';
        h += '<label style="display:flex;align-items:center;gap:5px;font-size:10px;color:#37474f;cursor:pointer">';
        h += '<input type="checkbox"' + (on ? ' checked' : '') + ' onchange="_kl8CoverToggle(\\'' + opt.key + '\\')" style="cursor:pointer">';
        h += '<b>覆盖模式</b>（3 注不重叠）<span style="color:#ef6c00">成本 6 元/期 · 命中率约 ×2.6</span>';
        h += '</label>';
        if (!on) return h + '</div>';
        var groups = _kl8CoverGroups(opt.scores, opt.size, 3);
        if (!groups.length) return h + '</div>';
        h += '<div style="display:flex;flex-wrap:wrap;gap:3px;margin:4px 0">';
        for (var gi = 0; gi < groups.length; gi++) {
          h += '<span style="background:#fff;border:1px solid #cfd8dc;border-radius:3px;padding:1px 4px;font-size:9px">' + (gi + 1) + ': '
            + groups[gi].map(function (n) { return String(n).padStart(2, '0'); }).join(' ') + '</span>';
        }
        h += '</div>';
        var ym = new Date().getFullYear() + '-' + String(new Date().getMonth() + 1).padStart(2, '0');
        var recKey = opt.key + '_recs';
        var st = null;
        try { st = JSON.parse(localStorage.getItem(recKey)); } catch (e) {}
        var sig = groups.map(function (g) { return g.join(','); }).join('|');
        if (!st || st.month !== ym || st.sig !== sig) st = { month: ym, sig: sig, recs: {} };
        var found = 0;
        for (var i2 = 0; i2 < opt.data.length; i2++) {
          var it = opt.data[i2];
          if (!it || !it.d) continue;
          var dd = it.d.slice(0, 10);
          if (dd.slice(0, 7) !== ym || st.recs[dd]) continue;
          var draw = getNums(it);
          if (!draw || !draw.length) continue;
          var set = {}, zz;
          for (zz = 0; zz < draw.length; zz++) set[draw[zz]] = 1;
          var prizeSum = 0, det = [], wg = 0;
          for (var g2 = 0; g2 < groups.length; g2++) {
            var hc = 0;
            for (var n2 = 0; n2 < groups[g2].length; n2++) if (set[groups[g2][n2]]) hc++;
            var pz = opt.prize[hc] || 0;
            prizeSum += pz; if (pz > 0) wg++;
            det.push(hc);
          }
          st.recs[dd] = { d: det, p: prizeSum, w: wg };
          found++;
        }
        if (found > 0) { try { localStorage.setItem(recKey, JSON.stringify(st)); } catch (e) {} }
        var ds = Object.keys(st.recs).sort();
        if (ds.length) {
          var tot = 0, wins = 0, cost = ds.length * groups.length * 2;
          h += '<table style="width:100%;font-size:9px;border-collapse:collapse;margin-top:3px">';
          h += '<tr style="background:#eceff1"><th style="padding:1px 3px;text-align:left;width:38px">日期</th><th style="padding:1px 3px;text-align:center">各注命中</th><th style="padding:1px 3px;text-align:right;width:36px">奖金</th></tr>';
          for (var k2 = 0; k2 < ds.length; k2++) {
            var rr = st.recs[ds[k2]];
            tot += rr.p; if (rr.w > 0) wins++;
            h += '<tr><td style="padding:1px 3px;color:#666">' + ds[k2].slice(5) + '</td>';
            h += '<td style="padding:1px 3px;text-align:center;color:' + (rr.w > 0 ? '#2e7d32' : '#bbb') + '">' + rr.d.join('/') + '</td>';
            h += '<td style="padding:1px 3px;text-align:right;color:' + (rr.p > 0 ? '#2e7d32' : '#ccc') + '">' + (rr.p > 0 ? '+' + rr.p : '-') + '</td></tr>';
          }
          h += '<tr style="background:#eceff1;font-weight:700"><td style="padding:2px 3px">合计</td>';
          h += '<td style="padding:2px 3px;text-align:center">' + ds.length + '天 · 中奖' + wins + '天</td>';
          h += '<td style="padding:2px 3px;text-align:right;color:' + (tot - cost >= 0 ? '#2e7d32' : '#c62828') + '">' + (tot - cost >= 0 ? '+' : '') + (tot - cost) + '</td></tr>';
          h += '</table>';
        }
        return h + '</div>';
      }
      window._kl8CoverToggle = _kl8CoverToggle;

"""

# 1) 插入 helper（在选三卡之前）
ANCHOR_HELPER = "    /* ===== 选三·每月追号推荐（EMA评分+最优3区）===== */"

# 2) 三处调用：各自卡内、收尾之前
PATCHES = [
    ("选三", "    /* ===== 选六·每月追号推荐（EMA评分总分Top6 + 翻倍追号）===== */",
     "      _reHtml += _kl8CoverBlock({ key: 'kl8_cover_x3', size: 3, scores: _x3Score, prize: { 3: 52, 2: 3 }, data: data });\n"),
    ("选六", "    /* ===== 选二·每月追号推荐（EMA评分+最优2区）===== */",
     "      _reHtml += _kl8CoverBlock({ key: 'kl8_cover_x6', size: 6, scores: _x6Score, prize: { 6: 2880, 5: 30, 4: 10, 3: 3 }, data: data });\n"),
    ("选二", "    /* ===== 选四·命中率优先（10 个玩法里命中率最高：25.89%/期）===== */",
     "      _reHtml += _kl8CoverBlock({ key: 'kl8_cover_x2', size: 2, scores: _x2Score, prize: { 2: 19 }, data: data });\n"),
]

# 3) 重渲染钩子
ANCHOR_RR = "function renderRecommend(type, data) {"

for f in FILES:
    p = os.path.join(ROOT, f)
    h = io.open(p, encoding="utf-8", newline="").read()
    if "_kl8CoverBlock" in h:
        print(f, "已存在, 跳过"); continue
    nl = "\r\n" if "\r\n" in h else "\n"
    n0 = h

    # helper
    a = ANCHOR_HELPER.replace("\n", nl)
    assert h.count(a) == 1, (f, "helper 锚点数量", h.count(a))
    h = h.replace(a, HELPER.replace("\n", nl) + a, 1)

    # 调用
    for name, next_anchor, call in PATCHES:
        tail = "      _reHtml += '</div></div>';" + nl + "    })();" + nl + nl + next_anchor.replace("\n", nl)
        assert h.count(tail) == 1, (f, name, "尾部锚点数量", h.count(tail))
        repl = call.replace("\n", nl) + tail
        h = h.replace(tail, repl, 1)

    # 重渲染钩子
    a2 = ANCHOR_RR.replace("\n", nl)
    assert h.count(a2) == 1, (f, "renderRecommend 锚点数量", h.count(a2))
    hook = a2 + nl + "  window._kl8ReRender = function () { try { if (cache[cur]) renderRecommend(cur, cache[cur]); } catch (e) {} };"
    h = h.replace(a2, hook, 1)

    io.open(p, "w", encoding="utf-8", newline="").write(h)
    print(f, "已打补丁 ✓ 增长", len(h) - len(n0), "字节")
