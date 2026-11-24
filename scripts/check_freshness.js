#!/usr/bin/env node
/**
 * 数据新鲜度检查（防"数据冻结"静默发生）
 *
 * 背景：2026-11-15 上游 huiniao 接口冻结在 11-14，接口仍返回 200、数据合法，
 *       于是流水线每天"成功"跑完却什么都没更新。可用性检查抓不到这种故障，
 *       只有"最新期号有没有推进"能抓到。
 *
 * 用法：
 *   node scripts/check_freshness.js          # 检查并打印表格；有陈旧项则 exit 1
 *   node scripts/check_freshness.js --strict # 同样逻辑，陈旧时不打印 OK 行
 *
 * 判定：lag = 今天 - 最新开奖日期（天）；lag > 阈值 即为"冻结/陈旧"。
 *   日开彩种（kl8/fc3d/pl3/pl5）阈值 1 天（当天 21:30 开奖，次日仍无新数据即异常）
 *   隔日彩种（ssq/dlt/qlc/qxc）阈值 3 天（最长开奖间隔）
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const FILE_ARG = (process.argv.find(a => a.startsWith("--file=")) || "").slice(7);
const HTML = FILE_ARG ? path.resolve(ROOT, FILE_ARG) : path.join(ROOT, "index.html");

const LIMIT = { kl8: 1, fc3d: 1, pl3: 1, pl5: 1, ssq: 3, dlt: 3, qlc: 3, qxc: 3 };
const STOPPED = { ttcx4: "停售（最后开奖 2026-09-30）", sh15x5: "停售（最后开奖 2026-09-30）" };
const NAME = {
  kl8: "快乐8", fc3d: "福彩3D", pl3: "排列3", pl5: "排列5",
  ssq: "双色球", dlt: "大乐透", qlc: "七乐彩", qxc: "七星彩",
  ttcx4: "天天彩选4", sh15x5: "华东15选5",
};

function loadData() {
  const html = fs.readFileSync(HTML, "utf8");
  const m = html.match(/window\.__LOTTERY_DATA\s*=\s*(\{[\s\S]*?\});\s*<\/script>/);
  if (!m) throw new Error("index.html 里找不到 window.__LOTTERY_DATA");
  return JSON.parse(m[1]);
}

function today() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function main() {
  const strict = process.argv.includes("--strict");
  const data = loadData();
  const t0 = today();
  const stale = [];
  const rows = [];

  for (const type of Object.keys(LIMIT)) {
    const arr = data[type];
    if (!arr || !arr.length) { stale.push({ type, reason: "无数据" }); continue; }
    const latest = arr[0];
    const dt = new Date(String(latest.d).slice(0, 10) + "T00:00:00");
    const lag = Math.round((t0 - dt) / 86400000);
    const bad = lag > LIMIT[type];
    rows.push({ type, p: latest.p, d: String(latest.d).slice(0, 10), lag, limit: LIMIT[type], bad });
    if (bad) stale.push({ type, p: latest.p, d: latest.d, lag, limit: LIMIT[type] });
  }

  const pad = (s, n) => String(s).padEnd(n, " ");
  const pac = (s, n) => { // 中文按 2 列宽对齐
    let w = 0;
    for (const ch of String(s)) w += /[\u4e00-\u9fa5]/.test(ch) ? 2 : 1;
    return String(s) + " ".repeat(Math.max(1, n - w));
  };

  const ymd = d => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  console.log("=== 数据新鲜度检查 · " + ymd(t0) + " ===");
  console.log("  " + pac("彩种", 10) + pac("最新期号", 12) + pac("开奖日期", 13) + pac("滞后", 7) + pac("阈值", 7) + "状态");
  for (const r of rows) {
    if (strict && !r.bad) continue;
    console.log("  " + pac(NAME[r.type] || r.type, 10) + pac(r.p, 12) + pac(r.d, 13) +
      pac(r.lag + " 天", 7) + pac(r.limit + " 天", 7) + (r.bad ? "❌ 冻结" : "✅ 正常"));
  }

  const stoppedKeys = Object.keys(STOPPED).filter(k => data[k] && data[k][0]);
  if (stoppedKeys.length) {
    console.log("  —— 不参与判定：" + stoppedKeys.map(k => (NAME[k] || k) + " " + data[k][0].d).join("、") + "（已停售）");
  }

  if (stale.length) {
    console.log("");
    console.log("❌ 发现 " + stale.length + " 项数据陈旧/冻结：");
    stale.forEach(s => {
      if (s.reason) console.log("   - " + (NAME[s.type] || s.type) + "：" + s.reason);
      else console.log("   - " + (NAME[s.type] || s.type) + " 停在 " + s.p + "（" + s.d + "），滞后 " + s.lag + " 天 > 阈值 " + s.limit + " 天");
    });
    console.log("   → 上游数据源可能已停止更新，请勿发布，先排查数据源。");
    process.exit(1);
  }

  console.log("");
  console.log("✅ 全部新鲜（" + rows.length + " 个彩种均在阈值内）");
}

try {
  main();
} catch (e) {
  console.error("❌ 检查失败：" + e.message);
  process.exit(2);
}
