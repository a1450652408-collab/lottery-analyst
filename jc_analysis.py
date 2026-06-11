"""
竞彩足球价值分析 & 每日推荐 (V4 - 无偏见价值评分 + 凯利公式)
数据源:
  1. 竞彩网官方API webapi.sporttery.cn (赔率/比赛)
  2. football-data.org (队伍排名/实力) — API Key: 1163986726a345ffb7093db9e34a5e3f
输出: 推荐结果JSON + 内嵌数据到jc.html

V4改进:
  - 去掉主胜偏见，三个赛果平等竞争
  - 让球盘(HHAD)用于修正推荐方向，不仅做加减分
  - 增加5级信心度（基于期望价值EV）
  - 集成凯利公式资金管理建议
  - 优化串联组合策略
"""
import requests, json, os, math, re
from datetime import datetime, timedelta

# 导入队伍数据模块
try:
    from team_data import fetch_and_cache_all, enrich_match_with_team_data, TEAM_NAME_MAP, get_team_score
    TEAM_DATA_AVAILABLE = True
except ImportError:
    TEAM_DATA_AVAILABLE = False
    print('⚠️ team_data模块未加载，队伍基本面数据不可用')

BASE_URL = 'https://webapi.sporttery.cn/gateway/uniform/football'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.sporttery.cn/',
    'Origin': 'https://www.sporttery.cn'
}
OUTPUT_FILE = 'jc_recommend.json'


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
        date_label = group.get('businessDate', '')
        for sm in group.get('subMatchList', []):
            # 提取胜平负赔率 (poolCode=HAD)
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
                'status': sm.get('matchStatus', ''),
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


def calc_implied_prob(odds):
    """计算隐含概率和抽水"""
    if any(o <= 0 for o in odds):
        return 0, 0, 0
    probs = [1/o for o in odds]
    total = sum(probs)
    fair_probs = [p/total for p in probs]
    juice = (total - 1) * 100
    return probs, fair_probs, juice


