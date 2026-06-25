/**
 * 快乐8 橙色卡片 & 紫色卡片 选二/选三 每日命中记录
 * 算法从 index_modified.html 精确复制
 * 输出: data/kl8_orange_purple_hits.json
 * 供自动化: 每天更新后调用, 追加当天的记录
 */

const fs = require('fs');

// 加载数据
const html = fs.readFileSync('index_modified.html', 'utf8');
const match = html.match(/window\.__LOTTERY_DATA\s*=\s*(\{.*?\});\s*<\/script>/s);
if (!match) { console.error('未找到 __LOTTERY_DATA'); process.exit(1); }
const lotteryData = JSON.parse(match[1]);
const allData = lotteryData.kl8.slice().reverse();

function getNums(d) {
  if (d.n && Array.isArray(d.n)) return d.n;
  if (d.r && Array.isArray(d.r)) return d.r;
  return [];
}

function calcPrize(sn, hit) {
  if (sn === 2) return hit >= 2 ? 19 : 0;
  if (sn === 3) return hit >= 3 ? 53 : (hit >= 2 ? 3 : 0);
  return 0;
}

// ========== 橙色卡片：区间均衡·EMA评分 ==========
/* ★ 优化：单次扫描构建命中矩阵，避免重复遍历 */
function orangeCard_emaScore(trainingData, lastDraw) {
  const W = trainingData.length;
  
  /* 单次扫描：构建命中矩阵 [期][号] 和 各统计量 */
  const hitMatrix = [];     // hitMatrix[j][n] = 第j期n是否命中
  const knFreqAll = {};
  for (let n = 1; n <= 80; n++) knFreqAll[n] = 0;
  const knLastSeen = {};
  for (let n = 1; n <= 80; n++) knLastSeen[n] = -1;
  const knR5 = {}, knP5 = {};
  for (let n = 1; n <= 80; n++) { knR5[n] = 0; knP5[n] = 0; }
  const knFreq30 = {};
  for (let n = 1; n <= 80; n++) knFreq30[n] = 0;
  
  for (let j = 0; j < W; j++) {
    const nums = getNums(trainingData[j]);
    const row = {};
    nums.forEach(n => { row[n] = 1; knFreqAll[n]++; knLastSeen[n] = j; });
    hitMatrix.push(row);
    /* 近10期的R5/P5 */
    if (j < 10) {
      nums.forEach(n => { if (j < 5) knR5[n]++; else knP5[n]++; });
    }
    /* 近30期频率 */
    if (j < 30) {
      nums.forEach(n => { knFreq30[n]++; });
    }
  }
  
  /* 从矩阵计算EMA（一次遍历，无需重建序列） */
  const knEma = {};
  for (let n = 1; n <= 80; n++) {
    let e = 0;
    for (let j = W - 1; j >= 0; j--) {
      e = 0.5 * (hitMatrix[j][n] || 0) + 0.5 * e;
    }
    knEma[n] = e;
    
    /* ★ 多时间框架EMA：短(alpha=0.7)/长(alpha=0.3) 趋势确认 */
    let es = 0, ef = 0;
    for (let j = W - 1; j >= 0; j--) {
      const v = hitMatrix[j][n] || 0;
      es = 0.3 * v + 0.7 * es;
      ef = 0.7 * v + 0.3 * ef;
    }
    /* 短周期热且长周期也热 → 真趋势；短热长冷 → 噪音不采信 */
    knEma[n] = (ef > 0.15 && es > 0.12) ? knEma[n] * 1.2 : knEma[n] * 0.9;
  }
  
  /* 动量（R5 vs P5） */
  const knMom = {};
  for (let n = 1; n <= 80; n++) {
    const m = (knR5[n] - knP5[n]) / Math.max(knP5[n], 1);
    knMom[n] = Math.max(-2, Math.min(2, m));
  }
  
  const win30 = Math.min(30, W);
  const knPrevSet = new Set();
  if (lastDraw) lastDraw.forEach(n => knPrevSet.add(n));

  /* ★ 去掉kill set（它是不低于随机的根因之一） */
  
  const knScores = {};
  for (let n = 1; n <= 80; n++) {
    const missVal = W - 1 - knLastSeen[n];
    let s = (knEma[n] || 0) * 5.0 + (knFreq30[n] / win30) * 3.0 + (knMom[n] || 0) * 2.0;
    if (knPrevSet.has(n)) s += 3.0;
    s += Math.max(0, 10 - missVal) * 0.5;
    knScores[n] = s;
  }
  return knScores;
}

