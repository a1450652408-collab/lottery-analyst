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
    """数字彩预测模型v2（每位独立预测·权重自调优）"""
    
    # 9个因子名称与初始权重
    FACTOR_NAMES = [
        "freq", "ema", "momentum", "miss_revert", 
        "markov", "pattern_follow", "gap_uniform", 
        "macd_trend", "similarity"
    ]
    DEFAULT_WEIGHTS = {
        "freq": 0.12, "ema": 0.18, "momentum": 0.10, "miss_revert": 0.10,
        "markov": 0.12, "pattern_follow": 0.08, "gap_uniform": 0.08,
        "macd_trend": 0.12, "similarity": 0.10
    }
    
    def __init__(self, data, positions, window_size=50, analysis_window=20, weights=None):
        self.data = data  # 最新在前
        self.positions = positions
        self.window_size = min(window_size, max(len(data), 10))
        self.analysis_window = min(analysis_window, self.window_size)
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.similarity_cache = {}
        
    def _macd(self, seq, fast=3, slow=8, signal=3):
        """简化MACD计算（给每个数字算）"""
        if len(seq) < slow + signal:
            return 0.0
        # EMA fast
        ema_f = seq[0]
        for v in seq[1:]:
            ema_f = (2/(fast+1)) * v + (1 - 2/(fast+1)) * ema_f
        # EMA slow
        ema_s = seq[0]
        for v in seq[1:]:
            ema_s = (2/(slow+1)) * v + (1 - 2/(slow+1)) * ema_s
        macd_line = ema_f - ema_s
        # EMA signal
        ema_sig = macd_line
        # 简化为信号值
        return macd_line
    
    def _pattern_similarity(self, pos_nums, target_digit):
        """
        模式相似度匹配：找与最近N期模式相似的历史期，看后续出现频率
        """
        recent_len = min(5, len(pos_nums))
        if len(pos_nums) < recent_len + 2:
            return 0.0
        
        # 最近几期的模式
        recent_pattern = pos_nums[:recent_len]
        
        # 在所有历史中找最相似的
        scores = 0.0
        matches = 0
        
        for i in range(1, len(pos_nums) - recent_len - 1):
            # 计算欧氏距离
            dist = sum(abs(pos_nums[j] - recent_pattern[j]) for j in range(recent_len))
            dist = dist / (recent_len * 9)  # 归一化到 0~1
            
            if dist < 0.3:  # 相似度阈值
                matches += 1
                # 检查相似段的后一期
                next_val = pos_nums[i - recent_len - 1] if i - recent_len - 1 >= 0 else None
                # 实际上是 pos_nums[i] 之后出现的
                
        
        # 更简单的方法：检查最近recent_len期的组合在历史上出现后，下一期的数字分布
        pattern_key = tuple(recent_pattern)
        if pattern_key not in self.similarity_cache:
            followers = defaultdict(int)
            for i in range(len(pos_nums) - recent_len):
                if tuple(pos_nums[i:i+recent_len]) == pattern_key:
                    if i + recent_len < len(pos_nums):
                        followers[pos_nums[i + recent_len]] += 1
            self.similarity_cache[pattern_key] = followers
        
        followers = self.similarity_cache[pattern_key]
        total = sum(followers.values())
        if total == 0:
            return 0.0
        return followers.get(target_digit, 0) / total
    
    def predict_position(self, pos, weights=None):
        """对单个位置进行9因子预测"""
        w = weights or self.weights
        recent = self.data[:self.window_size]
        nums_list = [d["n"] for d in recent if len(d["n"]) > pos]
        
        if not nums_list:
            return {d: 0 for d in range(10)}
        
        pos_nums = [n[pos] for n in nums_list]
        total = len(pos_nums)
        if total < 5:
            return {d: 0 for d in range(10)}
        
        scores = {d: 0.0 for d in range(10)}
        
        # --- 因子1: 频率得分 ---
        freq = Counter(pos_nums)
        for d in range(10):
            scores[d] += (freq.get(d, 0) / total) * w["freq"]
        
        # --- 因子2: EMA热度 ---
        alpha = 0.35
        for d in range(10):
            ema = 0.0
            for n in reversed(pos_nums):
                hit = 1.0 if n == d else 0.0
                ema = alpha * hit + (1 - alpha) * ema
            scores[d] += ema * w["ema"]
        
        # --- 因子3: 近期动量 ---
        if total >= 10:
            r5 = pos_nums[:5]
            p5 = pos_nums[5:10]
            for d in range(10):
                mom = (r5.count(d) - p5.count(d)) * 3
                scores[d] += max(-0.3, min(0.3, mom * 0.01)) * w["momentum"]
        
        # --- 因子4: 遗漏值回补 ---
        last_seen = {}
        for i, n in enumerate(pos_nums):
            last_seen[n] = i
        for d in range(10):
            miss = last_seen.get(d, total)
            expected_interval = total / max(freq.get(d, 1), 1)
            miss_bonus = max(0, (miss - expected_interval) / total * 1.0)
            scores[d] += miss_bonus * w["miss_revert"]
        
        # --- 因子5: 马尔可夫链 (二阶) ---
        if total >= 3:
            trans = defaultdict(lambda: [0]*10)
            for i in range(total-1):
                trans[pos_nums[i]][pos_nums[i+1]] += 1
            last_val = pos_nums[0]
            tc = trans[last_val]
            tt = sum(tc)
            if tt > 0:
                for d in range(10):
                    scores[d] += (tc[d] / tt) * w["markov"]
        
        # --- 因子6: 模式跟随 ---
        if total >= 4:
            pattern3 = tuple(pos_nums[:min(3, total-1)])
            followers = []
            for i in range(total - len(pattern3)):
                if tuple(pos_nums[i:i+len(pattern3)]) == pattern3:
                    if i + len(pattern3) < total:
                        followers.append(pos_nums[i + len(pattern3)])
            if followers:
                fc = Counter(followers)
                for d in range(10):
                    scores[d] += (fc.get(d, 0) / len(followers)) * w["pattern_follow"]
        
        # --- 因子7: 间隔均匀度 ---
        for d in range(10):
            pos_d = [i for i, n in enumerate(pos_nums) if n == d]
            if len(pos_d) >= 2:
                gaps = [pos_d[j+1] - pos_d[j] for j in range(len(pos_d)-1)]
                mean_gap = sum(gaps) / len(gaps)
                var_ = sum((g - mean_gap)**2 for g in gaps) / len(gaps)
                uniformity = 1 / (1 + var_ / 100)
                scores[d] += uniformity * w["gap_uniform"]
        
        # --- 因子8: MACD趋势 ---
        for d in range(10):
            seq = [1.0 if n == d else 0.0 for n in pos_nums[:min(30, total)]]
            macd_val = self._macd(seq)
            # MACD正=升温，负=降温
            trend_score = max(-0.3, min(0.3, macd_val * 0.5))
            scores[d] += trend_score * w["macd_trend"]
        
        # --- 因子9: 模式相似度匹配 ---
        for d in range(10):
            sim = self._pattern_similarity(pos_nums, d)
            scores[d] += sim * w["similarity"]
        
        return scores
    
    def predict_all(self, weights=None):
        """预测所有位置"""
        results = []
        for pos in range(self.positions):
            self.similarity_cache = {}  # 每位独立缓存
            scores = self.predict_position(pos, weights)
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
        """最佳直选"""
        return [pr["top3"][0] for pr in pos_results]
    
    def weighted_combos(self, pos_results, count=5):
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
                cum = 0
                for s, w in zip(pr["ranked"], weights):
                    cum += w
                    if r <= cum:
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
# 4b. 权重优化引擎
# ============================================================
class WeightOptimizer:
    """
    权重优化器：通过网格搜索找到最优因子权重组合
    搜索空间：每个因子权重在 [0.5x, 2.0x] 范围内步进
    """
    
    def optimize(self, data, positions, window_sizes=[20, 30, 50]):
        """
        网格搜索最优权重（快速版：10候选 × 30验证期）
        返回: {weights, score, window}
        """
        import random
        
        best = {"score": 0, "weights": DigitPredictor.DEFAULT_WEIGHTS.copy(), "window": 20}
        
        # 10组随机权重组合（快速）
        random.seed(42)
        candidates = []
        for _ in range(10):
            w = {}
            raw = [random.uniform(0.5, 2.0) for _ in range(9)]
            total = sum(raw)
            for i, name in enumerate(DigitPredictor.FACTOR_NAMES):
                w[name] = DigitPredictor.DEFAULT_WEIGHTS[name] * (raw[i] / total * 9 / 1.0)
            candidates.append(w)
        # 加默认权重
        candidates.append(DigitPredictor.DEFAULT_WEIGHTS.copy())
        
        # 每组合测试所有窗口（仅验证30期）
        for ws in window_sizes:
            if len(data) < ws + 5:
                continue
            test_count = min(30, len(data) - ws - 1)
            
            for ci, w in enumerate(candidates):
                total_hits = {pos: 0 for pos in range(positions)}
                total_tests = 0
                
                for ti in range(test_count):
                    test_idx = len(data) - 1 - ti - 1  # 从最新往前
                    if test_idx < ws:
                        continue
                    train_data = data[test_idx - ws:test_idx]
                    actual = data[test_idx]["n"]
                    if len(actual) < positions:
                        continue
                    
                    predictor = DigitPredictor(train_data, positions, window_size=ws, weights=w)
                    pos_results = predictor.predict_all(w)
                    total_tests += 1
                    
                    for pos in range(positions):
                        if actual[pos] in pos_results[pos]["top3"]:
                            total_hits[pos] += 1
                
                if total_tests > 0:
                    avg_hit = sum(total_hits.values()) / (positions * total_tests) * 100
                    if avg_hit > best["score"]:
                        best = {
                            "score": round(avg_hit, 2),
                            "weights": w,
                            "window": ws,
                            "per_pos": {pos: round(h/total_tests*100, 2) for pos, h in total_hits.items()}
                        }
        
        return best


