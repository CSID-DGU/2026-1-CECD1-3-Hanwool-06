// 현재 사이트를 단일 HTML 파일로 추출한다.
//   1) vite-plugin-singlefile 로 JS/CSS 인라인 빌드
//   2) 데이터(bills·stations·daily·risk)와 에이전트 요약을 window 전역으로 주입 → fetch/백엔드 없이 동작
//   3) 노선도 이미지를 data URI 로 인라인
// 실행: node scripts/build-html.mjs   (백엔드 8000 이 떠 있으면 에이전트 요약도 캡처)
import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pub = resolve(root, "public");
const safe = (s) => s.replace(/<\/script/gi, "<\\/script"); // </script> 로 태그 닫힘 방지

console.log("1) 단일파일 빌드…");
execSync("npx vite build --config vite.singlefile.config.js", { cwd: root, stdio: "inherit" });
let html = readFileSync(resolve(root, "dist-single/index.html"), "utf8");

console.log("2) 데이터 읽기…");
const j = (f) => safe(readFileSync(resolve(pub, f), "utf8").trim());
const data = {
  BILLS: j("bills.json"),
  STATIONS: j("stations.json"),
  DAILY: j("daily.json"),
  RISK: j("risk.json"),
};

console.log("3) 에이전트 요약 캡처…");
let summary = "null";
try {
  const raw = execSync("curl -s --max-time 30 http://127.0.0.1:8000/api/summary", { encoding: "utf8" }).trim();
  JSON.parse(raw);
  summary = safe(raw);
  console.log("   요약 캡처 OK");
} catch {
  console.warn("   ⚠ 요약 캡처 실패 (백엔드 8000 미실행?) — __SUMMARY__ 없이 진행");
}

console.log("4) 노선도 이미지 인라인…");
const imgURI = `data:image/png;base64,${readFileSync(resolve(pub, "metro_map_rectangle.png")).toString("base64")}`;

const inject =
  `<script>window.__BILLS__=${data.BILLS};window.__STATIONS__=${data.STATIONS};` +
  `window.__DAILY__=${data.DAILY};window.__RISK__=${data.RISK};window.__SUMMARY__=${summary};</script>`;

html = html.replace("<head>", `<head>\n${inject}`).split("/metro_map_rectangle.png").join(imgURI);

const dest = resolve(root, "demo_site.html");
writeFileSync(dest, html);
console.log(`완료 → ${dest} (${(Buffer.byteLength(html) / 1024 / 1024).toFixed(1)} MB)`);
