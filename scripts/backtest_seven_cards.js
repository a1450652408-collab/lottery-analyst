/* 回测: 快乐8 截图中的 7 张卡片 (2026-09-01 ~ 2026-10-15, 41期)
 * 1. 1-15区间·选五3胆7拖(三区均衡法)  动态
 * 2. 选八9码复式·短连号拼接           静态 C(9,8)=9注 18元/天
 * 3. 选九10码复式·连号拼接            静态 C(10,9)=10注 20元/天
 * 4. 选十11码复式·连号拼接            静态 C(11,10)=11注 22元/天
 * 5. 选五9码复式·月均中头奖           静态 C(9,5)=126注 252元/天
 * 6. 信号策略(Top5∑≥18) + 热度TOP10    动态
 * 7. 选三·每月追号计划(EMA+最优3区)     动态(每月初换号, 月内固定)
 * 每期只用该期之前的数据(无未来函数) */
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");

/* ---------- 数据 ---------- */
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");
const m = html.match(/window\.__LOTTERY_DATA\s*=\s*(\{[\s\S]*?\});\s*<\/script>/);
const embedded = JSON.parse(m[1]).kl8;
const NEW_DRAWS = [
  ["2026234","2026-09-01",[3,8,15,21,36,37,42,44,46,50,52,55,56,57,60,61,68,72,75,79]],
  ["2026235","2026-09-02",[2,11,14,19,21,23,36,48,50,51,53,60,62,64,66,72,73,75,78,80]],
  ["2026236","2026-09-03",[15,19,24,25,28,29,31,37,45,50,55,56,61,62,64,65,70,75,76,80]],
  ["2026237","2026-09-04",[2,6,9,13,15,17,18,20,21,30,37,43,48,51,53,55,58,68,74,77]],
  ["2026238","2026-09-05",[1,4,6,11,12,16,17,20,22,32,41,47,51,52,62,63,64,68,72,75]],
  ["2026239","2026-09-06",[14,17,20,21,26,27,29,30,37,44,45,47,54,55,61,65,68,69,77,79]],
  ["2026240","2026-09-07",[2,6,9,10,16,21,27,28,32,33,38,39,55,63,64,66,67,70,75,78]],
  ["2026241","2026-09-08",[7,9,15,16,18,19,32,33,36,37,40,52,53,60,62,63,66,68,69,73]],
  ["2026242","2026-09-09",[4,20,28,32,35,37,39,44,48,50,52,53,55,56,57,63,71,72,76,77]],
  ["2026243","2026-09-10",[1,2,3,9,21,29,31,36,37,41,43,46,50,55,64,67,68,70,74,76]],
  ["2026244","2026-09-11",[1,4,7,8,10,12,34,46,47,53,55,56,59,61,63,65,71,73,78,79]],
  ["2026245","2026-09-12",[5,6,9,15,18,25,26,27,30,31,34,36,39,43,44,48,54,63,65,77]],
  ["2026246","2026-09-13",[3,8,10,16,18,20,23,29,31,35,51,53,54,56,58,69,70,75,78,80]],
  ["2026247","2026-09-14",[5,7,19,22,28,29,38,39,41,42,43,44,55,58,61,65,66,71,72,73]],
  ["2026248","2026-09-15",[3,5,9,15,23,28,31,33,34,35,39,42,48,50,53,70,73,74,76,78]],
  ["2026249","2026-09-16",[4,8,10,11,13,26,29,34,41,50,51,52,53,57,59,65,66,73,74,77]],
  ["2026250","2026-09-17",[4,5,6,8,17,22,23,31,35,47,49,51,59,60,62,65,67,68,76,78]],
  ["2026251","2026-09-18",[1,4,8,9,10,11,18,26,28,29,43,49,51,52,53,54,62,66,70,76]],
  ["2026252","2026-09-19",[2,3,4,8,36,38,40,41,46,49,50,52,53,56,57,62,63,65,68,72]],
  ["2026253","2026-09-20",[1,2,8,17,23,24,29,31,40,41,46,47,51,54,59,62,65,72,74,79]],
  ["2026254","2026-09-21",[2,4,10,13,18,20,21,26,32,37,43,49,50,57,62,66,69,73,78,80]],
  ["2026255","2026-09-22",[2,9,12,16,18,23,26,31,36,44,47,52,54,55,59,60,61,66,72,77]],
  ["2026256","2026-09-23",[1,2,6,11,12,14,15,22,24,32,33,35,38,46,67,68,71,73,74,76]],
  ["2026257","2026-09-24",[1,4,7,8,10,13,23,24,31,33,39,40,47,48,58,61,65,74,76,79]],
  ["2026258","2026-09-25",[7,13,14,15,17,19,20,24,28,30,35,44,50,51,54,57,60,64,75,78]],
  ["2026259","2026-09-26",[5,6,13,26,29,30,34,36,44,50,54,56,61,62,66,73,74,76,79,80]],
  ["2026260","2026-09-27",[2,7,16,19,21,25,30,31,33,35,42,45,50,52,53,55,56,60,63,72]],
  ["2026261","2026-09-28",[1,11,17,21,23,27,28,35,37,42,45,46,48,61,72,73,75,78,79,80]],
  ["2026262","2026-09-29",[4,6,9,12,15,17,20,33,42,44,49,54,55,59,61,65,72,73,78,80]],
  ["2026263","2026-09-30",[7,8,9,10,11,13,22,24,25,26,31,33,37,45,50,51,62,67,70,80]],
  ["2026264","2026-10-05",[5,15,16,21,24,30,34,37,42,47,54,60,62,63,64,66,73,77,79,80]],
  ["2026265","2026-10-06",[2,7,9,12,13,20,23,25,31,34,35,36,39,50,51,56,59,73,77,78]],
  ["2026266","2026-10-07",[2,4,8,9,14,32,36,45,48,51,52,54,56,57,64,65,66,72,73,77]],
  ["2026267","2026-10-08",[3,16,20,26,29,35,41,42,43,44,45,49,50,54,59,60,61,68,74,79]],
  ["2026268","2026-10-09",[1,2,6,7,16,19,26,31,35,40,45,46,48,49,52,59,62,68,73,79]],
  ["2026269","2026-10-10",[1,2,3,7,11,13,15,18,25,27,30,35,44,46,55,57,60,63,70,73]],
  ["2026270","2026-10-11",[3,6,7,8,9,16,21,22,23,27,39,40,41,44,48,54,60,65,68,75]],
  ["2026271","2026-10-12",[10,17,20,22,30,31,37,40,41,43,44,45,50,52,56,58,59,63,71,76]],
  ["2026272","2026-10-13",[11,14,19,20,39,40,41,43,47,51,57,62,64,66,67,68,72,76,77,80]],
  ["2026273","2026-10-14",[9,10,12,14,23,24,27,31,35,38,49,51,52,54,55,58,61,63,65,76]],
  ["2026274","2026-10-15",[8,9,15,17,27,29,35,38,43,44,45,46,47,48,54,56,63,64,70,78]]
];
let mm = 0;
NEW_DRAWS.forEach(nd => { const e = embedded.find(x => x.p === nd[0]);
  if (e && JSON.stringify(e.n.slice().sort((a,b)=>a-b)) !== JSON.stringify(nd[2].slice().sort((a,b)=>a-b))) { mm++; console.log("MISMATCH", nd[0]); }});
