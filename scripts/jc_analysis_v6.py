"""
竞彩 V6 全管道：ELO + 泊松模型混合分析
=====================================
1. 从 football-data.org 拉取最新比赛数据
2. 计算 ELO 评分 + 训练泊松模型
3. 预测赛果并生成推荐
4. 输出 jc_matches.json

用法: python scripts/jc_analysis_v6.py
"""

import json, os, sys, math
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
sys.path.insert(0, PROJECT_ROOT)

from poisson_model import (
    TeamStatsCalculator, match_score_prob, top_score_probs,
    poisson_value_bets, kelly_fraction
)

API_KEY = "1163986726a345ffb7093db9e34a5e3f"
COMPETITION_ID = 2000
ELO_K = 32
ELO_DEFAULT = 1500

# ===== 球队名称映射 (竞彩中文 → football-data.org 英文) =====
CN_TO_EN = {
    "西班牙": "Spain", "奥地利": "Austria",
    "葡萄牙": "Portugal", "克罗地亚": "Croatia",
    "瑞士": "Switzerland", "阿尔及利亚": "Algeria",
    "澳大利亚": "Australia", "埃及": "Egypt",
    "哥伦比亚": "Colombia", "加纳": "Ghana",
    "加拿大": "Canada", "摩洛哥": "Morocco",
    "巴拉圭": "Paraguay", "法国": "France",
    "巴西": "Brazil", "挪威": "Norway",
    "墨西哥": "Mexico", "英格兰": "England",
    "美国": "United States", "比利时": "Belgium",
    "阿根廷": "Argentina", "佛得角": "Cape Verde Islands",
    "乌拉圭": "Uruguay", "沙特": "Saudi Arabia",
    "伊朗": "Iran", "荷兰": "Netherlands",
    "日本": "Japan", "韩国": "South Korea",
    "德国": "Germany", "塞内加尔": "Senegal",
    "厄瓜多尔": "Ecuador", "卡塔尔": "Qatar",
    "瑞典": "Sweden", "突尼斯": "Tunisia",
    "土耳其": "Turkey", "库拉索": "Curaçao",
    "捷克": "Czechia", "南非": "South Africa",
    "新西兰": "New Zealand", "苏格兰": "Scotland",
    "波黑": "Bosnia-Herzegovina", "海地": "Haiti",
    "科特迪瓦": "Ivory Coast", "伊拉克": "Iraq",
    "乌兹别克斯坦": "Uzbekistan", "约旦": "Jordan",
    "刚果": "Congo DR", "巴拿马": "Panama",
    "巴拉": "Paraguay",
}

# 英文 → 中文 (用于展示)
EN_TO_CN = {v: k for k, v in CN_TO_EN.items()}


# ===== ELO 评分系统 =====

def expected_score(ra, rb):
    return 1.0 / (1 + math.pow(10, (rb - ra) / 400.0))


def update_elo(home_elo, away_elo, home_goals, away_goals):
    actual_home = 1.0 if home_goals > away_goals else (0.5 if home_goals == away_goals else 0.0)
    actual_away = 1.0 - actual_home
    exp_home = expected_score(home_elo, away_elo)
    exp_away = 1.0 - exp_home
    goal_diff = abs(home_goals - away_goals)
    goal_margin = math.log(goal_diff + 1) / math.log(3) if goal_diff > 0 else 0
    k = ELO_K * (1 + goal_margin * 0.5)
    new_home = home_elo + k * (actual_home - exp_home)
    new_away = away_elo + k * (actual_away - exp_away)
    return round(new_home, 1), round(new_away, 1)


def compute_elo_ratings(matches):
    elo = {}
    sorted_matches = sorted(matches, key=lambda m: m.get("date", ""))
    for m in sorted_matches:
        home = m.get("home", "")
        away = m.get("away", "")
        hs = m.get("home_score", 0)
        aws = m.get("away_score", 0)
        if home not in elo:
            elo[home] = ELO_DEFAULT
        if away not in elo:
            elo[away] = ELO_DEFAULT
        home_elo, away_elo = update_elo(elo[home], elo[away], hs, aws)
        elo[home] = home_elo
        elo[away] = away_elo
    return elo


# ===== 比赛推荐生成 =====