function zoneSelect(scores, selectN, avoidSet, allowedSet) {
  const zones = [[1,20],[21,40],[41,60],[61,80]];
  let result = [];
  if (selectN <= 6 || selectN >= 10) {
    const zPer = Math.floor(selectN / 4);
    const zExtra = selectN % 4;
    for (let zi = 0; zi < 4; zi++) {
      const zTake = zPer + (zi < zExtra ? 1 : 0);
      if (zTake <= 0) continue;
      const zNums = [];
      for (let n = zones[zi][0]; n <= zones[zi][1]; n++) {
        if (!allowedSet || allowedSet.has(n)) zNums.push(n);
      }
      if (zNums.length === 0) continue; // 该区没有允许的号
      zNums.sort((a,b) => (scores[b]||-999) - (scores[a]||-999));
      /* ★ 改进：从Top40%池中加权随机选，替代原来的硬取TopN，杜绝钉子户 */
      const poolSize = Math.max(zTake, Math.ceil(zNums.length * 0.4));
      const pool = zNums.slice(0, poolSize);
      let weighted = pool.map(n => {
        let w = Math.max(0.1, (scores[n]||0) + 1);
        if (result.indexOf(n) >= 0) w = 0;          // 已入选的归零
        if (avoidSet && avoidSet.has(n)) w *= 0.3;  // 最近推过的降低权重
        return { n, w };
      });
      let taken = 0;
      while (taken < zTake && weighted.length > 0) {
        const totalW = weighted.reduce((s, x) => s + x.w, 0);
        if (totalW <= 0) break;
        let r = Math.random() * totalW;
        let pickIdx = 0;
        for (let i = 0; i < weighted.length; i++) { r -= weighted[i].w; if (r <= 0) { pickIdx = i; break; } }
        const picked = weighted[pickIdx].n;
        if (result.indexOf(picked) < 0) { result.push(picked); taken++; }
        weighted.splice(pickIdx, 1);
      }
      /* 还缺的话补最热的 */
      if (taken < zTake) {
        for (let t = 0; t < zNums.length && taken < zTake; t++) {
          if (result.indexOf(zNums[t]) < 0) { result.push(zNums[t]); taken++; }
        }
      }
    }
  }
  if (result.length < selectN) {
    const oAll = [];
    for (let n = 1; n <= 80; n++) {
      if (!allowedSet || allowedSet.has(n)) oAll.push(n);
    }
    oAll.sort((a,b) => (scores[b]||-999) - (scores[a]||-999));
    for (let i = 0; i < oAll.length && result.length < selectN; i++) {
      if (result.indexOf(oAll[i]) < 0) result.push(oAll[i]);
    }
  }
  return result.slice(0, selectN);
}

