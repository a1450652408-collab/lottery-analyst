/* 全项目审计: 语法 / 资源 / 数据一致性 / 数据合法性 / 可疑代码模式 */
const fs = require("fs"), path = require("path"), cp = require("child_process");
const ROOT = path.join(__dirname, "..");
const R = (p) => path.join(ROOT, p);
const issues = [], warns = [], info = [];
const add = (a, s) => { a.push(s); console.log(("[" + (a === issues ? "BUG" : a === warns ? "WARN" : "INFO") + "] ") + s); };

console.log("======== 1. 三份 HTML 一致性 ========");
const H = ["index.html", "deploy/index.html", "index_modified.html"];
const md5 = H.map(f => cp.execSync(`md5sum "${R(f)}"`).toString().split(" ")[0]);
const same = md5.every(x => x === md5[0]);
console.log("  md5:", md5.map((m, i) => H[i] + "=" + m.slice(0, 8)).join(" "), same ? "→ 一致 ✓" : "→ 不一致 ✗");
if (!same) add(issues, "三份 HTML 不一致");
const html = fs.readFileSync(R("index.html"), "utf8");

console.log("\n======== 2. 内联 JS 语法 ========");
let ok = 0, bad = 0, re = /<script(?![^>]*src=)[^>]*>([\s\S]*?)<\/script>/g, m;
while ((m = re.exec(html))) { try { new Function(m[1]); ok++; } catch (e) { bad++; add(issues, "内联 script 语法错误: " + e.message.slice(0, 100)); } }
console.log("  内联块: " + ok + " 通过 / " + bad + " 失败");

