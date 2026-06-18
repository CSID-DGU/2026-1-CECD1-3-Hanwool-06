// daily-snapshot 브랜치의 risk.json·daily.json 을 front/public 으로 동기화한다.
// npm run dev / build 전에 자동 실행(predev·prebuild). 실패해도(오프라인 등) 막지 않고 기존 데이터로 진행.
import { execFileSync } from "node:child_process";
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const files = ["risk.json", "daily.json"];

try {
  execFileSync("git", ["fetch", "origin", "daily-snapshot", "-q"], { cwd: root, stdio: "ignore" });
  for (const f of files) {
    const buf = execFileSync("git", ["show", `origin/daily-snapshot:front/public/${f}`], {
      cwd: root,
      maxBuffer: 64 * 1024 * 1024,
    });
    writeFileSync(resolve(root, "front/public", f), buf);
    console.log(`[sync] front/public/${f} ← daily-snapshot`);
  }
} catch {
  console.log("[sync] 건너뜀 (오프라인 또는 daily-snapshot 접근 불가) — 기존 데이터로 진행");
}
