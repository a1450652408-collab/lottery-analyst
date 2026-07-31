"""
竞彩价值投注模型回测 (V4 - 无偏见价值评分)
数据结构与jc_analysis.py保持一致，用于验证推荐准确率
"""
import requests, json
from math import log

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.sporttery.cn/',
    'Origin': 'https://www.sporttery.cn'
}

def fetch_all_results():
    """拉取历史赛果（多页）"""
    all_matches = []
    for page in [1, 2, 3]:
        r = requests.get(
            f'https://webapi.sporttery.cn/gateway/uniform/football/getUniformMatchResultV1.qry'
            f'?matchBeginDate=2026-05-10&matchEndDate=2026-06-10&leagueId='
            f'&pageSize=100&pageNo={page}&isFix=0&matchPage={page}&pcOrWap=1',
            headers=HEADERS, timeout=15)
        data = r.json()
        if data.get('value') and data['value'].get('matchResult'):
            all_matches.extend(data['value']['matchResult'])
    return all_matches

def get_result(score_str):
    """从比分判断主胜/平/客胜"""
    if not score_str or ':' not in score_str:
        return None
    parts = score_str.split(':')
    try:
        hs, aw = int(parts[0]), int(parts[1])
    except:
        return None
    return '主胜' if hs > aw else ('平局' if hs == aw else '客胜')

def calc_implied_prob(odds):
    """计算公平概率"""
    if any(o <= 0 for o in odds):
        return [0, 0, 0], 0
    probs = [1/o for o in odds]
    total = sum(probs)
    fair = [p/total for p in probs]
    juice = (total - 1) * 100
    return fair, juice

def evaluate_options(h, d, a):
    """
    V4无偏见评估：对主胜/平局/客胜分别计算价值分
    返回[{label, odds, value_pct, ev, score}, ...]
    """
    fair, juice = calc_implied_prob([h, d, a])
    if any(o <= 0 for o in [h, d, a]) or juice > 15:
        return None
    
    labels = ['主胜', '平局', '客胜']
    odds = [h, d, a]
    options = []
    
    for i in range(3):
        o = odds[i]
        fp = fair[i]
        if o <= 0 or fp <= 0:
            continue
        
        implied_p = 1 / o
        value_pct = (implied_p - fp) / fp * 100
        ev = o * fp - 1
        
        score = 0
        score += max(0, 15 - juice) * 1.5
        
        if value_pct > 5:
            score += min(15, value_pct * 0.5)
        elif value_pct > 2:
            score += 5
        elif value_pct > 0:
            score += 2
        
        # 赔率区间偏置
        if labels[i] == '主胜':
            if 1.30 <= o <= 1.80:
                score += 8
            elif 1.80 < o <= 2.50:
                score += 5
            elif 2.50 < o <= 4.00:
                score += 1
        elif labels[i] == '客胜':
            if 1.80 <= o <= 3.00:
                score += 4
            elif o > 3.00 and value_pct > 10:
                score += 6
        elif labels[i] == '平局':
            if 2.80 <= o <= 3.60:
                score += 6 if value_pct > 5 else 2
            elif o > 3.60 and value_pct > 10:
                score += 4
        
        # 均衡度
        odds_range = max(odds) - min(odds)
        if odds_range < 1.0 and labels[i] in ['主胜', '客胜']:
            score += 3
        elif odds_range > 3.0 and labels[i] == '客胜':
            score += 2
        
        options.append({
            'label': labels[i],
            'odds': o,
            'value_pct': round(value_pct, 1),
            'ev': round(ev * 100, 1),
            'score': round(score, 1),
        })
    
    if not options:
        return None
    options.sort(key=lambda x: -x['score'])
    return options

def make_recommendation(m):
    """对单场比赛生成推荐（V4无偏见）"""
    try:
        h, d, a = float(m['h']), float(m['d']), float(m['a'])
    except:
        return None
    
    options = evaluate_options(h, d, a)
    if not options:
        return None
    
    best = options[0]
    
    # 信心度
    conf_score = 0
    if best['score'] >= 25: conf_score += 3
    elif best['score'] >= 18: conf_score += 2
    elif best['score'] >= 10: conf_score += 1
    
    if best['ev'] > 10: conf_score += 2
    elif best['ev'] > 5: conf_score += 1
    elif best['ev'] <= 0: conf_score -= 1
    
    if best['value_pct'] > 10: conf_score += 2
    elif best['value_pct'] > 5: conf_score += 1
    
    if 1.30 <= best['odds'] <= 4.00: conf_score += 1
    
    if conf_score >= 6: confidence = '★★★★★'
    elif conf_score >= 4: confidence = '★★★★'
    elif conf_score >= 2: confidence = '★★★'
    elif conf_score >= 0: confidence = '★★'
    else: confidence = '★'
    
    return {
        'label': best['label'],
        'odds': best['odds'],
        'score': best['score'],
        'value': best['value_pct'],
        'ev': best['ev'],
        'confidence': confidence,
        'all_options': options,
    }