if (mm) process.exit(1);

const ALL = {};
embedded.forEach(x => ALL[parseInt(x.p)] = {p:parseInt(x.p), d:x.d, n:x.n.slice()});
NEW_DRAWS.forEach(x => ALL[parseInt(x[0])] = {p:parseInt(x[0]), d:x[1], n:x[2].slice()});
const P_SORTED = Object.keys(ALL).map(Number).sort((a,b)=>a-b);

/* hist before period P, 新→旧 */
function histBefore(P) { return P_SORTED.filter(p => p < P).sort((a,b)=>b-a).map(p => ALL[p]); }

/* ---------- 奖表 (官方) ---------- */
const PZ = {
  "选三": {3:52, 2:3},
  "选五": {5:1000, 4:20, 3:3},
  "选八": {8:50000, 7:800, 6:80, 5:10, 4:3, 0:2},
  "选九": {9:300000, 8:2000, 7:225, 6:22, 5:5, 4:3, 0:2},
  "选十": {10:5000000, 9:8000, 8:800, 7:80, 6:5, 5:3, 0:2}
};
function prizeOf(play, hit, ticketSize) {
  const t = PZ[play];
  if (hit === 0 && t[0] !== undefined) return t[0];   // 全不中
  return t[hit] || 0;
}

function combos(arr, k) {
  const out = [];
  (function rec(start, cur) { if (cur.length === k) { out.push(cur.slice()); return; }
    for (let i = start; i < arr.length; i++) { cur.push(arr[i]); rec(i+1, cur); cur.pop(); } })(0, []);
  return out;
}
function evalTickets(tickets, draw, play) {
  const ds = new Set(draw);
  let prize = 0, best = 0, bestT = null, winCnt = 0; const dist = {};
  tickets.forEach(t => {
    const h = t.filter(n => ds.has(n)).length;
    const pr = prizeOf(play, h, t.length);
    prize += pr; if (pr > 0) winCnt++;
    dist[h] = (dist[h]||0)+1;
    if (h > best) { best = h; bestT = t.slice(); }
  });
  return {prize, best, bestT, winCnt, dist};
}

