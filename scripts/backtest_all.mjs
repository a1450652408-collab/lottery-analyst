/**
 * 全彩种回测脚本 v2
 * 用 Node.js vm 模块直接执行算法代码，不依赖 DOM
 */
import { readFileSync, writeFileSync } from 'fs';
import vm from 'vm';

const CONFIG = {
  outputFile: 'data/backtest_result.json'
};

const LOTTERY_TYPES = [
  { type: 'ssq', name: '双色球', recPeriod: 15 },
  { type: 'dlt', name: '大乐透', recPeriod: 15 },
  { type: 'qlc', name: '七乐彩', recPeriod: 15 },
  { type: 'kl8', name: '快乐8', recPeriod: 30 },
  { type: 'fc3d', name: '福彩3D', recPeriod: 30 },
  { type: 'pl3', name: '排列三', recPeriod: 30 },
  { type: 'pl5', name: '排列五', recPeriod: 30 },
  { type: 'qxc', name: '七星彩', recPeriod: 30 }
];

function extractAlgorithms(html) {
  let idx = 0, lastS, lastE;
  while (true) {
    const s = html.indexOf('<script>', idx);
    if (s < 0) break;
    const e = html.indexOf('</script>', s);
    if (e < 0) break;
    lastS = s + 8; lastE = e;
    idx = e + 9;
  }
  
  const mainCode = html.substring(lastS, lastE);
  
  // 找到 IIFE 的起始和结束位置
  const iifeStart = mainCode.indexOf('(function(){');
  const iifeEnd = mainCode.lastIndexOf('})();');
  
  let code;
  if (iifeStart >= 0 && iifeEnd >= 0) {
    // 保留函数体，但不立即执行
    // 把 (function(){ → function algoWrapper() {
    // 把 })(); → } (只是定义，不执行)
    const prefix = mainCode.substring(0, iifeStart);
    const body  = mainCode.substring(iifeStart + 11, iifeEnd);
    // 平衡 IIFE 体（+1未闭合）
    const readyCheck = body.lastIndexOf('if (document.readyState');
    const cleanBody = (readyCheck > 0 ? body.substring(0, readyCheck) : body) + '\n}';
    code = prefix + 'function algoWrapper() {\n' + cleanBody + '\nreturn { generateRecommend:generateRecommend, getNums:getNums, C:typeof C!==\"undefined\"?C:window._C };\n}\n';
  } else {
    code = mainCode;
  }
  
  return code;
}