def odds_from_model(home_prob, draw_prob, away_prob):
    eps = 0.001
    return [
        round(1.0 / max(eps, home_prob), 2),
        round(1.0 / max(eps, draw_prob), 2),
        round(1.0 / max(eps, away_prob), 2),
    ]


def extract_team(match, key):
    """从API比赛对象中提取球队名称字符串"""
    val = match.get(key, "")
    if isinstance(val, dict):
        return val.get("name") or ""
    return val or ""


def generate_recommendations(upcoming, coefficients, league_avg_home, league_avg_away, elo, results):
    recs = []

    for m in upcoming:
        try:
            home = extract_team(m, "homeTeam")
            away = extract_team(m, "awayTeam")

            if not home or not away:
                continue

            match_date = (m.get("utcDate") or "")[:10]
            match_time = ""
            if m.get("utcDate"):
                try:
                    dt = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
                    match_time = dt.strftime("%H:%M")
                except:
                    match_time = ""

            home_elo = elo.get(home, ELO_DEFAULT)
            away_elo = elo.get(away, ELO_DEFAULT)
            elo_diff = home_elo - away_elo

            stage = m.get("stage", "GROUP_STAGE") or "GROUP_STAGE"
            stage_map = {
                "GROUP_STAGE": "小组赛", "LAST_16": "1/8决赛",
                "QUARTER_FINALS": "1/4决赛", "SEMI_FINALS": "半决赛",
                "THIRD_PLACE": "季军赛", "FINAL": "决赛",
            }
            stage_cn = stage_map.get(stage, stage)

            hc = coefficients.get(home, {})
            ac = coefficients.get(away, {})

            MIN_COEF = 0.30
            ha = max(hc.get("home_attack", 1.0), MIN_COEF)
            hd = max(hc.get("home_defense", 1.0), MIN_COEF)
            aa = max(ac.get("away_attack", 1.0), MIN_COEF)
            ad = max(ac.get("away_defense", 1.0), MIN_COEF)

            hp, dp, ap, sm = match_score_prob(ha, aa, hd, ad, league_avg_home, league_avg_away)
            top_scores = top_score_probs(sm, 5)
            fair_odds = odds_from_model(hp, dp, ap)

            elo_fav = "主胜" if elo_diff > 100 else ("客胜" if elo_diff < -100 else "平局")
            model_fav = "主胜" if hp > dp and hp > ap else ("客胜" if ap > dp and ap > hp else "平局")
            max_prob = max(hp, dp, ap)

            if hp > dp and hp > ap:
                direction = "主胜"; prob_val = hp; odds_val = max(fair_odds[0], 1.01)
            elif ap > dp and ap > hp:
                direction = "客胜"; prob_val = ap; odds_val = max(fair_odds[2], 1.01)
            else:
                direction = "平局"; prob_val = dp; odds_val = max(fair_odds[1], 1.01)

            if max_prob >= 0.55:
                confidence = "★★★"
            elif max_prob >= 0.45:
                confidence = "★★"
            else:
                confidence = "★"

            reasons = []
            is_aligned = (elo_fav == model_fav) or (abs(elo_diff) < 100)
            is_confident = max_prob > 0.45

            if is_aligned and is_confident:
                reasons.append(f"ELO评分支持({home}:{home_elo:.0f}, {away}:{away_elo:.0f})")
                reasons.append(f"泊松模型看好{direction}({prob_val*100:.0f}%)")
            if abs(elo_diff) > 200 and max_prob > 0.50:
                reasons.append(f"实力差距明显(ELO差{elo_diff:.0f}分)")
            if abs(hp - ap) < 0.10 and max_prob < 0.40:
                reasons.append("伯仲之间，建议观望")

            team_stats = {}
            for team_name in [home, away]:
                for r in results:
                    if r.get("status") != "finished":
                        continue
                    if r.get("home") == team_name or r.get("away") == team_name:
                        is_home = r.get("home") == team_name
                        opponent = r.get("away") if is_home else r.get("home")
                        gf = r.get("home_score") if is_home else r.get("away_score")
                        ga = r.get("away_score") if is_home else r.get("home_score")
                        if team_name not in team_stats:
                            team_stats[team_name] = {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "opponents": []}
                        ts = team_stats[team_name]
                        ts["played"] += 1; ts["gf"] += gf; ts["ga"] += ga
                        ts["opponents"].append(opponent)
                        if gf > ga: ts["wins"] += 1
                        elif gf == ga: ts["draws"] += 1
                        else: ts["losses"] += 1

            rec = {
                "homeTeam": home, "awayTeam": away,
                "matchDate": match_date, "matchTime": match_time,
                "stage": stage_cn,
                "recommend": direction, "recommend_odds": odds_val,
                "confidence": confidence,
                "fav_team": home if hp > ap else away,
                "fav_odds": fair_odds[0] if hp > ap else fair_odds[2],
                "fair_odds": fair_odds,
                "model_prob": {"home_pct": round(hp * 100, 1), "draw_pct": round(dp * 100, 1), "away_pct": round(ap * 100, 1)},
                "elo_rating": {home: round(home_elo, 0), away: round(away_elo, 0)},
                "top_scores": [{"score": s, "prob": p} for s, p in top_scores],
                "reasons": reasons, "team_stats": team_stats,
            }
            recs.append(rec)
        except Exception as e:
            print(f"    ⚠️ 处理 {home if 'home' in dir() else '?'} vs {away if 'away' in dir() else '?'} 出错: {e}")
            import traceback
            traceback.print_exc()

    return recs


