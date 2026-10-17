/* 功能审计: 用桩 DOM 加载 index.html 的应用脚本, 对 10 个彩种跑 generateRecommend + renderAnalysis
 * 目的: 捕捉运行时异常(如历史上的 双色球 getBlues 崩溃) */
const fs = require("fs"), path = require("path"), vm = require("vm");
const ROOT = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "index.html"), "utf8");

/* ---- 找到含 window._C 的 script 块并注入导出 ---- */
const blocks = [...html.matchAll(/<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const idx = blocks.findIndex(b => b.includes("window._C = {"));
if (idx < 0) { console.log("未找到应用脚本块"); process.exit(1); }
let app = blocks[idx];
const tail = app.lastIndexOf("})();");
if (tail < 0) { console.log("未找到 IIFE 结尾"); process.exit(1); }
const EXPORT = `;window.__T = { generateRecommend: generateRecommend, renderAnalysis: renderAnalysis, renderRecommend: renderRecommend, _C: window._C, setCur: function(v){ cur = v; }, getCur: function(){ return cur; } };\n`;
app = app.slice(0, tail) + EXPORT + app.slice(tail);
console.log("应用脚本块 #" + (idx + 1) + " (" + blocks[idx].length + " 字符) 已注入导出");

/* ---- 桩 DOM ---- */
const ctxStub = new Proxy({}, { get: (t, k) => (k === "canvas" ? { width: 300, height: 150 } : (k === "measureText" ? (() => ({ width: 10 })) : (() => {}))) });
let PARENT = null;
function getParent() {
  if (!PARENT) PARENT = {
    style: {}, classList: { add() {}, remove() {}, contains() { return false; } }, innerHTML: "", children: [],
    clientWidth: 360, clientHeight: 220, offsetWidth: 360, offsetHeight: 220,
    appendChild() {}, addEventListener() {}, querySelector() { return fakeEl(); }, querySelectorAll() { return []; },
    getAttribute() { return null; }, setAttribute() {}, getBoundingClientRect() { return { width: 360, height: 220, top: 0, left: 0 }; }
  };
  return PARENT;
}
function fakeEl() {
  const el = {
    style: {}, classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    innerHTML: "", textContent: "", value: "0", checked: false, dataset: {}, children: [],
    appendChild() {}, removeChild() {}, insertBefore() {}, addEventListener() {}, removeEventListener() {},
    querySelector() { return fakeEl(); }, querySelectorAll() { return []; },
    getAttribute() { return null; }, setAttribute() {}, removeAttribute() {},
    getContext() { return ctxStub; }, getBoundingClientRect() { return { width: 360, height: 220, top: 0, left: 0 }; },
    focus() {}, click() {}, closest() { return null; }, cloneNode() { return fakeEl(); }, remove() {},
    parentNode: null, nextSibling: null, offsetWidth: 360, offsetHeight: 220, clientWidth: 360, clientHeight: 220,
    scrollTop: 0, scrollHeight: 300, getElementsByTagName() { return []; }, insertAdjacentHTML() {}, contains() { return false; }
  };
  el.parentNode = getParent();
  return el;
}
const elCache = {};
const document = {
  getElementById(id) { if (!elCache[id]) elCache[id] = fakeEl(); return elCache[id]; },
  querySelector() { return fakeEl(); }, querySelectorAll() { return []; },
  createElement() { return fakeEl(); }, createTextNode() { return {}; },
  addEventListener() {}, removeEventListener() {}, body: fakeEl(), head: fakeEl(), documentElement: fakeEl(),
  cookie: "", readyState: "complete", title: "", hidden: false,
  getElementsByClassName() { return []; }, getElementsByTagName() { return []; }
};
const sandbox = {
  console, setTimeout, clearTimeout, setInterval, clearInterval,
  document, localStorage: { getItem(k) { return (process.env.COVER === "1" && String(k).indexOf("kl8_cover") === 0) ? "1" : null; }, setItem() {}, removeItem() {} },
  navigator: { userAgent: "node", clipboard: { writeText() {} } }, location: { href: "http://x/", search: "", hash: "" },
  requestAnimationFrame(cb) { return 1; }, cancelAnimationFrame() {},
  getComputedStyle() { return { getPropertyValue() { return ""; } }; },
  IntersectionObserver: class { observe() {} unobserve() {} disconnect() {} },
  ResizeObserver: class { observe() {} unobserve() {} disconnect() {} },
  fetch: (url) => {
    const u = String(url).split("?")[0];
    try {
      const p = path.join(ROOT, u);
      if (fs.existsSync(p)) return Promise.resolve({ ok: true, json: () => Promise.resolve(JSON.parse(fs.readFileSync(p, "utf8"))) });
    } catch (e) {}
    return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
  },
  alert() {}, encodeURIComponent, decodeURIComponent, Math, Date, JSON, Object, Array, String, Number, Boolean, isNaN, parseInt, parseFloat, Set, Map, RegExp, Error, Promise
};
sandbox.window = sandbox; sandbox.globalThis = sandbox; sandbox.self = sandbox;
vm.createContext(sandbox);

/* ---- 1) 按 DOM 顺序加载全部 script 块 (应用块用注入版本) ---- */
blocks.forEach((b, i) => {
  const src = (i === idx) ? app : b;
  const tag = (i === idx) ? "app-block(注入)" : (b.includes("__LOTTERY_DATA") ? "data-block" : "block#" + (i + 1));
  try { vm.runInContext(src, sandbox, { filename: tag }); console.log("加载 " + tag + " ✓ (" + b.length + " 字符)"); }
  catch (e) { console.log("加载 " + tag + " 失败: " + e.message + "\n  " + (e.stack || "").split("\n")[1]); }
});
console.log("window.__T 可用: " + !!(sandbox.window.__T));

const T = sandbox.window.__T;
if (!T) { console.log("导出失败, 终止"); process.exit(1); }
const EMD = sandbox.window.__LOTTERY_DATA;

/* ---- 2) 逐彩种跑 generateRecommend + renderAnalysis ---- */
console.log("\n======== 逐彩种功能测试 ========");
const types = ["ssq", "dlt", "qlc", "kl8", "fc3d", "pl3", "pl5", "qxc", "ttcx4", "sh15x5"];
let fail = 0;
types.forEach(t => {
  const cfg = T._C[t], data = (EMD[t] || []).map(x => ({
    p: x.p, d: x.d,
    n: x.n ? x.n.slice() : (x.r ? (Array.isArray(x.r) ? x.r.slice() : [x.r]) : undefined),
    r: x.r ? (Array.isArray(x.r) ? x.r.slice() : [x.r]) : x.r,
    b: x.b
  }));
  if (!data.length) { console.log("  ✗ " + t + ": 无数据"); fail++; return; }
  const use = data.slice(0, Math.min(cfg.recPeriod || 30, data.length));
  let recErr = null, rec = null;
  try { rec = T.generateRecommend(use, cfg); } catch (e) { recErr = e; }
  let rndErr = null;
  try { T.setCur(t); T.renderAnalysis(t, data); } catch (e) { rndErr = e; }
  const okRec = !recErr, okRnd = !rndErr;
  if (!okRec || !okRnd) fail++;
  const summary = okRec ? Object.keys(rec || {}).length + " 字段" : "-";
  console.log(`  ${okRec && okRnd ? "✓" : "✗"} ${t.padEnd(7)} generateRecommend:${okRec ? "OK" : "异常"}(${summary}) renderAnalysis:${okRnd ? "OK" : "异常"}`);
  if (recErr) console.log("      recErr: " + recErr.message + "\n      " + (recErr.stack || "").split("\n")[1]);
  if (rndErr) console.log("      rndErr: " + rndErr.message + "\n      " + (rndErr.stack || "").split("\n")[1]);
});

/* ---- 3) kl8 卡片渲染覆盖检查 (异步: 让 fetch 回调跑完) ---- */
(async function () {
  const emd = (EMD.kl8 || []).map(x => ({ p: x.p, d: x.d, n: x.n.slice() }));
  T.setCur("kl8");
  T.renderAnalysis("kl8", emd);
  T.renderRecommend("kl8", emd);
  await new Promise(r => setTimeout(r, 200));   // 等 fetch(...).then 回调
  const recHtml = elCache["enhancedRecs"] ? elCache["enhancedRecs"].innerHTML : "";
  const x7 = elCache["kl8_x7_dynamic"] ? elCache["kl8_x7_dynamic"].innerHTML : "";
  console.log("\n======== kl8 卡片渲染检查 (enhancedRecs " + recHtml.length + " 字符, x7动态 " + x7.length + " 字符) ========");
  const required = ["1-15区间", "选八9码复式", "选九10码复式", "选十11码复式", "选五9码复式", "信号策略", "热度TOP10", "选三·每月追号", "选六·每月追号", "选二·每月追号", "选四·命中率优先"];
  required.forEach(r => console.log("  " + (recHtml.includes(r) ? "✓" : "✗") + " 含卡片: " + r));
  console.log("  " + (x7.includes("25码选七") ? "✓" : "✗") + " 含卡片: 25码选七·智能推荐");
  console.log("  覆盖模式开关出现次数: " + (recHtml.match(/覆盖模式/g) || []).length + " (COVER=" + (process.env.COVER || "0") + ")");
  console.log("  覆盖模式明细表: " + (recHtml.includes("本月明细 · ") ? "已渲染" : "未渲染"));
  if (process.env.DUMP) { require("fs").writeFileSync(process.env.DUMP, recHtml); console.log("  已导出渲染结果 → " + process.env.DUMP); }
  const dm = recHtml.match(/胆码:([\d,]+)/), tm = recHtml.match(/拖码:([\d,]+)/);
  console.log("  卡片1 渲染值 → 胆码:" + (dm ? dm[1] : "?") + " 拖码:" + (tm ? tm[1] : "?") + "  (期望 近5期口径, 数据止于" + emd[0].d + ")");

  console.log("\n======== 汇总 ========");
  console.log("彩种流程失败: " + fail + "/" + types.length);
})();