// ========== 紫色卡片：区间均衡·多因子投票（优化：单次扫描矩阵）==========
function purpleCard_votes(trainingData, lastDraw) {
  const W = trainingData.length;
  
  /* 单次扫描构建命中矩阵 */
  const hitMatrix = [];
  const knFreq30 = {};
  for (let n = 1; n <= 80; n++) knFreq30[n] = 0;
  const knR5 = {}, knP5 = {};
  for (let n = 1; n <= 80; n++) { knR5[n] = 0; knP5[n] = 0; }
  const knR10 = {}, knP10 = {};
  for (let n = 1; n <= 80; n++) { knR10[n] = 0; knP10[n] = 0; }
  
  for (let j = 0; j < W; j++) {
    const nums = getNums(trainingData[j]);
    const row = {};
    nums.forEach(n => { row[n] = 1; });
    hitMatrix.push(row);
    if (j < 10) {
      nums.forEach(n => { if (j < 5) knR5[n]++; else knP5[n]++; });
    }
    if (j < 20) {
      nums.forEach(n => { if (j < 10) knR10[n]++; else knP10[n]++; });
    }
    if (j < 30) {
      nums.forEach(n => { knFreq30[n]++; });
    }
  }

  /* 从矩阵计算EMA(alpha=0.5) + EMA快(0.2) + EMA慢(0.8) — 一次遍历 */
  const knEma = {}, emaFast = {}, emaSlow = {};
  for (let n = 1; n <= 80; n++) {
    let e = 0, ef = 0, es = 0;
    for (let j = W - 1; j >= 0; j--) {
      const v = hitMatrix[j][n] || 0;
      e = 0.5 * v + 0.5 * e;
      ef = 0.2 * v + 0.8 * ef;
      es = 0.8 * v + 0.2 * es;
    }
    knEma[n] = e;
    emaFast[n] = ef;
    emaSlow[n] = es;
  }
  const emaComb = {};
  for (let n = 1; n <= 80; n++)
    emaComb[n] = (emaFast[n]||0)*2.0 + (knEma[n]||0)*3.0 + (emaSlow[n]||0)*1.0;

  /* 动量（R5/P5 + R10/P10） */
  const knMomC = {};
  for (let n = 1; n <= 80; n++) {
    const m5 = (knR5[n] - knP5[n]) / Math.max(knP5[n], 1);
    const m10 = (knR10[n] - knP10[n]) / Math.max(knP10[n], 1);
    knMomC[n] = Math.max(-2, Math.min(2, m5)) * 0.6 + Math.max(-2, Math.min(2, m10)) * 0.4;
  }
  const knStreak = {};
  for (let n = 1; n <= 80; n++) {
    let s = 0;
    for (let si = 0; si < Math.min(5, W); si++) {
      if (getNums(trainingData[si]).indexOf(n) >= 0) s++; else break;
    }
    knStreak[n] = s;
  }
  const pool = [];
  for (let n = 1; n <= 80; n++) pool.push(n);
  const emaRank = pool.slice().sort((a,b) => (emaComb[b]||-999) - (emaComb[a]||-999));
  const momRank = pool.slice().sort((a,b) => (knMomC[b]||-999) - (knMomC[a]||-999));
  const freqRank = pool.slice().sort((a,b) => (knFreq30[b]||-999) - (knFreq30[a]||-999));
  const streakRank = pool.slice().sort((a,b) => (knStreak[b]||0) - (knStreak[a]||0));
  const zvVotes = {};
  pool.forEach(n => {
    const emaR = emaRank.indexOf(n), momR = momRank.indexOf(n);
    const freqR = freqRank.indexOf(n), streakR = streakRank.indexOf(n);
    zvVotes[n] = (80 - Math.min(emaR, 79)) * 1.5 + (80 - Math.min(momR, 79)) * 1.0
               + (80 - Math.min(freqR, 79)) * 1.0 + (80 - Math.min(streakR, 79)) * 0.5;
  });
  return zvVotes;
}

// ========== 主逻辑 ==========
const TRAIN_WIN = 50;
const results = [];