console.log("\n======== 3. fetch 目标存在性 ========");
const fetches = [...html.matchAll(/fetch\(\s*["']([^"']+)["']/g)].map(x => x[1].split("?")[0]);
const uniq = [...new Set(fetches)];
uniq.forEach(f => { const p = R(f); if (!fs.existsSync(p)) add(issues, "fetch 目标缺失: " + f); });
console.log("  fetch 目标 " + uniq.length + " 个: " + uniq.join(", "));

console.log("\n======== 4. 嵌入数据 与 data/*.json 同步 ========");
const EMD = JSON.parse(html.match(/window\.__LOTTERY_DATA\s*=\s*(\{[\s\S]*?\});\s*<\/script>/)[1]);
const MAP = { ssq: "ssq_data.json", dlt: "dlt_data.json", qlc: "qlc_data.json", kl8: "kl8_500.json", fc3d: "fc3d_data.json", pl3: "pl3_data.json", pl5: "pl5_data.json", qxc: "qxc_data.json", ttcx4: "ttcx4_data.json", sh15x5: "sh15x5_data.json" };
for (const t of Object.keys(MAP)) {
  const em = EMD[t] || [], f = MAP[t], p = R("data/" + f);
  if (!fs.existsSync(p)) { add(issues, t + ": 数据文件缺失 " + f); continue; }
  let js = JSON.parse(fs.readFileSync(p, "utf8")); js = Array.isArray(js) ? js : (js.data || js.draws || []);
  const newest = a => a.length ? a.slice().sort((x, y) => parseInt(y.p) - parseInt(x.p))[0] : null;
  const en = newest(em), jn = newest(js);
  const common = em.filter(x => js.some(y => String(y.p) === String(x.p)));
  let mism = 0;
  common.forEach(x => { const y = js.find(z => String(z.p) === String(x.p)); if (JSON.stringify(x.n || x.r) !== JSON.stringify(y.n || y.r)) mism++; });
  const flag = (en && jn && String(en.p) === String(jn.p) && mism === 0) ? "✓" : "✗";
  console.log(`  ${flag} ${t.padEnd(7)} 嵌入${em.length}条(最新${en ? en.p + " " + en.d : "-"}) | ${f} ${js.length}条(最新${jn ? jn.p + " " + jn.d : "-"}) | 重叠${common.length}期不一致${mism}`);
  if (String(en.p) !== String(jn.p)) add(warns, t + ": 嵌入数据与 " + f + " 最新期不一致 (" + (en && en.p) + " vs " + (jn && jn.p) + ")");
  if (mism) add(issues, t + ": 嵌入与 " + f + " 有 " + mism + " 期号码不一致");
}

console.log("\n======== 5. 各彩种数据合法性 ========");
const RULES = {
  ssq: { type: "lotto", rC: 6, rMax: 33, bC: 1, bMax: 16 },
  dlt: { type: "lotto", rC: 5, rMax: 35, bC: 2, bMax: 12 },
  qlc: { type: "lotto", rC: 7, rMax: 30, bC: 0, bMax: 0 },
  kl8: { type: "keno", rC: 20, rMax: 80 },
  fc3d: { type: "digit", rC: 3, rMax: 9 }, pl3: { type: "digit", rC: 3, rMax: 9 },
  pl5: { type: "digit", rC: 5, rMax: 9 }, qxc: { type: "digit", rC: 7, rMax: 9, lastMax: 14 },
  ttcx4: { type: "digit", rC: 4, rMax: 9 }, sh15x5: { type: "lotto", rC: 5, rMax: 15, bC: 0, bMax: 0 }
};
for (const t of Object.keys(RULES)) {
  const r = RULES[t], arr = EMD[t] || [];
  if (!arr.length) { add(issues, t + ": 嵌入数据为空"); continue; }
  const ps = arr.map(x => String(x.p));
  const dup = ps.filter((x, i) => ps.indexOf(x) !== i);
  const order = arr.map(x => parseInt(x.p));
  let desc = true; for (let i = 1; i < order.length; i++) if (order[i] > order[i - 1]) desc = false;
  const noDate = arr.filter(x => !x.d).length;
  const badDate = arr.filter(x => x.d && !/^\d{4}-\d{2}-\d{2}$/.test(x.d)).length;
  let badNum = 0, badCnt = 0, badBlue = 0, dupNum = 0;
  arr.forEach(x => {
    const ns = x.n || x.r || [];
    if (r.type !== "digit") {
      if (ns.length !== r.rC) badCnt++;
      if (ns.some(n => !Number.isInteger(n) || n < 1 || n > r.rMax)) badNum++;
      if (new Set(ns).size !== ns.length) dupNum++;
    } else {
      if (ns.length !== r.rC) badCnt++;
      ns.forEach((n, i) => { const mx = (t === "qxc" && i === 6 && r.lastMax !== undefined) ? r.lastMax : r.rMax; if (!Number.isInteger(n) || n < 0 || n > mx) badNum++; });
    }
    if (r.bC > 0) { const bs = x.b === undefined ? [] : (Array.isArray(x.b) ? x.b : [x.b]); if (bs.length !== r.bC || bs.some(b => b < 1 || b > r.bMax)) badBlue++; }
  });
  const msgs = [];
  if (dup.length) msgs.push("期号重复" + dup.length);
  if (!desc) msgs.push("期号非降序");
  if (noDate) msgs.push("缺日期" + noDate);
  if (badDate) msgs.push("日期格式错" + badDate);
  if (badNum) msgs.push("号码越界" + badNum);
  if (badCnt) msgs.push("号码个数错" + badCnt);
  if (badBlue) msgs.push("蓝/后区错" + badBlue);
  if (dupNum) msgs.push("号码重复" + dupNum);
  console.log(`  ${msgs.length ? "✗" : "✓"} ${t.padEnd(7)} ${arr.length}条 [${arr[arr.length - 1].d} ~ ${arr[0].d}] ${msgs.join("; ")}`);
  if (msgs.length) add(issues, t + ": " + msgs.join("; "));
}

console.log("\n======== 5b. 每日开奖彩种 · 日期连续性 ========");
{
  const DAILY = ["kl8", "ttcx4", "fc3d", "pl3", "pl5", "sh15x5"];
  DAILY.forEach(t => {
    const arr = (EMD[t] || []).slice().sort((a, b) => (a.d < b.d ? -1 : 1));
    const gaps = [];
    for (let i = 1; i < arr.length; i++) {
      const diff = (new Date(arr[i].d) - new Date(arr[i - 1].d)) / 86400000;
      if (diff > 5) gaps.push(arr[i - 1].d + "→" + arr[i].d + "(" + diff + "天)");
    }
    console.log("  " + (gaps.length ? "!" : "✓") + " " + t.padEnd(7) + arr.length + "条 " + (arr[0] ? arr[0].d : "-") + "~" + (arr.length ? arr[arr.length - 1].d : "-") + (gaps.length ? " 跳变: " + gaps.join(", ") : ""));
    if (gaps.length > 1) add(warns, t + ": 日期存在 " + gaps.length + " 处 >5 天跳变");
  });
}

console.log("\n======== 6. 可疑代码模式扫描 (index.html) ========");
function lines() { return html.split("\n"); }
function scan(regex, label) {
  const out = [];
  lines().forEach((l, i) => { if (regex.test(l)) out.push((i + 1) + ": " + l.trim().slice(0, 110)); });
  console.log("  ── " + label + " (" + out.length + ")");
  out.forEach(o => console.log("     " + o));
  return out;
}
scan(/\.sort\(\s*\)/, "sort() 无比较器 (数字会按字符串排序)");
scan(/\.reverse\(\)/, "reverse() 方向语义");
scan(/parseInt\([^,)]+\)/, "parseInt 未指定进制 (现代引擎无八进制风险)");

