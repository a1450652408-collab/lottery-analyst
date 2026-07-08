"""
竞彩足球 V5 — Poisson 模型 + 价值投注扫描 + 每日报告
============================================================

改进:
  1. 泊松分布比分模型计算真实概率 (poisson_model.py)
  2. 历史比赛数据训练攻防系数 (team_data.py)
  3. 实力评分作为数据不足时的后备
  4. 每日价值投注报告输出

数据源:
  1. 竞彩网官方API: webapi.sporttery.cn (今日赔率)
  2. football-data.org (历史比赛+球队排名+阵容)
  3. 泊松模型计算赛果概率 vs 市场赔率 → 价值投注

输出:
  - jc_recommend_v5.json (扩展推荐数据)
  - jc_analysis_report.md (可读报告)
  - 数据嵌入 jc.html
"""

import requests, json, os, math, sys, re
from datetime import datetime, timedelta

# 导入泊松模型
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from poisson_model import (
        match_score_prob, top_score_probs, calc_implied_prob,
        poisson_value_bets, TeamStatsCalculator,
        strength_to_coefficients, format_score_prediction, kelly_fraction
    )
    POISSON_AVAILABLE = True
except ImportError as e:
    print(f'⚠️ Poisson模型加载失败: {e}')
    POISSON_AVAILABLE = False

# 导入队伍数据模块
try:
    from team_data import (
        fetch_and_cache_all, enrich_match_with_team_data,
        TEAM_NAME_MAP, get_team_score
    )
    TEAM_DATA_AVAILABLE = True
except ImportError:
    TEAM_DATA_AVAILABLE = False
    print('⚠️ team_data模块未加载')

BASE_URL = 'https://webapi.sporttery.cn/gateway/uniform/football'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.sporttery.cn/',
    'Origin': 'https://www.sporttery.cn'
}
OUTPUT_FILE = 'jc_recommend_v5.json'
REPORT_FILE = 'jc_report.md'

# 中文队名反转映射: 英文 -> 中文 (用于泊松模型结果匹配)
REVERSE_TEAM_MAP = {}
for cn, (_, en) in TEAM_NAME_MAP.items():
    REVERSE_TEAM_MAP[en] = cn


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
            match = {
                'matchId': sm.get('matchId'),
                'matchNum': sm.get('matchNumStr', ''),
                'league': sm.get('leagueAbbName', ''),
                'homeTeam': sm.get('homeTeamAbbName', ''),
                'awayTeam': sm.get('awayTeamAbbName', ''),
                'matchDate': sm.get('matchDate', ''),
                'matchTime': sm.get('matchTime', ''),
                'had_h': float(had_odds.get('h', 0) or 0),
                'had_d': float(had_odds.get('d', 0) or 0),
                'had_a': float(had_odds.get('a', 0) or 0),
                'hhad_goalLine': float(hhad_odds.get('goalLine', 0) or 0) if hhad_odds else 0,
                'hhad_h': float(hhad_odds.get('h', 0) or 0) if hhad_odds else 0,
                'hhad_d': float(hhad_odds.get('d', 0) or 0) if hhad_odds else 0,
                'hhad_a': float(hhad_odds.get('a', 0) or 0) if hhad_odds else 0,
            }
            result.append(match)
    return result


def get_english_name(cn_name):
    """中文队名 -> football-data.org 英文队名"""
    mapping = TEAM_NAME_MAP.get(cn_name)
    if mapping:
        return mapping[1]
    return None


def get_coefficients_from_poisson(coefficients, cn_home, cn_away):
    """
    从泊松模型系数表中查找两队系数
    返回 (home_coef, away_coef) 或 None
    """
    en_home = get_english_name(cn_home)
    en_away = get_english_name(cn_away)
    if not en_home or not en_away:
        return None

    hc = coefficients.get(en_home)
    ac = coefficients.get(en_away)
    if not hc or not ac:
        return None

    return hc, ac


