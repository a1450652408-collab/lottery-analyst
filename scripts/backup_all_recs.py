#!/usr/bin/env python3
"""
全彩种推荐历史备份脚本

读取 index_modified.html 中的彩票数据，对每一期跑推荐算法，
记录推荐号码 + 实际命中情况，存入 data/all_recommendations_archive.json。
"""

import json, re, os, sys, time, math

# ====== 路径 ======
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(PROJECT_ROOT, "index_modified.html")
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "data", "all_recommendations_archive.json")

# ====== 加载 gen_recommendations.py 的算法 ======
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "scripts"))
from gen_recommendations import (
    recommend_kl8, recommend_kl8_enhanced, kl8_dantuo, select_kl8_9dan,
    recommend_lotto, recommend_lotto_enhanced,
    recommend_digit,
    get_nums, get_blue
)


# ====== 工具函数 ======
def load_lottery_data():
    """从 index_modified.html 读取彩票数据"""
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    m = re.search(r"window\.__LOTTERY_DATA\s*=\s*(\{.+?\});", html, re.DOTALL)
    if not m:
        print("ERROR: 未找到 __LOTTERY_DATA")
        sys.exit(1)
    return json.loads(m.group(1))


def calc_kl8_xuan_prize(rec_nums, drawn_set, xuan_n):
    """
    快乐8 选N玩法奖金计算
    """
    hit = sum(1 for n in rec_nums if n in drawn_set)
    # 快乐8 选N中M 奖金表
    prize_table = {
        1: {1: 4.6},
        2: {2: 19},
        3: {3: 53, 2: 3},
        4: {4: 100, 3: 5},
        5: {5: 1000, 4: 21, 3: 3},
        6: {6: 2880, 5: 30, 4: 10, 3: 3},
        7: {7: 10000, 6: 288, 5: 28, 4: 4},
        8: {8: 50000, 7: 800, 6: 88, 5: 10},
        9: {9: 300000, 8: 2000, 7: 200, 6: 20},
        10: {10: 5000000, 9: 8000, 8: 800, 7: 80, 6: 5},
        11: {11: 0, 10: 0, 9: 0, 8: 0, 7: 0, 6: 0},
        12: {12: 0, 11: 0, 10: 0, 9: 0, 8: 0, 7: 0},
        13: {13: 0, 12: 0, 11: 0, 10: 0, 9: 0, 8: 0},
    }
    table = prize_table.get(xuan_n, {})
    return table.get(hit, 0), hit


def calc_digit_prize(rec_nums, drawn_nums, count):
    """
    数字彩直选奖金：全部位置匹配=1040(fc3d/pl3)或10万(pl5)
    注意：FC3D/PL3的直选必须位置一致，但这里rec_nums是单个数字的组合
    简化：只记录逐位命中数
    """
    if len(rec_nums) != count or len(drawn_nums) < count:
        return 0, 0
    # 逐位对比
    pos_hits = sum(1 for i in range(count) if i < len(rec_nums) and i < len(drawn_nums) and rec_nums[i] == drawn_nums[i])
    # 直选：全部命中=中奖
    if pos_hits == count:
        prize = {3: 1040, 5: 100000, 7: 0}.get(count, 0)
        return prize, pos_hits
    return 0, pos_hits


def calc_lotto_prize(rec_reds, drawn_reds, rec_blues, drawn_blues):
    """乐透型（SSQ/DLT/QLC）命中统计"""
    red_hit = len(set(rec_reds) & set(drawn_reds))
    blue_hit = 0
    if rec_blues:
        if isinstance(drawn_blues, list):
            blue_hit = len(set(rec_blues) & set(drawn_blues))
        else:
            blue_hit = 1 if rec_blues[0] == drawn_blues else 0
    return red_hit, blue_hit


def make_kl8_per_play_recommendations(voted_list, recent):
    """
    选一~选十的号码池推荐
    使用 gen_recommendations.py 的 voted_list 作为基础号码池
    """
    pool = voted_list[:35]  # 35码池
    return {
        "xuan1": sorted(pool[:5])[:1],
        "xuan2": sorted(pool[:5])[:2],
        "xuan3": sorted(pool[:5])[:3],
        "xuan4": sorted(pool[:5])[:4],
        "xuan5": sorted(pool[:5])[:5],
        "xuan6": sorted(pool[:5])[:6],
        "xuan7": sorted(pool[:15])[:7],
        "xuan8": sorted(pool[:15])[:8],
        "xuan9": sorted(pool[:20])[:9],
        "xuan10": sorted(pool[:20])[:10],
    }