def evaluate_three_outcomes(match):
    """
    V5 优化版: 让球盘连续评分 + 平局检测 + 赔率区间细分

    核心改进:
    1. 让球盘连续分（非二元阈值）— HHAD概率×权重
    2. 平局均衡检测 — HHAD三态接近时提升平局
    3. 赔率区间细分 — 1.10-1.30/1.30-1.60/1.60-1.80 不同权重
    4. 剔除伪价值信号
    5. 不偏袒任意方向
    """
    had = [match['had_h'], match['had_d'], match['had_a']]
    _, fair_probs, juice = calc_implied_prob(had)

    if not any(had) or juice > 15:
        return None

    labels = ['主胜', '平局', '客胜']
    odds = [match['had_h'], match['had_d'], match['had_a']]

    # ===== 让球盘分析 —— 连续信号 =====
    hhad_fair = None   # [h, d, a] fair probs from HHAD
    hhad_raw = None    # raw implied probs
    hhad_juice = 0
    hhad_home_ratio = 0.33  # HHAD_H占HHAD总概率的比例（≈1/3默认）
    hhad_away_ratio = 0.33
    hhad_draw_ratio = 0.33
    hhad_balance = 0.0   # 让球盘均衡度 0~1, 1=完全均衡
    hhad_home_margin = 0.0  # 主胜优势（正=主队强，负=客队强）

    if match.get('hhad_h', 0) > 0 and match.get('hhad_a', 0) > 0:
        hhad_raw, hhad_fair, hhad_juice = calc_implied_prob([
            match['hhad_h'], match['hhad_d'], match['hhad_a']
        ])
        hhad_home_ratio = hhad_fair[0]
        hhad_away_ratio = hhad_fair[2]
        hhad_draw_ratio = hhad_fair[1]

        # 主胜优势 = HHAD_H - HHAD_A（正值=主队+让球盘更强）
        hhad_home_margin = hhad_home_ratio - hhad_away_ratio

        # 均衡度: HHAD三个概率的均匀度
        # 0=极度不均衡（一边倒），1=完全均衡（33%/33%/33%）
        hhad_balance = 1.0 - (
            abs(hhad_home_ratio - 1/3) +
            abs(hhad_draw_ratio - 1/3) +
            abs(hhad_away_ratio - 1/3)
        ) / (4/3)  # 归一化到 0~1
        hhad_balance = max(0, min(1, hhad_balance))

    # ===== 阵容深度评分（基于football-data.org数据）=====
    squad_home_score = 0
    squad_away_score = 0
    squad_insights = []
    home_coach = match.get('home_coach', '—')
    away_coach = match.get('away_coach', '—')

    # 年龄分析
    ha = match.get('home_avg_age', 0)
    aa = match.get('away_avg_age', 0)
    if ha and aa:
        def _ab(a): d=abs(a-26.5); return 1.5 if d<=1.5 else 0.5 if d<=3 else -0.5
        hb, abm = _ab(ha), _ab(aa)
        squad_home_score += hb; squad_away_score += abm
        if abs(ha-aa) > 1.5:
            o = 'home' if ha > aa else 'away'
            squad_insights.append(f'均龄{ha if o=="home" else aa}岁')

    # 教练名气
    _elite = {'Lionel Scaloni','Carlo Ancelotti','Thomas Tuchel','Julian Nagelsmann',
              'Ronald Koeman','Mauricio Pochettino','Didier Deschamps','Marcelo Bielsa'}
    if home_coach in _elite: squad_home_score += 2; squad_insights.append(f'教练{home_coach}')
    if away_coach in _elite: squad_away_score += 2; squad_insights.append(f'教练{away_coach}')

    squad_net = round(squad_home_score - squad_away_score, 1)

    # ===== 三选项评分 =====
    options = []
    for i in range(3):
        o = odds[i]
        fp = fair_probs[i]
        if o <= 0 or fp <= 0:
            continue

        ev = o * fp - 1

        score = 0.0
        reasons = []

        # 1. 抽水质量（低抽水=可信度更高，上限3分）
        score += max(0, 18 - juice) * 0.5  # juice≈13% → +2.5分

        # 2. 让球盘连续评分（核心信号，上限15分）
        if hhad_fair:
            if labels[i] == '主胜':
                # HHAD主队概率×20 + 对冲缓和×3
                base = hhad_home_ratio * 18
                if hhad_home_ratio > 0.45:
                    base += 3  # 超过45%额外奖励
                score += base
                reasons.append(f'让球{hhad_home_ratio:.0%}')
            elif labels[i] == '客胜':
                base = hhad_away_ratio * 18
                if hhad_away_ratio > 0.45:
                    base += 3
                score += base
                reasons.append(f'让球客{hhad_away_ratio:.0%}')
            elif labels[i] == '平局':
                # 平局得分来自均衡度: 均衡时≈7分，不均衡时≈2分
                draw_score = hhad_balance * 7 + 2
                if hhad_home_margin > -0.20 and hhad_home_margin < 0.20:
                    # 主客接近时额外加分
                    draw_score += (1 - abs(hhad_home_margin) / 0.20) * 3
                score += draw_score
                if hhad_balance > 0.6:
                    reasons.append('让球均衡')

        # 3. 赔率区间细分（基于历史分布）
        if labels[i] == '主胜':
            if 1.10 <= o < 1.30:
                bonus = 5
                reasons.append('主胜极低赔')
            elif 1.30 <= o < 1.60:
                bonus = 4
                reasons.append('主胜低赔')
            elif 1.60 <= o < 1.80:
                bonus = 3
                reasons.append('主胜中低赔')
            elif 1.80 <= o < 2.50:
                bonus = 2  # 中赔主胜，有一定风险
            elif 2.50 <= o < 4.00:
                bonus = 1  # 高赔主胜，可博
            else:
                bonus = 0
            score += bonus

        elif labels[i] == '客胜':
            if o < 1.60:
                bonus = 4
                reasons.append('客胜低赔')
            elif 1.60 <= o < 2.50:
                bonus = 3
                reasons.append('客胜中赔')
            elif 2.50 <= o < 4.00:
                bonus = 1
            else:
                bonus = 0
            score += bonus

        elif labels[i] == '平局':
            if 2.80 <= o <= 3.60:
                bonus = 3
            elif 3.60 < o <= 5.00:
                bonus = 1
            else:
                bonus = 0
            score += bonus

        # 4. 队伍实力（当有真实数据时，上限8分）
        if match.get('home_detail', {}).get('has_data'):
            strength_diff = match.get('strength_diff', 0)
            if labels[i] == '主胜' and strength_diff > 0:
                bonus = min(8, strength_diff * 0.15)
                score += bonus
                reasons.append(f'实力+{bonus:.0f}')
            elif labels[i] == '客胜' and strength_diff < 0:
                bonus = min(8, abs(strength_diff) * 0.15)
                score += bonus
                reasons.append(f'实力+{bonus:.0f}')
            elif labels[i] == '平局' and abs(strength_diff) < 5:
                bonus = 3
                score += bonus
                reasons.append('实力接近')

        # 4. 阵容深度评分（结合球队阵容数据进行调整）
        # 基于年龄、教练实力等因子，方向性影响（不改变推荐方向，只微调分数）
        if squad_net != 0:
            if labels[i] == '主胜' and squad_net > 0:
                bonus = min(4, squad_net * 1.5)
                score += bonus
                if squad_insights:
                    reasons.extend(squad_insights[:2])
            elif labels[i] == '客胜' and squad_net < 0:
                bonus = min(4, abs(squad_net) * 1.5)
                score += bonus
                if squad_insights:
                    reasons.extend(squad_insights[:2])
            elif labels[i] == '平局' and abs(squad_net) < 1:
                score += 1  # 实力接近

        options.append({
            'label': labels[i],
            'odds': o,
            'value_pct': round(ev * 100 + juice, 1),
            'ev': round(ev * 100, 1),
            'score': round(score, 1),
            'reasons': reasons,
        })

    if not options:
        return None

    # 评分降序，评分相同用让球盘优势幅度排序
    def sort_key(x):
        idx = labels.index(x['label'])
        # 第二排序: 让球盘优势幅度匹配
        if hhad_home_margin > 0.10 and x['label'] == '主胜':
            second = 1.0
        elif hhad_home_margin < -0.10 and x['label'] == '客胜':
            second = 1.0
        else:
            second = 0.0
        return (-x['score'], -second)

    options.sort(key=sort_key)
    return options
    return options