# ============================================================
# 4c. 集成预测（多模型投票）
# ============================================================
class EnsemblePredictor:
    """多模型集成预测"""
    
    @staticmethod
    def predict(data, positions, window_size=50):
        """
        多模型集成：
        1. 标准9因子模型
        2. 纯频率模型
        3. 纯EMA模型
        4. 纯马尔可夫模型
        """
        models = [
            ("9因子", DigitPredictor(data, positions, window_size)),
            ("频率", DigitPredictor(data, positions, window_size, weights={
                "freq": 0.5, "ema": 0, "momentum": 0, "miss_revert": 0,
                "markov": 0, "pattern_follow": 0, "gap_uniform": 0,
                "macd_trend": 0, "similarity": 0
            })),
            ("EMA", DigitPredictor(data, positions, window_size, weights={
                "freq": 0, "ema": 0.5, "momentum": 0, "miss_revert": 0,
                "markov": 0, "pattern_follow": 0, "gap_uniform": 0,
                "macd_trend": 0, "similarity": 0
            })),
            ("Markov", DigitPredictor(data, positions, window_size, weights={
                "freq": 0, "ema": 0, "momentum": 0, "miss_revert": 0,
                "markov": 0.5, "pattern_follow": 0, "gap_uniform": 0,
                "macd_trend": 0, "similarity": 0
            })),
        ]
        
        results = []
        for pos in range(positions):
            votes = {d: 0 for d in range(10)}
            all_top3 = set()
            
            for name, model in models:
                scores = model.predict_position(pos)
                ranked = sorted(scores.items(), key=lambda x: -x[1])
                top3 = [d for d, s in ranked[:3]]
                # 投票：第一名3分，第二名2分，第三名1分
                votes[top3[0]] += 3
                votes[top3[1]] += 2
                votes[top3[2]] += 1
                all_top3.update(top3)
            
            # 按总分排序
            ranked = sorted(votes.items(), key=lambda x: -x[1])
            results.append({
                "pos": pos,
                "ranked": [{"digit": d, "score": s / len(models)} for d, s in ranked],
                "top3": [d for d, s in ranked[:3]],
                "top5": [d for d, s in ranked[:5]],
                "consensus": len(ranked) > 0 and ranked[0][1] >= 7  # 是否有强共识
            })
        
        return results


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
    
    # 5. 运行预测 (v2: 9因子 + 集成 + 权重优化)
    # 5a. 权重优化
    optimizer = WeightOptimizer()
    opt_result = optimizer.optimize(data, positions, window_sizes=[20, 30, 50, 100])
    opt_weights = opt_result["weights"]
    opt_ws = opt_result["window"]
    opt_score = opt_result["score"]
    print(f"  权重优化: 最优窗口{opt_ws}期, 平均Top3命中率{opt_score:.2f}%")
    if "per_pos" in opt_result:
        for pos, rate in opt_result["per_pos"].items():
            print(f"    位{pos+1}: {rate}%")
    
    # 5b. 标准9因子预测 (用优化权重)
    predictor = DigitPredictor(recent, positions, window_size=opt_ws if opt_ws <= len(recent) else 20, weights=opt_weights)
    pos_predictions = predictor.predict_all(opt_weights)
    best_combo = predictor.best_combo(pos_predictions)
    weighted_combos = predictor.weighted_combos(pos_predictions, count=3)
    top3_combos = []
    for combo in [best_combo] + weighted_combos:
        if combo not in top3_combos:
            top3_combos.append(combo)
            if len(top3_combos) >= 3:
                break
    
    # 5c. 集成预测
    ensemble = EnsemblePredictor()
    ensemble_predictions = ensemble.predict(recent, positions, window_size=opt_ws if opt_ws <= len(recent) else 20)
    ensemble_combo = [ep["top3"][0] for ep in ensemble_predictions]
    
    # 5d. 五码定位复式回测
    wu_ma_hit_rate = {}
    for ws in [20, 30, 50]:
        wu_hits_top5 = {pos: 0 for pos in range(positions)}
        wu_full_hits = 0
        wu_tests = 0
        
        for test_idx in range(ws, len(data) - 1):
            train_data = data[test_idx - ws:test_idx]
            actual = data[test_idx]["n"]
            if len(actual) < positions:
                continue
            p = DigitPredictor(train_data, positions, window_size=ws, weights=opt_weights)
            pr = p.predict_all(opt_weights)
            wu_tests += 1
            all_in_top5 = True
            for pos in range(positions):
                if actual[pos] in pr[pos]["top5"]:
                    wu_hits_top5[pos] += 1
                else:
                    all_in_top5 = False
            if all_in_top5:
                wu_full_hits += 1
        
        if wu_tests > 0:
            wu_ma_hit_rate[f"win_{ws}"] = {
                "per_pos": {pos: round(h/wu_tests*100, 2) for pos, h in wu_hits_top5.items()},
                "full_match_top5": round(wu_full_hits/wu_tests*100, 4),
                "total_tests": wu_tests,
                "full_hits": wu_full_hits
            }
    
    # 6. 滚动回测 (v2: 使用优化权重)
    backtest_results = rolling_backtest(data, positions)  # 保留原始回测用于对比
    # 添加优化权重的v2回测
    backtest_results["v2_optimized"] = {
        "weights": {k: round(v, 4) for k, v in opt_weights.items()},
        "best_window": opt_ws,
        "avg_top3_rate": round(opt_score, 2)
    }
    
    # 7. 参数调优建议
    tuning = {
        "current_window": 20,
        "suggested_window": opt_ws,
        "reason": f"权重优化后窗口{opt_ws}期平均命中率{opt_score:.2f}%",
        "optimized_weights": {k: round(v, 4) for k, v in opt_weights.items()},
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
            "ensemble_combo": ensemble_combo,
            "ensemble_predictions": ensemble_predictions,
            "method": "9因子v2(频率+EMA+动量+遗漏+Markov+模式跟随+间隔均匀度+MACD趋势+相似度匹配)+集成投票+权重自调优"
        },
        
        "backtest": backtest_results,
        
        "wu_ma_hit_rate": wu_ma_hit_rate,
        
        "tuning": tuning,
    }
    
    # 打印关键摘要
    print(f"最佳推荐(v2): {''.join(str(d) for d in best_combo)}")
    print(f"集成推荐: {''.join(str(d) for d in ensemble_combo)}")
    print(f"优化窗口: {opt_ws}期 (平均Top3 {opt_score:.2f}%)")
    # 五码回测
    for k, v in wu_ma_hit_rate.items():
        ws = k.split("_")[1]
        pos_str = " | ".join([f"位{p+1}:{r}%" for p, r in v["per_pos"].items()])
        print(f"  五码(window {ws}期): {pos_str} | 全位Top5: {v['full_match_top5']}%")
    
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