/* ---------- 动态卡片生成器 ---------- */
/* 1. 15区间选五3胆7拖 (复刻 _ztData 逻辑, 含 .reverse() 语义) */
function gen3dan7tuo(P) {
  const data = histBefore(P);                 // 新→旧
  const arr = data.slice(0, Math.min(50, data.length)).reverse(); // 旧→新
  const Z15 = []; for (let n=1;n<=15;n++) Z15.push(n);
  const f5 = {}; Z15.forEach(n=>f5[n]=0);
  arr.slice(0,5).forEach(it => it.n.forEach(x => { if (x>=1&&x<=15) f5[x]++; }));
  const zones = [[1,5],[6,10],[11,15]], dan = [];
  zones.forEach(z => { const nums=[]; for(let n=z[0];n<=z[1];n++) nums.push(n);
    nums.sort((a,b)=>(f5[b]||0)-(f5[a]||0)); dan.push(nums[0]); });
  dan.sort((a,b)=>a-b);
  const f10 = {}; Z15.forEach(n=>f10[n]=0);
  arr.slice(0,10).forEach(it => it.n.forEach(x => { if (x>=1&&x<=15) f10[x]++; }));
  const tuo = Z15.filter(n => dan.indexOf(n)<0).sort((a,b)=>(f10[b]||0)-(f10[a]||0)).slice(0,7).sort((a,b)=>a-b);
  const pairs = combos(tuo, 2);
  return { dan, tuo, tickets: pairs.map(pr => dan.concat(pr)) };
}
/* 6. 信号策略: 14码 (ZONE=1-20+60-80, 近5期频率) */
function genSignal(P) {
  const data = histBefore(P);
  const ZONE = []; for (let i=1;i<=20;i++) ZONE.push(i); for (let i=60;i<=80;i++) ZONE.push(i);
  const zs = new Set(ZONE);
  const recent5 = data.slice(0, Math.min(5, data.length));
  const freq = {}; ZONE.forEach(n=>freq[n]=0);
  recent5.forEach(it => it.n.forEach(n => { if (zs.has(n)) freq[n]++; }));
  const sorted = ZONE.slice().sort((a,b)=>(freq[b]||0)-(freq[a]||0));
  let top5Sum = 0; for (let k=0;k<5;k++) top5Sum += freq[sorted[k]]||0;
  const p14 = []; for (let k=0;k<Math.min(14,sorted.length);k++) if (freq[sorted[k]]>0) p14.push(sorted[k]);
  if (p14.length<14) ZONE.forEach(n => { if (p14.length>=14) return; if (p14.indexOf(n)===-1) p14.push(n); });
  p14.sort((a,b)=>a-b);
  const p10 = sorted.slice(0,10);
  return { top5Sum, picks14: p14, picks10: p10, fire: top5Sum>=18 };
}
/* 7. 选三/选二 每月追号: 用月初前的数据算, 月内固定 */
function genX3(ym) {   // ym like "2026-09"
  const data = P_SORTED.slice().reverse().map(p=>ALL[p]).filter(it => it.d.slice(0,7) < ym).slice(0,50);
  return genXGeneric(data, 3);
}
function genXGeneric(dat, nZones) {
  const per = dat.length;
  const ema = {};
  for (let n=1;n<=80;n++) { const seq = dat.map(it=>it.n.indexOf(n)>=0?1:0);
    let e = seq[seq.length-1]; for (let j=seq.length-2;j>=0;j--) e = 0.5*seq[j]+0.5*e; ema[n]=e; }
  const R5={}, P5={}; for(let n=1;n<=80;n++){R5[n]=0;P5[n]=0;}
  dat.slice(0,Math.min(10,per)).forEach((it,j)=>it.n.forEach(n=>{ if(j<5)R5[n]++; else P5[n]++; }));
  const mom={}; for(let n=1;n<=80;n++){const v=(R5[n]-P5[n])/Math.max(P5[n],1); mom[n]=Math.max(-2,Math.min(2,v));}
  const f30={}; for(let n=1;n<=80;n++)f30[n]=0;
  dat.slice(0,Math.min(30,per)).forEach(it=>it.n.forEach(n=>f30[n]++));
  const zones=[[1,20],[21,40],[41,60],[61,80]], score={}, win=Math.min(30,per);
  for(let n=1;n<=80;n++) score[n]=(ema[n]||0)*5+(Math.min(f30[n]||0,win)/win)*3+(mom[n]||0)*2;
  const zAvg=[]; for(let zi=0;zi<4;zi++){let s=0;for(let n=zones[zi][0];n<=zones[zi][1];n++)s+=score[n]||0; zAvg.push({i:zi,a:s/20});}
  zAvg.sort((a,b)=>b.a-a.a);
  const picks=[]; for(let k=0;k<nZones;k++){const z=zones[zAvg[k].i];let best=z[0],bs=-999;
    for(let n=z[0];n<=z[1];n++){ if((score[n]||0)>bs){bs=score[n];best=n;} } picks.push(best);}
  picks.sort((a,b)=>a-b);
  return picks;
}