def analyze_match_poisson(match, coefficients, league_avg_home, league_avg_away):
    """
    用泊松模型分析单场比赛
    返回 {home_prob, draw_prob, away_prob, value_bets, top_scores, coefficient_source}
    或 None（数据不足）
    """
    result = get_coefficients_from_poisson(coefficients, match['homeTeam'], match['awayTeam'])
    if not result:
        return None

    hc, ac = result

    # 使用主客场分离系数（如果有足够数据）
    home_attack = hc['home_attack'] if hc['matches'] >= 3 else hc['attack']
    home_defense = hc['home_defense'] if hc['matches'] >= 3 else hc['defense']
    away_attack = ac['away_attack'] if ac['matches'] >= 3 else ac['attack']
    away_defense = ac['away_defense'] if ac['matches'] >= 3 else ac['defense']

    hp, dp, ap, score_matrix = match_score_prob(
        home_attack, away_attack,
        home_defense, away_defense,
        league_avg_home, league_avg_away
    )

    had_odds = [match['had_h'], match['had_d'], match['had_a']]
    value_bets = poisson_value_bets(hp, dp, ap, had_odds)

    top_scores = top_score_probs(score_matrix, 5)

    return {
        'home_prob': hp,
        'draw_prob': dp,
        'away_prob': ap,
        'value_bets': value_bets,
        'top_scores': top_scores,
        'coef_home_attack': home_attack,
        'coef_home_defense': home_defense,
        'coef_away_attack': away_attack,
        'coef_away_defense': away_defense,
        'coef_matches': hc['matches'],
        'coef_confidence': hc['confidence'],
        'source': 'poisson_historical'
    }


def analyze_match_strength(match):
    """
    用实力评分近似泊松模型（数据不足时的后备方案）
    仅在球队有实际比赛数据时使用
    """
    had_odds = [match['had_h'], match['had_d'], match['had_a']]

    # 检查是否有真实的比赛数据（非默认值50）
    home_detail = match.get('home_detail', {})
    away_detail = match.get('away_detail', {})
    home_played = home_detail.get('played', 0) if home_detail else 0
    away_played = away_detail.get('played', 0) if away_detail else 0

    # 两侧都无比赛数据 → 无法用泊松，返回None
    if home_played == 0 and away_played == 0:
        return None

    strength_diff = match.get('strength_diff', 0)

    coefs = strength_to_coefficients(strength_diff,
                                      match.get('home_strength', 50),
                                      match.get('away_strength', 50))

    hp, dp, ap, score_matrix = match_score_prob(
        coefs['home_attack'], coefs['away_attack'],
        coefs['home_defense'], coefs['away_defense']
    )

    value_bets = poisson_value_bets(hp, dp, ap, had_odds)
    top_scores = top_score_probs(score_matrix, 3)

    return {
        'home_prob': hp,
        'draw_prob': dp,
        'away_prob': ap,
        'value_bets': value_bets,
        'top_scores': top_scores,
        'source': 'strength_estimate'
    }


def analyze_odds_only(match):
    """
    仅基于赔率的分析（无球队数据时的最终后备）
    使用V4风格的评分逻辑
    """
    had_odds = [match['had_h'], match['had_d'], match['had_a']]
    _, fair_probs, juice = calc_implied_prob(had_odds)
    if juice is None or juice > 15:
        return None

    labels = ['主胜', '平局', '客胜']
    odds = [match['had_h'], match['had_d'], match['had_a']]

    options = []
    for i in range(3):
        o = odds[i]
        fp = fair_probs[i]
        if o <= 0 or fp <= 0:
            continue

        ev = o * fp - 1
        score = max(0, 18 - juice) * 0.3  # 抽水质量
        ev_value_bonus = min(5, max(0, ev * 50)) if ev > 0 else 0
        score += ev_value_bonus

        options.append({
            'label': labels[i],
            'odds': o,
            'ev': round(ev * 100, 1),
            'score': round(score, 1),
            'market_prob': round(fp * 100, 1),
            'model_prob': round(fp * 100, 1),
            'value_gap': 0,
            'is_value': ev > 0
        })

    options.sort(key=lambda x: (-x['score'], -x['ev']))

    # 用公平概率构造伪泊松结果
    return {
        'home_prob': fair_probs[0],
        'draw_prob': fair_probs[1],
        'away_prob': fair_probs[2],
        'value_bets': options,
        'top_scores': [],
        'source': 'odds_only'
    }


