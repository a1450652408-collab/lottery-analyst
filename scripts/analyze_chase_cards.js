/* 三张追号卡（选二/选三/选六）到底有没有"算法边际"？
 * 1) 理论回收率（固定奖表下的数学期望）
 * 2) 历史全量实际回收率（用卡片真实号码）
 * 3) 随机选号基线分布 → 实际值落在第几百分位（>95 才算有边际）
 */
const fs = require("fs"), path = require("path");
const ROOT = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const KL8 = JSON.parse(html.match(/window\.__LOTTERY_DATA\s*=\s*(\{[\s\S]*?\});\s*<\/script>/)[1]).kl8;
const ARCH = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "all_recommendations_archive.json"), "utf8")).kl8;

const PRIZE = { x2: { 2: 19 }, x3: { 3: 52, 2: 3 }, x6: { 6: 2880, 5: 30, 4: 10, 3: 3 } };
const COST = 2;

/* ---------- 理论: 超几何分布 P(命中 k 个 | 选 n 个, 80 球开 20) ---------- */
function C(n, k) { if (k < 0 || k > n) return 0; let r = 1; for (let i = 1; i <= k; i++) r = r * (n - k + i) / i; return r; }
function pHit(n, k) { return C(n, k) * C(80 - n, 20 - k) / C(80, 20); }
function evOf(play, n) {
  let ev = 0, rows = [];
  for (let k = n; k >= 0; k--) {
    const p = pHit(n, k), w = PRIZE[play][k] || 0;
    if (p > 1e-12) rows.push({ k, p, w, contrib: p * w });
    ev += p * w;
  }
  return { ev, roi: ev / COST, rows };
}

console.log("======== 1. 理论（数学期望，与选号算法无关） ========");
[["选二", "x2", 2], ["选三", "x3", 3], ["选六", "x6", 6]].forEach(([name, key, n]) => {
  const { ev, roi, rows } = evOf(key, n);
  console.log(`  ${name}: 每注成本 ${COST} 元, 期望回报 ${ev.toFixed(3)} 元 → **回收率 ${(roi * 100).toFixed(1)}%** (每期平均亏 ${(COST - ev).toFixed(3)} 元)`);
  rows.filter(r => r.w > 0).forEach(r => console.log(`      中${r.k}: 概率 ${(r.p * 100).toFixed(3)}% × ${r.w}元 = ${r.contrib.toFixed(4)}`));
});

/* ---------- 2. 历史实际（卡片真实号码） ---------- */
const byDate = {};
(KL8 || []).forEach(x => byDate[x.d] = x);
const archByDate = {};
(Array.isArray(ARCH) ? ARCH : Object.values(ARCH)).forEach(x => archByDate[x.date] = x);

function evalPickSet(picks, days, prizeMap) {
  let cost = 0, prize = 0, dist = {};
  days.forEach(d => {
    const draw = byDate[d]; if (!draw) return;
    const set = new Set(draw.n);
    const h = picks.filter(n => set.has(n)).length;
    cost += COST; prize += (prizeMap[h] || 0);
    dist[h] = (dist[h] || 0) + 1;
  });
  return { cost, prize, roi: prize / cost, dist, days: cost / COST };
}

console.log("\n======== 2. 历史实际（卡片真实号码，全部可回测期） ========");
const x2days = Object.keys(archByDate).filter(d => archByDate[d].x2_monthly && byDate[d]);
const x3days = Object.keys(archByDate).filter(d => archByDate[d].x3_monthly && byDate[d]);
const x2 = evalPickSet(archByDate[x2days[0]].x2_monthly.rec, x2days, PRIZE.x2);
const x3 = evalPickSet(archByDate[x3days[0]].x3_monthly.rec, x3days, PRIZE.x3);
console.log(`  选二: ${x2.days} 期, 投入 ${x2.cost} 元, 奖金 ${x2.prize} 元 → 回收率 ${(x2.roi * 100).toFixed(1)}% | 命中分布 ${JSON.stringify(x2.dist)}`);
console.log(`  选三: ${x3.days} 期, 投入 ${x3.cost} 元, 奖金 ${x3.prize} 元 → 回收率 ${(x3.roi * 100).toFixed(1)}% | 命中分布 ${JSON.stringify(x3.dist)}`);

