"""
维基百科世界杯数据爬虫 (BeautifulSoup版)
每天抓取：球队阵容、教练、伤病信息、FIFA排名
"""
import requests, json, os, re
from bs4 import BeautifulSoup
from datetime import datetime

DATA_FILE = 'wiki_wc_data.json'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

TEAM_CN = {
    'South Korea': '韩国', 'Czech Republic': '捷克', 'Mexico': '墨西哥', 'South Africa': '南非',
    'Portugal': '葡萄牙', 'Nigeria': '尼日利亚', 'France': '法国', 'England': '英格兰',
    'Belgium': '比利时', 'Canada': '加拿大', 'Croatia': '克罗地亚', 'Ghana': '加纳',
    'Panama': '巴拿马', 'Ivory Coast': '科特迪瓦', 'Ecuador': '厄瓜多尔', 'New Zealand': '新西兰',
    'Iran': '伊朗', 'Senegal': '塞内加尔', 'Egypt': '埃及', 'Hungary': '匈牙利',
    'Kazakhstan': '哈萨克', 'Uzbekistan': '乌兹别克', 'Bosnia and Herzegovina': '波黑',
    'Haiti': '海地', 'Scotland': '苏格兰', 'Thailand': '泰国', 'Netherlands': '荷兰',
    'Italy': '意大利', 'Uruguay': '乌拉圭', 'Colombia': '哥伦比亚', 'Morocco': '摩洛哥',
    'Paraguay': '巴拉圭', 'Turkey': '土耳其', 'Venezuela': '委内瑞拉', 'Peru': '秘鲁',
    'Jordan': '约旦', 'Bolivia': '玻利维亚', 'Iceland': '冰岛', 'Northern Ireland': '北爱尔兰',
    'Saudi Arabia': '沙特', 'China': '中国', 'Indonesia': '印尼', 'Slovakia': '斯洛伐克',
    'Slovenia': '斯洛文尼', 'Greece': '希腊', 'Norway': '挪威', 'Romania': '罗马尼亚',
    'Wales': '威尔士', 'United States': '美国', 'Argentina': '阿根廷', 'Brazil': '巴西',
    'Spain': '西班牙', 'Germany': '德国', 'Japan': '日本', 'Australia': '澳大利亚',
    'Sweden': '瑞典', 'Switzerland': '瑞士', 'Poland': '波兰', 'Denmark': '丹麦',
    'Austria': '奥地利', 'Ukraine': '乌克兰', 'Serbia': '塞尔维亚', 'Russia': '俄罗斯',
}

CN_TO_EN = {v: k for k, v in TEAM_CN.items()}

SKIP_TEAMS = {'Group A', 'Group B', 'Group C', 'Group D', 'Group E', 'Group F', 'Group G', 'Group H',
              'Squad list', 'Notes', 'References', 'Contents', 'Squads', 'Player representation by club',
              'Average age of squads', 'Age', 'Coach', 'External links'}

def fetch_squads():
    """爬取所有球队阵容"""
    r = requests.get('https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads', headers=HEADERS, timeout=20)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    teams = {}
    for h3 in soup.find_all('h3'):
        if not h3.get('id'): continue
        team_name = h3.get('id').replace('_', ' ')
        if team_name in SKIP_TEAMS or len(team_name) > 30: continue
        
        # 教练
        coach = '—'
        p = h3.find_next('p')
        if p:
            cm = p.find('a', href=True)
            if cm and 'wiki' in cm['href']:
                coach = cm.get_text(strip=True)
        
        # 伤病：从h3到表格之间找"withdrew injured"
        injuries = []
        table = h3.find_next('table', class_='wikitable')
        if table:
            between = str(h3) + str(h3.find_all_next(text=True, limit=50))
            for m in re.finditer(r'<a[^>]*>([^<]+)</a>\s+withdrew', between):
                injuries.append(m.group(1).strip())
        
        # 球员（注意：球员名在<th>中，不在<td>）
        players = []
        if table:
            for row in table.find_all('tr')[1:]:
                tds = row.find_all('td')
                ths = row.find_all('th')
                # 球员名在第一个<th>中（如果有）
                name_tag = ths[0].find('a') if ths else None
                # 位置在第二个<td>中（如果有）
                pos_tag = tds[1].find('a') if len(tds) >= 2 else None
                # 俱乐部在最后一个<td>中（如果有）
                club_tag = tds[-1].find('a') if tds else None
                
                pname = name_tag.get_text(strip=True) if name_tag else ''
                pos = pos_tag.get_text(strip=True) if pos_tag else '?'
                club = club_tag.get_text(strip=True) if club_tag else ''
                
                if pname and len(pname) > 1:
                    entry = f'{pos} {pname}'
                    if club:
                        entry += f' ({club})'
                    players.append(entry)
        
        teams[team_name] = {
            'coach': coach,
            'player_count': len(players),
            'players': players[:11],
            'injuries': injuries
        }
    
    return teams