def score_to_confidence(match, poisson_result):
    """
    综合泊松概率 + 阵容/状态分析 → 5级信心度
    """
    if not poisson_result:
        return '★', 0, []

    # 取最优价值投注选项
    vbs = poisson_result.get('value_bets', [])
    if not vbs:
        return '★', 0, []

    best = vbs[0]
    ev = best.get('ev', -100)
    model_prob = best.get('model_prob', 0) / 100
    gap = best.get('value_gap', 0)

    reasons = []

    # 基础分 (0~5)
    base_score = 1.0

    # 正EV加分
    if ev > 20:
        base_score += 3.0
        reasons.append(f'高价值(EV+{ev:.0f}%)')
    elif ev > 10:
        base_score += 2.0
        reasons.append(f'正价值(EV+{ev:.0f}%)')
    elif ev > 5:
        base_score += 1.5
        reasons.append(f'微价值(EV+{ev:.0f}%)')
    elif ev > 0:
        base_score += 1.0

    # 模型 vs 市场差距加分
    if gap > 15:
        base_score += 1.5
        reasons.append(f'模型看好+{gap:.0f}%')
    elif gap > 8:
        base_score += 1.0

    # 赔率合理性 (避免太低赔)
    odds = best.get('odds', 0)
    if odds < 1.20:
        base_score -= 1.0
        reasons.append('赔率过低')
    elif odds > 10:
        base_score -= 0.5

    # 数据源置信度修正
    if poisson_result.get('source') == 'poisson_historical':
        conf = poisson_result.get('coef_confidence', 'none')
        if conf == 'high':
            base_score += 1.0
        elif conf == 'medium':
            base_score += 0.5
    else:
        base_score -= 0.5  # 实力估算折价

    # 阵容分析
    if match.get('home_avg_age', 0) and match.get('away_avg_age', 0):
        age_diff = abs(match.get('home_avg_age', 0) - match.get('away_avg_age', 0))
        if age_diff > 3 and best['label'] == '主胜':
            if match.get('home_avg_age', 0) < match.get('away_avg_age', 0):
                base_score += 0.5
                reasons.append('均龄年轻')

    # 状态分析（连胜/连败）
    home_form = match.get('home_form', '')
    away_form = match.get('away_form', '')
    if home_form and away_form:
        if best['label'] == '主胜' and home_form.endswith('WW'):
            base_score += 0.5
        elif best['label'] == '客胜' and away_form.endswith('WW'):
            base_score += 0.5

    # 信心映射
    if base_score >= 5.5:
        confidence = '★★★★★'
    elif base_score >= 4.0:
        confidence = '★★★★'
    elif base_score >= 2.5:
        confidence = '★★★'
    elif base_score >= 1.0:
        confidence = '★★'
    else:
        confidence = '★'

    return confidence, round(base_score, 1), reasons


