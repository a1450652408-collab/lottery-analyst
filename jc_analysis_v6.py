"""
竞彩足球 V6 — 反被高估热门策略
================================

策略: 市场强烈看好某队(低赔率)，但该队在WC实际表现匹配不上
      → 市场高估了该队 → 推荐下盘/平局

核心逻辑:
  1. 从赔率找热门: 某方向赔率 < 1.60
  2. 从WC赛果验证: 该队在已经踢过的比赛中表现如何?
  3. 表现不匹配 = 信号: 推荐平局(下盘)

数据源:
  1. 竞彩网官方API (赔率)
  2. jc_results.json (WC赛果)
  3. team_data.py (积分榜)
"""

import requests, json, os, sys
from datetime import datetime

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
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

# 策略参数
FAVORITE_MAX_ODDS = 1.60   # 热门赔率不超过此值
MIN_GAMES = 1              # 至少踢过1场

# ===== 球队名称归一化 =====
NAME_NORMALIZE = {
    '克罗地': '克罗地亚', '阿尔及利': '阿尔及利亚',
    '塞内': '塞内加尔', '新西': '新西兰', '佛得': '佛得角',
    '突尼': '突尼斯', '科特迪': '科特迪瓦', '厄瓜多': '厄瓜多尔',
    '澳大': '澳大利亚', '卡塔': '卡塔尔', '巴拉': '巴拉圭',
    '巴拿': '巴拿马', '库拉': '库拉索',
}

def normalize_name(name):
    if not name:
        return name
    if name in NAME_NORMALIZE:
        return NAME_NORMALIZE[name]
    for short, full in NAME_NORMALIZE.items():
        if short in name:
            return full
    return name


# ===== WC表现数据库 =====
def build_team_stats():
    """从 jc_results.json 构建每队WC表现"""
    results_file = os.path.join(DATA_DIR, 'jc_results.json')
    if not os.path.exists(results_file):
        return {}, {}
    
    with open(results_file, encoding='utf-8') as f:
        results = json.load(f)
    
    team_stats = {}
    for r in results:
        home = normalize_name(r['home'])
        away = normalize_name(r['away'])
        hs = r.get('home_score', 0)
        aws = r.get('away_score', 0)
        
        for team, gf, ga, opp in [(home, hs, aws, away), (away, aws, hs, home)]:
            if team not in team_stats:
                team_stats[team] = {'played': 0, 'gf': 0, 'ga': 0, 'wins': 0, 'draws': 0, 'losses': 0,
                                     'opponents': [], 'results': []}
            s = team_stats[team]
            s['played'] += 1
            s['gf'] += gf
            s['ga'] += ga
            s['opponents'].append(opp)
            if gf > ga:
                s['wins'] += 1
                s['results'].append('W')
            elif gf == ga:
                s['draws'] += 1
                s['results'].append('D')
            else:
                s['losses'] += 1
                s['results'].append('L')
    
    # 计算对手质量: 对手的平均净胜球
    for team, s in team_stats.items():
        opp_quality = 0
        for opp in s['opponents']:
            if opp in team_stats:
                opp_quality += team_stats[opp]['gf'] - team_stats[opp]['ga']
        s['opp_quality'] = opp_quality / max(1, len(s['opponents']))
    
    return team_stats



def team_is_overrated(team_name, stats):
    """基于胜负+对手质量判断"""
    if team_name not in stats:
        return False, '无数据'
    
    s = stats[team_name]
    if s['played'] < MIN_GAMES:
        return False, f'仅{s["played"]}场'
    
    gf_pg = s['gf'] / s['played']
    ga_pg = s['ga'] / s['played']
    opp_q = s['opp_quality']
    
    # 确实强的证据 → 不触发
    # 1. 至少赢过1场且净胜球>=2
    if s['wins'] >= 1 and (s['gf'] - s['ga']) >= 2:
        return False, f'已证明({s["wins"]}胜,净胜{s["gf"]-s["ga"]})'
    
    # 2. 场均进球>=3
    if gf_pg >= 3.0:
        return False, f'攻击强(场均{gf_pg:.1f}球)'
    
    # 被高估的证据 → 触发
    reasons = []
    
    # A. 0胜
    if s['wins'] == 0:
        reasons.append(f'{s["played"]}场0胜')
    
    # B. 攻击弱 + 对手弱(虐菜都虐不动)
    if gf_pg < 1.5 and opp_q <= 0:
        reasons.append(f'场均{gf_pg:.1f}球(vs弱队)')
    
    # C. 防守差
    if ga_pg >= 2.0:
        reasons.append(f'场均失{ga_pg:.1f}球')
    
    # D. 净胜球很差
    if s['gf'] - s['ga'] <= -2:
        reasons.append(f'净胜{s["gf"]-s["ga"]}')
    
    if reasons:
        return True, ', '.join(reasons)
    
    return False, f'合理({s["wins"]}W{s["draws"]}D{s["losses"]}L, GF{s["gf"]}GA{s["ga"]})'


