#!/usr/bin/env python3
"""
数字彩深度分析引擎 v1.0
================================
福彩3D / 排列三 / 排列五 综合分析系统

功能模块:
1. 数据预处理 - 时序去重、滑动窗口、归一化
2. 特征工程 - 奇偶/大小/012路/质合/跨度/和值/位置差
3. 模式识别 - 重复模式检测、连号模式、间隔分布
4. 预测模型 - 加权投票 + 马尔可夫 + 贝叶斯 + 趋势加权
5. 参数调优 - 动态窗口(20~100期) 自适应
6. 命中率验证 - 滚动回测

输出: data/fc3d_analysis.json, data/pl3_analysis.json, data/pl5_analysis.json
"""

import json
import os
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# ============================================================
# 1. 数据加载
# ============================================================
def load_data(filename):
    """从 data/ 目录加载 JSON 数据"""
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(f"[WARN] {path} not found")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[OK] {path}: {len(data)} 期")
    return data


def normalize_digit_data(raw):
    """标准化为统一的列表格式 [{p,d,n}]，n为数字列表"""
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        n = item.get("n") or item.get("r") or []
        if isinstance(n, int):
            n = [n]
        if not isinstance(n, list) or len(n) == 0:
            continue
        result.append({
            "p": str(item.get("p", "")),
            "d": str(item.get("d", "")),
            "n": [int(x) for x in n]
        })
    # 按期号降序（最新在前）
    result.sort(key=lambda x: int(x["p"]) if x["p"].isdigit() else 0, reverse=True)
    return result


# ============================================================
# 2. 特征工程
# ============================================================
def extract_features(nums_list, positions):
    """
    从号码序列中提取特征。
    nums_list: [[d1,d2,...], ...] 列表，每期号码
    positions: 位数
    返回: dict of feature arrays
    """
    features = {
        "odd_even": [],      # 奇偶模式
        "big_small": [],     # 大小模式
        "route012": [],      # 012路模式
        "prime_comp": [],    # 质合模式
        "sums": [],          # 和值
        "spans": [],         # 跨度
        "pos_diffs": [],     # 位置差
    }
    primes = {2, 3, 5, 7}
    
    for nums in nums_list:
        nums = nums[:positions]
        if len(nums) < positions:
            continue
        
        # 奇偶: 0=偶, 1=奇
        oe = [1 if n % 2 == 1 else 0 for n in nums]
        features["odd_even"].append(oe)
        
        # 大小: 0=小(0-4), 1=大(5-9)
        bs = [1 if n >= 5 else 0 for n in nums]
        features["big_small"].append(bs)
        
        # 012路: n%3
        r012 = [n % 3 for n in nums]
        features["route012"].append(r012)
        
        # 质合: 0=合, 1=质
        pc = [1 if n in primes else 0 for n in nums]
        features["prime_comp"].append(pc)
        
        # 和值
        features["sums"].append(sum(nums))
        
        # 跨度
        features["spans"].append(max(nums) - min(nums))
        
        # 位置差 (相邻位差)
        diffs = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
        features["pos_diffs"].append(diffs)
    
    return features


def pattern_vector(feature_row):
    """
    将特征行转换为模式向量字符串，用于模式匹配。
    例: odd_even=[1,0,1] → "101"
    """
    return "".join(str(x) for x in feature_row)


def pattern_frequencies(feature_arrays, pattern_type="odd_even"):
    """统计各模式的出现频率"""
    patterns = [pattern_vector(row) for row in feature_arrays]
    counter = Counter(patterns)
    total = len(patterns)
    return {
        "patterns": {k: {"count": v, "pct": round(v/total*100, 1)} for k, v in counter.most_common()},
        "total": total
    }


def transition_matrix(states, n_states=2):
    """计算马尔可夫转移矩阵"""
    size = n_states ** 3  # 3期状态
    trans = defaultdict(lambda: [0] * n_states)
    
    for i in range(len(states) - 3):
        key = tuple(states[i:i+3])
        next_val = states[i+3]
        trans[key][next_val] += 1
    
    # 归一化
    result = {}
    for key, counts in trans.items():
        total = sum(counts)
        if total > 0:
            result["".join(str(k) for k in key)] = {
                "next_0": round(counts[0]/total*100, 1),
                "next_1": round(counts[1]/total*100, 1),
                "cnt": total
            }
    return result