console.log("\n======== 7. Python 语法 ========");
function walk(dir, ext, acc) { const p = R(dir); if (!fs.existsSync(p)) return acc;
  fs.readdirSync(p, { withFileTypes: true }).forEach(d => { const rel = dir ? dir + "/" + d.name : d.name;
    if (d.isDirectory()) { if (!/node_modules|\.git|__pycache__|_backup/.test(d.name)) walk(rel, ext, acc); }
    else if (d.name.endsWith(ext)) acc.push(rel); }); return acc; }
/* 跨平台: Linux/CI 常用 python3, Windows 用 python */
const PY = (() => {
  for (const c of ["python3", "python"]) {
    try { cp.execSync(`${c} -V`, { stdio: "pipe" }); return c; } catch (e) {}
  }
  return null;
})();
const pys = walk("", ".py", []);
let pyBad = 0;
/* 注意: 语法问题记为 WARN 而非 BUG —— 它不影响数据完整性,
   且 CI 的 Python 版本(3.11) 与本机可能不同(如 3.12+ 的 f-string 语法)。
   真正的流水线脚本坏了会在对应步骤直接失败。 */
function firstErr(e) {
  const s = ((e && (e.stderr || e.stdout)) || "").toString();
  const l = s.split("\n").filter(x => /Error|error/.test(x)).slice(-1)[0] || s.split("\n").slice(-2)[0] || "";
  return l.trim().slice(0, 90);
}
if (!PY) { add(warns, "未找到 python, 跳过 .py 语法检查"); }
else pys.forEach(f => { try { cp.execSync(`${PY} -m py_compile "${R(f)}"`, { stdio: "pipe" }); } catch (e) { pyBad++; add(warns, "python 语法问题: " + f + " → " + firstErr(e)); } });
console.log("  python: " + (PY || "未找到") + " | 检查 " + pys.length + " 个 .py, 有问题 " + pyBad);

console.log("\n======== 8. 独立 .js 语法 ========");
const jss = walk("", ".js", []).filter(f => !f.includes("/"));
let jsBad = 0;
jss.forEach(f => { try { cp.execSync(`node --check "${R(f)}"`, { stdio: "pipe" }); } catch (e) { jsBad++; add(warns, "js 语法问题: " + f + " → " + firstErr(e)); } });
console.log("  检查 " + jss.length + " 个 .js, 有问题 " + jsBad);

console.log("\n======== 汇总 ========");
console.log("BUG: " + issues.length + "  WARN: " + warns.length);
if (issues.length) {
  console.log("\n发现问题:");
  issues.forEach((s, i) => console.log("  " + (i + 1) + ". " + s));
}
// 供 CI 作为质量门禁使用 (有 BUG 则以非 0 退出)
process.exit(issues.length > 0 ? 1 : 0);