// 生成所有历史天数据
const oRecHistory = []; // 橙卡近7天推荐
const pRecHistory = []; // 紫卡近7天推荐
for (let idx = 0; idx < allData.length; idx++) {
  const d = allData[idx];
  const drawn = getNums(d);
  const drawnSet = new Set(drawn);
  const pastData = allData.slice(0, idx);
  const trainEnd = Math.max(0, pastData.length - TRAIN_WIN);
  const trainingData = pastData.slice(trainEnd);
  if (trainingData.length < TRAIN_WIN) continue;
  const lastDraw = trainEnd > 0 ? getNums(pastData[pastData.length - 1]) : [];

  const orangeScores = orangeCard_emaScore(trainingData, lastDraw);
  const purpleVotes = purpleCard_votes(trainingData, lastDraw);

  /* ★ 橙卡只用1-40区间 / 紫卡只用41-80区间 */
  const orangeAllowed = new Set();
  for (let n = 1; n <= 40; n++) orangeAllowed.add(n);
  const purpleAllowed = new Set();
  for (let n = 41; n <= 80; n++) purpleAllowed.add(n);

  /* ★ 防死磕：最近7天推过的号降低权重（橙/紫分开跟踪） */
  const oAvoidSet = new Set();
  const pAvoidSet = new Set();
  const lookback = Math.min(7, oRecHistory.length);
  for (let ri = oRecHistory.length - lookback; ri < oRecHistory.length; ri++) {
    oRecHistory[ri].forEach(n => oAvoidSet.add(n));
    pRecHistory[ri].forEach(n => pAvoidSet.add(n));
  }

  const o2 = zoneSelect(orangeScores, 2, oAvoidSet, orangeAllowed);
  const p2 = zoneSelect(purpleVotes, 2, pAvoidSet, purpleAllowed);
  const o3 = zoneSelect(orangeScores, 3, oAvoidSet, orangeAllowed);
  const p3 = zoneSelect(purpleVotes, 3, pAvoidSet, purpleAllowed);

  /* 记录本次推荐，供后续防死磕 */
  oRecHistory.push([...o2, ...o3]);
  pRecHistory.push([...p2, ...p3]);
  if (oRecHistory.length > 30) oRecHistory.shift();
  if (pRecHistory.length > 30) pRecHistory.shift();

  results.push({
    date: d.d, period: d.p,
    orange_x2: { rec: o2, hit: o2.filter(n => drawnSet.has(n)), prize: calcPrize(2, o2.filter(n => drawnSet.has(n)).length) },
    purple_x2: { rec: p2, hit: p2.filter(n => drawnSet.has(n)), prize: calcPrize(2, p2.filter(n => drawnSet.has(n)).length) },
    orange_x3: { rec: o3, hit: o3.filter(n => drawnSet.has(n)), prize: calcPrize(3, o3.filter(n => drawnSet.has(n)).length) },
    purple_x3: { rec: p3, hit: p3.filter(n => drawnSet.has(n)), prize: calcPrize(3, p3.filter(n => drawnSet.has(n)).length) }
  });
}

// 保存
const outputPath = 'data/kl8_orange_purple_hits.json';
fs.mkdirSync('data', { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf8');

// 统计
const total = results.length;
const o2wins = results.filter(r => r.orange_x2.prize > 0).length;
const p2wins = results.filter(r => r.purple_x2.prize > 0).length;
const o3wins = results.filter(r => r.orange_x3.prize > 0).length;
const p3wins = results.filter(r => r.purple_x3.prize > 0).length;

console.log(`保存到 ${outputPath}, 共 ${total} 天`);
console.log(`橙选二: ${o2wins}/${total}天中奖 | 紫选二: ${p2wins}/${total}天`);
console.log(`橙选三: ${o3wins}/${total}天中奖 | 紫选三: ${p3wins}/${total}天`);
console.log('最新10天:');
results.slice(-10).forEach(r => {
  const wins = [];
  if (r.orange_x2.prize > 0) wins.push(`橙二+${r.orange_x2.prize}`);
  if (r.purple_x2.prize > 0) wins.push(`紫二+${r.purple_x2.prize}`);
  if (r.orange_x3.prize > 0) wins.push(`橙三+${r.orange_x3.prize}`);
  if (r.purple_x3.prize > 0) wins.push(`紫三+${r.purple_x3.prize}`);
  console.log(`  ${r.date} 橙二[${r.orange_x2.rec}] 紫二[${r.purple_x2.rec}] 橙三[${r.orange_x3.rec}] 紫三[${r.purple_x3.rec}] ${wins.length ? '>> ' + wins.join(' ') : ''}`);
});