# ============================================================
# 3. 模式识别引擎
# ============================================================
class PatternEngine:
    """模式识别引擎：检测重复模式、趋势、异常"""
    
    @staticmethod
    def consecutive_patterns(pattern_list, min_length=2):
        """检测连续重复模式"""
        streaks = []
        current = (pattern_list[0], 0, 1) if pattern_list else None
        
        for i in range(1, len(pattern_list)):
            if pattern_list[i] == pattern_list[i-1]:
                current = (pattern_list[i], 0, 0)  # placeholder
            else:
                if current[2] >= min_length:
                    streaks.append({
                        "pattern": str(pattern_list[i-1]),
                        "length": current[2],
                        "end_pos": i-1
                    })
                current = (pattern_list[i], i, 1)
        
        # 检查最后一个
        if current and current[2] >= min_length:
            streaks.append({
                "pattern": str(current[0]),
                "length": current[2],
                "end_pos": len(pattern_list)-1
            })
        
        # 重新构建正确的 streaks
        # 简化版：只检测连续相同模式
        result = []
        if not pattern_list:
            return result
        
        cur_val = pattern_list[0]
        cur_len = 1
        for i in range(1, len(pattern_list)):
            if pattern_list[i] == cur_val:
                cur_len += 1
            else:
                if cur_len >= min_length:
                    # 将模式列表转换为字符串
                    result.append({
                        "pattern": str(int(cur_val)),
                        "length": cur_len,
                        "end_pos": i-1,
                        "pct": round(cur_len / len(pattern_list) * 100, 1)
                    })
                cur_val = pattern_list[i]
                cur_len = 1
        if cur_len >= min_length:
            result.append({
                "pattern": str(int(cur_val)),
                "length": cur_len,
                "end_pos": len(pattern_list)-1,
                "pct": round(cur_len / len(pattern_list) * 100, 1)
            })
        return result
    
    @staticmethod
    def gap_distribution(seq, value=1):
        """计算某个值出现的间隔分布"""
        last = -1
        gaps = []
        for i, v in enumerate(seq):
            if v == value:
                if last >= 0:
                    gaps.append(i - last)
                last = i
        if gaps:
            return {
                "avg_gap": round(sum(gaps) / len(gaps), 1),
                "min_gap": min(gaps),
                "max_gap": max(gaps),
                "current_miss": len(seq) - last - 1 if last >= 0 else len(seq),
                "gaps": gaps[-10:]  # 最近10个间隔
            }
        return {"avg_gap": 0, "min_gap": 0, "max_gap": 0, "current_miss": len(seq), "gaps": []}
    
    @staticmethod
    def hot_cold_position(freq_dict, pos, threshold_hot=0.12, threshold_cold=0.05):
        """
        按位分析热/冷号
        freq_dict: {digit: count} per position
        """
        total = sum(freq_dict.values())
        if total == 0:
            return {"hot": [], "cold": [], "normal": list(range(10))}
        
        ranked = sorted(freq_dict.items(), key=lambda x: -x[1])
        return {
            "hot": [d for d, c in ranked if c/total >= threshold_hot and c >= 3],
            "cold": [d for d, c in ranked if c/total <= threshold_cold and c <= 1],
            "normal": [d for d, c in ranked if threshold_cold < c/total < threshold_hot]
        }


