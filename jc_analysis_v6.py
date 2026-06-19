"""
竞彩足球 V6 — ELO + 市场赔率混合策略
========================================

放弃纯泊松模型（世界杯数据量不足），改用:
  1. 锦标赛ELO（从实际赛果滚动训练）
  2. 市场隐含概率（赔率反推）
  3. 加权混合: 70%市场 + 30% ELO
  4. 仅在模型与市场分歧显著时产生推荐

数据源:
  1. 竞彩网官方API: webapi.sporttery.cn (今日赔率)
  2. jc_results.json (历史赛果 → ELO计算)
  3. team_data.py (实力评分/积分榜)

输出:
  - jc_recommend_v6.json
  - jc_analysis_report_v6.md
"""

import requests, json, os, math, sys, re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ===== 配置 =====
BASE_URL = 'https://webapi.sporttery.cn/gateway/uniform/football'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.sporttery.cn/',
    'Origin': 'https://www.sporttery.cn'
}
OUTPUT_FILE = 'jc_recommend_v6.json'
REPORT_FILE = 'jc_report_v6.md'
RESULTS_FILE = 'data/jc_results.json'
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# ELO参数
ELO_INIT = 1500
ELO_K = 16  # 降低K值，避免2场比赛过度波动
ELO_HOME_ADV = 80

# 混合权重
MARKET_WEIGHT = 0.70
ELO_WEIGHT = 0.30

# 推荐阈值 (新策略: ELO+市场一致优先)
MIN_ODDS = 1.30        # 最低赔率
MAX_ODDS = 5.00        # 最高赔率（超过则太冷门，不推荐）
MIN_PROB_THRESHOLD = 35  # 混合概率至少35%才推荐

# ===== 球队名称归一化 (简称 → 全名) =====
NAME_NORMALIZE = {
    '克罗地': '克罗地亚', '阿尔及利': '阿尔及利亚',
    '塞内': '塞内加尔', '新西': '新西兰', '佛得': '佛得角',
    '突尼': '突尼斯', '科特迪': '科特迪瓦', '厄瓜多': '厄瓜多尔',
    '澳大': '澳大利亚', '卡塔': '卡塔尔', '巴拉': '巴拉圭',
    '巴拿': '巴拿马', '库拉': '库拉索',
}

def normalize_name(name):
    """统一队名"""
    if not name:
        return name
    # 直接映射
    if name in NAME_NORMALIZE:
        return NAME_NORMALIZE[name]
    # 部分匹配
    for short, full in NAME_NORMALIZE.items():
        if short in name:
            return full
    return name


# ===== ELO 计算 =====
def build_tournament_elo(results_file=None):
    """从历史赛果构建锦标赛ELO"""
    if results_file is None:
        results_file = os.path.join(os.path.dirname(__file__), RESULTS_FILE)
    
    if not os.path.exists(results_file):
        print(f'[ELO] ⚠️ 没有历史赛果: {results_file}')
        return {}
    
    with open(results_file, encoding='utf-8') as f:
        results = json.load(f)
    
    elo = {}
    
    for r in reversed(results):  # 时间正序
        home = normalize_name(r['home'])
        away = normalize_name(r['away'])
        hs = r.get('home_score', 0)
        aws = r.get('away_score', 0)
        
        if home not in elo:
            elo[home] = ELO_INIT
        if away not in elo:
            elo[away] = ELO_INIT
        
        elo_h = elo[home] + ELO_HOME_ADV
        elo_a = elo[away]
        
        e_h = 1 / (1 + 10 ** ((elo_a - elo_h) / 400))
        e_a = 1 - e_h
        
        if hs > aws:
            s_h, s_a = 1, 0
        elif hs < aws:
            s_h, s_a = 0, 1
        else:
            s_h, s_a = 0.5, 0.5
        
        elo[home] += ELO_K * (s_h - e_h)
        elo[away] += ELO_K * (s_a - e_a)
    
    print(f'[ELO] 从 {len(results)} 场比赛计算出 {len(elo)} 队ELO')
    return elo