/* ---------- 静态卡片 ---------- */
const S8 = [5,11,12,18,19,62,63,77,78];
const S9 = [8,9,15,16,65,66,72,73,79,80];
const S10 = [1,2,5,6,12,18,19,27,40,41,53];
const S5 = [5,11,12,18,19,62,63,77,78];

/* ---------- 校验: 复现截图(状态=数据至10-14/10-15) ---------- */
console.log("=== 复现校验 ===");
const chk3 = gen3dan7tuo(2026274); // 数据到 10-14 时 (期2026274未开奖前), 即 histBefore(2026274)
console.log("卡片1 胆码:", chk3.dan.join(","), " 拖码:", chk3.tuo.join(","), "  (截图应为 胆4,8,12 拖3,5,7,9,13,14,15)");
console.log("卡片7 选三 10月号:", genX3("2026-10").join(","), "  (截图应为 25,45,80)");
console.log("卡片7 选三  9月号:", genX3("2026-09").join(","));
console.log("");

/* ---------- 回测 ---------- */
const WIN = P_SORTED.filter(p => p >= 2026234 && p <= 2026274);
const results = [];
function record(name, costPerDay, rows) {
  let cost = 0, prize = 0;
  const days = [];
  rows.forEach(r => {
    cost += costPerDay; prize += r.prize;
    days.push({d:r.d, prize:r.prize, best:r.best, bestT:r.bestT, winCnt:r.winCnt, dist:r.dist});
  });
  const hd = days.filter(r=>r.prize>0).length;
  const bd = days.slice().sort((a,b)=>b.prize-a.prize)[0];
  const agg = {}; days.forEach(r=>Object.keys(r.dist).forEach(h=>agg[h]=(agg[h]||0)+r.dist[h]));
  results.push({name, cost, prize, net:prize-cost, roi:100*prize/cost, hd, bd, agg, days});
}

