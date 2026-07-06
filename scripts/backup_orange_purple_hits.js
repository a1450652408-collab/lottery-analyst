/**
 * 快乐8 橙色卡片 & 紫色卡片 选二/选三 每日命中记录
 * ★ V5优化版 — 平衡评分 + 30码池过滤 + 自适应分区
 *
 * 流程: 全80码评分 → Top30码池 → 橙卡(1-40)/紫卡(41-80)分区选号
 *
 * 优化要点:
 * 1. 评分: 平衡评分(热×0.6+冷×0.4+重号+近期补偿)，消除热号系统性偏差
 * 2. 选号: 确定性TOP N，无随机化
 * 3. 30码池: 全80码评分取Top30，非30池号得-999
 * 4. 分区: 选二=2区(1-40/41-80)，选三=4区(各10号)
 *
 * 输出: data/kl8_orange_purple_hits.json
 */

const fs = require('fs');

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

// ========== 全80码平衡评分（统一评分，然后取Top30）==========
function computeAllScores(trainingData, lastDraw) {
  const W = trainingData.length;
  const expectedFreq = W * 20 / 80;
  
  const freq = {}, lastSeen = {}, freq5 = {};
  for (let n = 1; n <= 80; n++) { freq[n] = 0; lastSeen[n] = -1; freq5[n] = 0; }
  
  for (let j = 0; j < W; j++) {
    getNums(trainingData[j]).forEach(n => {
      if (n < 1 || n > 80) return;
      freq[n]++;
      lastSeen[n] = j;
      if (j < 5) freq5[n]++;
    });
  }
  
  const prevSet = new Set(lastDraw || []);
  
  const scores = {};
  for (let n = 1; n <= 80; n++) {
    const missVal = W - 1 - lastSeen[n];
    const freqRatio = freq[n] / Math.max(expectedFreq, 1);
    
    const heatScore = freqRatio * 8.0;
    const coldScore = Math.max(0, (1 - freqRatio)) * 4.0 + missVal * 1.0;
    const repeatBonus = prevSet.has(n) ? 6.0 : 0.0;
    const recentBonus = freq5[n] > 0 ? freq5[n] * 0.5 : 3.0;
    
    scores[n] = heatScore * 0.6 + coldScore * 0.4 + repeatBonus + recentBonus;
  }
  return scores;
}

// ========== 构建Top30码池并过滤评分 ==========
function buildTop30Pool(allScores) {
  const ranked = Object.entries(allScores)
    .map(([n, s]) => ({ n: parseInt(n), s }))
    .sort((a, b) => b.s - a.s);
  
  const top30Set = new Set(ranked.slice(0, 30).map(x => x.n));
  
  const filtered = {};
  for (let n = 1; n <= 80; n++) {
    filtered[n] = top30Set.has(n) ? (allScores[n] || 0) : -999;
  }
  return { filtered, top30Set };
}

// ========== 自适应分区选号（基于Top30过滤后评分） ==========
function zoneSelectFromPool(scores, selectN, avoidSet, rangeStart, rangeEnd) {
  /* 选二=2大区(各20号)，选三=4小区(各10号) */
  const nZones = (selectN === 2) ? 2 : 4;
  
  const zones = [];
  const step = Math.ceil((rangeEnd - rangeStart + 1) / nZones);
  for (let z = 0; z < nZones; z++) {
    const sz = rangeStart + z * step;
    const ez = Math.min(rangeEnd, sz + step - 1);
    zones.push([sz, ez]);
  }
  
  let result = [];
  const perZone = Math.ceil(selectN / zones.length);
  
  for (let zi = 0; zi < zones.length; zi++) {
    const zNums = [];
    for (let n = zones[zi][0]; n <= zones[zi][1]; n++) {
      zNums.push({ n, s: scores[n] || -999 });
    }
    zNums.sort((a, b) => b.s - a.s);
    
    let taken = 0;
    for (let i = 0; i < zNums.length && taken < perZone; i++) {
      const cand = zNums[i].n;
      /* 跳过非Top30(s=-999) 和 已选/避集 */
      if (zNums[i].s <= -999) continue;
      if (result.indexOf(cand) >= 0) continue;
      if (avoidSet && avoidSet.has(cand)) continue;
      result.push(cand);
      taken++;
    }
    /* 补漏：同一个区里如果有非Top30但需要凑数 */
    if (taken < perZone) {
      for (let i = 0; i < zNums.length && taken < perZone; i++) {
        const cand = zNums[i].n;
        if (result.indexOf(cand) < 0) { result.push(cand); taken++; }
      }
    }
  }
  
  return result.slice(0, selectN);
}