def elo_win_prob(home_elo, away_elo):
    """ELO → 胜平负概率 (使用经典公式 + 平局模型)"""
    elo_diff = home_elo - away_elo + ELO_HOME_ADV
    
    # 主胜概率 (ELO基础)
    p_home = 1 / (1 + 10 ** (-elo_diff / 400))
    
    # 平局概率模型: 平局概率随elo差增大而减小
    # 基于经验: 实力越接近，平局概率越高
    abs_diff = abs(elo_diff)
    p_draw_raw = max(0.15, 0.32 - abs_diff / 1200)  # 15%~32%范围
    
    # 归一化
    p_away = 1 - p_home
    p_draw = p_draw_raw
    p_home = p_home * (1 - p_draw_raw)
    p_away = p_away * (1 - p_draw_raw)
    
    total = p_home + p_draw + p_away
    return p_home / total, p_draw / total, p_away / total


def calc_implied_prob(odds):
    """从赔率反推市场隐含概率（去抽水）"""
    if len(odds) != 3 or min(odds) <= 0:
        return None, None, None
    
    implied = [1/o for o in odds]
    total_imp = sum(implied)
    juice = (total_imp - 1) * 100
    
    if juice > 15:
        return None, None, None
    
    fair_probs = [i / total_imp for i in implied]
    return implied, fair_probs, juice


# ===== API 数据获取 =====
def fetch_today_matches():
    """获取今日竞彩比赛列表"""
    r = requests.get(f'{BASE_URL}/getMatchListV1.qry?clientCode=3001', headers=HEADERS, timeout=15)
    data = r.json()
    if not data.get('success'):
        print('API请求失败:', data.get('errorMessage'))
        return []
    matches = data['value']['matchInfoList']
    result = []
    for group in matches:
        for sm in group.get('subMatchList', []):
            had_odds = None
            hhad_odds = None
            for odds in sm.get('oddsList', []):
                if odds.get('poolCode') == 'HAD':
                    had_odds = odds
                elif odds.get('poolCode') == 'HHAD':
                    hhad_odds = odds
            
            if not had_odds:
                continue
            
            try:
                home = sm.get('homeTeamAbbName', '') or sm.get('homeTeamAllName', '')
                away = sm.get('awayTeamAbbName', '') or sm.get('awayTeamAllName', '')
                league = sm.get('leagueAbbName', '') or sm.get('leagueAllName', '')
                match_time = sm.get('matchTime', '')
            except:
                continue
            
            result.append({
                'homeTeam': home,
                'awayTeam': away,
                'league': league,
                'matchTime': match_time,
                'matchDate': sm.get('matchDate', ''),
                'had_h': float(had_odds.get('h', 0)),
                'had_d': float(had_odds.get('d', 0)),
                'had_a': float(had_odds.get('a', 0)),
                'hhad_h': float(hhad_odds.get('h', 0)) if hhad_odds else 0,
                'hhad_d': float(hhad_odds.get('d', 0)) if hhad_odds else 0,
                'hhad_a': float(hhad_odds.get('a', 0)) if hhad_odds else 0,
            })
    return result