def generate_report(output, matches_scored):
    """生成可读的价值投注报告"""
    now = datetime.now()
    lines = [
        f"# 竞彩价值投注报告 ({output['date']})",
        f"",
        f"> 生成时间: {output['updateTime']}",
        f"> 数据源: 竞彩网赔率 + football-data.org 球队数据 + 泊松比分模型",
        f"> 本报告仅供参考，不构成投注建议",
        f"",
        f"---",
        f"",
        f"## 今日概览",
        f"",
        f"- 今日共 {output['totalMatches']} 场比赛",
        f"- 正价值（正EV）场次: {output['posEvCount']} 场",
        f"- 价值投注选项: {output['valueBetCount']} 个",
        f"",
        f"---",
        f"",
    ]

    # 价值投注列表
    value_bets = output.get('valueBets', [])
    if value_bets:
        lines.extend([
            f"## 💰 价值投注 (正EV)",
            f"",
            f"| 比赛 | 推荐 | 赔率 | 模型概率 | 市场概率 | EV | 价值差 |",
            f"|:---|:---:|:---:|:---:|:---:|:---:|:---:|",
        ])
        for vb in value_bets:
            lines.append(
                f"| {vb['homeTeam']} vs {vb['awayTeam']} "
                f"| {vb['recommend']} "
                f"| {vb['odds']} "
                f"| {vb.get('fair_prob', '?')}% "
                f"| {vb.get('market_prob', '?')}% "
                f"| +{vb['ev']}% "
                f"| +{vb.get('value_gap', '?')}% |"
            )
        lines.append("")
    else:
        lines.append("## 💰 价值投注\n\n⚠️ 今日无正EV选项\n")

    # 全部推荐
    lines.extend([
        f"## 📋 推荐列表",
        f"",
        f"| 信心 | 联赛 | 主队 | 客队 | 推荐 | 赔率 | EV | 理由 |",
        f"|:---:|:---|:---|:---|:---:|:---:|:---:|:---|",
    ])
    for r in output.get('recommendations', []):
        ev_str = f"+{r['ev']}%" if r.get('ev', 0) > 0 else f"{r['ev']}%"
        reasons = ', '.join(r.get('reasons', []) or ['—'])
        lines.append(
            f"| {r.get('confidence', '★')} "
            f"| {r.get('league', '')} "
            f"| {r['homeTeam']} "
            f"| {r['awayTeam']} "
            f"| {r.get('recommend', '?')} "
            f"| {r.get('best_odds', '?')} "
            f"| {ev_str} "
            f"| {reasons} |"
        )
    lines.append("")

    # 比分预测
    if output.get('score_predictions'):
        lines.append(f"## ⚽ 比分预测（泊松模型）\n")
        for sp in output['score_predictions']:
            lines.append(f"### {sp['homeTeam']} vs {sp['awayTeam']}")
            lines.append(f"- 赛果概率: 主胜{sp['homeProb']}% / 平{sp['drawProb']}% / 客胜{sp['awayProb']}%")
            if sp.get('topScores'):
                scores_str = ', '.join([f"{s[0]}({s[1]}%)" for s in sp['topScores'][:3]])
                lines.append(f"- 最可能比分: {scores_str}")
            if sp.get('valueBets'):
                best_val = sp['valueBets'][0]
                if best_val.get('is_value'):
                    lines.append(f"- 💰 价值投注: {best_val['label']} @{best_val['odds']} (EV+{best_val['ev']}%)")
            lines.append("")

    # 2串1推荐
    s2 = output.get('s2recommend')
    if s2:
        lines.extend([
            f"## 🔗 2串1推荐",
            f"",
            f"- 第1场: {s2.get('match1')} → {s2.get('match1_rec')} (EV {s2.get('match1_ev')})",
            f"- 第2场: {s2.get('match2')} → {s2.get('match2_rec')} (EV {s2.get('match2_ev')})",
            f"- 组合赔率: {s2.get('combined_odds')}",
            f"- 备注: {s2.get('note', '')}",
            f"",
        ])

    # 凯利建议
    if value_bets and value_bets[0].get('kelly_advice'):
        ka = value_bets[0]['kelly_advice']
        lines.append(f"## 💳 凯利资金管理建议")
        lines.append(f"")
        lines.append(f"- 推荐本金: ¥{ka.get('bankroll_ref', 100000):,}")
        lines.append(f"- 建议单注: ¥{ka.get('suggest_stake', 0)} ({ka.get('kelly_pct', 0)}%)")
        lines.append(f"- {ka.get('note', '')}")
        lines.append(f"")

    # 风险提示
    lines.extend([
        f"---",
        f"",
        f"## ⚠️ 风险提示",
        f"",
        f"1. 泊松模型基于历史数据，世界杯初期数据量有限，系数置信度偏低",
        f"2. 正EV不代表单次必赢，长期坚持才有统计优势",
        f"3. 建议使用凯利公式（1/4凯利）控制注码",
        f"4. 不要追逐损失，设定每日止损",
        f"5. 本报告仅供参考，请理性投注",
        f"",
        f"---",
        f"",
        f"*报告由 V5 泊松模型自动生成，仅用于学习研究*",
    ])

    return '\n'.join(lines)