def main():
    print('='*65)
    print('竞彩价值投注模型 · 历史回测 (V4无偏见)')
    print('='*65)
    
    matches = fetch_all_results()
    print(f'\n📦 获取到 {len(matches)} 场历史比赛')
    
    valid = [m for m in matches if m.get('h') and m.get('a') and m.get('sectionsNo999')]
    print(f'📊 有效数据: {len(valid)} 场')
    
    results = []
    for m in valid:
        rec = make_recommendation(m)
        if not rec:
            continue
        actual = get_result(m['sectionsNo999'])
        if not actual:
            continue
        
        correct = (rec['label'] == actual)
        results.append({
            'date': m['matchDate'],
            'league': m.get('leagueName', ''),
            'home': m['homeTeam'],
            'away': m['awayTeam'],
            'score': m['sectionsNo999'],
            'odds': f"{float(m['h']):.2f}/{float(m['d']):.2f}/{float(m['a']):.2f}",
            'recommend': rec['label'],
            'rec_odds': rec['odds'],
            'actual': actual,
            'correct': correct,
            'score': rec['score'],
            'value': rec['value'],
            'ev': rec['ev'],
            'confidence': rec['confidence'],
            'all_options': rec['all_options'],
        })
    
    total = len(results)
    correct_count = sum(1 for r in results if r['correct'])
    wrong_count = total - correct_count
    accuracy = correct_count / total * 100 if total else 0
    
    print(f'\n📋 回测覆盖: {total} 场推荐')
    print(f'✅ 正确: {correct_count} 场')
    print(f'❌ 错误: {wrong_count} 场')
    print(f'📈 综合准确率: {accuracy:.1f}%')
    print(f'🎲 随机概率(33%基准): {"✅ 高于" if accuracy > 33 else "❌ 低于"}随机')
    
    # 按推荐类型分层
    print(f'\n📊 推荐类型分析:')
    for opt in ['主胜', '平局', '客胜']:
        group = [r for r in results if r['recommend'] == opt]
        if group:
            c = sum(1 for r in group if r['correct'])
            print(f'  {opt}: {len(group)}场, 正确{c}场, 准确率{c/len(group)*100:.1f}%, 占总推荐{len(group)/total*100:.1f}%')
    
    # 按信心度分层
    print(f'\n📊 信心分层:')
    for star in ['★★★★★', '★★★★', '★★★', '★★', '★']:
        group = [r for r in results if r['confidence'] == star]
        if group:
            c = sum(1 for r in group if r['correct'])
            print(f'  {star}: {len(group)}场, 正确{c}场, 准确率{c/len(group)*100:.1f}%')
    
    # 正EV推荐准确率
    pos_ev = [r for r in results if r['ev'] > 0]
    neg_ev = [r for r in results if r['ev'] <= 0]
    if pos_ev:
        ce = sum(1 for r in pos_ev if r['correct'])
        print(f'\n💰 正EV(EV>0)推荐: {len(pos_ev)}场, 正确{ce}场, 准确率{ce/len(pos_ev)*100:.1f}%')
    if neg_ev:
        cne = sum(1 for r in neg_ev if r['correct'])
        print(f'💸 负EV(EV≤0)推荐: {len(neg_ev)}场, 正确{cne}场, 准确率{cne/len(neg_ev)*100:.1f}%')
    
    # 模拟投注效果
    stake_per_bet = 100
    total_cost = total * stake_per_bet
    total_return = 0
    for r in results:
        if r['correct']:
            total_return += stake_per_bet * r['rec_odds']
    net = total_return - total_cost
    roi = (total_return / total_cost - 1) * 100 if total_cost else 0
    
    print(f'\n💰 模拟投注（每场100元，共{total}场）:')
    print(f'  总投入: {total_cost}元')
    print(f'  总回报: {total_return:.0f}元')
    print(f'  净盈亏: {net:+.0f}元')
    print(f'  ROI: {roi:+.1f}%')
    
    # 仅正EV模拟
    if pos_ev:
        pe_cost = len(pos_ev) * stake_per_bet
        pe_return = sum(stake_per_bet * r['rec_odds'] for r in pos_ev if r['correct'])
        print(f'\n💰 仅正EV投注（{len(pos_ev)}场）:')
        print(f'  投入: {pe_cost}元, 回报: {pe_return:.0f}元, 净盈亏: {pe_return-pe_cost:+.0f}元, ROI: {(pe_return/pe_cost-1)*100:.1f}%')
    
    # 显示最近结果
    print(f'\n📋 最近5场回测明细:')
    print(f'{"日期":>10} {"主队":>8} vs {"客队":>8} {"推荐":>6} {"赔率":>5} {"实绩":>4} {"EV":>6} {"✓/✗":>3}')
    print('-'*60)
    for r in results[-5:]:
        mark = '✅' if r['correct'] else '❌'
        print(f'{r["date"]:>10} {r["home"]:>8} vs {r["away"]:>8} {r["recommend"]:>6} {r["rec_odds"]:>5} {r["actual"]:>4} {r["ev"]:>+5.1f}% {mark:>3}')

if __name__ == '__main__':
    main()
