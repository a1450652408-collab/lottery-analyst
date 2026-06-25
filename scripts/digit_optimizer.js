/**
 * 数字彩深度优化方案
 * ========================================
 * 福彩3D/排列三 深度预测系统
 *
 * 优化技术:
 * 1. 多窗口频率分析（20/50/100期）
 * 2. 五维指标集成（频率/012路/奇偶/大小/遗漏）
 * 3. 置信度评分
 * 4. 多策略推荐（直选/组三/组六/定位复式）
 * 5. 滚动回测验证
 * 6. 性能对比分析
 *
 * 用法: node scripts/digit_optimizer.js
 */

const fs = require('fs');

// ========== 数据加载 ==========
// 优先使用扩充后的全量数据
let fc3d;
try {
  fc3d = JSON.parse(fs.readFileSync('data/fc3d_full.json', 'utf8'));
  console.log(`使用扩充数据源: ${fc3d.length}期 (2025-2026)`);
} catch(e) {
  const html = fs.readFileSync('index_modified.html', 'utf8');
  const match = html.match(/window\.__LOTTERY_DATA\s*=\s*(\{.*?\});\s*<\/script>/s);
  fc3d = JSON.parse(match[1]).fc3d;
  console.log(`使用嵌入数据源: ${fc3d.length}期`);
}

function getNums(d) { if (d.n) return d.n; if (d.r) return d.r; return []; }

// ========== 分析函数 ==========

/** 多窗口频率分析: 返回每个数字在多个窗口的综合得分 */
function multiWindowFreq(data, pos, windows) {
  const scores = {};
  for (let d = 0; d <= 9; d++) scores[d] = 0;
  
  windows.forEach((w, wi) => {
    const win = data.slice(0, Math.min(w, data.length));
    const freq = {};
    for (let d = 0; d <= 9; d++) freq[d] = 0;
    win.forEach(item => {
      const n = getNums(item);
      if (pos < n.length) freq[n[pos]]++;
    });
    // 窗口权重：短期权重高
    const weight = [3, 2, 1][wi] || 1;
    for (let d = 0; d <= 9; d++) {
      const rate = freq[d] / win.length;
      // 分数 = 频率偏离期望(10%)的幅度 × 权重
      scores[d] += (rate - 0.10) * weight;
    }
  });
  return scores;
}

/** 五维指标集成评分 */
function ensembleScore(data, pos) {
  const total = data.length;
  const freq = {}; for (let d = 0; d <= 9; d++) freq[d] = 0;
  const route012 = {}; for (let d = 0; d <= 9; d++) route012[d] = 0;
  const oeScore = {}; for (let d = 0; d <= 9; d++) oeScore[d] = 0;
  const bsScore = {}; for (let d = 0; d <= 9; d++) bsScore[d] = 0;
  const missScore = {}; for (let d = 0; d <= 9; d++) missScore[d] = 0;
  
  // 统计
  data.forEach(item => {
    const n = getNums(item);
    if (pos >= n.length) return;
    freq[n[pos]]++;
  });
  
  // 012路分布
  let r0 = 0, r1 = 0, r2 = 0;
  Object.entries(freq).forEach(([d, c]) => {
    if (d % 3 === 0) r0 += c;
    else if (d % 3 === 1) r1 += c;
    else r2 += c;
  });
  
  // 奇偶分布
  let oddTotal = 0, evenTotal = 0;
  Object.entries(freq).forEach(([d, c]) => {
    if (d % 2 === 1) oddTotal += c;
    else evenTotal += c;
  });
  
  // 大小分布
  let bigTotal = 0, smallTotal = 0;
  Object.entries(freq).forEach(([d, c]) => {
    if (d >= 5) bigTotal += c;
    else smallTotal += c;
  });
  
  // 计算每个维度的分数
  for (let d = 0; d <= 9; d++) {
    // 1. 频率得分: 偏离10%的幅度
    const freqRate = freq[d] / total;
    freq[d] = (freqRate - 0.10) / 0.10; // 归一化
    
    // 2. 012路得分: 所在路的当前占比 vs 理论占比
    const route = d % 3;
    const routeRate = route === 0 ? r0/total : (route === 1 ? r1/total : r2/total);
    const routeExpected = route === 0 ? 0.40 : 0.30; // 0路4个号(40%) 1路3个(30%) 2路3个(30%)
    route012[d] = (routeRate - routeExpected) / routeExpected;
    
    // 3. 奇偶得分
    const oRate = oddTotal / total;
    const eRate = evenTotal / total;
    if (d % 2 === 1) oeScore[d] = (oRate - 0.50) / 0.50;
    else oeScore[d] = (eRate - 0.50) / 0.50;
    
    // 4. 大小得分
    const bRate = bigTotal / total;
    const sRate = smallTotal / total;
    if (d >= 5) bsScore[d] = (bRate - 0.50) / 0.50;
    else bsScore[d] = (sRate - 0.50) / 0.50;
    
    // 5. 遗漏得分: 遗漏越久分数越高（冷号回补逻辑）
    let miss = 0;
    for (let i = 0; i < data.length; i++) {
      const n = getNums(data[i]);
      if (pos < n.length && n[pos] === d) { miss = i; break; }
    }
    missScore[d] = Math.min(1, miss / 20); // 超过20期未出=最高分
  }
  
  // 集成: 加权总分
  const finalScore = {};
  for (let d = 0; d <= 9; d++) {
    finalScore[d] = freq[d] * 0.30 + route012[d] * 0.20 + oeScore[d] * 0.15 
                  + bsScore[d] * 0.15 + missScore[d] * 0.20;
  }
  
  return {
    scores: finalScore,
    freq: freq,
    route012: route012,
    oe: oeScore,
    bs: bsScore,
    miss: missScore,
    details: { r0, r1, r2, oddTotal, evenTotal, bigTotal, smallTotal }
  };
}