# ====== 各彩种备份函数 ======
def calc_zone15_dantuo(training, period_data):
    """
    三区均衡法：1-5/6-10/11-15各取最热号做胆，剩余取近10期最热7个做拖
    返回: {dan, tuo, dan_hit, tuo_hit}
    """
    from collections import Counter
    
    # 近5期各区间最热号 (training是oldest-first, 最后5个是最新的)
    zones = [(1,5), (6,10), (11,15)]
    recent5 = training[-5:] if len(training) >= 5 else training
    freq5 = Counter()
    for item in recent5:
        for n in item.get("n", item.get("r", [])):
            if 1 <= n <= 15: freq5[n] += 1
    
    dans = []
    for lo, hi in zones:
        zone_nums = [n for n in range(lo, hi+1)]
        best = max(zone_nums, key=lambda x: freq5.get(x, 0))
        dans.append(best)
    dans.sort()
    
    # 近10期1-15取拖（排除胆码, training是oldest-first, 最后10个是最新的）
    recent10 = training[-10:] if len(training) >= 10 else training
    freq10 = Counter()
    for item in recent10:
        for n in item.get("n", item.get("r", [])):
            if 1 <= n <= 15 and n not in dans: freq10[n] += 1
    
    tuos = [n for n, _ in freq10.most_common(7)]
    tuos.sort()
    
    # 命中
    drawn = set(period_data.get("n", period_data.get("r", [])))
    dan_hit = sorted([n for n in dans if n in drawn])
    tuo_hit = sorted([n for n in tuos if n in drawn])
    
    return {"dan": dans, "tuo": tuos, "dan_hit": dan_hit, "tuo_hit": tuo_hit, "dan_hit_count": len(dan_hit), "tuo_hit_count": len(tuo_hit)}


def backup_kl8(all_data):
    """快乐8全推荐备份（含选一~选十 + 20码 + 胆拖 + 9胆 + 橙紫卡）"""
    records = []
    train_win = 50
    # 数据从 HTML 读取是 newest-first，需要反转成 oldest-first
    all_data = list(reversed(all_data))
    
    for idx in range(train_win, len(all_data)):
        period_data = all_data[idx]
        drawn = get_nums(period_data)
        drawn_set = set(drawn)
        period = period_data.get("p", "?")
        date = period_data.get("d", "?")
        
        # 训练数据：前50期
        training = all_data[idx - train_win:idx]
        
        # 20码基础推荐
        try:
            voted_20, voted_list = recommend_kl8(training, rMax=80, rC=20)
            e20, evoted_list = recommend_kl8_enhanced(training, rMax=80, rC=20)
            dantuo = kl8_dantuo(voted_list, training, rC=20)
            edantuo = kl8_dantuo(evoted_list, training, rC=20)
            d9 = select_kl8_9dan(training, evoted_list)
            
            # 选一~选十
            per_play = make_kl8_per_play_recommendations(voted_list, training)
            e_per_play = make_kl8_per_play_recommendations(evoted_list, training)
            
            # 记录命中
            hit_20 = sorted([n for n in voted_20 if n in drawn_set])
            e_hit_20 = sorted([n for n in e20 if n in drawn_set])
            
            per_play_hits = {}
            for key, nums in per_play.items():
                xuan_n = int(key.replace("xuan", ""))
                prize, hit_count = calc_kl8_xuan_prize(nums, drawn_set, xuan_n)
                per_play_hits[key] = {
                    "rec": nums,
                    "hit": sorted([n for n in nums if n in drawn_set]),
                    "hit_count": hit_count,
                    "prize": prize
                }
            
            e_per_play_hits = {}
            for key, nums in e_per_play.items():
                xuan_n = int(key.replace("xuan", ""))
                prize, hit_count = calc_kl8_xuan_prize(nums, drawn_set, xuan_n)
                e_per_play_hits[key] = {
                    "rec": nums,
                    "hit": sorted([n for n in nums if n in drawn_set]),
                    "hit_count": hit_count,
                    "prize": prize
                }
            
            dantuo_hits = []
            for dt in dantuo:
                dan_hit = sorted([n for n in dt["dan"] if n in drawn_set])
                tuo_hit = sorted([n for n in dt["tuo"] if n in drawn_set])
                dantuo_hits.append({"dan": dt["dan"], "tuo": dt["tuo"], "dan_hit": dan_hit, "tuo_hit": tuo_hit})
            
            edantuo_hits = []
            for dt in edantuo:
                dan_hit = sorted([n for n in dt["dan"] if n in drawn_set])
                tuo_hit = sorted([n for n in dt["tuo"] if n in drawn_set])
                edantuo_hits.append({"dan": dt["dan"], "tuo": dt["tuo"], "dan_hit": dan_hit, "tuo_hit": tuo_hit})
            
            d9_hit = sorted([n for n in d9 if n in drawn_set])
            
            # 三区均衡法（1-15 选五3胆7拖）
            zone15 = calc_zone15_dantuo(training, period_data)
            
            records.append({
                "period": period, "date": date,
                "basic": {"rec": sorted(voted_20), "hit": hit_20, "hit_count": len(hit_20)},
                "enhanced": {"rec": sorted(e20), "hit": e_hit_20, "hit_count": len(e_hit_20)},
                "dantuo": dantuo_hits,
                "enhanced_dantuo": edantuo_hits,
                "d9dan": {"rec": d9, "hit": d9_hit, "hit_count": len(d9_hit)},
                "per_play": per_play_hits,
                "enhanced_per_play": e_per_play_hits,
                "zone15_xuan5": zone15,
            })
        except Exception as ex:
            records.append({"period": period, "date": date, "error": str(ex)[:100]})
    
    return records


