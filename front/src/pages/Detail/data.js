const KDOW = ["일", "월", "화", "수", "목", "금", "토"];
export function kdate(iso) {
  if (!iso) return "기준일 없음";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return Number.isNaN(date.getTime()) ? "기준일 없음" : `${m}/${d} (${KDOW[date.getDay()]})`;
}
export const won = (n) => Number.isFinite(n) ? Math.round(n).toLocaleString("ko-KR") : "—";
export const ton = (n) => Number.isFinite(n) ? n.toLocaleString("ko-KR", { maximumFractionDigits: 1 }) : "—";
const baseName = (name) => String(name || "").replace(/\d+$/, "");
const sorted = (series = []) => [...series].sort((a, b) => a.date.localeCompare(b.date));

export function buildRisk(arr = []) {
  const all = sorted(arr);
  const clean = all.filter((r) => !r.err && Number.isFinite(r.pred) && Number.isFinite(r.actual) && Number.isFinite(r.residual));
  if (!clean.length) return null;
  const last = clean.at(-1);
  const pct = (r) => r.pred > 0 ? Math.round((r.residual / r.pred) * 100) : null;
  return {
    predicted: last.pred, actual: last.actual, error: last.residual, pct: pct(last),
    방향: last.dir || (last.residual >= 0 ? "과다" : "과소"), severity: last.severity,
    기준일: last.date, latestError: Boolean(all.at(-1)?.err),
    history: clean.slice(-5).map((r) => ({ date: r.date, severity: r.severity, pct: pct(r) })),
  };
}

// Every registered contract is retained, even before the first bill or collection.
export function buildStations(bills = {}, meta = {}, daily = {}, risk = {}, meters = []) {
  const registry = meters.length ? meters : Object.entries(meta).map(([cid, m]) => ({
    id: cid, customer_number: cid, station_id: m.station_id || baseName(m.역명),
    station_name: baseName(m.역명), line: m.호선, office_name: m.영업사업소, active: true,
  }));
  const groups = new Map();
  for (const meter of registry) {
    if (meter.deleted_at || meter.active === false || meter.active === 0) continue;
    const cid = meter.customer_number;
    const key = String(meter.id);
    const b = bills[key] || {}, m = meta[key] || {}, d = daily[key] || {};
    const stationId = meter.station_id || m.station_id || baseName(m.역명 || meter.station_name);
    const name = meter.station_name || baseName(m.역명 || b.역명) || "미지정 역";
    const usage = d.usage?.filter((p) => Number.isFinite(p.value)) || [];
    const dataMode = meter.data_mode || m.data_mode || (usage.length ? "daily" : meter.daily_enabled ? "pending" : "billing_only");
    const record = {
      ...meter, meterId: String(meter.id), line: meter.line ?? m.호선 ?? null,
      dataMode,
      고객번호: cid, 영업사업소: meter.office_name || m.영업사업소 || b.사업소명 || "미지정",
      base: name, 주소: meter.address || b.주소 || "—", 용도: meter.purpose || b.용도 || "—", 사용자명: name,
      bills: [...(b.bills || [])].sort((a, b) => a.ym.localeCompare(b.ym)),
      전자수용가번호: b.전자수용가번호, 전자납부번호: b.전자납부번호,
      계량기번호: meter.meter_number || b.계량기번호, 구경: b.구경, 가구수: b.가구수,
      daily: usage.length ? sorted(usage) : null,
      ridership: d.ridership?.length ? sorted(d.ridership) : null,
      risk: dataMode === "daily" ? buildRisk(risk[key]) : null,
      riskError: dataMode === "daily" && Boolean(sorted(risk[key]).at(-1)?.err),
    };
    if (!groups.has(stationId)) groups.set(stationId, { id: stationId, 역명: name, 사용자명: name, lines: [] });
    groups.get(stationId).lines.push(record);
  }
  return [...groups.values()].map((station) => ({
    ...station,
    lines: station.lines.sort((a, b) => Number(a.line) - Number(b.line) || a.고객번호.localeCompare(b.고객번호)),
    tier: station.lines.some((l) => l.risk) ? "full74" : station.lines.some((l) => l.daily || l.ridership) ? "cut3" : "billonly",
  })).sort((a, b) => a.역명.localeCompare(b.역명, "ko"));
}
export function latestDate(stations) {
  return stations.flatMap((s) => s.lines).flatMap((l) => [l.daily?.at(-1)?.date, l.ridership?.at(-1)?.date, l.risk?.기준일]).filter(Boolean).sort().at(-1) || "";
}
export const detailHref = (meterId) => `#/detail?meter=${encodeURIComponent(meterId)}`;
export const billNoticeNumber = (bill) => String(bill.notice_number || bill.고지번호 || "").trim();
export const billLabel = (bill) => `${bill.gubun || "정기분"}${billNoticeNumber(bill) ? ` · 고지번호 ${billNoticeNumber(bill)}` : ""}`;
export function billUsage(bill) {
  if (bill.사용량 != null) return bill.사용량;
  const detailed = !bill.summary_only && (Object.hasOwn(bill, "사용량") || bill.detail_available || bill.source === "i121_public_detail");
  return detailed ? null : bill.총사용량 ?? null;
}
export const billGroundwater = (bill) => ({
  usage: bill.지하수사용량 ?? bill.지하수_사용량 ?? null,
  current: bill.지하수당월지침 ?? bill.지하수_당월지침 ?? null,
  previous: bill.지하수전월지침 ?? bill.지하수_전월지침 ?? null,
});
export function billWindow(bills, ym) {
  const [year, month] = ym.split("-").map(Number);
  const selected = year * 12 + month;
  return bills.filter((b) => {
    const [y, m] = b.ym.split("-").map(Number);
    return y * 12 + m <= selected && y * 12 + m > selected - 12;
  });
}

export function chartRange(values, showValues = false) {
  const finite = values.filter(Number.isFinite);
  if (!finite.length) return null;
  const min = Math.min(...finite), max = Math.max(...finite);
  const span = max - min || 1;
  const lo = min >= 0 ? Math.max(0, min - span * 0.14) : min - span * 0.14;
  // Three integer labels must remain distinct, including a series of valid zeroes.
  const hi = Math.max(lo + 2, max + span * (showValues ? 0.2 : 0.14));
  return { lo, hi };
}