/* 选六: 复刻卡片算法（按"月初之前的数据"取 EMA×5+频率×3+动量×2 的 Top6） */
const sorted = KL8.slice().sort((a, b) => parseInt(a.p) - parseInt(b.p));
function pick6(ym) {
  const prev = sorted.filter(x => x.d < ym + "-01").slice(-50).reverse(); // newest-first 50
  const ema = {}, R5 = {}, P5 = {}, f30 = {};
  for (let n = 1; n <= 80; n++) { ema[n] = 0; R5[n] = 0; P5[n] = 0; f30[n] = 0; }
  for (let n = 1; n <= 80; n++) {
    const seq = prev.map(x => x.n.indexOf(n) >= 0 ? 1 : 0);
    let e = seq[seq.length - 1]; for (let j = seq.length - 2; j >= 0; j--) e = 0.5 * seq[j] + 0.5 * e;
    ema[n] = e;
  }
  prev.slice(0, 10).forEach((x, j) => x.n.forEach(n => { if (j < 5) R5[n]++; else P5[n]++; }));
  prev.slice(0, 30).forEach(x => x.n.forEach(n => f30[n]++));
  const score = {};
  for (let n = 1; n <= 80; n++) {
    const mom = Math.max(-2, Math.min(2, (R5[n] - P5[n]) / Math.max(P5[n], 1)));
    score[n] = ema[n] * 5 + (Math.min(f30[n], 30) / 30) * 3 + mom * 2;
  }
  return Array.from({ length: 80 }, (_, i) => i + 1).sort((a, b) => score[b] - score[a]).slice(0, 6).sort((a, b) => a - b);
}
const months = [...new Set(KL8.map(x => x.d.slice(0, 7)))].sort();
const x6days = KL8.filter(x => x.d >= "2026-05-01").map(x => x.d);   // 卡6上线后区间
let x6 = { cost: 0, prize: 0, dist: {} };
months.forEach(ym => {
  const days = KL8.filter(x => x.d.slice(0, 7) === ym).map(x => x.d);
  if (!days.length) return;
  const picks = pick6(ym);
  const r = evalPickSet(picks, days, PRIZE.x6);
  x6.cost += r.cost; x6.prize += r.prize;
  Object.keys(r.dist).forEach(k => x6.dist[k] = (x6.dist[k] || 0) + r.dist[k]);
});
console.log(`  选六: ${x6.cost / COST} 期, 投入 ${x6.cost} 元, 奖金 ${x6.prize} 元 → 回收率 ${(x6.prize / x6.cost * 100).toFixed(1)}% | 命中分布 ${JSON.stringify(x6.dist)}`);

/* ---------- 3. 随机基线: 同样的"每月换一次号 + 每天 1 注" ---------- */
console.log("\n======== 3. 随机选号基线（同结构: 每月固定一组号、每天1注） ========");
function simRandom(size, prizeMap, trials) {
  const out = [];
  for (let t = 0; t < trials; t++) {
    let cost = 0, prize = 0;
    months.forEach(ym => {
      const days = KL8.filter(x => x.d.slice(0, 7) === ym).map(x => x.d);
      if (!days.length) return;
      const pool = Array.from({ length: 80 }, (_, i) => i + 1);
      const picks = [];
      while (picks.length < size) { const i = Math.floor(Math.random() * pool.length); picks.push(pool.splice(i, 1)[0]); }
      days.forEach(d => {
        const set = new Set(byDate[d].n);
        cost += COST; prize += (prizeMap[picks.filter(n => set.has(n)).length] || 0);
      });
    });
    out.push(prize / cost);
  }
  out.sort((a, b) => a - b);
  return out;
}
function pct(sortedArr, v) { return 100 * sortedArr.filter(x => x <= v).length / sortedArr.length; }
[["选二", "x2", 2, x2.roi], ["选三", "x3", 3, x3.roi], ["选六", "x6", 6, x6.prize / x6.cost]].forEach(([name, key, n, actual]) => {
  const R = simRandom(n, PRIZE[key], 3000);
  const mean = R.reduce((a, b) => a + b, 0) / R.length;
  console.log(`  ${name}: 随机 3000 次 → 均值 ${(mean * 100).toFixed(1)}%, 5%~95% 区间 [${(R[150] * 100).toFixed(1)}%, ${(R[2849] * 100).toFixed(1)}%], 中位数 ${(R[1500] * 100).toFixed(1)}%`);
  console.log(`        卡片实际 ${(actual * 100).toFixed(1)}% → 位于随机分布第 **${pct(R, actual).toFixed(0)} 百分位** ${pct(R, actual) > 90 ? "（可能有边际）" : "（与随机无显著差别）"}`);
});

/* ---------- 4. 本月(2026-10)明细，对齐截图 ---------- */
console.log("\n======== 4. 2026-10 至今明细（对应你的截图） ========");
const octDays = KL8.filter(x => x.d.slice(0, 7) === "2026-10").map(x => x.d).sort();
[["选二", "x2", 2, PRIZE.x2], ["选三", "x3", 3, PRIZE.x3], ["选六", "x6", 6, PRIZE.x6]].forEach(([name, key, n, pm]) => {
  const picks = key === "x6" ? pick6("2026-10") : (key === "x2" ? archByDate["2026-10-16"].x2_monthly.rec : archByDate["2026-10-16"].x3_monthly.rec);
  let c = 0, p = 0, hits = [];
  octDays.forEach(d => { const set = new Set(byDate[d].n); const h = picks.filter(x => set.has(x)).length; c += 2; p += (pm[h] || 0); hits.push(h); });
  console.log(`  ${name} 号码 [${picks.join(",")}]: ${octDays.length} 期, 投入 ${c} 元, 奖金 ${p} 元, 净 ${p - c} 元 | 每期命中 ${hits.join("/")}`);
});
