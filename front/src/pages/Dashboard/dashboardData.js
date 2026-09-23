import { buildStations } from "../Detail/data.js";
export const lineMeta = {
  1: { name: "1호선", color: "#0052a4" }, 2: { name: "2호선", color: "#00a84d" },
  3: { name: "3호선", color: "#ef7c1c" }, 4: { name: "4호선", color: "#00a5de" },
  5: { name: "5호선", color: "#996cac" }, 6: { name: "6호선", color: "#cd7c2f" },
  7: { name: "7호선", color: "#747f00" }, 8: { name: "8호선", color: "#e6186c" },
  9: { name: "9호선", color: "#8e6e2e" },
};
export const riskMeta = {
  all: { label: "전체", tone: "all" }, alert: { label: "경고", tone: "alert" },
  warn: { label: "주의", tone: "warn" }, ok: { label: "정상", tone: "ok" },
  unknown: { label: "자료 확인", tone: "unknown" },
  analysis_pending: { label: "분석 대기", tone: "unknown" },
  pending: { label: "첫 수집 대기", tone: "pending" },
  billing_only: { label: "청구 전용", tone: "billing" },
};
const SEV = { 경고: "alert", 주의: "warn", 정상: "ok" };
export function buildDashboard(data) {
  const stations = buildStations(data.bills, data.stations, data.daily, data.risk, data.meters).flatMap((s) => s.lines.map((l) => {
    const reference = data.status?.reference_date || data.status?.latest_risk;
    const stale = Boolean(l.risk && reference && l.risk.기준일 < String(reference).slice(0, 10));
    return {
      id: l.meterId, stationId: s.id, name: s.역명, displayName: l.display_name || l.고객번호,
      dataMode: l.dataMode, latestBillMonth: l.bills.at(-1)?.ym || "",
      office: l.영업사업소, officeId: String(l.office_id ?? ""), lines: [String(l.line)],
      risk: l.dataMode === "billing_only" ? "billing_only" : l.dataMode === "pending" ? "pending" : l.riskError || stale ? "unknown" : SEV[l.risk?.severity] || "analysis_pending",
      riskDetail: l.dataMode === "billing_only" ? "청구·요금 자료 제공" : l.dataMode === "pending" ? "수집 대상 등록됨" : l.riskError ? "최근 분석 자료 확인 필요" : stale ? "이전 기준일 자료" : !l.risk ? "일일 사용량 수집됨" : "",
      customerNo: l.고객번호, usage: l.daily?.at(-1)?.value ?? l.risk?.actual ?? null,
      delta: l.risk?.pct ?? null,
      dailyDate: l.daily?.at(-1)?.date || "", riskDate: l.risk?.기준일 || "", dailyEnabled: l.daily_enabled,
    };
  }));
  return { stations, offices: data.offices || [] };
}

export function buildMapGroups(stations, locations = {}) {
  const groups = new Map();
  const rank = { billing_only: -2, pending: -1, analysis_pending: 0, ok: 1, unknown: 2, warn: 3, alert: 4 };
  for (const station of stations) {
    const id = station.stationId || station.name;
    const position = locations[id] || locations[station.id] || locations[station.customerNo];
    if (!groups.has(id)) groups.set(id, { id, name: station.name, meters: [], risk: "billing_only", position: null });
    const group = groups.get(id);
    group.meters.push(station);
    if (position && Number.isFinite(position.x) && Number.isFinite(position.y) && position.x >= 0 && position.x <= 100 && position.y >= 0 && position.y <= 100) group.position = position;
    if (rank[station.risk] > rank[group.risk]) group.risk = station.risk;
  }
  return [...groups.values()];
}
