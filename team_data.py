"""
足球队数据API模块 (football-data.org)
提供队伍实力评分、排名、近期表现等数据
增强竞彩价值投注推荐系统

API Key: 1163986726a345ffb7093db9e34a5e3f
免费层: TIER_ONE (10请求/分钟，限13个联赛)
"""

import urllib.request
import json
import os
import re
import time
from datetime import datetime, timedelta

# ===== 配置 =====
API_KEY = '1163986726a345ffb7093db9e34a5e3f'
BASE_URL = 'https://api.football-data.org/v4'
CACHE_FILE = 'team_data_cache.json'
CACHE_TTL = timedelta(hours=6)

# ===== 队伍名映射（中文 -> 英文 -> football-data.org 队名）=====
TEAM_NAME_MAP = {
    # 世界杯队伍 (A组)
    '韩国': ('South Korea', 'South Korea'),
    '捷克': ('Czech Republic', 'Czechia'),
    '墨西哥': ('Mexico', 'Mexico'),
    '南非': ('South Africa', 'South Africa'),
    # B组
    '波黑': ('Bosnia and Herzegovina', 'Bosnia-Herzegovina'),
    '加拿大': ('Canada', 'Canada'),
    '卡塔尔': ('Qatar', 'Qatar'),
    '瑞士': ('Switzerland', 'Switzerland'),
    # C组
    '巴西': ('Brazil', 'Brazil'),
    '摩洛哥': ('Morocco', 'Morocco'),
    '海地': ('Haiti', 'Haiti'),
    '苏格兰': ('Scotland', 'Scotland'),
    # D组
    '土耳其': ('Turkey', 'Turkey'),
    '美国': ('United States', 'United States'),
    '巴拉圭': ('Paraguay', 'Paraguay'),
    '澳大利亚': ('Australia', 'Australia'),
    # E组
    '德国': ('Germany', 'Germany'),
    '库拉索': ('Curacao', 'Curaçao'),
    '科特迪瓦': ('Ivory Coast', 'Ivory Coast'),
    '厄瓜多尔': ('Ecuador', 'Ecuador'),
    # F组
    '瑞典': ('Sweden', 'Sweden'),
    '荷兰': ('Netherlands', 'Netherlands'),
    '日本': ('Japan', 'Japan'),
    '突尼斯': ('Tunisia', 'Tunisia'),
    # G组
    '比利时': ('Belgium', 'Belgium'),
    '埃及': ('Egypt', 'Egypt'),
    '伊朗': ('Iran', 'Iran'),
    '新西兰': ('New Zealand', 'New Zealand'),
    # H组
    '西班牙': ('Spain', 'Spain'),
    '佛得角': ('Cape Verde', 'Cape Verde Islands'),
    '沙特': ('Saudi Arabia', 'Saudi Arabia'),
    '乌拉圭': ('Uruguay', 'Uruguay'),
    # I组
    '伊拉克': ('Iraq', 'Iraq'),
    '法国': ('France', 'France'),
    '塞内加尔': ('Senegal', 'Senegal'),
    '挪威': ('Norway', 'Norway'),
    # J组
    '阿根廷': ('Argentina', 'Argentina'),
    '阿尔及利亚': ('Algeria', 'Algeria'),
    '奥地利': ('Austria', 'Austria'),
    '约旦': ('Jordan', 'Jordan'),
    # K组
    '刚果': ('Congo DR', 'Congo DR'),
    '葡萄牙': ('Portugal', 'Portugal'),
    '乌兹别克': ('Uzbekistan', 'Uzbekistan'),
    '哥伦比亚': ('Colombia', 'Colombia'),
    # L组
    '英格兰': ('England', 'England'),
    '克罗地亚': ('Croatia', 'Croatia'),
    '加纳': ('Ghana', 'Ghana'),
    '巴拿马': ('Panama', 'Panama'),
}


def clean_proxy():
    """清除代理环境变量"""
    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(k, None)


def api_request(endpoint):
    """发送API请求到football-data.org"""
    clean_proxy()
    url = f'{BASE_URL}{endpoint}'
    req = urllib.request.Request(url)
    req.add_header('X-Auth-Token', API_KEY)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {'error': f'HTTP {e.code}', 'body': body[:200]}
    except Exception as e:
        return {'error': str(e)[:100]}


def load_cache():
    """加载缓存数据"""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                data = json.load(f)
            cache_time = datetime.fromisoformat(data.get('_cached_at', '2000-01-01'))
            if datetime.now() - cache_time < CACHE_TTL:
                return data
        except:
            pass
    return {'_cached_at': '2000-01-01', 'standings': {}, 'team_scores': {}}