def kelly_fraction(odds, estimated_prob, bankroll_pct=0.25):
    """
    凯利公式：f* = (p × b - q) / b
    b = odds - 1 (净赔率)
    p = 估计概率（公平概率）
    q = 1 - p
    使用 1/4 凯利降低风险
    """
    b = odds - 1
    if b <= 0:
        return 0
    p = estimated_prob
    q = 1 - p
    f = (p * b - q) / b
    return max(0, f * bankroll_pct)


def convert_to_confidence(options, match):
    """
    V5 优化版: 基于评分 + 让球盘优势幅度 + 赔率区间
    产生有区分度的5级信心
    """
    if not options:
        return None, None, None, None

    best = options[0]
    label = best['label']
    odds = best['odds']
    score = best['score']
    ev = best['ev']

    # 置信度评分 (0~9)
    conf_score = 0.0

    # 1. 评分：与让球盘优势幅度对应
    if score >= 16:
        conf_score += 3.0
    elif score >= 12:
        conf_score += 2.0
    elif score >= 8:
        conf_score += 1.0

    # 2. 赔率可博弈性
    if odds < 1.15:
        conf_score -= 2.0  # 极度低赔无价值
    elif odds < 1.25:
        conf_score -= 1.0
    elif odds <= 4.00:
        conf_score += 0.5
    elif odds > 8.00:
        conf_score -= 1.0  # 超高赔博冷减信心

    # 3. 正EV加分（冷门有正EV说明真有机会）
    if ev > 10:
        conf_score += 2.0
    elif ev > 5:
        conf_score += 1.5
    elif ev > 0:
        conf_score += 1.0
    elif ev <= -10:
        conf_score -= 0.5  # 高抽水比赛减一点信心

    # 4. 标注是否正EV
    has_pos_ev = ev > 0

    # 5级信心映射（带小数支持区分）
    if conf_score >= 4.5:
        confidence = '★★★★★'
    elif conf_score >= 3.0:
        confidence = '★★★★'
    elif conf_score >= 1.5:
        confidence = '★★★'
    elif conf_score >= 0:
        confidence = '★★'
    else:
        confidence = '★'

    # 凯利建议（使用公平概率而非隐含概率）
    bankroll = 100000
    had = [match['had_h'], match['had_d'], match['had_a']]
    _, fair_probs, _ = calc_implied_prob(had)
    idx = ['主胜', '平局', '客胜'].index(label)
    fair_prob = fair_probs[idx] if idx < len(fair_probs) else (1 / odds)

    kelly_pct = kelly_fraction(odds, fair_prob)
    suggest_stake = round(bankroll * kelly_pct)

    if ev <= 0:
        kelly_pct = 0
        suggest_stake = 0

    kelly_advice = {
        'suggest_stake': suggest_stake,
        'kelly_pct': round(kelly_pct * 100, 1),
        'bankroll_ref': bankroll,
        'note': ''
    }
    if suggest_stake > 0:
        kelly_advice['note'] = f'1/4凯利建议投{suggest_stake}元（{kelly_pct*100:.1f}%本金）'
    else:
        kelly_advice['note'] = '无正EV，不建议投注'

    return confidence, kelly_advice, score, ev


