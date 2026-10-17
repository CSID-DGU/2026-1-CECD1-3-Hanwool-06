import { billUsage, buildStations, SEVERITY_TONE } from "../Detail/data.js";
import { compareText, dateValue, nextSortKey, sortRows, splitSortKey } from "../../sorting.js";
// 서울교통공사 노선색.
export const lineColors = {
  1: "#0052a4", 2: "#00a84d", 3: "#ef7c1c", 4: "#00a5de", 5: "#996cac",
  6: "#cd7c2f", 7: "#747f00", 8: "#e6186c",
};
export const riskMeta = {
  all: { label: "전체", tone: "all" }, alert: { label: "경고", tone: "alert" },
  warn: { label: "주의", tone: "warn" }, ok: { label: "정상", tone: "ok" },
  unknown: { label: "자료 확인", tone: "unknown" },
  analysis_pending: { label: "분석 대기", tone: "unknown" },
  pending: { label: "첫 수집 대기", tone: "pending" },
  billing_only: { label: "청구 전용", tone: "billing" },
};
export function buildDashboard(data) {
  const stations = buildStations(data.bills, data.stations, data.daily, data.risk, data.meters).flatMap((s) => s.lines.map((l) => {
    const reference = data.status?.reference_date || data.status?.latest_risk;
    const stale = Boolean(l.risk && reference && l.risk.기준일 < String(reference).slice(0, 10));
    const waiting = l.dataMode === "daily" && !l.risk && !l.riskError;
    const lastBill = l.bills.at(-1);
    return {
      id: l.meterId, stationId: s.id, name: s.역명, displayName: l.display_name || l.고객번호,
      dataMode: l.dataMode, latestBillMonth: lastBill?.ym || "",
      latestBillUsage: lastBill ? billUsage(lastBill) : null, latestBillAmount: lastBill?.납부금액 ?? null,
      office: l.영업사업소, officeId: String(l.office_id ?? ""), lines: [String(l.line)],
      risk: l.dataMode === "billing_only" ? "billing_only" : l.dataMode === "pending" ? "pending" : l.riskError || stale ? "unknown" : SEVERITY_TONE[l.risk?.severity] || "analysis_pending",
      riskDetail: l.dataMode !== "daily" ? "" : l.riskError ? "최근 관측값 오류" : stale ? "분석일이 오래됨" : "",
      // 분석 대기인 까닭을 아는 경우에는 이름에 함께 적는다.
      riskLabel: waiting && l.historyShort ? "분석 대기(학습 데이터 부족)" : "",
      customerNo: l.고객번호, usage: l.daily?.at(-1)?.value ?? l.risk?.actual ?? null,
      delta: l.risk?.pct ?? null,
      dailyDate: l.daily?.at(-1)?.date || "", riskDate: l.risk?.기준일 || "", dailyEnabled: l.daily_enabled,
    };
  }));
  return { stations, offices: data.offices || [] };
}

// 계량기 목록 정렬 키: "<열>-asc|desc". 열: name(역명) · date(기준일) · usage(일 사용량) · delta(예측 대비).
// 기준일은 일일 관제에서는 사용량 날짜(없으면 분석일), 청구 전용에서는 최근 청구월이다. 숫자·날짜 열은 처음 누르면 큰 값·최신이 먼저다.
export const defaultSort = "name-asc";
export const sortDefaults = { name: "asc", date: "desc", usage: "desc", delta: "desc" };
export const nextSort = (current, column) => nextSortKey(current, column, sortDefaults);

// 실제 날짜로 비교할 수 있는 시각(ms). 비어 있거나 YYYY-MM(-DD) 형식이 아니면 null.
export function referenceTime(station, billingOnly = false) {
  return dateValue(billingOnly ? station.latestBillMonth : station.dailyDate || station.riskDate);
}

const byName = (a, b) => compareText(a.name, b.name) || compareText(a.displayName, b.displayName) || compareText(a.customerNo, b.customerNo);

// 원본 배열은 바꾸지 않는다. 역명이 같으면 계량기 이름·고객번호 순, 값이 없는 계량기는 어느 방향이든 뒤로 간다.
export function sortStations(stations, sortKey = defaultSort, billingOnly = false) {
  const columns = {
    name: { value: (s) => s.name, type: "text" },
    date: { value: (s) => (billingOnly ? s.latestBillMonth : s.dailyDate || s.riskDate), type: "date" },
    usage: { value: (s) => s.usage, type: "number" },
    delta: { value: (s) => s.delta, type: "number" },
  };
  const { column } = splitSortKey(sortKey, defaultSort);
  const tieBreak = column === "name" ? (a, b) => compareText(a.displayName, b.displayName) || compareText(a.customerNo, b.customerNo) : byName;
  return sortRows(stations, columns[column] ? sortKey : defaultSort, columns, tieBreak);
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