def backup_digit(all_data, type_name, pos_count):
    """数字彩（FC3D/PL3/PL5/QXC）推荐备份"""
    records = []
    train_win = 30
    all_data = list(reversed(all_data))
    
    for idx in range(train_win, len(all_data)):
        period_data = all_data[idx]
        drawn = get_nums(period_data)
        period = period_data.get("p", "?")
        date = period_data.get("d", "?")
        
        training = all_data[idx - train_win:idx]
        
        try:
            r = recommend_digit(training, pos_count)
            # basic: 每位置Top3
            basic_rec = [r["basic"][i][0] for i in range(pos_count)]
            alt_rec = [r["basic"][i][1] for i in range(pos_count)]
            third_rec = [r["basic"][i][2] for i in range(pos_count)]
            
            # 逐位命中
            pos_hits = {str(i): {
                "rec": r["basic"][i],
                "hit": r["basic"][i][0] if i < len(drawn) and r["basic"][i][0] == drawn[i] else None
            } for i in range(pos_count)}
            
            # 直选命中
            z1_prize, z1_hits = calc_digit_prize(basic_rec, drawn, pos_count)
            z2_prize, z2_hits = calc_digit_prize(alt_rec, drawn, pos_count)
            z3_prize, z3_hits = calc_digit_prize(third_rec, drawn, pos_count)
            
            # 胆拖命中
            dantuo_hits = []
            for i, dt in enumerate(r["dantuo"]):
                # 胆拖的命中：胆码命中且位置匹配
                dan_n = dt["dan"][0]
                dan_pos = dt.get("pos", i)
                dan_match = dan_pos < len(drawn) and dan_n == drawn[dan_pos]
                tuo_hit_rates = []
                for tn in dt["tuo"]:
                    # 如果拖码在该位置也匹配
                    match = dan_pos < len(drawn) and tn == drawn[dan_pos]
                    tuo_hit_rates.append(match)
                dantuo_hits.append({
                    "pos": dan_pos,
                    "dan": {"num": dan_n, "hit": dan_match},
                    "tuo": dt["tuo"],
                    "tuo_hits": [tn for ti, tn in enumerate(dt["tuo"]) if ti < len(tuo_hit_rates) and tuo_hit_rates[ti]]
                })
            
            # 多注命中
            multi_hits = []
            for mi, mnums in enumerate(r["multi"]):
                p, h = calc_digit_prize(mnums, drawn, pos_count)
                multi_hits.append({"rec": mnums, "hit_count": h, "prize": p})
            
            records.append({
                "period": period, "date": date, "pos": pos_count,
                "basic": {
                    "z1": {"rec": basic_rec, "hit_count": z1_hits, "prize": z1_prize},
                    "z2": {"rec": alt_rec, "hit_count": z2_hits, "prize": z2_prize},
                    "z3": {"rec": third_rec, "hit_count": z3_hits, "prize": z3_prize}
                },
                "dantuo": dantuo_hits,
                "multi": multi_hits,
                "enhanced": {
                    "pos_top5": [sorted(r["scored_pos"][pi])[:5] for pi in range(pos_count)]
                }
            })
        except Exception as ex:
            records.append({"period": period, "date": date, "error": str(ex)[:100]})
    
    return records