# ============================================================
# 4. 预测模型
# ============================================================
class DigitPredictor:
    """数字彩预测模型（每位独立预测）"""
    
    def __init__(self, data, positions, window_size=50, analysis_window=20):
        self.data = data  # 最新在前
        self.positions = positions
        self.window_size = min(window_size, max(len(data), 10))
        self.analysis_window = min(analysis_window, self.window_size)
        
    def predict_position(self, pos):
        """
        对单个位置进行预测。
        返回: {digit: score} 排名
        """
        recent = self.data[:self.window_size]
        nums_list = [d["n"] for d in recent if len(d["n"]) > pos]
        
        if not nums_list:
            return {d: 0 for d in range(10)}
        
        pos_nums = [n[pos] for n in nums_list]
        recent_nums = pos_nums[:self.analysis_window]
        older_nums = pos_nums[self.analysis_window:] if len(pos_nums) > self.analysis_window else []
        
        scores = {d: 0.0 for d in range(10)}
        
        # --- 因子1: 频率得分 (权重0.15) ---
        freq = Counter(pos_nums)
        total = len(pos_nums)
        for d in range(10):
            scores[d] += (freq.get(d, 0) / total) * 0.15
        
        # --- 因子2: EMA热度 (权重0.20) ---
        alpha = 0.4
        for d in range(10):
            ema = 0.0
            for n in reversed(pos_nums):  # 从旧到新
                hit = 1.0 if n == d else 0.0
                ema = alpha * hit + (1 - alpha) * ema
            scores[d] += ema * 0.20
        
        # --- 因子3: 近期动量 (权重0.15) ---
        if len(recent_nums) >= 10:
            r5 = recent_nums[:5]
            p5 = recent_nums[5:10]
            for d in range(10):
                mom = (r5.count(d) - p5.count(d)) * 2
                scores[d] += max(-0.5, min(0.5, mom * 0.01)) * 0.15
        
        # --- 因子4: 遗漏值回补 (权重0.15) ---
        last_seen = {}
        for i, n in enumerate(pos_nums):
            last_seen[n] = i
        total_len = len(pos_nums)
        for d in range(10):
            miss = last_seen.get(d, total_len)
            expected_interval = total_len / max(freq.get(d, 1), 1)
            miss_bonus = max(0, (miss - expected_interval) / total_len * 0.5)
            scores[d] += miss_bonus * 0.15
        
        # --- 因子5: 马尔可夫链 (权重0.15) ---
        if len(pos_nums) >= 4:
            trans = defaultdict(lambda: [0]*10)
            for i in range(len(pos_nums)-1):
                trans[pos_nums[i]][pos_nums[i+1]] += 1
            last_val = pos_nums[0]
            trans_counts = trans[last_val]
            total_trans = sum(trans_counts)
            if total_trans > 0:
                for d in range(10):
                    scores[d] += (trans_counts[d] / total_trans) * 0.15
        
        # --- 因子6: 模式跟随 (权重0.10) ---
        if len(pos_nums) >= 6:
            # 最近3期模式
            pattern3 = tuple(pos_nums[:3])
            followers = []
            for i in range(len(pos_nums)-3):
                if tuple(pos_nums[i:i+3]) == pattern3:
                    followers.append(pos_nums[i+3])
            if followers:
                f_counter = Counter(followers)
                for d in range(10):
                    scores[d] += (f_counter.get(d, 0) / len(followers)) * 0.10
        
        # --- 因子7: 间隔均匀度 (权重0.10) ---
        for d in range(10):
            positions_d = [i for i, n in enumerate(pos_nums) if n == d]
            if len(positions_d) >= 2:
                gaps = [positions_d[i+1] - positions_d[i] for i in range(len(positions_d)-1)]
                if gaps:
                    mean_gap = sum(gaps) / len(gaps)
                    variance = sum((g - mean_gap)**2 for g in gaps) / len(gaps)
                    # 间隔越均匀, 分数越高
                    uniformity = 1 / (1 + variance / 100)
                    scores[d] += uniformity * 0.10
        
        return scores
    
    def predict_all(self):
        """预测所有位置"""
        results = []
        for pos in range(self.positions):
            scores = self.predict_position(pos)
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            total = sum(scores.values()) or 1
            results.append({
                "pos": pos,
                "ranked": [{"digit": d, "score": round(s, 4), "pct": round(s/total*100, 1)} for d, s in ranked],
                "top3": [d for d, s in ranked[:3]],
                "top5": [d for d, s in ranked[:5]],
            })
        return results
    
    def best_combo(self, pos_results):
        """根据各位置预测组合最佳直选"""
        combo = []
        for pr in pos_results:
            combo.append(pr["top3"][0])  # 每位置取最高分
        return combo
    
    def weighted_combos(self, pos_results, count=10):
        """加权随机生成多组直选"""
        import random
        combos = []
        seen = set()
        attempts = 0
        while len(combos) < count and attempts < 1000:
            combo = []
            key_parts = []
            for pr in pos_results:
                weights = [max(0.01, s["score"]) for s in pr["ranked"]]
                total_w = sum(weights)
                r = random.random() * total_w
                cumulative = 0
                for s, w in zip(pr["ranked"], weights):
                    cumulative += w
                    if r <= cumulative:
                        combo.append(s["digit"])
                        key_parts.append(str(s["digit"]))
                        break
            key = "".join(key_parts)
            if key not in seen:
                seen.add(key)
                combos.append(combo)
            attempts += 1
        return combos