def save_cache(data):
    """保存缓存"""
    data['_cached_at'] = datetime.now().isoformat()
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_wc_standings():
    """获取世界杯小组赛排名数据"""
    data = api_request('/competitions/WC/standings')
    if 'error' in data:
        return None
    
    standings_by_team = {}
    team_id_map = {}  # name -> id
    for st in data.get('standings', []):
        group = st.get('group', 'Unknown')
        for t in st.get('table', []):
            team = t.get('team', {})
            team_name = team.get('name', '')
            team_id = team.get('id')
            standings_by_team[team_name] = {
                'position': t['position'],
                'group': group,
                'points': t.get('points', 0),
                'playedGames': t.get('playedGames', 0),
                'won': t.get('won', 0),
                'draw': t.get('draw', 0),
                'lost': t.get('lost', 0),
                'goalsFor': t.get('goalsFor', 0),
                'goalsAgainst': t.get('goalsAgainst', 0),
                'goalDifference': t.get('goalDifference', 0),
                'form': t.get('form', ''),
                'teamId': team_id
            }
            if team_id:
                team_id_map[team_id] = team_name
    return standings_by_team, team_id_map


TEAM_SQUADS_CACHE = {}  # eng_name -> {coach, players}


def fetch_team_squad(team_id, team_name):
    """获取单支球队的阵容数据（教练+球员+深度分析）"""
    data = api_request(f'/teams/{team_id}')
    if 'error' in data:
        return None
    
    coach_name = '—'
    if data.get('coach'):
        coach_name = data['coach'].get('name', '—')
    
    from datetime import datetime
    
    players = []
    ages = []
    pos_counts = {'GK': 0, 'DF': 0, 'MF': 0, 'FW': 0}
    today = datetime.now()
    
    for p in data.get('squad', []):
        pos_raw = p.get('position', '?')
        name = p.get('name', '?')
        dob_str = p.get('dateOfBirth', '')
        
        # 位置简写
        pos_short = {'Goalkeeper': 'GK', 'Defence': 'DF', 'Midfield': 'MF', 'Offence': 'FW'}.get(pos_raw, pos_raw[:2])
        if pos_short in pos_counts:
            pos_counts[pos_short] += 1
        
        # 年龄计算
        age = None
        if dob_str:
            try:
                dob = datetime.strptime(dob_str[:10], '%Y-%m-%d')
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                ages.append(age)
            except:
                pass
        
        players.append({
            'name': name,
            'pos': pos_short,
            'age': age or 0,
            'dob': (dob_str or '')[:10],
        })
    
    avg_age = round(sum(ages) / len(ages), 1) if ages else 0
    
    return {
        'coach': coach_name,
        'player_count': len(players),
        'players_raw': players,
        'avg_age': avg_age,
        'pos_dist': pos_counts,
        'injuries': []
    }


def fetch_all_team_squads(team_id_map, cache):
    """批量获取所有球队阵容数据（带缓存）"""
    squads = cache.get('team_squads', {})
    if not squads:
        squads = {}
    
    fetched = 0
    for tid, name in team_id_map.items():
        if name in squads:
            continue  # 已有缓存
        squad = fetch_team_squad(tid, name)
        if squad:
            squads[name] = squad
            fetched += 1
            if fetched % 5 == 0:
                print(f'  [阵容] 已获取 {fetched} 队...')
        time.sleep(0.3)  # 限速保护
    
    if fetched > 0:
        print(f'  [阵容] 新增 {fetched} 队')
    return squads


def calc_team_strength(standings):
    """
    根据排名数据计算队伍实力评分 (0~100)
    基于 FIFA 排名公式概念：积分、净胜球、进球、防守
    """
    if not standings:
        return {}
    
    scores = {}
    # 先计算所有队的原始得分
    raw_scores = {}
    for name, st in standings.items():
        played = st['playedGames']
        if played == 0:
            raw_scores[name] = 50  # 默认中等
            continue
        
        pts_per_game = st['points'] / played
        gd_per_game = (st['goalsFor'] - st['goalsAgainst']) / played
        
        # 综合评分公式
        score = min(100, max(0, 
            pts_per_game * 20 +     # 每场积分 * 20
            gd_per_game * 10 +       # 净胜球 * 10
            st['won'] / played * 30 - # 胜率权重
            (1 - st['goalsFor'] / max(1, st['goalsFor'] + st['goalsAgainst'])) * 20  # 进球占比
        ))
        raw_scores[name] = round(score, 1)
    
    # 归一化到0~100
    if raw_scores:
        max_s = max(raw_scores.values())
        min_s = min(raw_scores.values())
        range_s = max_s - min_s if max_s != min_s else 1
        for name, s in raw_scores.items():
            scores[name] = round((s - min_s) / range_s * 100, 1)
    
    return scores


def fetch_wc_matches():
    """
    获取世界杯历史比赛结果（用于泊松模型训练）
    返回: [{homeTeam, awayTeam, homeGoals, awayGoals, date, stage}]
    """
    data = api_request('/competitions/WC/matches')
    if 'error' in data:
        print(f'  [比赛数据] API错误: {data.get("error")}')
        return []
    
    matches = []
    for m in data.get('matches', []):
        # 只取已结束的比赛（有比分）
        if m.get('status') != 'FINISHED':
            continue
        
        home_team = m.get('homeTeam', {}).get('name', '')
        away_team = m.get('awayTeam', {}).get('name', '')
        score = m.get('score', {})
        full_time = score.get('fullTime', {})
        home_goals = full_time.get('home')
        away_goals = full_time.get('away')
        
        if None in (home_goals, away_goals):
            continue
        
        matches.append({
            'homeTeam': home_team,
            'awayTeam': away_team,
            'homeGoals': home_goals,
            'awayGoals': away_goals,
            'date': m.get('utcDate', '')[:10],
            'stage': m.get('stage', ''),
            'matchday': m.get('matchday', 0)
        })
    
    print(f'  [比赛数据] 获取到 {len(matches)} 场已结束比赛')
    return matches


