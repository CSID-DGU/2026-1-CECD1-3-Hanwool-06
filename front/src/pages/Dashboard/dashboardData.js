// 전체현황 대시보드 데이터: public/risk.json + stations.json 을 런타임에 읽어 역 목록을 구성한다.
// 정적 data.js 대신 사용 → daily-snapshot 에서 sync 된 최신 데이터가 그대로 반영됨.
// (build_dashboard_map.py 의 역 빌드 로직을 JS로 옮긴 것. 좌표는 제외 — 리스트·테이블·필터용)

export const lineMeta = {
  1: { name: "1호선", color: "#0052a4" },
  2: { name: "2호선", color: "#00a84d" },
  3: { name: "3호선", color: "#ef7c1c" },
  4: { name: "4호선", color: "#00a5de" },
  5: { name: "5호선", color: "#996cac" },
  6: { name: "6호선", color: "#cd7c2f" },
  7: { name: "7호선", color: "#747f00" },
  8: { name: "8호선", color: "#e6186c" },
};

export const riskMeta = {
  all: { label: "전체", tone: "all" },
  alert: { label: "경고", tone: "alert" },
  warn: { label: "주의", tone: "warn" },
  ok: { label: "정상", tone: "ok" },
};

const SEV = { 경고: "alert", 주의: "warn", 정상: "ok" };

const display = (name) => name.replace(/\d+$/, ""); // "왕십리역5" → "왕십리역"

function buildStations(risk, smeta) {
  const out = [];
  for (const [cid, arr] of Object.entries(risk)) {
    const meta = smeta[cid];
    if (!meta || !arr || arr.length === 0) continue;
    const latest = arr.reduce((a, b) => (a.date >= b.date ? a : b));
    const pred = latest.pred || 0;
    const resid = latest.residual || 0;
    const d = new Date(`${latest.date}T00:00:00Z`); // UTC 고정으로 날짜 밀림 방지
    d.setUTCDate(d.getUTCDate() + 1);
    out.push({
      id: cid,
      name: display(meta.역명),
      office: meta.영업사업소 || "",
      lines: [String(meta.호선)],
      risk: SEV[latest.severity] || "ok",
      customerNo: cid,
      usage: Math.round(latest.actual || 0),
      delta: pred ? Math.round((resid / pred) * 1000) / 10 : 0,
      checkedAt: `${d.toISOString().slice(0, 10)} 08:00`,
    });
  }
  out.sort((a, b) =>
    a.lines[0] !== b.lines[0] ? a.lines[0].localeCompare(b.lines[0]) : a.name.localeCompare(b.name),
  );
  return out;
}

export async function loadDashboard() {
  const base = import.meta.env.BASE_URL;
  // 정적 HTML(단일파일)에서는 주입된 전역(window.__RISK__ 등)을 우선 사용
  const g = typeof window !== "undefined" ? window : {};
  try {
    const [risk, smeta] = await Promise.all([
      g.__RISK__ ? Promise.resolve(g.__RISK__) : fetch(`${base}risk.json`).then((r) => r.json()),
      g.__STATIONS__ ? Promise.resolve(g.__STATIONS__) : fetch(`${base}stations.json`).then((r) => r.json()),
    ]);
    const stations = buildStations(risk, smeta);
    const offices = [...new Set(stations.map((s) => s.office).filter(Boolean))].sort();
    return { stations, offices };
  } catch {
    return { stations: [], offices: [] };
  }
}