# ===== 混合分析 =====
def analyze_match_hybrid(match, elo, standings=None):
    """ELO + 市场赔率 混合分析"""
    had_odds = [match['had_h'], match['had_d'], match['had_a']]
    
    # 1. 市场隐含概率
    _, fair_probs, juice = calc_implied_prob(had_odds)
    if fair_probs is None:
        return None
    
    market_h, market_d, market_a = fair_probs[0], fair_probs[1], fair_probs[2]
    
    # 2. ELO概率
    home_en = normalize_name(match['homeTeam'])
    away_en = normalize_name(match['awayTeam'])
    
    home_elo = elo.get(home_en, ELO_INIT)
    away_elo = elo.get(away_en, ELO_INIT)
    
    elo_h, elo_d, elo_a = elo_win_prob(home_elo, away_elo)
    
    # 3. 混合概率
    blend_h = MARKET_WEIGHT * market_h + ELO_WEIGHT * elo_h
    blend_d = MARKET_WEIGHT * market_d + ELO_WEIGHT * elo_d
    blend_a = MARKET_WEIGHT * market_a + ELO_WEIGHT * elo_a
    
    # 4. 计算各选项EV（用混合概率 × 赔率）
    labels = ['主胜', '平局', '客胜']
    blenders = [blend_h, blend_d, blend_a]
    market_probs = [market_h, market_d, market_a]
    elo_probs = [elo_h, elo_d, elo_a]
    
    options = []
    for i in range(3):
        bp = blenders[i]
        mp = market_probs[i]
        ep = elo_probs[i]
        odds = had_odds[i]
        
        ev = odds * bp - 1
        divergence = (ep - mp) * 100  # 正 = ELO比市场更看好
        
        options.append({
            'label': labels[i],
            'odds': odds,
            'blend_prob': round(bp * 100, 1),
            'market_prob': round(mp * 100, 1),
            'elo_prob': round(ep * 100, 1),
            'ev': round(ev * 100, 1),
            'divergence': round(divergence, 1),
            'abs_div': abs(divergence),
        })
    
    options.sort(key=lambda x: (-x['ev'], -x['abs_div']))
    
    # 5. 评分 — ELO做方向过滤器，不调节概率
    elo_best_idx = max(range(3), key=lambda i: elo_probs[i])
    market_best_idx = max(range(3), key=lambda i: market_probs[i])
    
    elo_direction = labels[elo_best_idx]
    market_direction = labels[market_best_idx]
    
    agree = (elo_best_idx == market_best_idx)
    
    # ELO差距（主队+主场优势 vs 客队）
    elo_gap = abs(home_elo + ELO_HOME_ADV - away_elo)
    market_strength = market_probs[market_best_idx] * 100  # 市场对热门的信心
    
    if agree:
        fav_label = market_direction
        fav_idx = market_best_idx
        fav_odds = had_odds[fav_idx]
        fav_market_pct = market_probs[fav_idx] * 100
        
        best = next((o for o in options if o['label'] == fav_label), options[0])
        score = 2.0
        reasons = [f'ELO+市场一致→{fav_label}']
        
        # ELO差距越大，信号越强
        if elo_gap > 100:
            score += 2.5
            reasons.append(f'ELO差{elo_gap:.0f}点')
        elif elo_gap > 60:
            score += 1.5
        elif elo_gap > 30:
            score += 0.5
        
        # 市场强倾向
        if fav_market_pct > 60:
            score += 1.5
            reasons.append('市场强信号')
        elif fav_market_pct > 50:
            score += 1.0
        
        # 赔率区间评分
        if 1.50 <= fav_odds <= 2.20:
            score += 2.0
        elif 1.30 <= fav_odds < 1.50:
            score += 1.0
        elif fav_odds < 1.20:
            score -= 1.0
            reasons.append('赔率偏低')
        
        # 平局共识降权
        if fav_label == '平局':
            score -= 1.0
        
        # 推荐条件：赔率合理 + 不是纯平局
        should_recommend = (fav_odds >= MIN_ODDS and fav_label != '平局')
    else:
        # 不一致：检查ELO方向是否有价值
        elo_fav_odds = had_odds[elo_best_idx]
        elo_divergence = (elo_probs[elo_best_idx] - market_probs[elo_best_idx]) * 100
        
        best = next((o for o in options if o['label'] == elo_direction), options[0])
        score = 0.5
        reasons = [f'ELO→{elo_direction} ≠ 市场→{market_direction}']
        
        if abs(elo_divergence) > 15:
            score += 1.5
            reasons.append(f'大分歧{abs(elo_divergence):.0f}%')
        
        if 2.0 <= elo_fav_odds <= MAX_ODDS:
            score += 1.0
        elif elo_fav_odds > MAX_ODDS:
            score -= 2.0
        
        # 仅在ELO强烈分歧且赔率合理时推荐ELO方向
        should_recommend = (elo_divergence > 12 and 2.0 <= elo_fav_odds <= MAX_ODDS)
    
    # 信心映射
    if score >= 5.0:
        confidence = '★★★★★'
    elif score >= 3.5:
        confidence = '★★★★'
    elif score >= 2.5:
        confidence = '★★★'
    elif score >= 1.5:
        confidence = '★★'
    else:
        confidence = '★'
    
    return {
        'options': options,
        'best': best,
        'score': round(score, 1),
        'confidence': confidence,
        'reasons': reasons,
        'should_recommend': should_recommend,
        'agree': agree,
        'elo': {'home': round(home_elo, 1), 'away': round(away_elo, 1)},
        'blend_probs': {'home': round(blend_h*100,1), 'draw': round(blend_d*100,1), 'away': round(blend_a*100,1)},
    }


