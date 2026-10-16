/* 补齐 kl8 数据到 2026-10-15: 嵌入 __LOTTERY_DATA.kl8 (×3 HTML) + data/kl8_500.json */
const fs = require("fs"), path = require("path");
const ROOT = path.join(__dirname, "..");
const NEW = [
  ["2026268","2026-10-09",[1,2,6,7,16,19,26,31,35,40,45,46,48,49,52,59,62,68,73,79]],
  ["2026269","2026-10-10",[1,2,3,7,11,13,15,18,25,27,30,35,44,46,55,57,60,63,70,73]],
  ["2026270","2026-10-11",[3,6,7,8,9,16,21,22,23,27,39,40,41,44,48,54,60,65,68,75]],
  ["2026271","2026-10-12",[10,17,20,22,30,31,37,40,41,43,44,45,50,52,56,58,59,63,71,76]],
  ["2026272","2026-10-13",[11,14,19,20,39,40,41,43,47,51,57,62,64,66,67,68,72,76,77,80]],
  ["2026273","2026-10-14",[9,10,12,14,23,24,27,31,35,38,49,51,52,54,55,58,61,63,65,76]],
  ["2026274","2026-10-15",[8,9,15,17,27,29,35,38,43,44,45,46,47,48,54,56,63,64,70,78]]
].map(([p, d, n]) => ({ p, d, n }));

/* ---- 1) data/kl8_500.json ---- */
const kf = path.join(ROOT, "data", "kl8_500.json");
const raw = fs.readFileSync(kf, "utf8");
const kArr = JSON.parse(raw);
let added = 0;
NEW.forEach(x => { if (!kArr.some(y => String(y.p) === x.p)) { kArr.push(x); added++; } });
kArr.sort((a, b) => parseInt(b.p) - parseInt(a.p));
fs.writeFileSync(kf, JSON.stringify(kArr));
console.log("kl8_500.json: +" + added + " → " + kArr.length + " 条, 最新 " + kArr[0].p + " " + kArr[0].d + " (紧凑格式 " + raw.trim()[0] + "…)");

/* ---- 2) 三份 HTML 嵌入数据 (按索引精确替换 JSON 文本, 不动其他字节) ---- */
["index.html", "deploy/index.html", "index_modified.html"].forEach(f => {
  const p = path.join(ROOT, f);
  const h = fs.readFileSync(p, "utf8");
  const re = /window\.__LOTTERY_DATA\s*=\s*(\{[\s\S]*?\});\s*<\/script>/;
  const m = h.match(re);
  if (!m) throw new Error(f + ": 未找到嵌入数据");
  const jsonStart = m.index + m[0].indexOf("{");
  const jsonEnd = jsonStart + m[1].length;                 // JSON 文本区间 [jsonStart, jsonEnd)
  if (h.slice(jsonStart, jsonEnd) !== m[1]) throw new Error(f + ": 索引定位失败");
  const obj = JSON.parse(m[1]);
  const before = obj.kl8.length;
  let a = 0;
  NEW.forEach(x => { if (!obj.kl8.some(y => String(y.p) === x.p)) { obj.kl8.push(x); a++; } });
  obj.kl8.sort((x, y) => parseInt(y.p) - parseInt(x.p));
  const newJson = JSON.stringify(obj);
  const out = h.slice(0, jsonStart) + newJson + h.slice(jsonEnd);
  fs.writeFileSync(p, out);
  // 复核: 重新解析, 且非 kl8 数据必须与原来逐字一致
  const chk = JSON.parse(fs.readFileSync(p, "utf8").match(re)[1]);
  const othersOk = Object.keys(obj).filter(k => k !== "kl8").every(k => {
    const orig = m[1].includes(JSON.stringify({ [k]: undefined })) ? true : true;
    return JSON.stringify(chk[k]) === JSON.stringify(obj[k]);
  });
  console.log(f + ": kl8 +" + a + " → " + chk.kl8.length + " 条(原" + before + "), 最新 " + chk.kl8[0].p + " " + chk.kl8[0].d + " | 彩种数 " + Object.keys(chk).length + " | 其他彩种不变 " + othersOk);
});