# ===== 反热门分析 =====

def fade_overrated_favorites(recs):
    """
    用真实市场赔率检测被高估热门
    逻辑: 市场热门赔率<1.6 但泊松模型不看好该方向(模型认为另一方向更可能)
    """
    faded = []
    for r in recs:
        market_odds = r.get("market_odds")
        if not market_odds or len(market_odds) != 3:
            continue

        had = market_odds
        total_implied = 1/had[0] + 1/had[1] + 1/had[2]
        labels = ["主胜", "平局", "客胜"]

        # 市场热门方向(去水后概率最高)
        market_fair = [1/o/total_implied for o in had]
        market_fav_idx = market_fair.index(max(market_fair))
        market_fav_odds = had[market_fav_idx]

        # 泊松模型看好方向
        hp = r["model_prob"]["home_pct"] / 100
        dp = r["model_prob"]["draw_pct"] / 100
        ap = r["model_prob"]["away_pct"] / 100
        model_probs = [hp, dp, ap]
        model_fav_idx = model_probs.index(max(model_probs))
        model_max = max(model_probs)

        # 判断: 市场热门赔率低(<1.6) 但模型方向和市场方向不一致
        is_market_hot = market_fav_odds < 1.6
        is_disagreed = market_fav_idx != model_fav_idx
        is_model_uncertain = model_max < 0.55  # 模型也不是特别有把握

        if is_market_hot and is_disagreed:
            alt_label = labels[model_fav_idx]
            alt_odds = had[model_fav_idx]

            team_stats_text = ""
            hot_team = r["homeTeam"] if market_fav_idx == 0 else (r["awayTeam"] if market_fav_idx == 2 else "双方")
            if r.get("team_stats"):
                ts = r["team_stats"].get(r["homeTeam"] if market_fav_idx == 0 else r["awayTeam"] if market_fav_idx == 2 else r["homeTeam"], {})
                if ts:
                    team_stats_text = f"{ts.get('played',0)}场{ts.get('wins',0)}胜, 场均{round(ts.get('gf',0)/max(1,ts.get('played',1)),1)}球"

            r_copy = dict(r)
            r_copy["recommend"] = alt_label
            r_copy["recommend_odds"] = alt_odds
            r_copy["fav_odds"] = market_fav_odds
            r_copy["fav_team"] = hot_team
            r_copy["confidence"] = "★★" if model_max > 0.40 else "★"
            r_copy["reasons"] = list(r.get("reasons", []))
            reason = (f"市场热门({labels[market_fav_idx]}@{market_fav_odds:.2f})与模型分歧, "
                      f"模型看好{alt_label}({model_max*100:.0f}%), 推荐{alt_label}@{alt_odds:.2f}")
            r_copy["reasons"].append(reason)
            if team_stats_text:
                r_copy["reasons"].append(f"热门表现: {team_stats_text}")
            faded.append(r_copy)

    return faded


# ===== 竞彩赔率获取 =====