# ===== 报告生成 =====
def generate_report(output, results):
    lines = [
        f"# 竞彩 V6 混合分析报告 ({output['date']})",
        f"",
        f"> 生成时间: {output['updateTime']}",
        f"> 策略: ELO(30%) + 市场赔率(70%) 混合，ELO+市场一致优先",
        f"> ELO训练数据: {output['elo_info']['matches']}场比赛, {output['elo_info']['teams']}支球队",
        f"> 推荐阈值: ELO+市场方向一致 且 赔率≥{MIN_ODDS}",
        f"",
        f"---",
        f"",
        f"## 今日概览",
        f"",
        f"- 今日共 {output['totalMatches']} 场比赛",
        f"- 产生推荐: {len(output['recommendations'])} 场",
        f"- 无分歧不推荐: {output.get('no_signal', 0)} 场",
        f"",
        f"---",
        f"",
    ]
    
    recs = output.get('recommendations', [])
    if recs:
        lines.extend([
            f"## 📋 推荐列表",
            f"",
            f"| 信心 | 比赛 | 推荐 | 赔率 | 混合概率 | 市场概率 | ELO概率 | EV | 分歧 |",
            f"|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
        ])
        for r in recs:
            best = r['best']
            bl = r['blend_probs']
            opt = best
            lines.append(
                f"| {r['confidence']} "
                f"| {r['homeTeam']} vs {r['awayTeam']} "
                f"| {best['label']} "
                f"| {best['odds']} "
                f"| {best['blend_prob']}% "
                f"| {best['market_prob']}% "
                f"| {best['elo_prob']}% "
                f"| +{best['ev']}% "
                f"| {best['divergence']:+.0f}% |"
            )
        lines.append("")
    
    # 无信号比赛
    no_signal = output.get('no_signal_matches', [])
    if no_signal:
        lines.extend([
            f"## 🔇 无信号比赛（不推荐）",
            f"",
            f"| 比赛 | 市场倾向 | ELO倾向 | 分歧度 | 说明 |",
            f"|:---|:---:|:---:|:---:|:---|",
        ])
        for ns in no_signal:
            lines.append(
                f"| {ns['homeTeam']} vs {ns['awayTeam']} "
                f"| {ns['market_favor']} "
                f"| {ns['elo_favor']} "
                f"| {ns['max_div']:.0f}% "
                f"| {ns['reason']} |"
            )
        lines.append("")
    
    # ELO排名
    lines.extend([
        f"## 📊 锦标赛ELO排名 (Top 15)",
        f"",
        f"| 排名 | 球队 | ELO | 变化 |",
        f"|:---:|:---|:---:|:---:|",
    ])
    elo_rank = output.get('elo_rankings', [])
    for i, (team, e) in enumerate(elo_rank[:15], 1):
        delta = e - ELO_INIT
        lines.append(f"| {i} | {team} | {e:.1f} | {delta:+.1f} |")
    lines.append("")
    
    # 风险提示
    lines.extend([
        f"---",
        f"",
        f"## ⚠️ 策略说明",
        f"",
        f"1. **混合策略**: 70%跟随市场 + 30%锦标赛ELO，ELO与市场一致时才推荐",
        f"2. **推荐条件**: ELO+市场指向同一方向 且 赔率≥{MIN_ODDS}"
        f"（平局共识除外）",
        f"3. **无信号**: 赔率过低或方向分歧的比赛不强行推荐",
        f"4. **ELO限制**: 基于世界杯28场小组赛训练，纯WC表现",
        f"5. 本报告仅供参考，请理性投注",
        f"",
        f"---",
        f"",
        f"*报告由 V6 ELO+市场混合模型自动生成*",
    ])
    
    return '\n'.join(lines)


def sync_jc_matches(output):
    """同步到前端 jc.html"""
    data_path = os.path.join(DATA_DIR, 'jc_matches.json')
    matches_data = []
    for r in output.get('recommendations', []):
        matches_data.append({
            'homeTeam': r['homeTeam'],
            'awayTeam': r['awayTeam'],
            'recommend': r['best']['label'],
            'best_odds': r['best']['odds'],
            'confidence': r['confidence'],
            'ev': r['best']['ev'],
            'divergence': r['best']['divergence'],
            'blend_prob': r['best']['blend_prob'],
        })
    
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump({
            'date': output['date'],
            'updateTime': output['updateTime'],
            'matches': matches_data,
            'summary': {
                'total': len(matches_data),
                'strategy': 'V6 ELO+Market Hybrid',
            }
        }, f, ensure_ascii=False, indent=2)
    print(f'[同步] jc_matches.json ({len(matches_data)}场)')


