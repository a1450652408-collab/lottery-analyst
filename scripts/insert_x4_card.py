#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 kl8 推荐区插入「选四·命中率优先」卡片（三份 HTML 同步）
- 4 码：四个区间各取评分最高号（EMA×5+频率×3+动量×2）
- 每月初换号，月内固定；localStorage 记录每日命中
- 命中率 25.89%/期（10 个玩法最高），回收率仍 57%
"""
import io, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["index.html", "deploy/index.html", "index_modified.html"]

ANCHOR = """          _reHtml += '<td style="padding:2px 3px;text-align:right;color:' + (_net >= 0 ? '#2e7d32' : '#c62828') + '">' + (_net >= 0 ? '+' : '') + _net + '</td></tr>';
          _reHtml += '</table></div>';
        }
      })();

      _reHtml += '</div></div>';
    })();

  }"""

BLOCK = """          _reHtml += '<td style="padding:2px 3px;text-align:right;color:' + (_net >= 0 ? '#2e7d32' : '#c62828') + '">' + (_net >= 0 ? '+' : '') + _net + '</td></tr>';
          _reHtml += '</table></div>';
        }
      })();

      _reHtml += '</div></div>';
    })();

    /* ===== 选四·命中率优先（10 个玩法里命中率最高：25.89%/期）===== */
    (function() {
      if (cfg.type !== "keno") return;
      if (!_knEma || !_knFreq30 || !_knMom) return;

      var _now4 = new Date();
      var _ym4 = _now4.getFullYear() + '-' + String(_now4.getMonth() + 1).padStart(2, '0');

      /* 用"当月1号之前"的数据算号，保证月内不变 */
      var _x4Data = [];
      for (var _xi4 = 0; _xi4 < data.length; _xi4++) {
        var _it4 = data[_xi4];
        if (!_it4 || !_it4.d) continue;
        if (_it4.d.slice(0, 7) < _ym4) _x4Data.push(_it4);
        if (_x4Data.length >= 50) break;
      }
      if (_x4Data.length < 10) _x4Data = data.slice(0, Math.min(50, data.length));
      var _x4Period = _x4Data.length;

      var _x4Ema = {};
      for (var _x4n = 1; _x4n <= 80; _x4n++) {
        var _seq4 = [];
        for (var _j24 = 0; _j24 < _x4Period; _j24++) _seq4.push(getNums(_x4Data[_j24]).indexOf(_x4n) >= 0 ? 1 : 0);
        if (!_seq4.length) { _x4Ema[_x4n] = 0; continue; }
        var _e4 = _seq4[_seq4.length - 1];
        for (var _j34 = _seq4.length - 2; _j34 >= 0; _j34--) _e4 = 0.5 * _seq4[_j34] + 0.5 * _e4;
        _x4Ema[_x4n] = _e4;
      }

      var _x4R5 = {}, _x4P5 = {};
      for (var _x4n = 1; _x4n <= 80; _x4n++) { _x4R5[_x4n] = 0; _x4P5[_x4n] = 0; }
      for (var _j4 = 0; _j4 < Math.min(10, _x4Period); _j4++) {
        var _nd4 = getNums(_x4Data[_j4]);
        for (var _k4 = 0; _k4 < _nd4.length; _k4++) { if (_j4 < 5) _x4R5[_nd4[_k4]]++; else _x4P5[_nd4[_k4]]++; }
      }
      var _x4Mom = {};
      for (var _x4n = 1; _x4n <= 80; _x4n++) {
        var _m4 = (_x4R5[_x4n] - _x4P5[_x4n]) / Math.max(_x4P5[_x4n], 1);
        _x4Mom[_x4n] = Math.max(-2, Math.min(2, _m4));
      }

      var _x4F30 = {};
      for (var _x4n = 1; _x4n <= 80; _x4n++) _x4F30[_x4n] = 0;
      for (var _j4b = 0; _j4b < Math.min(30, _x4Period); _j4b++) {
        getNums(_x4Data[_j4b]).forEach(function(n) { _x4F30[n] = (_x4F30[n] || 0) + 1; });
      }

      var _x4Win = Math.min(30, _x4Data.length);
      var _x4Score = {};
      for (var _x4n = 1; _x4n <= 80; _x4n++) {
        _x4Score[_x4n] = (_x4Ema[_x4n] || 0) * 5 + (Math.min(_x4F30[_x4n] || 0, _x4Win) / _x4Win) * 3 + (_x4Mom[_x4n] || 0) * 2;
      }

      /* 四个区间各取评分最高号 → 4 码（区间分散，命中率最高） */
      var _x4Zones = [[1, 20], [21, 40], [41, 60], [61, 80]];
      var _x4Picks = [];
      for (var _zi4 = 0; _zi4 < 4; _zi4++) {
        var _z4 = _x4Zones[_zi4], _best4 = _z4[0], _bs4 = -999;
        for (var _n4 = _z4[0]; _n4 <= _z4[1]; _n4++) {
          var _s4 = _x4Score[_n4] || 0;
          if (_s4 > _bs4) { _bs4 = _s4; _best4 = _n4; }
        }
        _x4Picks.push(_best4);
      }
      _x4Picks.sort(function(a, b) { return a - b; });

      /* 快乐8「选四」官方奖金（1注2元）：中4=93, 中3=5, 中2=3 */
      function _x4Prize(h) { return h >= 4 ? 93 : h === 3 ? 5 : h === 2 ? 3 : 0; }

      _reHtml += '<div class="rec-card" style="border-left-color:#00838f;background:linear-gradient(135deg,#e0f7fa,#b2ebf2)">';
      _reHtml += '<div class="rec-header">🎯 选四·命中率优先（同价最高 25.89%/期）</div>';
      _reHtml += '<div style="padding:4px 6px;font-size:10px;color:#333;line-height:1.6">';
      _reHtml += '<div style="display:flex;flex-wrap:wrap;gap:4px;margin:4px 0">';
      _x4Picks.forEach(function(n) { _reHtml += '<span class="ball r">' + String(n).padStart(2, "0") + '</span>'; });
      _reHtml += '</div>';
      _reHtml += '<div style="margin:2px 0"><b>每月1注×30天=60元</b> · 每月初换号 · 中4=93 / 中3=5 / 中2=3</div>';
      _reHtml += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin:2px 0">';
      _reHtml += '<span style="background:#e0f7fa;padding:1px 6px;border-radius:4px;font-size:9px;color:#00838f">命中率 25.89%/期 → 月均中奖 7.8 次</span>';
      _reHtml += '<span style="background:#fff3e0;padding:1px 6px;border-radius:4px;font-size:9px;color:#e65100">对比: 选二 6.0% / 选三 15.3% / 选六 16.2%</span>';
      _reHtml += '</div>';
      _reHtml += '<div style="font-size:9px;color:#999;margin-top:2px">命中率高≠更赚钱：任何玩法回收率都是 57%（每 60 元期望返 34 元）。此卡用"更频繁的小奖"换"更少的大奖"。</div>';
      _reHtml += '<div class="rec-copy" onclick="navigator.clipboard.writeText(\\'' + _x4Picks.join(' ') + '\\')" style="text-align:right;font-size:10px;cursor:pointer;color:#999;padding:2px 4px;user-select:none">📋复制</div>';

      /* 每日追号详情（localStorage，次月自动清零） */
      (function() {
        var _chKey4 = 'kl8_x4_chase_v1';
        var _ch4 = null;
        try { _ch4 = JSON.parse(localStorage.getItem(_chKey4)); } catch (e) {}
        var _numsStr4 = _x4Picks.join(',');
        if (!_ch4 || _ch4.month !== _ym4 || _ch4.numbers !== _numsStr4) {
          _ch4 = { month: _ym4, numbers: _numsStr4, recs: {} };
        }
        var _found4 = 0;
        try {
          for (var _di4 = 0; _di4 < data.length; _di4++) {
            var _it4b = data[_di4];
            if (!_it4b || !_it4b.d) continue;
            var _dStr4 = _it4b.d.slice(0, 10);
            if (_dStr4.slice(0, 7) !== _ym4) continue;
            if (_ch4.recs[_dStr4]) continue;
            var _draw4 = getNums(_it4b);
            if (!_draw4 || !_draw4.length) continue;
            var _hit4 = 0, _hitNs4 = [];
            for (var _h4 = 0; _h4 < 4; _h4++) {
              if (_draw4.indexOf(_x4Picks[_h4]) >= 0) { _hit4++; _hitNs4.push(_x4Picks[_h4]); }
            }
            _ch4.recs[_dStr4] = { h: _hit4, p: _x4Prize(_hit4), hn: _hitNs4 };
            _found4++;
          }
        } catch (e) {}
        if (_found4 > 0) { try { localStorage.setItem(_chKey4, JSON.stringify(_ch4)); } catch (e) {} }

        var _dates4 = Object.keys(_ch4.recs).sort();
        if (_dates4.length > 0) {
          var _tot4 = 0, _win4 = 0;
          _reHtml += '<div style="margin-top:5px;border-top:1px dashed #80deea;padding-top:4px">';
          _reHtml += '<div style="font-size:10px;font-weight:700;color:#00838f;margin-bottom:2px">📋 本月追号详情（' + _ym4 + '）</div>';
          _reHtml += '<table style="width:100%;font-size:9px;border-collapse:collapse">';
          _reHtml += '<tr style="background:#e0f7fa"><th style="padding:1px 3px;text-align:left;width:38px">日期</th><th style="padding:1px 3px;text-align:center;width:28px">中</th><th style="padding:1px 3px;text-align:left">命中号码</th><th style="padding:1px 3px;text-align:right;width:32px">奖金</th></tr>';
          for (var _d4 = 0; _d4 < _dates4.length; _d4++) {
            var _dd4 = _dates4[_d4], _r4 = _ch4.recs[_dd4];
            _tot4 += _r4.p; if (_r4.p > 0) _win4++;
            var _c4 = _r4.h >= 4 ? '#00695c' : _r4.h === 3 ? '#e65100' : _r4.h === 2 ? '#2e7d32' : '#bbb';
            _reHtml += '<tr><td style="padding:1px 3px;color:#666">' + _dd4.slice(5) + '</td>';
            _reHtml += '<td style="padding:1px 3px;text-align:center;color:' + _c4 + ';font-weight:' + (_r4.h > 0 ? '700' : '400') + '">' + (_r4.h > 0 ? '中' + _r4.h : '-') + '</td>';
            _reHtml += '<td style="padding:1px 3px;color:' + _c4 + '">' + (_r4.hn.length > 0 ? _r4.hn.join(',') : '-') + '</td>';
            _reHtml += '<td style="padding:1px 3px;text-align:right;color:' + (_r4.p > 0 ? '#2e7d32' : '#ccc') + '">' + (_r4.p > 0 ? '+' + _r4.p : '-') + '</td></tr>';
          }
          var _net4 = _tot4 - _dates4.length * 2;
          _reHtml += '<tr style="background:#e0f7fa;font-weight:700"><td style="padding:2px 3px;color:#333">合计</td>';
          _reHtml += '<td style="padding:2px 3px;text-align:center;color:#00838f">' + _dates4.length + '天 · 中奖' + _win4 + '天</td>';
          _reHtml += '<td style="padding:2px 3px;color:#00838f">¥' + _tot4 + '</td>';
          _reHtml += '<td style="padding:2px 3px;text-align:right;color:' + (_net4 >= 0 ? '#2e7d32' : '#c62828') + '">' + (_net4 >= 0 ? '+' : '') + _net4 + '</td></tr>';
          _reHtml += '</table></div>';
        }
      })();

      _reHtml += '</div></div>';
    })();

  }"""

for f in FILES:
    p = os.path.join(ROOT, f)
    h = io.open(p, encoding="utf-8", newline="").read()
    if "选四·命中率优先" in h:
        print(f, "已存在, 跳过"); continue
    # 统一行尾：anchor 里用 \n，实际文件是 \r\n
    nl = "\r\n" if "\r\n" in h else "\n"
    a = ANCHOR.replace("\n", nl)
    b = BLOCK.replace("\n", nl)
    if a not in h:
        print(f, "!! 未找到锚点, 跳过"); continue
    h = h.replace(a, b, 1)
    io.open(p, "w", encoding="utf-8", newline="").write(h)
    print(f, "已插入 ✓", len(b) - len(a), "字节")
