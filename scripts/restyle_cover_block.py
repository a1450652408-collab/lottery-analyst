#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重做「覆盖模式」UI：白色面板 + 一注一行 + 每注独立列 + 清晰的汇总行"""
import io, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["index.html", "deploy/index.html", "index_modified.html"]

NEW_FN = r'''      function _kl8CoverBlock(opt) {
        var on = _kl8CoverOn(opt.key);
        var h = '<div style="margin-top:10px;padding:10px;background:#fff;border:1px solid #eceff1;border-radius:10px">';
        /* ── 标题行 ── */
        h += '<div style="display:flex;align-items:center;justify-content:space-between;gap:8px">';
        h += '<label style="display:flex;align-items:center;gap:7px;cursor:pointer;margin:0">';
        h += '<input type="checkbox"' + (on ? ' checked' : '') + ' onchange="_kl8CoverToggle(\'' + opt.key + '\')" style="width:16px;height:16px;margin:0;cursor:pointer">';
        h += '<span style="font-size:12px;font-weight:700;color:#263238">覆盖模式</span>';
        h += '</label>';
        h += '<span style="font-size:10px;color:' + (on ? '#ef6c00' : '#90a4ae') + '">命中率 ' + opt.rate1 + ' → <b>' + opt.rate3 + '</b> · 成本 ×3</span>';
        h += '</div>';
        if (!on) { return h + '</div>'; }

        var groups = _kl8CoverGroups(opt.scores, opt.size, 3, opt.base);
        if (!groups.length) { return h + '</div>'; }

        /* ── 号码：一注一行 ── */
        h += '<div style="margin-top:9px">';
        for (var gi = 0; gi < groups.length; gi++) {
          h += '<div style="display:flex;align-items:center;gap:5px;margin:3px 0">';
          h += '<span style="font-size:10px;color:#b0bec5;width:26px;flex:none">注' + (gi + 1) + '</span>';
          for (var bn = 0; bn < groups[gi].length; bn++) {
            h += '<span style="display:inline-block;min-width:21px;padding:1px 0;background:#f5f7f8;border:1px solid #e3e9eb;border-radius:11px;font-size:11px;color:#37474f;text-align:center">'
              + String(groups[gi][bn]).padStart(2, '0') + '</span>';
          }
          if (gi === 0) { h += '<span style="font-size:9px;color:#b0bec5;margin-left:2px">= 原号码</span>'; }
          h += '</div>';
        }
        h += '</div>';

        /* ── 本月明细 ── */
        var ym = new Date().getFullYear() + '-' + String(new Date().getMonth() + 1).padStart(2, '0');
        var recKey = opt.key + '_recs';
        var st = null;
        try { st = JSON.parse(localStorage.getItem(recKey)); } catch (e) {}
        var sig = groups.map(function (g) { return g.join(','); }).join('|');
        if (!st || st.month !== ym || st.sig !== sig) { st = { month: ym, sig: sig, recs: {} }; }
        var found = 0;
        for (var i2 = 0; i2 < opt.data.length; i2++) {
          var it = opt.data[i2];
          if (!it || !it.d) { continue; }
          var dd = it.d.slice(0, 10);
          if (dd.slice(0, 7) !== ym || st.recs[dd]) { continue; }
          var draw = getNums(it);
          if (!draw || !draw.length) { continue; }
          var set = {}, zz;
          for (zz = 0; zz < draw.length; zz++) { set[draw[zz]] = 1; }
          var prizeSum = 0, det = [], wg = 0;
          for (var g2 = 0; g2 < groups.length; g2++) {
            var hc = 0;
            for (var n2 = 0; n2 < groups[g2].length; n2++) { if (set[groups[g2][n2]]) { hc++; } }
            var pz = opt.prize[hc] || 0;
            prizeSum += pz; if (pz > 0) { wg++; }
            det.push(hc);
          }
          st.recs[dd] = { d: det, p: prizeSum, w: wg };
          found++;
        }
        if (found > 0) { try { localStorage.setItem(recKey, JSON.stringify(st)); } catch (e) {} }

        var ds = Object.keys(st.recs).sort();
        if (!ds.length) { return h + '</div>'; }

        var tot = 0, wins = 0, cost = ds.length * groups.length * 2;
        h += '<div style="margin-top:11px;font-size:10px;color:#90a4ae;margin-bottom:3px">本月明细 · ' + ym + '</div>';
        h += '<table style="width:100%;border-collapse:collapse;font-size:11px">';
        h += '<tr style="color:#90a4ae">'
          + '<th style="padding:3px 2px;text-align:left;font-weight:600">日期</th>'
          + '<th style="padding:3px 2px;font-weight:600">注1</th>'
          + '<th style="padding:3px 2px;font-weight:600">注2</th>'
          + '<th style="padding:3px 2px;font-weight:600">注3</th>'
          + '<th style="padding:3px 2px;text-align:right;font-weight:600">奖金</th></tr>';
        for (var k2 = 0; k2 < ds.length; k2++) {
          var rr = st.recs[ds[k2]];
          tot += rr.p; if (rr.w > 0) { wins++; }
          h += '<tr style="border-top:1px solid #f4f6f7' + (rr.p > 0 ? ';background:#f1f8e9' : '') + '">';
          h += '<td style="padding:3px 2px;color:#546e7a">' + ds[k2].slice(5) + '</td>';
          for (var c2 = 0; c2 < rr.d.length; c2++) {
            h += '<td style="padding:3px 2px;text-align:center;color:' + (rr.d[c2] >= 2 ? '#37474f' : '#b0bec5') + '">' + rr.d[c2] + '</td>';
          }
          h += '<td style="padding:3px 2px;text-align:right;font-weight:' + (rr.p > 0 ? '700' : '400') + ';color:' + (rr.p > 0 ? '#2e7d32' : '#cfd8dc') + '">'
            + (rr.p > 0 ? '+' + rr.p : '–') + '</td></tr>';
        }
        h += '</table>';
        var net = tot - cost;
        h += '<div style="display:flex;align-items:center;gap:12px;margin-top:8px;padding-top:7px;border-top:1px solid #f4f6f7;font-size:11px;color:#78909c">';
        h += '<span>投入 <b style="color:#37474f">' + cost + '</b></span>';
        h += '<span>奖金 <b style="color:' + (tot > 0 ? '#2e7d32' : '#37474f') + '">' + tot + '</b></span>';
        h += '<span>净 <b style="color:' + (net >= 0 ? '#2e7d32' : '#c62828') + '">' + (net >= 0 ? '+' : '') + net + '</b></span>';
        h += '<span style="margin-left:auto">中奖 <b style="color:#37474f">' + wins + '</b> / ' + ds.length + ' 天</span>';
        h += '</div>';
        return h + '</div>';
      }

'''

RATES = {
    "kl8_cover_x2": ("6.0%", "17.3%"),
    "kl8_cover_x3": ("15.3%", "39.9%"),
    "kl8_cover_x6": ("16.0%", "42.6%"),
}

for f in FILES:
    p = os.path.join(ROOT, f)
    h = io.open(p, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in h else "\n"
    src = h.replace("\r\n", "\n")

    start = src.find("      function _kl8CoverBlock(opt) {")
    end = src.find("      window._kl8CoverToggle = _kl8CoverToggle;")
    assert start > 0 and end > start, (f, "定位失败", start, end)
    src = src[:start] + NEW_FN + src[end:]

    # 三处调用补 rate1/rate3
    for key, (r1, r3) in RATES.items():
        old = "key: '" + key + "',"
        assert src.count(old) == 1, (f, key, src.count(old))
        src = src.replace(old, "key: '" + key + "', rate1: '" + r1 + "', rate3: '" + r3 + "',", 1)

    io.open(p, "w", encoding="utf-8", newline="").write(src.replace("\n", nl))
    print(f, "UI 重做 ✓")