def backup_lotto(all_data, type_name, r_max, r_count, b_max, b_count):
    """乐透型（SSQ/DLT/QLC）推荐备份"""
    records = []
    train_win = 15
    all_data = list(reversed(all_data))
    
    for idx in range(train_win, len(all_data)):
        period_data = all_data[idx]
        drawn_r = get_nums(period_data)
        drawn_b = get_blue(period_data)
        period = period_data.get("p", "?")
        date = period_data.get("d", "?")
        
        training = all_data[idx - train_win:idx]
        
        try:
            r = recommend_lotto(training, r_max, r_count, b_max, b_count)
            er = recommend_lotto_enhanced(training, r_max, r_count, b_max, b_count)
            
            red_hit, blue_hit = calc_lotto_prize(r["reds"], drawn_r, r["blues"], drawn_b)
            e_red_hit, e_blue_hit = calc_lotto_prize(er["reds"], drawn_r, er["blues"], drawn_b)
            
            records.append({
                "period": period, "date": date,
                "basic": {
                    "reds": {"rec": r["reds"], "hit": sorted(set(r["reds"]) & set(drawn_r)), "hit_count": red_hit},
                    "blues": {"rec": r["blues"], "hit": sorted(set(r["blues"]) & set(drawn_b)), "hit_count": blue_hit}
                },
                "enhanced": {
                    "reds": {"rec": er["reds"], "hit": sorted(set(er["reds"]) & set(drawn_r)), "hit_count": e_red_hit},
                    "blues": {"rec": er["blues"], "hit": sorted(set(er["blues"]) & set(drawn_b)), "hit_count": e_blue_hit}
                },
                "dantuo": [{"dan": dt["dan"], "tuo": dt["tuo"],
                           "dan_hit": sorted(set(dt["dan"]) & set(drawn_r)),
                           "tuo_hit": sorted(set(dt["tuo"]) & set(drawn_r)),
                           "blue_dan": dt.get("blueDan", []), "blue_tuo": dt.get("blueTuo", [])}
                          for dt in r["dantuo"]],
            })
        except Exception as ex:
            records.append({"period": period, "date": date, "error": str(ex)[:100]})
    
    return records