# ===== API =====
def fetch_today_matches():
    r = requests.get(f'{BASE_URL}/getMatchListV1.qry?clientCode=3001', headers=HEADERS, timeout=15)
    data = r.json()
    if not data.get('success'):
        return []
    matches = data['value']['matchInfoList']
    result = []
    for group in matches:
        for sm in group.get('subMatchList', []):
            had_odds = None
            for odds in sm.get('oddsList', []):
                if odds.get('poolCode') == 'HAD':
                    had_odds = odds
            if not had_odds:
                continue
            
            home = sm.get('homeTeamAbbName', '') or sm.get('homeTeamAllName', '')
            away = sm.get('awayTeamAbbName', '') or sm.get('awayTeamAllName', '')
            league = sm.get('leagueAbbName', '') or sm.get('leagueAllName', '')
            
            if not home or not away:
                continue
            
            result.append({
                'homeTeam': home,
                'awayTeam': away,
                'league': league,
                'matchTime': sm.get('matchTime', ''),
                'matchDate': sm.get('matchDate', ''),
                'had_h': float(had_odds.get('h', 0)),
                'had_d': float(had_odds.get('d', 0)),
                'had_a': float(had_odds.get('a', 0)),
            })
    return result


# ===== 核心分析 =====
def analyze_match(match, team_stats):
    """反被高估热门分析"""
    had = [match['had_h'], match['had_d'], match['had_a']]
    labels = ['主胜', '平局', '客胜']
    
    # 找市场热门
    fav_idx = min(range(3), key=lambda i: had[i])
    fav_label = labels[fav_idx]
    fav_odds = had[fav_idx]
    
    # 不是热门，不关注
    if fav_odds >= FAVORITE_MAX_ODDS or fav_label == '平局':
        return None
    
    # 确定热门是哪个队
    if fav_label == '主胜':
        fav_team = match['homeTeam']
        underdog_team = match['awayTeam']
        underdog_direction = '客胜' if had[2] >= had[1] else '平局'
    else:
        fav_team = match['awayTeam']
        underdog_team = match['homeTeam']
        underdog_direction = '主胜' if had[0] >= had[1] else '平局'
    
    fav_norm = normalize_name(fav_team)
    overrated, reason = team_is_overrated(fav_norm, team_stats)
    
    if not overrated:
        return None  # 热门表现合理，无信号
    
    # 热门被高估! → 推荐下盘/平局
    # 优先推荐平局（赔率通常3~5倍），其次推荐下盘方向
    draw_odds = had[1]
    
    if underdog_direction == '平局' or draw_odds <= 6.0:
        recommend = '平局'
        rec_odds = draw_odds
    else:
        # 推荐下盘方向
        ud_idx = 0 if underdog_direction == '主胜' else 2
        recommend = underdog_direction
        rec_odds = had[ud_idx]
    
    # 评分
    score = 0
    reasons_list = [f'{fav_team}被高估: {reason}']
    
    # 被高估程度
    if '场均仅' in reason and '场均失' in reason:
        score += 3.0
        reasons_list.append('攻防双弱')
    elif '场均仅' in reason:
        score += 1.5
    elif '场均失' in reason:
        score += 1.5
    
    # 赔率
    if 3.0 <= rec_odds <= 6.0:
        score += 2.0
        reasons_list.append(f'{recommend}@{rec_odds}')
    elif rec_odds > 6.0:
        score += 1.0
    
    # 热门赔率越低+被高估 → 信号越强
    if fav_odds < 1.30:
        score += 2.0
        reasons_list.append('极端热门')
    elif fav_odds < 1.45:
        score += 1.0
    
    # 信心
    if score >= 5.0:
        confidence = '★★★★'
    elif score >= 3.0:
        confidence = '★★★'
    elif score >= 2.0:
        confidence = '★★'
    else:
        confidence = '★'
    
    return {
        'homeTeam': match['homeTeam'],
        'awayTeam': match['awayTeam'],
        'league': match.get('league', ''),
        'matchDate': match.get('matchDate', ''),
        'matchTime': match.get('matchTime', ''),
        'confidence': confidence,
        'score': round(score, 1),
        'recommend': recommend,
        'recommend_odds': rec_odds,
        'fav_team': fav_team,
        'fav_odds': fav_odds,
        'fav_label': fav_label,
        'overrated_reason': reason,
        'reasons': reasons_list,
        'team_stats': {
            fav_team: team_stats.get(fav_norm, {}),
        }
    }