function main() {
  console.log('📊 全彩种回测开始...\n');
  
  const html = readFileSync('index.html', 'utf-8');
  const algoCode = extractAlgorithms(html);
  
  // 提取数据
  const dataMatch = html.match(/window\.__LOTTERY_DATA\s*=\s*({.+?});/s);
  if (!dataMatch) { console.error('数据块未找到'); return; }
  
  // 构建 VM 上下文 - window 指向自身
  const sandbox = { window: null, document: null, console: null, setTimeout: null, setInterval: null,
    clearTimeout: null, clearInterval: null, Promise: Promise,
    Math: Math, parseInt: parseInt, parseFloat: parseFloat,
    isNaN: isNaN, Array: Array, Object: Object, String: String,
    Number: Number, Boolean: Boolean, Map: Map, Set: Set,
    RegExp: RegExp, Date: Date, JSON: JSON, Error: Error,
    navigator: { clipboard: null, userAgent: 'node' },
    location: { href: '', search: '' },
    localStorage: { getItem: () => null, setItem: () => {} },
    addEventListener: () => {}, removeEventListener: () => {},
    __LOTTERY_DATA: null
  };
  sandbox.window = sandbox;
  sandbox.document = { getElementById: () => null, addEventListener: () => {},
    createElement: (t) => ({ style: {}, textContent: '', appendChild: () => {},
      setAttribute: () => {}, addEventListener: () => {} }),
    body: { appendChild: () => {}, removeChild: () => {} },
    querySelectorAll: () => [], querySelector: () => null,
    documentElement: { style: {} }
  };
  sandbox.console = { log: () => {}, error: () => {}, warn: () => {} };
  
  // 构建包装代码
  const wrappedCode = `
    ${algoCode}
    var _algoExports = algoWrapper();
    if (_algoExports && _algoExports.generateRecommend) {
      this.generateRecommend = _algoExports.generateRecommend;
      this.getNums = _algoExports.getNums;
      this.getBlues = _algoExports.getBlues || function(d) { var b=d.b||[]; return Array.isArray(b)?b:[b]; };
      this.C = _algoExports.C;
    }
  `;
  
  const script = new vm.Script(wrappedCode, { filename: 'algorithms.js' });
  try {
    script.runInNewContext(sandbox, { timeout: 30000 });
  } catch(e) {
    console.error('算法加载失败:', e.message);
    return;
  }
  
  const generateRecommend = sandbox.generateRecommend;
  const getNums = sandbox.getNums;
  const getBlues = sandbox.getBlues;
  const C = sandbox.C;
  
  if (!generateRecommend || !C) {
    console.error('推荐函数不可用');
    return;
  }
  
  // 解析数据
  const rawData = JSON.parse(dataMatch[1]);
  const cache = {};
  for (const type of Object.keys(rawData)) {
    cache[type] = rawData[type];
  }
  
  const allResults = {};
  
  for (const lt of LOTTERY_TYPES) {
    const data = cache[lt.type];
    if (!data || data.length < 40) {
      console.log(`⚠ ${lt.name}: 数据不足 (${data ? data.length : 0}期)`);
      allResults[lt.type] = { error: '数据不足' };
      continue;
    }
    
    console.log(`\n🔍 ${lt.name} (${lt.recPeriod}期窗口, ${data.length}期数据) ` + '='.repeat(30));
    
    const cfg = C[lt.type];
    const bt = {
      total: 0,
      basicHits: [],
      danHits: [],
      enhancedHits: [],
      dantuoEnhancedHits: []
    };
    
    const startIdx = lt.recPeriod + 1;
    
    for (let i = startIdx; i < data.length; i++) {
      const pastData = data.slice(i - lt.recPeriod, i);
      const draw = data[i];
      const drawn = getNums(draw);
      const blues = getBlues ? getBlues(draw) : [];
      
      if (!drawn || drawn.length === 0) continue;
      
      const rec = generateRecommend(pastData, cfg);
      if (!rec || !rec.basic) continue;
      
      bt.total++;
      
      // 1. 基本推荐
      rec.basic.forEach((item, idx) => {
        const nums = item.nums || item.r || [];
        const itemBlues = item.blues || item.b || [];
        const hits = nums.filter(n => drawn.includes(n)).length;
        const bHits = itemBlues.filter(n => blues.includes(n)).length;
        if (!bt.basicHits[idx]) bt.basicHits[idx] = { label: item.label || `注${idx+1}`, reds: [], blues: [], count: 0 };
        bt.basicHits[idx].reds.push(hits);
        bt.basicHits[idx].blues.push(bHits);
        bt.basicHits[idx].count++;
      });
      
      // 2. 胆拖推荐
      if (rec.dantuo) {
        rec.dantuo.forEach((item, di) => {
          const dan = item.dan || [];
          const tuo = item.tuo || [];
          const dHit = dan.filter(n => drawn.includes(n)).length;
          const tHit = tuo.filter(n => drawn.includes(n)).length;
          if (!bt.danHits[di]) bt.danHits[di] = { dan: [], tuo: [], count: 0 };
          bt.danHits[di].dan.push(dHit);
          bt.danHits[di].tuo.push(tHit);
          bt.danHits[di].count++;
        });
      }
      
      // 3. 增强推荐（大复试/多策略/大底）
      if (cfg.type === 'lotto') {
        const hotReds = (rec.analysis && rec.analysis.hotReds) || [];
        const hotBlues = (rec.analysis && rec.analysis.hotBlues) || [];
        const ec = lt.type === 'dlt' ? 8 : 9;
        const er = hotReds.slice(0, ec);
        const eb = hotBlues.slice(0, 3);
        const rh = er.filter(n => drawn.includes(n)).length;
        const bh = eb.filter(n => blues.includes(n)).length;
        bt.enhancedHits.push({ reds: rh, blues: bh });
      } else if (cfg.type === 'keno') {
        // 用热号前20个
        const hot = (rec.analysis && rec.analysis.hotReds) || [];
        const e20 = hot.slice(0, 20);
        const h = e20.filter(n => drawn.includes(n)).length;
        bt.enhancedHits.push({ hits: h, total: 20 });
      } else if (cfg.type === 'digit') {
        // 每位统计
        // 暂不统计digit增强
      }
    }
    
    allResults[lt.type] = bt;
    printSummary(lt.name, bt, cfg);
  }
  
  // 保存详细结果
  writeFileSync(CONFIG.outputFile, JSON.stringify(allResults, (key, val) => {
    if (key === 'reds' || key === 'blues' || key === 'dan' || key === 'tuo' || key === 'hits') return val.slice(0, 30) + '...';
    return val;
  }, 2));
  console.log(`\n✅ 结果已保存到 ${CONFIG.outputFile}`);
}