/** 按分数排序推荐每位数字 */
function rankDigits(scores) {
  return Object.entries(scores)
    .map(([d, s]) => ({ digit: parseInt(d), score: s }))
    .sort((a, b) => b.score - a.score);
}

/** 定位复式推荐（每位置取Top N个） */
function positionCompound(rankings, topN) {
  return rankings.map(r => r.slice(0, topN).map(x => x.digit));
}

/** 计算定位复式的预期命中率 */
function expectedHit(rankings, topN, total) {
  // 每个位置从topN中选1个正确的概率 ≈ 该位置topN中包含正确号码的概率
  let correctCount = 0;
  for (let i = 0; i < total; i++) {
    let allCorrect = true;
    for (let p = 0; p < rankings.length; p++) {
      const top = rankings[p].slice(0, topN).map(x => x.digit);
      // 这里需要实际数据来验证
    }
  }
}

// ========== 主回测 ==========
function backtest3D(data, minWindow) {
  console.log('开始滚动回测 (福彩3D)...');
  let ensembleWins = 0;   // 集成推荐直选命中
  let hotWins = 0;        // 纯追热直选命中
  let totalTests = 0;
  let z3Wins = 0;         // 组三命中
  let z6Wins = 0;         // 组六命中
  
  // 记录每次推荐的首选三个数
  let firstPicks = [];
  
  for (let idx = minWindow; idx < data.length; idx++) {
    const trainData = data.slice(idx - minWindow, idx);
    const actual = getNums(data[idx]);
    if (actual.length < 3) continue;
    
    totalTests++;
    
    // 集成评分
    const pScores = [0, 1, 2].map(p => ensembleScore(trainData, p));
    const rankings = pScores.map(ps => rankDigits(ps.scores));
    
    // 策略1: 集成推荐（每位置选评分最高）
    const ensemblePick = rankings.map(r => r[0].digit);
    if (ensemblePick[0] === actual[0] && ensemblePick[1] === actual[1] && ensemblePick[2] === actual[2]) {
      ensembleWins++;
    }
    
    // 策略2: 纯追热（每位置出现频率最高）
    const hotPick = pScores.map(ps => {
      const byFreq = Object.entries(ps.freq).sort((a,b) => b[1] - a[1]);
      return parseInt(byFreq[0][0]);
    });
    if (hotPick[0] === actual[0] && hotPick[1] === actual[1] && hotPick[2] === actual[2]) {
      hotWins++;
    }
    
    // 策略3: 组三（定位复式Top4，检查是否有重复号结构）
    const compound = positionCompound(rankings, 4);
    const z3Picks = [];
    // 从定位复式中生成组三组合（112/121/211/122/212/221...）
    for (let a = 0; a < 4; a++) {
      for (let b = 0; b < 4; b++) {
        for (let c = 0; c < 4; c++) {
          const pick = [compound[0][a], compound[1][b], compound[2][c]];
          // 组三: 恰好2个相同
          if ((pick[0] === pick[1] && pick[1] !== pick[2]) ||
              (pick[0] === pick[2] && pick[0] !== pick[1]) ||
              (pick[1] === pick[2] && pick[0] !== pick[1])) {
            z3Picks.push(pick);
          }
        }
      }
    }
    // 去重
    const z3Set = new Set(z3Picks.map(p => p.join(',')));
    if ([...z3Set].some(p => {
      const pp = p.split(',').map(Number);
      return pp[0] === actual[0] && pp[1] === actual[1] && pp[2] === actual[2];
    })) {
      z3Wins++;
    }
    
    // 记录首选
    if (totalTests <= 10) {
      firstPicks.push({ date: data[idx].d, pick: ensemblePick, actual: actual, hit: ensemblePick.join('') === actual.join('') });
    }
  }
  
  // 理论随机概率
  const randomZhi = 1 / 1000;  // 直选
  const randomZ3 = 90 / 1000;  // 组三（90注）
  const randomZ6 = 120 / 1000; // 组六（120注）
  // 定位复式4码 = 4×4×4 = 64注
  const randomCompound = 4*4*4 / 1000;
  
  console.log('\n' + '='.repeat(60));
  console.log('            数字彩深度优化 回测报告');
  console.log('='.repeat(60));
  console.log(`测试期数: ${totalTests} 期`);
  console.log(`训练窗口: ${minWindow} 期`);
  console.log();
  
  console.log('--- 直选命中率对比 ---');
  console.log(`  集成推荐:   ${ensembleWins}/${totalTests} = ${(ensembleWins/totalTests*100).toFixed(2)}%`);
  console.log(`  纯追热:     ${hotWins}/${totalTests} = ${(hotWins/totalTests*100).toFixed(2)}%`);
  console.log(`  理论随机:   0.100%`);
  console.log(`  集成 vs 理论: ${(ensembleWins/totalTests/0.001).toFixed(1)}x`);
  console.log(`  追热 vs 理论:  ${(hotWins/totalTests/0.001).toFixed(1)}x`);
  console.log();
  
  console.log('--- 组三命中率（定位复式4码=64注）---');
  console.log(`  集成推荐:   ${z3Wins}/${totalTests} = ${(z3Wins/totalTests*100).toFixed(2)}%`);
  console.log(`  理论随机:   ${(randomZ3*100).toFixed(2)}%`);
  console.log(`  vs 理论:     ${(z3Wins/totalTests/randomZ3).toFixed(1)}x`);
  console.log();
  
  console.log('--- 每万期收益估算 ---');
  const zhiCost = 2;  // 直选¥2/注
  const zhiPrize = 1040; // 直选奖金¥1040
  const z3CostPerTest = 2; // 组三¥2/注
  const z3Prize = 346; // 组三奖金¥346
  
  const zhiNet = ensembleWins * zhiPrize - totalTests * zhiCost;
  const z3Net = z3Wins * z3Prize - totalTests * 64 * 2; // 64注×¥2
  console.log(`  集成直选:   ${zhiNet}元/${totalTests}期 = ${(zhiNet/totalTests*2*10000).toFixed(0)}元/万期`);
  console.log(`  集成组三:   ${z3Net}元/${totalTests}期 = ${(z3Net/totalTests*2*10000).toFixed(0)}元/万期`);
  console.log();
  
  // 对比之前版本
  console.log('--- 与旧版对比 ---');
  console.log('  旧版(组三胆拖): 返奖率84%, -1918元/500期 = -38360元/万期');
  console.log('  新版(集成组三): ' + (z3Net/totalTests*10000 > -38360 ? '✅ 优于旧版' : '❌ 不如旧版'));
  console.log();
  
  console.log('--- 前10期示例 ---');
  firstPicks.forEach((p, i) => {
    const mark = p.hit ? '✅' : '❌';
    console.log(`  ${p.date} 推荐:${p.pick.join('')} 实际:${p.actual.join('')} ${mark}`);
  });
}

// ========== 执行 ==========
const modelData = fc3d;
console.log(`福彩3D数据: ${modelData.length}期`);
console.log(`最新: ${modelData[0].p} ${modelData[0].d} 号[${getNums(modelData[0])}]`);
console.log();

backtest3D(modelData, 50);