def fetch_real_odds():
    """从竞彩官网(sporttery.cn)获取实时赔率"""
    from urllib.request import Request, urlopen
    url = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchListV1.qry?clientCode=3001"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.sporttery.cn/", "Origin": "https://www.sporttery.cn"}
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        result = {}
        for day in data.get("value", {}).get("matchInfoList", []):
            for m in day.get("subMatchList", []):
                home_cn = m.get("homeTeamAllName", "")
                away_cn = m.get("awayTeamAllName", "")
                home_en = CN_TO_EN.get(home_cn, home_cn)
                away_en = CN_TO_EN.get(away_cn, away_cn)
                odds_info = {"home_cn": home_cn, "away_cn": away_cn}
                for od in m.get("oddsList", []):
                    code = od.get("poolCode")
                    if code == "HAD":
                        odds_info["had"] = [float(od.get("h",0)), float(od.get("d",0)), float(od.get("a",0))]
                    elif code == "HHAD":
                        odds_info["hhad"] = [float(od.get("h",0)), float(od.get("d",0)), float(od.get("a",0))]
                        odds_info["goal_line"] = od.get("goalLine", "")
                key = (home_en, away_en)
                result[key] = odds_info
        return result
    except Exception as e:
        print(f"  ⚠️ 竞彩赔率获取失败: {e}")
        return {}


# ===== 主流程 =====