def main():
    print(f'[{datetime.now().strftime("%H:%M:%S")}] === 竞彩V6 ELO+市场混合分析 ===')
    
    # 1. 构建ELO
    elo = build_tournament_elo()
    
    # 2. 获取今日比赛
    matches = fetch_today_matches()
    if not matches:
        print('❌ 今日无比赛')
        return
    print(f'✅ 获取到 {len(matches)} 场比赛')
    
    # 3. 混合分析
    recommendations = []
    no_signal = []
    
    for m in matches:
        result = analyze_match_hybrid(m, elo)
        if not result:
            continue
        
        if result['should_recommend']:
            rec = {
                'homeTeam': m['homeTeam'],
                'awayTeam': m['awayTeam'],
                'league': m.get('league', ''),
                'matchTime': m.get('matchTime', ''),
                'matchDate': m.get('matchDate', ''),
                'confidence': result['confidence'],
                'score': result['score'],
                'best': result['best'],
                'blend_probs': result['blend_probs'],
                'elo': result['elo'],
                'options': result['options'],
                'reasons': result['reasons'],
                'agree': result.get('agree', False),
            }
            recommendations.append(rec)
        else:
            options = result['options']
            market_favor = max(options, key=lambda x: x['market_prob'])['label']
            elo_favor = max(options, key=lambda x: x['elo_prob'])['label']
            max_div = max(o['abs_div'] for o in options)
            
            agree = result.get('agree', False)
            if agree:
                fav_idx = max(range(3), key=lambda i: {
                    'home': result['blend_probs']['home'],
                    'draw': result['blend_probs']['draw'],
                    'away': result['blend_probs']['away']
                }[['home', 'draw', 'away'][i]])
                fav_label = ['主胜', '平局', '客胜'][fav_idx]
                fav_odds = [match['had_h'], match['had_d'], match['had_a']][fav_idx]
                if fav_odds < MIN_ODDS:
                    reason = f'赔率过低 @{fav_odds}'
                else:
                    reason = f'混合概率不足 (ELO+市场一致{fav_label})'
            else:
                reason = 'ELO与市场方向分歧'
            
            no_signal.append({
                'homeTeam': m['homeTeam'],
                'awayTeam': m['awayTeam'],
                'market_favor': market_favor,
                'elo_favor': elo_favor,
                'max_div': max_div,
                'reason': reason,
            })
    
    # 4. 排序推荐 (按分数降序)
    recommendations.sort(key=lambda x: (-x['score'], -x['best']['ev']))
    
    # ELO排名
    elo_rank = sorted(elo.items(), key=lambda x: -x[1])
    
    # 5. 输出
    now = datetime.now()
    output = {
        'date': now.strftime('%Y-%m-%d'),
        'updateTime': now.strftime('%Y-%m-%d %H:%M:%S'),
        'totalMatches': len(matches),
        'recommendations': recommendations,
        'recommend_count': len(recommendations),
        'no_signal': len(no_signal),
        'no_signal_matches': no_signal,
        'elo_info': {
            'matches': sum(1 for _ in open(os.path.join(os.path.dirname(__file__), RESULTS_FILE), encoding='utf-8')),
            'teams': len(elo),
        },
        'elo_rankings': elo_rank,
        'strategy': f'V6 ELO({ELO_WEIGHT*100:.0f}%) + Market({MARKET_WEIGHT*100:.0f}%)',
        'thresholds': {
            'min_odds': MIN_ODDS,
            'max_odds': MAX_ODDS,
        },
    }
    
    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # 同步到前端
    sync_jc_matches(output)
    
    # 生成报告
    report = generate_report(output, [])
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 6. 打印摘要
    print(f'\n{"="*60}')
    print(f'  🏆 竞彩V6 混合分析 {output["date"]}')
    print(f'  策略: {output["strategy"]}')
    print(f'  ELO: {len(elo)}队 (基于{output["elo_info"]["matches"]}场比赛)')
    print(f'  推荐: {len(recommendations)}场 | 无信号: {len(no_signal)}场')
    print(f'{"="*60}')
    
    if recommendations:
        print(f'\n📋 推荐列表:')
        for i, r in enumerate(recommendations[:6], 1):
            best = r['best']
            div_str = f'ELO分歧{best["divergence"]:+.0f}%'
            print(f'  {i}. [{r["confidence"]}] {r["homeTeam"]} vs {r["awayTeam"]} → {best["label"]} @{best["odds"]} (EV+{best["ev"]}%, {div_str})')
    
    if no_signal:
        print(f'\n🔇 无信号比赛 ({len(no_signal)}场):')
        for ns in no_signal:
            print(f'  {ns["homeTeam"]} vs {ns["awayTeam"]}: {ns["reason"]}')
    
    print(f'\n✅ 输出: {OUTPUT_FILE}, {REPORT_FILE}')


if __name__ == "__main__":
    main()