// ========== 主逻辑 ==========
const TRAIN_WIN = 50;
const results = [];

const oRecHistory = [];
const pRecHistory = [];
for (let idx = 0; idx < allData.length; idx++) {
  const d = allData[idx];
  const drawn = getNums(d);
  const drawnSet = new Set(drawn);
  const pastData = allData.slice(0, idx);
  const trainEnd = Math.max(0, pastData.length - TRAIN_WIN);
  const trainingData = pastData.slice(trainEnd);
  if (trainingData.length < TRAIN_WIN) continue;
  const lastDraw = trainEnd > 0 ? getNums(pastData[pastData.length - 1]) : [];

  /* 1. 全80码评分 */
  const allScores = computeAllScores(trainingData, lastDraw);
  
  /* 2. 过滤到Top30码池 */
  const { filtered: poolScores } = buildTop30Pool(allScores);

  /* 3. 分区选号（橙=1-40, 紫=41-80） */
  const oAvoidSet = new Set();
  const pAvoidSet = new Set();
  const lookback = Math.min(7, oRecHistory.length);
  for (let ri = oRecHistory.length - lookback; ri < oRecHistory.length; ri++) {
    oRecHistory[ri].forEach(n => oAvoidSet.add(n));
    pRecHistory[ri].forEach(n => pAvoidSet.add(n));
  }

  const o2 = zoneSelectFromPool(poolScores, 2, oAvoidSet, 1, 40);
  const p2 = zoneSelectFromPool(poolScores, 2, pAvoidSet, 41, 80);
  const o3 = zoneSelectFromPool(poolScores, 3, oAvoidSet, 1, 40);
  const p3 = zoneSelectFromPool(poolScores, 3, pAvoidSet, 41, 80);

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

const outputPath = 'data/kl8_orange_purple_hits.json';
fs.mkdirSync('data', { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf8');

const total = results.length;
const o2wins = results.filter(r => r.orange_x2.prize > 0).length;
const p2wins = results.filter(r => r.purple_x2.prize > 0).length;
const o3_53 = results.filter(r => r.orange_x3.prize >= 53).length;
const p3_53 = results.filter(r => r.purple_x3.prize >= 53).length;
const o3_3 = results.filter(r => r.orange_x3.prize >= 3 && r.orange_x3.prize < 53).length;
const p3_3 = results.filter(r => r.purple_x3.prize >= 3 && r.purple_x3.prize < 53).length;

console.log(`保存到 ${outputPath}, 共 ${total} 天`);
console.log(`--- V5 平衡评分 + 30码池 ---`);
console.log(`橙选二: ${o2wins}/${total} (${(o2wins/total*100).toFixed(2)}%) 中2 | 紫选二: ${p2wins}/${total} (${(p2wins/total*100).toFixed(2)}%) 中2`);
console.log(`橙选三: 中3=${o3_53}(${(o3_53/total*100).toFixed(2)}%) 中2=${o3_3}(${(o3_3/total*100).toFixed(2)}%) | 紫选三: 中3=${p3_53}(${(p3_53/total*100).toFixed(2)}%) 中2=${p3_3}(${(p3_3/total*100).toFixed(2)}%)`);
console.log('最新10天:');
results.slice(-10).forEach(r => {
  const wins = [];
  if (r.orange_x2.prize > 0) wins.push(`橙二+${r.orange_x2.prize}`);
  if (r.purple_x2.prize > 0) wins.push(`紫二+${r.purple_x2.prize}`);
  if (r.orange_x3.prize > 0) wins.push(`橙三+${r.orange_x3.prize}`);
  if (r.purple_x3.prize > 0) wins.push(`紫三+${r.purple_x3.prize}`);
  console.log(`  ${r.date} 橙二[${r.orange_x2.rec}] 紫二[${r.purple_x2.rec}] 橙三[${r.orange_x3.rec}] 紫三[${r.purple_x3.rec}] ${wins.length ? '>> ' + wins.join(' ') : ''}`);
});