# ===== 报告 =====
def generate_report(output):
    lines = [
        f"# 竞彩 V6 反热门分析 ({output['date']})",
        f"",
        f"> 生成: {output['updateTime']}",
        f"> 策略: 市场热门(赔率<{FAVORITE_MAX_ODDS}) + WC表现不匹配 → 推荐下盘",
        f"> 数据: {output['stats_info']['teams']}队WC实际表现",
        f"",
        f"---",
        f"",
        f"## 今日概览",
        f"",
        f"- 比赛: {output['totalMatches']}场",
        f"- 热门被高估信号: {len(output['recommendations'])}场",
        f"- 无信号: {output.get('no_signal', 0)}场",
        f"",
    ]
    
    recs = output.get('recommendations', [])
    if recs:
        lines.extend([
            f"## 🔴 反热门推荐",
            f"",
            f"| 信心 | 比赛 | 热门 | 赔率 | 被高估原因 | 推荐 | 赔率 |",
            f"|:---:|:---|:---|:---:|:---|:---:|:---:|",
        ])
        for r in recs:
            lines.append(
                f"| {r['confidence']} "
                f"| {r['homeTeam']} vs {r['awayTeam']} "
                f"| {r['fav_team']}({r['fav_label']}) "
                f"| {r['fav_odds']} "
                f"| {r['overrated_reason']} "
                f"| {r['recommend']} "
                f"| {r['recommend_odds']} |"
            )
        lines.append("")
    
    lines.extend([
        f"## ⚠️ 策略说明",
        f"",
        f"1. 找市场热门（某方向赔率<{FAVORITE_MAX_ODDS})",
        f"2. 查WC表现：0胜+弱攻击+差防守+对手质量 → 高估"
        f"3. 已证明的强队(净胜≥2 或 场均≥3球) → 不触发",
        f"3. 被高估的热门 → 推荐平局/下盘",
        f"4. 热门表现匹配则不推荐（无信号）",
        f"5. 纯数据驱动，请理性参考",
        f"",
        f"*V6 反被高估热门策略*",
    ])
    
    return '\n'.join(lines)


def sync_jc_matches(output):
    data_path = os.path.join(DATA_DIR, 'jc_matches.json')
    matches_data = []
    for r in output.get('recommendations', []):
        matches_data.append({
            'homeTeam': r['homeTeam'],
            'awayTeam': r['awayTeam'],
            'recommend': r['recommend'],
            'recommend_odds': r['recommend_odds'],
            'confidence': r['confidence'],
            'fav_team': r['fav_team'],
            'fav_odds': r['fav_odds'],
            'reason': r['overrated_reason'],
        })
    
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump({
            'date': output['date'],
            'updateTime': output['updateTime'],
            'matches': matches_data,
            'summary': {'total': len(matches_data), 'strategy': 'V6 Fade Overrated Favorite'},
        }, f, ensure_ascii=False, indent=2)
    print(f'[同步] jc_matches.json ({len(matches_data)}场)')


# ===== Main =====
def main():
    print(f'[{datetime.now().strftime("%H:%M:%S")}] === 竞彩V6 反被高估热门 ===')
    
    # 1. 构建WC球队表现
    team_stats = build_team_stats()
    print(f'[数据] {len(team_stats)}队WC表现')
    for team, s in sorted(team_stats.items()):
        if s['played'] > 0:
            print(f'  {team}: {s["played"]}场 GF{s["gf"]} GA{s["ga"]}')
    
    # 2. 获取今日比赛
    matches = fetch_today_matches()
    if not matches:
        print('❌ 今日无比赛')
        return
    print(f'\n[比赛] {len(matches)}场')
    
    # 3. 分析
    recommendations = []
    no_signal_count = 0
    
    for m in matches:
        result = analyze_match(m, team_stats)
        if result:
            recommendations.append(result)
        else:
            no_signal_count += 1
    
    recommendations.sort(key=lambda x: -x['score'])
    
    # 4. 输出
    now = datetime.now()
    output = {
        'date': now.strftime('%Y-%m-%d'),
        'updateTime': now.strftime('%Y-%m-%d %H:%M:%S'),
        'totalMatches': len(matches),
        'recommendations': recommendations,
        'no_signal': no_signal_count,
        'stats_info': {'teams': len(team_stats)},
        'strategy': f'V6 Fade Overrated Favorite (odds<{FAVORITE_MAX_ODDS})',
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    sync_jc_matches(output)
    
    report = generate_report(output)
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 5. 打印
    print(f'\n{"="*60}')
    print(f'  🔴 反热门推荐 ({len(recommendations)}场)')
    print(f'{"="*60}')
    
    for i, r in enumerate(recommendations, 1):
        print(f'  {i}. [{r["confidence"]}] {r["homeTeam"]} vs {r["awayTeam"]}')
        print(f'     热门: {r["fav_team"]}({r["fav_label"]}) @{r["fav_odds"]}')
        print(f'     原因: {r["overrated_reason"]}')
        print(f'     推荐: {r["recommend"]} @{r["recommend_odds"]}')
    
    if no_signal_count > 0:
        print(f'\n  ✓ 无信号: {no_signal_count}场')
    
    print(f'\n✅ {OUTPUT_FILE}, {REPORT_FILE}')


if __name__ == "__main__":
    main()