/* 卡片1 */
record("卡片1 1-15区间·选五3胆7拖(42元/期)", 42, WIN.map(P => {
  const g = gen3dan7tuo(P);
  const r = evalTickets(g.tickets, ALL[P].n, "选五");
  r.d = ALL[P].d; r.P = P; r.extra = "胆" + g.dan.join(",") + "/拖" + g.tuo.join(",");
  return r;
}));
/* 卡片2 */
record("卡片2 选八9码复式(18元/天)", 18, WIN.map(P => { const r = evalTickets(combos(S8,8), ALL[P].n, "选八"); r.d=ALL[P].d; return r; }));
/* 卡片3 */
record("卡片3 选九10码复式(20元/天)", 20, WIN.map(P => { const r = evalTickets(combos(S9,9), ALL[P].n, "选九"); r.d=ALL[P].d; return r; }));
/* 卡片4 */
record("卡片4 选十11码复式(22元/天)", 22, WIN.map(P => { const r = evalTickets(combos(S10,10), ALL[P].n, "选十"); r.d=ALL[P].d; return r; }));
/* 卡片5 */
record("卡片5 选五9码复式(252元/天)", 252, WIN.map(P => { const r = evalTickets(combos(S5,5), ALL[P].n, "选五"); r.d=ALL[P].d; return r; }));
/* 卡片6 */
record("卡片6 信号策略·选十14码复式(触发才出手, 2002元/次)", 0, WIN.map(P => {
  const g = genSignal(P);
  const r = { d: ALL[P].d, prize: 0, best: 0, bestT: null, winCnt: 0, dist: {}, fired: g.fire, t5: g.top5Sum };
  if (g.fire) { const e = evalTickets(combos(g.picks14,10), ALL[P].n, "选十"); Object.assign(r, e); r.cost = 2002; }
  return r;
}));
/* 卡片7 */
record("卡片7 选三·每月追号(2元/天)", 2, WIN.map(P => {
  const ym = ALL[P].d.slice(0,7);
  const picks = genX3(ym);
  const ds = new Set(ALL[P].n);
  const hit = picks.filter(n => ds.has(n)).length;
  const pr = hit >= 3 ? 53 : hit >= 2 ? 3 : 0;
  return { d: ALL[P].d, P, prize: pr, best: hit, bestT: picks.slice(), winCnt: pr>0?1:0, dist: {[hit]:1} };
}));

/* ---------- 输出 ---------- */
results.forEach(R => {
  if (R.name.startsWith("卡片6")) {
    const fired = R.days.filter(d=>d.fired);
    const cost = fired.length * 2002, prize = fired.reduce((a,b)=>a+b.prize,0);
    console.log("===== " + R.name + " =====");
    console.log("窗口内触发次数: " + fired.length + " (阈值Top5∑≥18)");
    console.log("触发日: " + (fired.length ? fired.map(f=>f.d+"(∑"+f.t5+")").join(", ") : "无"));
    if (fired.length) {
      console.log("投入: " + cost + " 元 | 奖金: " + prize + " 元 | 净: " + (prize-cost) + " 元 | 回收率: " + (100*prize/cost).toFixed(1) + "%");
      fired.forEach(f => console.log("  " + f.d + " 奖金" + f.prize + "元 单注最高中" + f.best + "个: " + (f.bestT||[]).map(n=>String(n).padStart(2,"0")).join(" ")));
    }
    console.log("");
    return;
  }
  console.log("===== " + R.name + " =====");
  console.log("总投入: " + R.cost + " 元 (" + R.days.length + "期)");
  console.log("总奖金: " + R.prize + " 元 | 净: " + R.net + " 元 | 回收率: " + R.roi.toFixed(1) + "%");
  console.log("有奖金天数: " + R.hd + "/" + R.days.length);
  console.log("单注命中分布: " + JSON.stringify(R.agg));
  if (R.bd) console.log("最佳一天: " + R.bd.d + " 奖金" + R.bd.prize + "元 单注最高中" + R.bd.best + "个 " + (R.bd.bestT||[]).map(n=>String(n).padStart(2,"0")).join(" "));
  /* 打印达到"较大奖"的日子 */
  const bigHits = R.days.filter(d => d.prize > 0).sort((a,b)=>b.prize-a.prize).slice(0,8);
  bigHits.forEach(d => console.log("  " + d.d + " 奖金" + String(d.prize).padStart(5) + "元 净" + (d.prize-R.cost/R.days.length>=0?"+":"") + (d.prize-R.cost/R.days.length) + " 最高中" + d.best + "个: " + (d.bestT||[]).map(n=>String(n).padStart(2,"0")).join(" ")));
  console.log("");
});