def main():
    print(f'[{datetime.now().strftime("%H:%M:%S")}] === 竞彩V5泊松模型分析 ===')
    
    # ===== 第1步：获取球队基本面数据 =====
    poisson_coefficients = None
    league_avg_home = 1.5
    league_avg_away = 1.2
    standings_data = None
    team_scores_data = None
    team_squads_data = None

    if TEAM_DATA_AVAILABLE and POISSON_AVAILABLE:
        print('[球队数据] 获取football-data.org数据...')
        result_all = fetch_and_cache_all()
        standings_data, team_scores_data, team_squads_data, wc_matches = result_all

        if wc_matches:
            print(f'[泊松模型] 训练攻防系数 ({len(wc_matches)}场比赛)...')
            calculator = TeamStatsCalculator(wc_matches)
            poisson_coefficients, league_avg_home, league_avg_away = calculator.analyze()
            print(f'[泊松模型] 计算了 {len(poisson_coefficients)} 支球队的攻防系数')
            if poisson_coefficients:
                teams_with_data = sum(1 for c in poisson_coefficients.values() if c['matches'] > 0)
                print(f'[泊松模型] 其中 {teams_with_data} 队有实际比赛数据')
        
        # 后备：加载本地训练的泊松模型 (来自 jc_results.json 24场赛果训练)
        if not poisson_coefficients:
            trained_path = os.path.join(os.path.dirname(__file__), 'data', 'poisson_trained.json')
            if os.path.exists(trained_path):
                try:
                    with open(trained_path, encoding='utf-8') as f:
                        trained = json.load(f)
                    poisson_coefficients = trained.get('coefficients', {})
                    league_avg_home = trained.get('league_avg_home', 1.5)
                    league_avg_away = trained.get('league_avg_away', 1.2)
                    total_teams = len(poisson_coefficients)
                    trained_at = trained.get('trained_at', '?')
                    print(f'[泊松模型] ✅ 加载本地训练模型 ({total_teams}队, {trained.get("total_matches",0)}场, 训练于{trained_at[:10]})')
                except Exception as e:
                    print(f'[泊松模型] ⚠️ 加载本地模型失败: {e}')
        
        if not poisson_coefficients:
            print('[泊松模型] ⚠️ 无历史比赛数据，将使用实力评分近似')
    else:
        print('[数据] 使用独立赔率分析模式')
        if not POISSON_AVAILABLE:
            print('  ↳ Poisson模型不可用')
        if not TEAM_DATA_AVAILABLE:
            print('  ↳ team_data模块不可用')

    # ===== 第2步：获取今日竞彩比赛 =====
    matches = fetch_today_matches()
    if not matches:
        print('❌ 今日无比赛')
        return
    print(f'✅ 获取到 {len(matches)} 场比赛')

    # ===== 第3步：融合球队数据 =====
    enriched = []
    for m in matches:
        team_data_added = False
        if TEAM_DATA_AVAILABLE and standings_data and team_scores_data:
            try:
                m_with = enrich_match_with_team_data(m, standings_data, team_scores_data, team_squads_data)
                enriched.append(m_with)
                team_data_added = True
            except:
                pass
        if not team_data_added:
            enriched.append(m)

    # ===== 第4步：泊松分析每场比赛 =====
    scored = []
    score_predictions = []

    for m in enriched:
        poisson_result = None

        # 优先使用泊松历史系数
        if poisson_coefficients:
            poisson_result = analyze_match_poisson(m, poisson_coefficients,
                                                    league_avg_home, league_avg_away)

        # 后备：实力评分近似（需球队有实际比赛数据）
        if not poisson_result:
            poisson_result = analyze_match_strength(m)

        # 最终后备：用V4赔率分析（仅基于赔率，不依赖球队数据）
        if not poisson_result:
            poisson_result = analyze_odds_only(m)

        if not poisson_result:
            continue

        had_odds = [m['had_h'], m['had_d'], m['had_a']]
        _, fair_probs, juice = calc_implied_prob(had_odds)

        value_bets = poisson_result.get('value_bets', [])
        if not value_bets:
            continue

        best = value_bets[0]
        confidence, final_score, reasons = score_to_confidence(m, poisson_result)

        # 评分归一化 (兼容旧版前端)
        m['recommend'] = best['label']
        m['best_odds'] = best['odds']
        m['best_value'] = round((best['odds'] * (best['model_prob'] / 100) - 1) * 100 + juice, 1)
        m['ev'] = best['ev']
        m['score'] = final_score
        m['confidence'] = confidence
        m['reasons'] = reasons
        m['poisson_source'] = poisson_result.get('source', 'unknown')
        m['home_prob'] = round(poisson_result['home_prob'] * 100, 1)
        m['draw_prob'] = round(poisson_result['draw_prob'] * 100, 1)
        m['away_prob'] = round(poisson_result['away_prob'] * 100, 1)

        # 价值投注
        all_options = []
        for vb in value_bets[:3]:
            all_options.append({
                'label': vb['label'],
                'odds': vb['odds'],
                'model_prob': vb['model_prob'],
                'market_prob': vb['market_prob'],
                'value_gap': vb['value_gap'],
                'ev': vb['ev'],
                'is_value': vb.get('is_value', False)
            })
        m['all_options'] = all_options

        # 凯利建议
        if best['ev'] > 0:
            kelly_pct = kelly_fraction(best['odds'], best['model_prob'] / 100)
            suggest_stake = round(100000 * kelly_pct)
            m['kelly_advice'] = {
                'suggest_stake': suggest_stake,
                'kelly_pct': round(kelly_pct * 100, 1),
                'bankroll_ref': 100000,
                'note': f'1/4凯利建议投{suggest_stake}元' if suggest_stake > 0 else '不建议投注'
            }
        else:
            m['kelly_advice'] = {
                'suggest_stake': 0, 'kelly_pct': 0,
                'note': '无正EV，不建议投注'
            }

        # 比分预测信息（用于报告）
        score_predictions.append({
            'homeTeam': m['homeTeam'],
            'awayTeam': m['awayTeam'],
            'homeProb': round(poisson_result['home_prob'] * 100, 1),
            'drawProb': round(poisson_result['draw_prob'] * 100, 1),
            'awayProb': round(poisson_result['away_prob'] * 100, 1),
            'topScores': poisson_result.get('top_scores', []),
            'valueBets': value_bets
        })

        scored.append(m)

    print(f'📊 有效评分 {len(scored)} 场')

    # ===== 第5步：排序推荐 =====
    pos_ev = [m for m in scored if m.get('ev', 0) > 0]
    neg_ev = [m for m in scored if m.get('ev', 0) <= 0]
    pos_ev.sort(key=lambda x: (-x['score'], -x.get('ev', 0)))
    neg_ev.sort(key=lambda x: (-x['score'], -x.get('ev', 0)))
    recommends = (pos_ev + neg_ev)[:6]

    # 价值投注列表
    value_bets_list = []
    for m in scored:
        for opt in m.get('all_options', []):
            if opt.get('is_value'):
                value_bets_list.append({
                    'league': m.get('league', ''),
                    'matchNum': m.get('matchNum', ''),
                    'homeTeam': m['homeTeam'],
                    'awayTeam': m['awayTeam'],
                    'recommend': opt['label'],
                    'odds': opt['odds'],
                    'ev': opt['ev'],
                    'market_prob': opt['market_prob'],
                    'fair_prob': opt['model_prob'],
                    'value_gap': opt['value_gap'],
                    'reasons': m.get('reasons', []),
                    'kelly_advice': m.get('kelly_advice', {}),
                })
    value_bets_list.sort(key=lambda x: -x['ev'])

    # 2串1推荐（简化版，与V4相同逻辑）
    s2rec = None
    s2pool = [r for r in recommends if r.get('ev', 0) > 0 and 1.50 <= r.get('best_odds', 0) <= 4.00]
    if len(s2pool) >= 2:
        s2pool.sort(key=lambda x: -x['ev'])
        m1, m2 = s2pool[0], s2pool[1]
        s2rec = {
            'match1': f'{m1["homeTeam"]} vs {m1["awayTeam"]}',
            'match1_rec': f'{m1["recommend"]} @{m1["best_odds"]}',
            'match1_ev': f'+{m1["ev"]}%',
            'match2': f'{m2["homeTeam"]} vs {m2["awayTeam"]}',
            'match2_rec': f'{m2["recommend"]} @{m2["best_odds"]}',
            'match2_ev': f'+{m2["ev"]}%',
            'combined_odds': round(m1['best_odds'] * m2['best_odds'], 2),
        }

    # ===== 第6步：构建输出 =====
    output = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'updateTime': datetime.now().strftime('%H:%M'),
        'modelVersion': 'V5 (Poisson + 泊松模型)',
        'totalMatches': len(matches),
        'topRecommend': recommends[0] if recommends else None,
        'recommendations': recommends[:6],
        's2recommend': s2rec,
        'valueBets': value_bets_list,
        'scorePredictions': score_predictions[:5],  # 前5场比分预测
        'posEvCount': len(pos_ev),
        'valueBetCount': len(value_bets_list),
        'poissonDataAvailable': bool(poisson_coefficients),
        'dataSource': {
            'odds': 'webapi.sporttery.cn',
            'teamData': 'api.football-data.org (排名+阵容+比赛)',
            'model': 'Poisson Distribution (泊松分布)',
            'poissonTeams': len(poisson_coefficients) if poisson_coefficients else 0,
        }
    }

    # ===== 第7步：打印输出 =====
    print(f'\n{"=" * 60}')
    print(f'  🏆 竞彩V5推荐 {output["date"]}')
    print(f'  {output["modelVersion"]}')
    print(f'{"=" * 60}')

    if recommends:
        r = recommends[0]
        ev_str = f' (EV+{r["ev"]}%)' if r.get('ev', 0) > 0 else ''
        print(f'\n今日精选: {r["league"]} {r["homeTeam"]} vs {r["awayTeam"]}')
        print(f'  推荐: {r["recommend"]} @ {r["best_odds"]}{ev_str}')
        print(f'  信心: {r["confidence"]}  |  评分: {r["score"]}')
        print(f'  赛果概率: 主胜{r.get("home_prob","?")}% / 平{r.get("draw_prob","?")}% / 客胜{r.get("away_prob","?")}%')
        if r.get('reasons'):
            print(f'  理由: {", ".join(r["reasons"])}')
        if r.get('all_options'):
            print(f'  价值分析:')
            for opt in r['all_options'][:3]:
                tag = '💰' if opt.get('is_value') else '  '
                print(f'    {tag} {opt["label"]} 模型{opt["model_prob"]}% vs 市场{opt["market_prob"]}% (EV{opt["ev"]}%)')

    print(f'\n📊 推荐列表（正EV {len(pos_ev)}场）:')
    for r in recommends[:6]:
        ev_str = f' (EV+{r["ev"]}%)' if r.get('ev', 0) > 0 else ''
        print(f'  {r["confidence"]} {r["league"]:8s} {r["homeTeam"]} vs {r["awayTeam"]} → {r["recommend"]} @{r["best_odds"]}{ev_str}')

    if value_bets_list:
        print(f'\n💰 价值投注 ({len(value_bets_list)}个):')
        for vb in value_bets_list[:5]:
            print(f'  {vb["homeTeam"]} vs {vb["awayTeam"]}: {vb["recommend"]} @{vb["odds"]} (EV+{vb["ev"]}%, '
                  f'模型{vb["fair_prob"]}% > 市场{vb["market_prob"]}%)')

    if poisson_coefficients:
        data_teams = sum(1 for c in poisson_coefficients.values() if c['matches'] >= 1)
        print(f'\n📈 泊松模型: {data_teams}/{len(poisson_coefficients)}支球队有比赛数据')

    # ===== 第8步：保存输出 =====
    # JSON (V5版本)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\n✅ 推荐已保存至 {OUTPUT_FILE}')

    # 兼容旧版：也输出到 jc_recommend.json（网站前端 fetch 这个文件）
    legacy_file = 'jc_recommend.json'
    with open(legacy_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'✅ 兼容输出: {legacy_file}')

    # 同步到 data/jc_matches.json（前端 jc.html 的 fetch 目标）
    os.makedirs('data', exist_ok=True)
    jc_matches_path = 'data/jc_matches.json'
    jc_matches = []
    for m in matches:
        jc_matches.append({
            'match': m.get('matchNum', ''),
            'home': m.get('homeTeam', ''),
            'away': m.get('awayTeam', ''),
            'date': m.get('matchDate', ''),
            'time': m.get('matchTime', ''),
            'gl': float(m.get('hhad_goalLine', 0)),
            'had': [float(m.get('had_h', 0)), float(m.get('had_d', 0)), float(m.get('had_a', 0))],
            'hhad': [float(m.get('hhad_h', 0)), float(m.get('hhad_d', 0)), float(m.get('hhad_a', 0))],
        })
    with open(jc_matches_path, 'w', encoding='utf-8') as f:
        json.dump(jc_matches, f, ensure_ascii=False, indent=2)
    print(f'✅ 前端数据已同步至 {jc_matches_path}')

    # Markdown报告
    report = generate_report(output, scored)
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f'✅ 报告已保存至 {REPORT_FILE}')

    # 嵌入jc.html
    jc_path = 'jc.html'
    if os.path.exists(jc_path):
        with open(jc_path, 'r', encoding='utf-8') as f:
            jc_html = f.read()
        json_str = json.dumps(output, ensure_ascii=False)
        pattern = r'var JC_DATA = \{.*?\};'
        replacement = 'var JC_DATA = ' + json_str + ';'
        if re.search(pattern, jc_html, re.DOTALL):
            jc_html = re.sub(pattern, replacement, jc_html, flags=re.DOTALL)
            with open(jc_path, 'w', encoding='utf-8') as f:
                f.write(jc_html)
            print(f'✅ 数据已嵌入 {jc_path}')
        else:
            print('⚠️ jc.html中未找到JC_DATA占位')

    return output


if __name__ == '__main__':
    main()