def main():
    from urllib.request import Request, urlopen
    from urllib.error import URLError

    print("=" * 55)
    print("  竞彩 V6 全管道分析")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)

    print("\n📡 正在从 football-data.org 拉取数据...")
    try:
        url = f"https://api.football-data.org/v4/competitions/{COMPETITION_ID}/matches"
        req = Request(url, headers={"X-Auth-Token": API_KEY, "User-Agent": "lottery-analyst/1.0"})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        print(f"❌ API 请求失败: {e}")
        return

    all_matches = data.get("matches", [])
    print(f"✅ 共 {len(all_matches)} 场比赛")

    finished = [m for m in all_matches if m.get("status") == "FINISHED"]
    upcoming_raw = [m for m in all_matches if m.get("status") in ("TIMED", "SCHEDULED")]
    print(f"   已完场: {len(finished)} | 未赛: {len(upcoming_raw)}")

    # 训练格式 + ELO格式
    training_data = []
    results_simple = []
    for m in finished:
        home = extract_team(m, "homeTeam")
        away = extract_team(m, "awayTeam")
        sc = m.get("score", {}); fs = sc.get("fullTime", {})
        hs, aws = fs.get("home"), fs.get("away")
        if hs is not None and aws is not None and home and away:
            entry = {"homeTeam": home, "awayTeam": away, "homeGoals": int(hs), "awayGoals": int(aws), "date": (m.get("utcDate") or "")[:10]}
            training_data.append(entry)
            results_simple.append({"home": home, "away": away, "home_score": int(hs), "away_score": int(aws), "date": entry["date"], "status": "finished"})

    print(f"\n🔧 训练数据: {len(training_data)} 场")

    print("\n🏆 计算 ELO 评分...")
    elo = compute_elo_ratings(results_simple)
    sorted_elo = sorted(elo.items(), key=lambda x: -x[1])
    print(f"  共 {len(elo)} 支球队")
    for team, rating in sorted_elo[:10]:
        print(f"  {team:20s} {rating:.0f}")
    print("  ...")

    print("\n📊 训练泊松模型...")
    calculator = TeamStatsCalculator(training_data)
    coefficients, league_avg_home, league_avg_away = calculator.analyze()
    print(f"  联赛平均: 主场 {league_avg_home:.2f} 球/场, 客场 {league_avg_away:.2f} 球/场")
    print(f"  已训练 {len(coefficients)} 支球队")

    model = {
        "trained_at": datetime.now().isoformat(),
        "total_matches": len(training_data),
        "total_teams": len(coefficients),
        "league_avg_home": round(league_avg_home, 3),
        "league_avg_away": round(league_avg_away, 3),
        "coefficients": coefficients,
    }
    model_path = os.path.join(DATA_DIR, "poisson_trained.json")
    with open(model_path, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)
    print(f"✅ 模型已保存: {model_path}")

    print("\n🎯 生成比赛推荐...")
    recs = generate_recommendations(upcoming_raw, coefficients, league_avg_home, league_avg_away, elo, results_simple)
    print(f"  常规推荐: {len(recs)} 场")

    # 5. 获取竞彩真实赔率
    print("\n💰 获取竞彩实时赔率...")
    real_odds = fetch_real_odds()
    odds_available = len(real_odds)
    if odds_available > 0:
        print(f"  ✅ 获取到 {odds_available} 场比赛的赔率")
        for (he, ae), o in real_odds.items():
            had = o.get("had", [])
            if had:
                print(f"    {he:20s} vs {ae:20s}  {had[0]:.2f} / {had[1]:.2f} / {had[2]:.2f}")
    else:
        print("  ⚠️ 使用模型公平赔率代替")

    # 整合真实赔率到推荐
    for r in recs:
        key = (r["homeTeam"], r["awayTeam"])
        if key in real_odds:
            o = real_odds[key]
            if o.get("had"):
                r["market_odds"] = o["had"]
                r["had_odds_cn"] = o.get("had", [])
                r["hhad_odds"] = o.get("hhad", [])
                r["goal_line"] = o.get("goal_line", "")

    # 6. 反热门分析（用真实赔率检测被高估热门）
    print("\n🔥 反被高估热门分析...")
    fade_recs = fade_overrated_favorites(recs)
    print(f"  发现 {len(fade_recs)} 场被高估热门")

    MIN_ODDS = 1.30
    filtered_recs = []
    for r in recs:
        if r["recommend"] == "平局" and r["recommend_odds"] <= 1.05:
            continue
        if r["recommend_odds"] < MIN_ODDS:
            continue
        if r["confidence"] == "★" and r["recommend_odds"] < 2.0:
            continue
        filtered_recs.append(r)

    output_matches = fade_recs if fade_recs else filtered_recs[:min(8, len(filtered_recs))]

    # 输出精简
    matches_json = []
    for r in output_matches:
        hm = EN_TO_CN.get(r["homeTeam"], r["homeTeam"])
        aw = EN_TO_CN.get(r["awayTeam"], r["awayTeam"])
        entry = {
            "homeTeam": r["homeTeam"], "awayTeam": r["awayTeam"],
            "homeTeamCn": hm, "awayTeamCn": aw,
            "matchDate": r["matchDate"], "matchTime": r["matchTime"],
            "stage": r.get("stage", ""),
            "recommend": r["recommend"], "recommend_odds": r["recommend_odds"],
            "confidence": r["confidence"],
            "fav_team": r.get("fav_team", ""), "fav_odds": r.get("fav_odds", 0),
            "market_odds": r.get("market_odds", []),
            "reasons": r.get("reasons", []),
        }
        stats_simple = {}
        if r.get("team_stats"):
            for team, s in r["team_stats"].items():
                stats_simple[team] = {k: s[k] for k in ("played","wins","draws","losses","gf","ga","opponents")}
        entry["team_stats"] = stats_simple
        matches_json.append(entry)

    no_signal = len(upcoming_raw) - len(output_matches)
    # 排除 TBD 比赛
    known_upcoming = sum(1 for m in upcoming_raw if extract_team(m, "homeTeam") and extract_team(m, "awayTeam"))
    no_signal_true = known_upcoming - len(output_matches)

    jc_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "matches": matches_json,
        "summary": {
            "total": len(output_matches),
            "no_signal": max(0, no_signal_true),
            "strategy": "V6 ELO + Poisson 混合模型",
            "data_source": "football-data.org API",
            "total_upcoming": known_upcoming,
        }
    }

    output_path = os.path.join(DATA_DIR, "jc_matches.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(jc_data, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 推荐已写入: {output_path}")
    print(f"   共 {len(output_matches)} 场推荐 ({no_signal_true} 场无信号)")

    print("\n📋 今日推荐:")
    for m in matches_json:
        cn = m.get("homeTeamCn", m["homeTeam"])
        cw = m.get("awayTeamCn", m["awayTeam"])
        market_str = ""
        if m.get("market_odds"):
            mo = m["market_odds"]
            market_str = f" | 市场赔率 {mo[0]:.2f}/{mo[1]:.2f}/{mo[2]:.2f}"
        print(f"  {cn:12s}({m['homeTeam']:20s}) vs {cw:12s}({m['awayTeam']:20s}){market_str}")
        print(f"  → 推荐: {m['recommend']} @{m['recommend_odds']:.2f} [{m['confidence']}]")
        for reason in m.get("reasons", [])[:2]:
            print(f"    ├ {reason}")
        print()

    return jc_data


if __name__ == "__main__":
    main()