# ====== 主流程 ======
def main():
    print("=" * 55)
    print("  全彩种推荐历史备份")
    print("=" * 55)
    
    # 加载数据
    data = load_lottery_data()
    print(f"\n彩种: {', '.join(data.keys())}")
    
    all_results = {}
    
    # ===== KL8 =====
    kl8_data = data.get("kl8", [])
    if len(kl8_data) > 50:
        print(f"\n--- 快乐8 ({len(kl8_data)}期) ---")
        recs = backup_kl8(kl8_data)
        all_results["kl8"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 KL8: 只有{len(kl8_data)}期 (<50)")
    
    # ===== FC3D =====
    fc3d_data = data.get("fc3d", [])
    if len(fc3d_data) > 30:
        print(f"\n--- 福彩3D ({len(fc3d_data)}期) ---")
        recs = backup_digit(fc3d_data, "fc3d", 3)
        all_results["fc3d"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 FC3D: 只有{len(fc3d_data)}期 (<30)")
    
    # ===== PL3 =====
    pl3_data = data.get("pl3", [])
    if len(pl3_data) > 30:
        print(f"\n--- 排列三 ({len(pl3_data)}期) ---")
        recs = backup_digit(pl3_data, "pl3", 3)
        all_results["pl3"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 PL3: 只有{len(pl3_data)}期 (<30)")
    
    # ===== PL5 =====
    pl5_data = data.get("pl5", [])
    if len(pl5_data) > 30:
        print(f"\n--- 排列五 ({len(pl5_data)}期) ---")
        recs = backup_digit(pl5_data, "pl5", 5)
        all_results["pl5"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 PL5: 只有{len(pl5_data)}期 (<30)")
    
    # ===== SSQ =====
    ssq_data = data.get("ssq", [])
    if len(ssq_data) > 15:
        print(f"\n--- 双色球 ({len(ssq_data)}期) ---")
        recs = backup_lotto(ssq_data, "ssq", 33, 6, 16, 1)
        all_results["ssq"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 SSQ: 只有{len(ssq_data)}期 (<15)")
    
    # ===== DLT =====
    dlt_data = data.get("dlt", [])
    if len(dlt_data) > 15:
        print(f"\n--- 大乐透 ({len(dlt_data)}期) ---")
        recs = backup_lotto(dlt_data, "dlt", 35, 5, 12, 2)
        all_results["dlt"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 DLT: 只有{len(dlt_data)}期 (<15)")
    
    # ===== QLC =====
    qlc_data = data.get("qlc", [])
    if len(qlc_data) > 15:
        print(f"\n--- 七乐彩 ({len(qlc_data)}期) ---")
        recs = backup_lotto(qlc_data, "qlc", 30, 7, 1, 0)
        all_results["qlc"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 QLC: 只有{len(qlc_data)}期 (<15)")
    
    # ===== QXC =====
    qxc_data = data.get("qxc", [])
    if len(qxc_data) > 30:
        print(f"\n--- 七星彩 ({len(qxc_data)}期) ---")
        recs = backup_digit(qxc_data, "qxc", 7)
        all_results["qxc"] = recs
        print(f"  ✅ {len(recs)}条记录")
    else:
        print(f"\n  跳过 QXC: 只有{len(qxc_data)}期 (<30)")
    
    # ===== 写入文件 =====
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    total_recs = sum(len(v) for v in all_results.values())
    print(f"\n✅ 总记录: {total_recs}条 → {OUTPUT_PATH}")
    
    # 输出统计摘要
    print("\n=== 统计摘要 ===\n")
    for type_name, recs in all_results.items():
        if not recs:
            continue
        total = len(recs)
        if type_name == "kl8":
            # 统计选五中5次数
            x5_5 = sum(1 for r in recs if r.get("per_play", {}).get("xuan5", {}).get("hit_count", 0) >= 5)
            x7_7 = sum(1 for r in recs if r.get("per_play", {}).get("xuan7", {}).get("hit_count", 0) >= 7)
            x8_8 = sum(1 for r in recs if r.get("per_play", {}).get("xuan8", {}).get("hit_count", 0) >= 8)
            x10_10 = sum(1 for r in recs if r.get("per_play", {}).get("xuan10", {}).get("hit_count", 0) >= 10)
            d9_9 = sum(1 for r in recs if r.get("d9dan", {}).get("hit_count", 0) >= 9)
            print(f"  KL8: {total}期 | 选五中5={x5_5} | 选七中7={x7_7} | 选八中8={x8_8} | 选十中10={x10_10} | 9胆中9={d9_9}")
        elif type_name in ("fc3d", "pl3"):
            z1_prize = sum(r.get("basic", {}).get("z1", {}).get("prize", 0) for r in recs)
            z1_hits = sum(1 for r in recs if r.get("basic", {}).get("z1", {}).get("hit_count", 0) >= 3)
            print(f"  {type_name.upper()}: {total}期 | 直选命中={z1_hits} | 假想奖金=¥{z1_prize}")
        elif type_name == "pl5":
            z1_hits = sum(1 for r in recs if r.get("basic", {}).get("z1", {}).get("hit_count", 0) >= 5)
            print(f"  PL5: {total}期 | 直选中5={z1_hits}")
        else:
            print(f"  {type_name.upper()}: {total}期")


if __name__ == "__main__":
    main()