def get_team_score(cn_name, standings, team_scores):
    """
    获取中文队名的实力评分
    返回 (strength_score, detail_dict) 
    """
    mapping = TEAM_NAME_MAP.get(cn_name)
    if not mapping:
        return 50, {'note': f'未找到映射: {cn_name}'}
    
    eng_name = mapping[1]  # football-data.org 的队名
    
    if standings and eng_name in standings:
        st = standings[eng_name]
        score = team_scores.get(eng_name, 50) if standings.get(eng_name, {}).get('playedGames', 0) > 0 else 50
        return score, {
            'eng_name': eng_name,
            'position': st.get('position', '?'),
            'group': st.get('group', '?'),
            'points': st.get('points', 0),
            'played': st.get('playedGames', 0),
            'form': st.get('form', ''),
            'has_data': st.get('playedGames', 0) > 0
        }
    
    return 50, {'eng_name': eng_name, 'note': '暂无数据', 'has_data': False}


def fetch_and_cache_all():
    """
    完整获取数据流程：
    1. 从缓存加载
    2. 获取世界杯排名 + 球队ID
    3. 获取每队阵容（教练+球员）
    4. 获取历史比赛结果（泊松模型用）
    5. 计算实力评分
    6. 保存缓存
    返回 (standings, team_scores, team_squads, matches)
    """
    cache = load_cache()
    result = fetch_wc_standings()
    
    if result is None:
        # 使用缓存
        if cache.get('standings'):
            return (cache['standings'], cache.get('team_scores', {}),
                    cache.get('team_squads', {}), cache.get('matches', []))
        return {}, {}, {}, []
    
    standings, team_id_map = result
    team_scores = calc_team_strength(standings)
    
    # 获取阵容数据
    team_squads = fetch_all_team_squads(team_id_map, cache)
    
    # 获取历史比赛结果
    matches = fetch_wc_matches()
    
    # 更新缓存
    cache['standings'] = standings
    cache['team_scores'] = team_scores
    cache['team_squads'] = team_squads
    cache['matches'] = matches
    save_cache(cache)
    
    return standings, team_scores, team_squads, matches


def enrich_match_with_team_data(match, standings, team_scores, team_squads=None):
    """
    给单场比赛数据增加队伍实力信息
    返回增强后的比赛字典
    """
    home_score, home_info = get_team_score(match['homeTeam'], standings, team_scores)
    away_score, away_info = get_team_score(match['awayTeam'], standings, team_scores)
    
    # 实力差 (正值表示主队更强)
    strength_diff = round(home_score - away_score, 1)
    
    match['home_strength'] = home_score
    match['away_strength'] = away_score
    match['strength_diff'] = strength_diff
    match['home_detail'] = home_info
    match['away_detail'] = away_info
    
    # 阵容数据（从football-data.org API获取）
    if team_squads:
        home_en = TEAM_NAME_MAP.get(match['homeTeam'], (None, None))[1]
        away_en = TEAM_NAME_MAP.get(match['awayTeam'], (None, None))[1]
        
        for side, en in [('home', home_en), ('away', away_en)]:
            if en and en in team_squads:
                sq = team_squads[en]
                match[f'{side}_coach'] = sq.get('coach', '—')
                match[f'{side}_player_count'] = sq.get('player_count', 0)
                match[f'{side}_avg_age'] = sq.get('avg_age', 0)
                match[f'{side}_pos_dist'] = sq.get('pos_dist', {})
                # 核心球员（前8人带年龄）
                raw = sq.get('players_raw', [])
                match[f'{side}_players'] = [f'{p["pos"]} {p["name"]}({p["age"]})' for p in raw[:8]]
    
    return match


if __name__ == '__main__':
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 测试 football-data.org API...')
    
    standings, team_scores, team_squads, matches = fetch_and_cache_all()
    
    if standings:
        print(f'✅ 成功获取 {len(standings)} 支球队数据')
        for name, st in sorted(standings.items()):
            score = team_scores.get(name, '-')
            print(f'  {name:25s} {st["group"]:10s} P{st["playedGames"]} Pts:{st["points"]} Score:{score}')
    else:
        print('⚠️ 未能获取球队数据（API可能不可达或无数据）')
    
    # 测试中文队名查询
    print('\n=== 中文队名映射测试 ===')
    test_teams = ['韩国', '捷克', '加纳', '巴西', '葡萄牙', '阿根廷', '日本']
    for cn in test_teams:
        score, info = get_team_score(cn, standings, team_scores)
        eng = info.get('eng_name', '?')
        has_data = '✓' if info.get('has_data') else '✗(0场)'
        print(f'  {cn:5s} -> {eng:20s} 实力:{score} {has_data}')