# ============================================================
# 5. 滚动回测
# ============================================================
def rolling_backtest(data, positions, window_sizes=[20, 30, 50, 100]):
    """
    滚动回测：用前N期预测下一期，验证命中率
    """
    results = {}
    for ws in window_sizes:
        hit_rate = {pos: {"total": 0, "top3_hits": 0, "top5_hits": 0} for pos in range(positions)}
        total_tests = 0
        
        for test_idx in range(ws, len(data) - 1):
            train_data = data[test_idx - ws:test_idx]
            actual = data[test_idx]["n"]
            if len(actual) < positions:
                continue
            
            predictor = DigitPredictor(train_data, positions, window_size=ws, analysis_window=min(20, ws//2))
            pos_results = predictor.predict_all()
            total_tests += 1
            
            for pos in range(positions):
                hit_rate[pos]["total"] += 1
                if actual[pos] in pos_results[pos]["top3"]:
                    hit_rate[pos]["top3_hits"] += 1
                if actual[pos] in pos_results[pos]["top5"]:
                    hit_rate[pos]["top5_hits"] += 1
        
        # 计算命中率
        rs = {}
        for pos in range(positions):
            t = hit_rate[pos]["total"]
            rs[f"pos{pos+1}"] = {
                "total": t,
                "top3_hits": hit_rate[pos]["top3_hits"],
                "top3_rate": round(hit_rate[pos]["top3_hits"] / max(t, 1) * 100, 2) if t > 0 else 0,
                "top5_hits": hit_rate[pos]["top5_hits"],
                "top5_rate": round(hit_rate[pos]["top5_hits"] / max(t, 1) * 100, 2) if t > 0 else 0,
                "random_top3": 30.0,  # 理论随机: 3/10
                "random_top5": 50.0,
            }
        
        # 全部位命中率（中奖率）
        all_top3 = 0
        for test_idx in range(ws, len(data) - 1):
            train_data = data[test_idx - ws:test_idx]
            actual = data[test_idx]["n"]
            if len(actual) < positions:
                continue
            predictor = DigitPredictor(train_data, positions, window_size=ws, analysis_window=min(20, ws//2))
            pos_results = predictor.predict_all()
            all_hit = True
            for pos in range(positions):
                if actual[pos] not in pos_results[pos]["top3"]:
                    all_hit = False
                    break
            if all_hit:
                all_top3 += 1
        
        test_count = max(len(data) - ws - 1, 1)
        rs["full_match_top3"] = {
            "hits": all_top3,
            "total": test_count,
            "rate": round(all_top3 / test_count * 100, 4) if test_count > 0 else 0
        }
        
        results[f"win_{ws}"] = rs
    
    # 找最优窗口
    best_window = max(results, key=lambda k: results[k]["pos1"]["top3_rate"])
    
    return {
        "windows": results,
        "best_window": best_window,
        "best_rate": results[best_window]["pos1"]["top3_rate"]
    }


# ============================================================
# 6. 主分析入口
# ============================================================
def analyze_digit(data_raw, key_name, positions=3):
    """
    对一个数字彩种进行完整深度分析
    """
    data = normalize_digit_data(data_raw)
    if len(data) < 10:
        print(f"[SKIP] {key_name}: 数据不足({len(data)}期)")
        return None
    
    nums_list = [d["n"] for d in data]
    recent = data[:100]  # 最近100期
    recent_nums = [d["n"] for d in recent]
    
    print(f"\n{'='*60}")
    print(f"数字彩深度分析: {key_name}")
    print(f"总期数: {len(data)}, 分析窗口: {len(recent)}期")
    
    # 2. 特征工程
    features = extract_features(nums_list, positions)
    recent_features = extract_features(recent_nums, positions)
    
    # 3. 模式识别
    engine = PatternEngine()
    
    # 奇偶模式
    oe_flatten = [1 if sum(row) > len(row)/2 else 0 for row in features["odd_even"]]
    oe_patterns = pattern_frequencies(features["odd_even"])
    oe_streaks = engine.consecutive_patterns(oe_flatten)
    oe_trans = transition_matrix(oe_flatten)
    
    # 大小模式
    bs_flatten = [1 if sum(row) > len(row)/2 else 0 for row in features["big_small"]]
    bs_patterns = pattern_frequencies(features["big_small"])
    bs_streaks = engine.consecutive_patterns(bs_flatten)
    
    # 和值分析
    sum_analysis = {}
    if features["sums"]:
        sum_analysis = {
            "avg": round(sum(features["sums"]) / len(features["sums"]), 1),
            "min": min(features["sums"]),
            "max": max(features["sums"]),
            "recent10": features["sums"][:10] if len(features["sums"]) >= 10 else features["sums"],
            "recent_avg": round(sum(features["sums"][:20]) / min(20, len(features["sums"])), 1) if features["sums"] else 0,
        }
    
    # 跨度分析
    span_analysis = {}
    if features["spans"]:
        span_analysis = {
            "avg": round(sum(features["spans"]) / len(features["spans"]), 1),
            "max": max(features["spans"]),
            "recent10": features["spans"][:10] if len(features["spans"]) >= 10 else features["spans"],
        }
    
    # 4. 每位数字分析
    pos_analysis = []
    for pos in range(positions):
        pos_nums = [n[pos] for n in recent_nums]
        freq = Counter(pos_nums)
        freq_sorted = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
        
        hc = engine.hot_cold_position(freq, pos)
        
        gap = engine.gap_distribution(pos_nums)
        
        # 号码跟随
        follow = defaultdict(lambda: Counter())
        for i in range(len(pos_nums)-1):
            follow[pos_nums[i]][pos_nums[i+1]] += 1
        
        follow_top = {}
        for d in range(10):
            if freq.get(d, 0) > 0:
                top_followers = follow[d].most_common(3)
                if top_followers:
                    follow_top[str(d)] = [{"digit": fd, "count": fc} for fd, fc in top_followers]
        
        # 012路
        pos_012 = [n%3 for n in pos_nums]
        pos_012_freq = Counter(pos_012)
        
        pos_analysis.append({
            "freq": {str(d): c for d, c in freq_sorted},
            "hot": hc["hot"],
            "cold": hc["cold"],
            "normal": hc["normal"],
            "gap": gap,
            "follow": follow_top,
            "route012": {str(r): pos_012_freq.get(r, 0) for r in range(3)},
            "last10": pos_nums[:10] if len(pos_nums) >= 10 else pos_nums,
        })
    
    # 5. 运行预测
    predictor = DigitPredictor(recent, positions)
    pos_predictions = predictor.predict_all()
    best_combo = predictor.best_combo(pos_predictions)
    weighted_combos = predictor.weighted_combos(pos_predictions, count=5)
    top3_combos = []
    for combo in [best_combo] + [wc for wc in weighted_combos]:
        if combo not in top3_combos:
            top3_combos.append(combo)
            if len(top3_combos) >= 3:
                break
    
    # 6. 滚动回测
    backtest_results = rolling_backtest(data, positions)
    
    # 7. 参数调优建议
    best_ws = int(backtest_results["best_window"].split("_")[1])
    tuning = {
        "current_window": 20,
        "suggested_window": best_ws,
        "reason": f"回测发现窗口{best_ws}期命中率最高({backtest_results['best_rate']}%)",
        "windows_tested": list(backtest_results["windows"].keys()),
    }
    
    # 8. 输出汇总
    result = {
        "name": key_name,
        "positions": positions,
        "total_periods": len(data),
        "analysis_periods": len(recent),
        "last_period": data[0]["p"] if data else "",
        "last_date": data[0]["d"] if data else "",
        "last_draw": data[0]["n"] if data else [],
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        
        "features": {
            "odd_even": {
                "patterns": oe_patterns,
                "streaks": oe_streaks,
                "transition": oe_trans,
            },
            "big_small": {
                "patterns": bs_patterns,
                "streaks": bs_streaks,
            },
            "sum": sum_analysis,
            "span": span_analysis,
            "balance": {
                "oe_ratio": round(sum(oe_flatten) / max(len(oe_flatten), 1) * 100, 1) if oe_flatten else 0,
                "bs_ratio": round(sum(bs_flatten) / max(len(bs_flatten), 1) * 100, 1) if bs_flatten else 0,
                "oe_current": oe_flatten[0] if oe_flatten else -1,
                "bs_current": bs_flatten[0] if bs_flatten else -1,
            }
        },
        
        "position_analysis": pos_analysis,
        
        "prediction": {
            "positions": pos_predictions,
            "best_combo": best_combo,
            "top3_combos": top3_combos,
            "method": "7因子加权评分(频率+EMA+动量+遗漏+Markov+模式跟随+间隔均匀度)"
        },
        
        "backtest": backtest_results,
        
        "tuning": tuning,
    }
    
    # 打印关键摘要
    print(f"最佳推荐: {''.join(str(d) for d in best_combo)}")
    print(f"最优窗口: {best_ws}期 (命中率 {backtest_results['best_rate']}%)")
    print(f"全位命中(TOP3): {backtest_results['windows'][backtest_results['best_window']]['full_match_top3']['rate']}%")
    
    return result


def analyze_all():
    """分析全部数字彩"""
    configs = [
        ("fc3d", "fc3d_full.json", 3),
        ("pl3", "pl3_full.json", 3),
        ("pl5", "pl5_full.json", 5),
    ]
    
    results = {}
    for key, filename, positions in configs:
        raw = load_data(filename)
        result = analyze_digit(raw, key, positions)
        if result:
            results[key] = result
            # 保存到文件
            out_path = os.path.join(DATA_DIR, f"{key}_deep_analysis.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"[SAVED] {out_path}")
    
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("数字彩深度分析引擎 v1.0")
    print("=" * 60)
    analyze_all()
    print("\n[DONE] 分析完成")
