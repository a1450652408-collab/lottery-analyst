"""
泊松分布比分预测模型
基于历史进球数据计算球队攻防系数 → 预期进球 → 比分概率 → 价值投注检测

核心公式:
  λ_home = league_avg_home × home_attack × away_defense
  λ_away = league_avg_away × away_attack × home_defense

算法步骤:
  1. 从比赛历史数据计算各队攻防系数
  2. 用泊松分布计算各种比分的概率
  3. 汇总为胜/平/负概率
  4. 与市场赔率对比，找出价值投注
"""

import math
from datetime import datetime, timedelta
import json, os


# ===== 泊松分布核心函数 =====

def poisson_prob(k, lam):
    """泊松分布概率：P(X=k) = λ^k × e^(-λ) / k!"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def match_score_prob(home_attack, away_attack, home_defense, away_defense,
                     league_avg_home=1.5, league_avg_away=1.2,
                     max_goals=8):
    """
    计算两队交锋的比分概率矩阵

    参数:
      home_attack: 主队攻击系数 (1.0=联赛平均)
      away_attack: 客队攻击系数
      home_defense: 主队防守系数 (1.0=联赛平均)
      away_defense: 客队防守系数
      league_avg_home: 联赛主场场均进球
      league_avg_away: 联赛客场场均进球

    返回:
      (prob_home, prob_draw, prob_away, score_matrix)
      score_matrix = {(h_goals, a_goals): prob}
    """
    lam_h = league_avg_home * home_attack * away_defense
    lam_a = league_avg_away * away_attack * home_defense

    probs_h = [poisson_prob(g, lam_h) for g in range(max_goals + 1)]
    probs_a = [poisson_prob(g, lam_a) for g in range(max_goals + 1)]

    # 比分矩阵 + 汇总
    score_matrix = {}
    prob_home = prob_draw = prob_away = 0.0

    for gh in range(max_goals + 1):
        for ga in range(max_goals + 1):
            p = probs_h[gh] * probs_a[ga]
            if p < 0.0001:
                continue
            score_matrix[(gh, ga)] = p
            if gh > ga:
                prob_home += p
            elif gh == ga:
                prob_draw += p
            else:
                prob_away += p

    total = prob_home + prob_draw + prob_away
    return prob_home / total, prob_draw / total, prob_away / total, score_matrix


def top_score_probs(score_matrix, top_n=5):
    """返回概率最高的前N个比分"""
    sorted_scores = sorted(score_matrix.items(), key=lambda x: -x[1])
    return [(f"{h}-{a}", round(p * 100, 1)) for (h, a), p in sorted_scores[:top_n]]


# ===== 攻防系数计算 =====

class TeamStatsCalculator:
    """
    从历史比赛结果计算各队攻防系数

    所需数据格式（每场比赛）:
    {
        "homeTeam": "队名",
        "awayTeam": "队名",
        "homeGoals": 2,
        "awayGoals": 1,
        "date": "2026-06-11"
    }
    """

    def __init__(self, matches):
        self.matches = matches
        self.team_stats = {}  # team_name -> {gf, ga, home_gf, home_ga, away_gf, away_ga, matches}

    def analyze(self):
        """分析所有比赛，计算各队攻防系数"""
        for m in self.matches:
            home = m.get('homeTeam', '')
            away = m.get('awayTeam', '')
            hg = m.get('homeGoals', 0)
            ag = m.get('awayGoals', 0)

            for team in [home, away]:
                if team not in self.team_stats:
                    self.team_stats[team] = {
                        'gf': 0, 'ga': 0,
                        'home_gf': 0, 'home_ga': 0,
                        'away_gf': 0, 'away_ga': 0,
                        'matches': 0, 'home_matches': 0, 'away_matches': 0
                    }

            # 主队
            self.team_stats[home]['gf'] += hg
            self.team_stats[home]['ga'] += ag
            self.team_stats[home]['home_gf'] += hg
            self.team_stats[home]['home_ga'] += ag
            self.team_stats[home]['matches'] += 1
            self.team_stats[home]['home_matches'] += 1

            # 客队
            self.team_stats[away]['gf'] += ag
            self.team_stats[away]['ga'] += hg
            self.team_stats[away]['away_gf'] += ag
            self.team_stats[away]['away_ga'] += hg
            self.team_stats[away]['matches'] += 1
            self.team_stats[away]['away_matches'] += 1

        # 计算联赛平均值
        total_gf = sum(s['gf'] for s in self.team_stats.values())
        total_matches = sum(s['matches'] for s in self.team_stats.values())

        if total_matches == 0:
            return {}, 0, 0

        avg_goals_per_match = total_gf / (total_matches or 1)

        # 主场/客场平均值
        total_home_g = sum(s['home_gf'] for s in self.team_stats.values())
        total_away_g = sum(s['away_gf'] for s in self.team_stats.values())
        total_home_m = sum(s['home_matches'] for s in self.team_stats.values())
        total_away_m = sum(s['away_matches'] for s in self.team_stats.values())

        league_avg_home = total_home_g / (total_home_m or 1)
        league_avg_away = total_away_g / (total_away_m or 1)

        if league_avg_home == 0:
            league_avg_home = avg_goals_per_match * 0.55
        if league_avg_away == 0:
            league_avg_away = avg_goals_per_match * 0.45

        # 计算各队攻防系数
        coefficients = {}
        for team, s in self.team_stats.items():
            if s['matches'] == 0:
                coefficients[team] = {
                    'attack': 1.0,
                    'defense': 1.0,
                    'home_attack': 1.0,
                    'home_defense': 1.0,
                    'away_attack': 1.0,
                    'away_defense': 1.0,
                    'matches': 0,
                    'confidence': 'none'
                }
                continue

            # 整体攻防
            attack = (s['gf'] / s['matches']) / (avg_goals_per_match or 1)
            defense = (s['ga'] / s['matches']) / (avg_goals_per_match or 1) if avg_goals_per_match > 0 else 1.0

            # 主场攻击 / 主场防守
            home_attack = (s['home_gf'] / max(1, s['home_matches'])) / (league_avg_home or 1)
            home_defense = (s['home_ga'] / max(1, s['home_matches'])) / (league_avg_away or 1)

            # 客场攻击 / 客场防守
            away_attack = (s['away_gf'] / max(1, s['away_matches'])) / (league_avg_away or 1)
            away_defense = (s['away_ga'] / max(1, s['away_matches'])) / (league_avg_home or 1)

            # 数据量置信度
            if s['matches'] >= 5:
                confidence = 'high'
            elif s['matches'] >= 3:
                confidence = 'medium'
            elif s['matches'] >= 1:
                confidence = 'low'
            else:
                confidence = 'none'

            coefficients[team] = {
                'attack': round(attack, 3),
                'defense': round(defense, 3),
                'home_attack': round(home_attack, 3),
                'home_defense': round(home_defense, 3),
                'away_attack': round(away_attack, 3),
                'away_defense': round(away_defense, 3),
                'matches': s['matches'],
                'avg_gf': round(s['gf'] / s['matches'], 2),
                'avg_ga': round(s['ga'] / s['matches'], 2),
                'confidence': confidence
            }

        return coefficients, league_avg_home, league_avg_away


# ===== 投注价值分析 =====

def calc_implied_prob(odds):
    """计算隐含概率和抽水"""
    if any(o <= 0 for o in odds):
        return None, None, 0
    probs = [1 / o for o in odds]
    total = sum(probs)
    fair_probs = [p / total for p in probs]
    juice = (total - 1) * 100
    return probs, fair_probs, juice


def poisson_value_bets(home_prob, draw_prob, away_prob, had_odds, label=""):
    """
    泊松概率 vs 市场赔率 → 价值投注分析

    返回:
      [{'label','odds','model_prob','market_prob','ev','value_gap'}, ...]
    """
    probs, fair_probs, juice = calc_implied_prob(had_odds)
    if not probs:
        return None

    model_probs = [home_prob, draw_prob, away_prob]
    labels = ['主胜', '平局', '客胜']

    results = []
    for i in range(3):
        mp = model_probs[i]  # 泊松模型概率
        fp = fair_probs[i] if i < len(fair_probs) else 0
        op = had_odds[i]

        if op <= 0 or mp <= 0:
            continue

        ev = op * mp - 1
        value_gap = (mp - fp) * 100  # 正值 = 模型比市场更看好

        results.append({
            'label': labels[i],
            'odds': op,
            'model_prob': round(mp * 100, 1),
            'market_prob': round(fp * 100, 1),
            'value_gap': round(value_gap, 1),
            'ev': round(ev * 100, 1),
            'is_value': ev > 0
        })

    results.sort(key=lambda x: -x['ev'])
    return results


def kelly_fraction(odds, estimated_prob, bankroll_pct=0.25):
    """凯利公式：f* = (p × b - q) / b"""
    b = odds - 1
    if b <= 0:
        return 0
    p = estimated_prob
    q = 1 - p
    f = (p * b - q) / b
    return max(0, f * bankroll_pct)


# ===== 系数修正：整合实力评分 =====

def strength_to_coefficients(strength_diff, home_strength=50, away_strength=50):
    """
    将实力评分（0~100）转换为攻防系数的近似值
    当历史比赛数据不足时作为备选方案

    原理: 实力分每差10分 ≈ 攻击力差0.15
    """
    # 基础值1.0 = 平均
    base_attack = 1.0
    base_defense = 1.0

    # 实力差归一化
    # strength_diff = home - away, 范围 -100~100
    # 映射到攻击系数: home_attack = 1.0 + diff/100 * 0.3
    # 映射到防守系数: home_defense = 1.0 - diff/100 * 0.3
    diff_norm = strength_diff / 100.0

    home_attack = 1.0 + diff_norm * 0.3
    away_attack = 1.0 - diff_norm * 0.3
    home_defense = 1.0 - diff_norm * 0.3
    away_defense = 1.0 + diff_norm * 0.3

    return {
        'home_attack': round(home_attack, 3),
        'away_attack': round(away_attack, 3),
        'home_defense': round(home_defense, 3),
        'away_defense': round(away_defense, 3),
        'source': 'strength_estimate',
        'strength_diff': strength_diff
    }


# ===== 比分预测输出 =====

def format_score_prediction(home_team, away_team, home_prob, draw_prob, away_prob,
                            score_matrix, top_scores, home_attack_coef, away_attack_coef,
                            home_defense_coef, away_defense_coef):
    """格式化比分预测结果"""
    lines = [
        f"\n{'=' * 55}",
        f"  泊松模型比分预测",
        f"  {home_team} vs {away_team}",
        f"{'=' * 55}",
        f"  攻防系数:",
        f"    主队攻击={home_attack_coef}  防守={home_defense_coef}",
        f"    客队攻击={away_attack_coef}  防守={away_defense_coef}",
        f"",
        f"  赛果概率:",
        f"    主胜: {home_prob * 100:.1f}%",
        f"    平局: {draw_prob * 100:.1f}%",
        f"    客胜: {away_prob * 100:.1f}%",
        f"",
        f"  最可能比分:",
    ]

    for score_str, pct in top_scores[:5]:
        lines.append(f"    {score_str}  {pct:.1f}%")

    return "\n".join(lines)


# ===== 主函数（测试用）=====

def demo():
    """用示例数据演示泊松模型"""
    print("=" * 55)
    print("  Poisson 泊松模型 - 比分预测演示")
    print("=" * 55)

    # 示例数据：2026世界杯强强对话
    demo_matches = generate_demo_data()
    calculator = TeamStatsCalculator(demo_matches)
    coefficients, league_avg_home, league_avg_away = calculator.analyze()

    print(f"\n联赛场均进球: 主场={league_avg_home:.2f}  客场={league_avg_away:.2f}")
    print(f"\n计算了 {len(coefficients)} 支球队的攻防系数:\n")

    for team, coef in sorted(coefficients.items()):
        print(f"  {team:15s} 攻击={coef['attack']:.3f}  防守={coef['defense']:.3f}  ({coef['matches']}场)")

    # 预测一场比赛
    home = "巴西"
    away = "德国"
    print(f"\n{'=' * 55}")
    print(f"  预测: {home} vs {away}")
    print(f"{'=' * 55}")

    if home in coefficients and away in coefficients:
        hc = coefficients[home]
        ac = coefficients[away]
        print(f"\n  主队({home}): 攻击={hc['home_attack']} 防守={hc['home_defense']}")
        print(f"  客队({away}): 攻击={ac['away_attack']} 防守={ac['away_defense']}")

        hp, dp, ap, sm = match_score_prob(
            hc['home_attack'], ac['away_attack'],
            hc['home_defense'], ac['away_defense'],
            league_avg_home, league_avg_away
        )

        print(f"\n  赛果概率:")
        print(f"    主胜: {hp * 100:.1f}%")
        print(f"    平局: {dp * 100:.1f}%")
        print(f"    客胜: {ap * 100:.1f}%")

        top = top_score_probs(sm, 8)
        print(f"\n  最可能比分:")
        for score_str, pct in top:
            bar = "█" * int(pct / 1.5)
            print(f"    {score_str}: {pct:.1f}% {bar}")

    print()


def generate_demo_data():
    """生成示例比赛数据用于测试"""
    return [
        {"homeTeam": "巴西", "awayTeam": "阿根廷", "homeGoals": 2, "awayGoals": 1, "date": "2026-06-11"},
        {"homeTeam": "德国", "awayTeam": "法国", "homeGoals": 3, "awayGoals": 0, "date": "2026-06-11"},
        {"homeTeam": "英格兰", "awayTeam": "巴西", "homeGoals": 1, "awayGoals": 1, "date": "2026-06-12"},
        {"homeTeam": "法国", "awayTeam": "荷兰", "homeGoals": 2, "awayGoals": 2, "date": "2026-06-12"},
        {"homeTeam": "阿根廷", "awayTeam": "德国", "homeGoals": 0, "awayGoals": 2, "date": "2026-06-13"},
        {"homeTeam": "荷兰", "awayTeam": "英格兰", "homeGoals": 1, "awayGoals": 0, "date": "2026-06-13"},
        {"homeTeam": "巴西", "awayTeam": "法国", "homeGoals": 3, "awayGoals": 1, "date": "2026-06-14"},
        {"homeTeam": "德国", "awayTeam": "英格兰", "homeGoals": 2, "awayGoals": 2, "date": "2026-06-14"},
        {"homeTeam": "阿根廷", "awayTeam": "荷兰", "homeGoals": 1, "awayGoals": 1, "date": "2026-06-15"},
        {"homeTeam": "法国", "awayTeam": "英格兰", "homeGoals": 0, "awayGoals": 0, "date": "2026-06-15"},
        {"homeTeam": "巴西", "awayTeam": "荷兰", "homeGoals": 4, "awayGoals": 0, "date": "2026-06-16"},
        {"homeTeam": "德国", "awayTeam": "巴西", "homeGoals": 1, "awayGoals": 2, "date": "2026-06-17"},
        {"homeTeam": "阿根廷", "awayTeam": "英格兰", "homeGoals": 0, "awayGoals": 3, "date": "2026-06-18"},
        {"homeTeam": "荷兰", "awayTeam": "德国", "homeGoals": 1, "awayGoals": 3, "date": "2026-06-19"},
        {"homeTeam": "法国", "awayTeam": "阿根廷", "homeGoals": 2, "awayGoals": 1, "date": "2026-06-20"},
        {"homeTeam": "英格兰", "awayTeam": "法国", "homeGoals": 1, "awayGoals": 0, "date": "2026-06-21"},
        {"homeTeam": "巴西", "awayTeam": "德国", "homeGoals": 2, "awayGoals": 0, "date": "2026-06-22"},
        {"homeTeam": "阿根廷", "awayTeam": "巴西", "homeGoals": 1, "awayGoals": 2, "date": "2026-06-23"},
        {"homeTeam": "荷兰", "awayTeam": "法国", "homeGoals": 0, "awayGoals": 3, "date": "2026-06-24"},
        {"homeTeam": "英格兰", "awayTeam": "德国", "homeGoals": 2, "awayGoals": 2, "date": "2026-06-25"},
    ]


if __name__ == '__main__':
    demo()