function printSummary(name, bt, cfg) {
  console.log(`  📋 基本推荐 (${bt.total}期):`);
  bt.basicHits.forEach((bh, idx) => {
    const avgR = (bh.reds.reduce((a,b) => a+b, 0) / bh.count).toFixed(2);
    const maxR = Math.max(...bh.reds);
    const freq = {};
    bh.reds.forEach(h => { const k = Math.min(h, 9); freq[k] = (freq[k] || 0) + 1; });
    const topHits = Object.entries(freq).sort((a,b) => b[0]-a[0]).slice(0,4).map(([k,v]) => `中${k}:${v}期`).join(' | ');
    console.log(`    ${bh.label} 红球: 平均${avgR}个 最高${maxR}个 分布: ${topHits}`);
  });
  
  if (bt.danHits.length > 0) {
    console.log(`  📋 胆拖推荐:`);
    bt.danHits.slice(0, 4).forEach((dh, idx) => {
      const avgD = (dh.dan.reduce((a,b) => a+b, 0) / dh.count).toFixed(2);
      const avgT = (dh.tuo.reduce((a,b) => a+b, 0) / dh.count).toFixed(2);
      const maxD = Math.max(...dh.dan);
      const maxT = Math.max(...dh.tuo);
      console.log(`    胆拖${idx+1}: 胆平均${avgD}个(最高${maxD}) 拖平均${avgT}个(最高${maxT})`);
    });
  }
  
  if (bt.enhancedHits.length > 0) {
    if (cfg.type === 'lotto') {
      const reds = bt.enhancedHits.map(h => h.reds);
      const avgR = (reds.reduce((a,b) => a+b, 0) / reds.length).toFixed(2);
      const maxR = Math.max(...reds);
      const freq = {};
      reds.forEach(h => { const k = Math.min(h, 9); freq[k] = (freq[k] || 0) + 1; });
      const dist = Object.entries(freq).sort((a,b) => b[0]-a[0]).slice(0,6).map(([k,v]) => `中${k}:${v}期`).join(' | ');
      const ec = cfg.rMax <= 35 && cfg.bMax > 0 ? (cfg.rC <= 6 ? '9红+3蓝' : '8红+3蓝') : `${cfg.rC}码`;
      console.log(`  🏆 大复试(${ec}): 平均${avgR}个 最高${maxR}个 分布: ${dist}`);
    } else if (cfg.type === 'keno') {
      const hits = bt.enhancedHits.map(h => h.hits);
      const avg = (hits.reduce((a,b) => a+b, 0) / hits.length).toFixed(2);
      const max = Math.max(...hits);
      const freq = {};
      hits.forEach(h => { const k = Math.min(h, 20); freq[k] = (freq[k] || 0) + 1; });
      const dist = Object.entries(freq).sort((a,b) => b[0]-a[0]).slice(0,5).map(([k,v]) => `中${k}:${v}期`).join(' | ');
      console.log(`  🏆 多策略20码: 平均${avg}个 最高${max}个 分布: ${dist}`);
    }
  }
}

main();