def fetch_rankings():
    """爬取FIFA排名（从维基百科2026年世界杯页面的排名表格）"""
    try:
        # FIFA世界排名页面
        r = requests.get('https://en.wikipedia.org/wiki/FIFA_World_Rankings', headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        rankings = {}
        # 找"Current rankings"或"Latest rankings"表格
        for h2 in soup.find_all(['h2', 'h3']):
            text = h2.get_text()
            if 'Current' in text or 'Latest' in text or 'Rankings' in text:
                table = h2.find_next('table')
                if table:
                    for row in table.find_all('tr')[1:]:
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            rank = cols[0].get_text(strip=True)
                            # 第二列可能包含队名和国旗
                            team_cell = cols[1]
                            team_link = team_cell.find('a')
                            team = team_link.get('title', team_link.get_text(strip=True)) if team_link else team_cell.get_text(strip=True)
                            if rank.isdigit() and team:
                                rankings[team] = int(rank)
                    if rankings:
                        break  # 找到并解析完了
        
        # 备用：尝试直接从国家表格找排名
        if not rankings:
            # 从2026世界杯页面找"Teams"表格
            r2 = requests.get('https://en.wikipedia.org/wiki/2026_FIFA_World_Cup', headers=HEADERS, timeout=20)
            soup2 = BeautifulSoup(r2.text, 'html.parser')
            for caption in soup2.find_all('caption'):
                if 'Teams' in caption.get_text():
                    table = caption.find_parent('table')
                    if table:
                        for row in table.find_all('tr')[1:]:
                            cols = row.find_all('td')
                            if cols:
                                link = cols[0].find('a')
                                if link:
                                    team = link.get_text(strip=True)
                                    rankings[team] = 0  # 占位，没有实际排名
        
        return rankings
    except:
        return {}

def fetch_all():
    """主入口"""
    result = {
        'updateTime': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'teams': fetch_squads(),
        'rankings': fetch_rankings()
    }
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    n_teams = len(result.get('teams', {}))
    n_ranks = len(result.get('rankings', {}))
    print(f'球队: {n_teams} 支 | 排名: {n_ranks} 条')
    return result

def query(cn_name):
    """查询球队信息"""
    if not os.path.exists(DATA_FILE):
        return {'error': '数据文件不存在，先运行 fetch_all()'}
    
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    en = CN_TO_EN.get(cn_name)
    if not en:
        return {'error': f'未找到球队: {cn_name}'}
    
    info = data['teams'].get(en, {})
    rank = data['rankings'].get(en, '—')
    
    return {
        'name': cn_name,
        'en_name': en,
        'rank': rank,
        'coach': info.get('coach', '—'),
        'player_count': info.get('player_count', 0),
        'players': info.get('players', []),
        'injuries': info.get('injuries', [])
    }

if __name__ == '__main__':
    fetch_all()
    
    # 测试
    for team in ['韩国', '捷克', '葡萄牙']:
        info = query(team)
        print(f'\n{info["name"]} ({info.get("en_name","")})')
        print(f'  FIFA排名: {info.get("rank","—")}')
        print(f'  教练: {info.get("coach","—")}')
        print(f'  球员: {info.get("player_count","0")}人')
        if info.get('injuries'):
            print(f'  ⚕️伤病: {info["injuries"]}')