def main():
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 开始抓取竞彩数据...')
    
    # ===== 第1步：获取队伍基本面数据（football-data.org）=====
    standings_data = None
    team_scores_data = None
    team_squads_data = None
    if TEAM_DATA_AVAILABLE:
        print('[球队数据] 获取football-data.org队伍排名+阵容...')
        result = fetch_and_cache_all()
        if len(result) == 3:
            standings_data, team_scores_data, team_squads_data = result
        else:
            standings_data, team_scores_data = result
            team_squads_data = None
        
        if standings_data:
            played_teams = sum(1 for s in standings_data.values() if s['playedGames'] > 0)
            squad_count = len(team_squads_data) if team_squads_data else 0
            print(f'[球队数据] ✅ {len(standings_data)}队排名 + {squad_count}队阵容 ({played_teams}队有比赛数据)')
            if played_teams == 0:
                print('[球队数据] ℹ️ 世界杯6月11日开赛，比赛开始后自动生成实力评分')
        else:
            print('[球队数据] ⚠️ 队伍数据获取失败，将只用赔率分析')
    else:
        print('[球队数据] ⚠️ team_data模块未加载')
    
    # ===== 第2步：获取竞彩比赛+赔率（sporttery.cn）=====
    matches = fetch_today_matches()
    if not matches:
        print('❌ 今日无比赛或数据获取失败')
        return
    
    print(f'✅ 获取到 {len(matches)} 场比赛')
    
    # ===== 第3步：融合数据：给每场比赛加上队伍实力评分 =====
    enriched = []
    for m in matches:
        team_data_added = False
        if TEAM_DATA_AVAILABLE and standings_data and team_scores_data:
            try:
                m_with_team = enrich_match_with_team_data(m, standings_data, team_scores_data, team_squads_data)
                enriched.append(m_with_team)
                team_data_added = True
            except:
                pass
        if not team_data_added:
            enriched.append(m)
    
    # ===== 第4步：三选项无偏见评分 =====
    scored = []
    for m in enriched:
        options = evaluate_three_outcomes(m)
        if options:
            confidence, kelly_advice, final_score, ev = convert_to_confidence(options, m)
            best = options[0]
            m['recommend'] = best['label']
            m['best_odds'] = best['odds']
            m['best_value'] = best['value_pct']
            m['score'] = final_score
            m['ev'] = ev
            m['confidence'] = confidence
            m['kelly_advice'] = kelly_advice
            m['reasons'] = best['reasons']
            # 保留所有选项信息
            m['all_options'] = options[:3]
            # 队伍基本面数据
            m['home_strength'] = m.get('home_strength')
            m['away_strength'] = m.get('away_strength')
            m['home_group'] = m.get('home_detail', {}).get('group')
            m['away_group'] = m.get('away_detail', {}).get('group')
            scored.append(m)
    
    print(f'📊 有效评分 {len(scored)} 场')
    
    # ===== 第5步：推荐排序 =====
    # 优先正EV，再按评分排序
    pos_ev = [m for m in scored if m.get('ev', 0) > 0]
    neg_ev = [m for m in scored if m.get('ev', 0) <= 0]
    pos_ev.sort(key=lambda x: (-x['score'], -x.get('best_odds', 0)))
    neg_ev.sort(key=lambda x: (-x['score'], -x.get('best_odds', 0)))
    recommends = (pos_ev + neg_ev)[:6]
    
    # 2串1推荐（优先正EV + 尽量不同联赛）
    s2pool_pos = [r for r in recommends if r.get('ev', 0) > 0 and 1.80 <= r.get('best_odds', 0) <= 4.00]
    s2pool_all = [r for r in recommends if 1.50 <= r.get('best_odds', 0) <= 4.00]
    s2rec = None
    if len(s2pool_pos) >= 2:
        s2pool_pos.sort(key=lambda x: -x['ev'])
        m1, m2 = s2pool_pos[0], s2pool_pos[1]
        s2odds = round(m1['best_odds'] * m2['best_odds'], 2)
        s2rec = {
            'match1': f'{m1["homeTeam"]} vs {m1["awayTeam"]}',
            'match1_rec': f'{m1["recommend"]} @{m1["best_odds"]}',
            'match1_ev': f'{m1["ev"]}%',
            'match2': f'{m2["homeTeam"]} vs {m2["awayTeam"]}',
            'match2_rec': f'{m2["recommend"]} @{m2["best_odds"]}',
            'match2_ev': f'{m2["ev"]}%',
            'combined_odds': s2odds,
            'note': '两场均有正EV，均注可期'
        }
        print(f'\n🔗 2串1推荐: {m1["homeTeam"]} {m1["recommend"]} @{m1["best_odds"]}(EV+{m1["ev"]}%) × {m2["homeTeam"]} {m2["recommend"]} @{m2["best_odds"]}(EV+{m2["ev"]}%) = {s2odds}')
    elif len(s2pool_all) >= 2:
        s2pool_all.sort(key=lambda x: -x['score'])
        m1, m2 = s2pool_all[0], s2pool_all[1]
        s2odds = round(m1['best_odds'] * m2['best_odds'], 2)
        s2rec = {
            'match1': f'{m1["homeTeam"]} vs {m1["awayTeam"]}',
            'match1_rec': f'{m1["recommend"]} @{m1["best_odds"]}',
            'match1_ev': f'{m1["ev"]}%',
            'match2': f'{m2["homeTeam"]} vs {m2["awayTeam"]}',
            'match2_rec': f'{m2["recommend"]} @{m2["best_odds"]}',
            'match2_ev': f'{m2["ev"]}%',
            'combined_odds': s2odds,
            'note': '两场全中才中奖，风险较高'
        }
        print(f'\n🔗 2串1推荐(备选): {m1["homeTeam"]} {m1["recommend"]} @{m1["best_odds"]} × {m2["homeTeam"]} {m2["recommend"]} @{m2["best_odds"]} = {s2odds}')
    
    # 串关推荐（基于正EV场次动态生成）
    big_odds_parlays = []
    pos_ev_matches = [r for r in recommends if r.get('ev', 0) > 0]
    if len(pos_ev_matches) >= 3:
        top3 = pos_ev_matches[:3]
        top3_odds = [m['best_odds'] for m in top3]
        combined = 1
        for o in top3_odds: combined *= o
        
        big_odds_parlays.append({
            'name': f'正EV 3串1',
            'matches': ' × '.join([f'{m["homeTeam"]}({m["recommend"]}@{m["best_odds"]})' for m in top3]),
            'type': '3串1',
            'cost': 2,
            'maxPayout': f'中3场={combined:.0f}元',
            'note': '三场全部正EV，均注长线优势'
        })
    
    if len(pos_ev_matches) >= 2:
        top2 = pos_ev_matches[:2]
        combined_2 = top2[0]['best_odds'] * top2[1]['best_odds']
        big_odds_parlays.append({
            'name': f'正EV 2串1',
            'matches': ' × '.join([f'{m["homeTeam"]}({m["recommend"]}@{m["best_odds"]})' for m in top2]),
            'type': '2串1',
            'cost': 2,
            'maxPayout': f'中2场={combined_2:.0f}元',
            'note': '正EV组合，长线正期望'
        })
    
    # ===== 第6步：输出 =====
    output = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'updateTime': datetime.now().strftime('%H:%M'),
        'totalMatches': len(matches),
        'topRecommend': recommends[0] if recommends else None,
        'recommendations': recommends[:6],
        's2recommend': s2rec,
        'bigOddsParlays': big_odds_parlays,
        'posEvCount': len(pos_ev_matches),
        'dataSource': {
            'odds': 'webapi.sporttery.cn (竞彩网)',
            'teamData': 'api.football-data.org' if (standings_data and team_scores_data) else '未加载',
            'teamDataStatus': 'ok' if (standings_data and team_scores_data) else 'unavailable'
        }
    }
    
    # 打印推荐
    print('\n' + '='*70)
    print(f'📋 竞彩推荐 {output["date"]}')
    print('='*70)
    
    if recommends:
        r = recommends[0]
        ev_str = f' EV+{r["ev"]}%' if r.get('ev', 0) > 0 else ''
        kelly_str = ''
        if r.get('kelly_advice'):
            kelly_str = f' | {r["kelly_advice"]["note"]}'
        print(f'\n🏆 今日精选: {r["league"]} {r["homeTeam"]} vs {r["awayTeam"]}')
        print(f'   推荐: {r["recommend"]}  @ {r["best_odds"]}{ev_str}')
        print(f'   信心: {r["confidence"]}  |  评分: {r["score"]}{kelly_str}')
        print(f'   理由: {", ".join(r["reasons"])}')
        print(f'   主胜{r["had_h"]}  平{r["had_d"]}  客胜{r["had_a"]}')
        if r.get('home_group'):
            print(f'   小组: {r["home_group"]}')
        
        # 深度阵容分析
        home_age = r.get('home_avg_age', 0)
        away_age = r.get('away_avg_age', 0)
        home_pos = r.get('home_pos_dist', {})
        away_pos = r.get('away_pos_dist', {})
        
        if r.get('home_players'):
            h_players = ', '.join(r['home_players'][:5])
            home_info = f'{r["homeTeam"]}:{r.get("home_player_count","?")}人'
            if r.get('home_coach') and r['home_coach'] != '—':
                home_info += f' 教练:{r["home_coach"]}'
            if home_age:
                home_info += f' 均龄{home_age}岁'
            if home_pos:
                home_info += f' {"|".join([f"{k}{v}" for k,v in sorted(home_pos.items()) if v>0])}'
            print(f'   {home_info}')
            print(f'   核心: {h_players}')
        if r.get('away_players'):
            a_players = ', '.join(r['away_players'][:5])
            away_info = f'{r["awayTeam"]}:{r.get("away_player_count","?")}人'
            if r.get('away_coach') and r['away_coach'] != '—':
                away_info += f' 教练:{r["away_coach"]}'
            if away_age:
                away_info += f' 均龄{away_age}岁'
            if away_pos:
                away_info += f' {"|".join([f"{k}{v}" for k,v in sorted(away_pos.items()) if v>0])}'
            print(f'   {away_info}')
            print(f'   核心: {a_players}')
        
        # 对比分析（评分侧面的阵容洞察）
        insights_display = []
        if r.get('reasons'):
            for reason in r['reasons']:
                if '教练' in reason or '均龄' in reason:
                    insights_display.append(reason)
        if insights_display:
            print(f'   📊 {" | ".join(insights_display)}')
    
    print(f'\n📊 全部推荐（正EV {len(pos_ev_matches)}场）:')
    for r in recommends[:6]:
        g = f' [{r.get("home_group","?")}]' if r.get('home_group') else ''
        ev_str = f'(EV+{r["ev"]}%)' if r.get('ev', 0) > 0 else ''
        print(f'  {r["confidence"]} {r["league"]:8s} {r["homeTeam"]} vs {r["awayTeam"]}{g} → {r["recommend"]} @{r["best_odds"]} {ev_str}')
    
    # 汇总统计
    stars_count = {'★★★★★': 0, '★★★★': 0, '★★★': 0, '★★': 0, '★': 0}
    for r in recommends:
        sc = r.get('confidence', '★')
        if sc in stars_count: stars_count[sc] += 1
    
    print(f'\n📈 信心分布:' + ' '.join([f'{k}{v}场' for k,v in stars_count.items() if v > 0]))
    
    # 正EV统计
    if pos_ev_matches:
        avg_ev = sum(m.get('ev', 0) for m in pos_ev_matches) / len(pos_ev_matches)
        print(f'💰 正EV场次: {len(pos_ev_matches)}场, 平均EV+{avg_ev:.1f}%')
    
    # 保存JSON
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'\n✅ 推荐已保存至 {OUTPUT_FILE}')
    
    # 嵌入数据到jc.html
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
            print('⚠️ jc.html中未找到JC_DATA占位，跳过嵌入')
    else:
        print(f'⚠️ {jc_path} 不存在，跳过嵌入')


if __name__ == '__main__':
    main()
