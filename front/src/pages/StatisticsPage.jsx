import { useEffect, useState } from "react";
import { exportUrl, request } from "../api.js";
import { ton, won, CHART_COLORS } from "./Detail/data.js";
import { Card, SectionTitle } from "./Detail/ui.jsx";
import LineChart from "./Detail/LineChart.jsx";
import FileLink from "../components/FileLink.jsx";
import { statisticsPeriod } from "./statisticsData.js";

export default function StatisticsPage({ data }) {
  const [filters, setFilters] = useState(() => ({ ...statisticsPeriod(), office_id: "", line: "", meter_id: "" }));
  const [query, setQuery] = useState(filters);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const change = (key, value) => setFilters((f) => ({ ...f, [key]: value, ...(["office_id", "line"].includes(key) ? { meter_id: "" } : {}) }));
  useEffect(() => {
    let alive = true;
    setLoading(true); setError("");
    const params = new URLSearchParams(Object.entries(query).filter(([, value]) => value));
    request(`/stats?${params}`).then((value) => { if (alive) setResult(value); })
      .catch((e) => { if (alive) { setError(e.message); setResult(null); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [query, data]);
  const rows = result?.rows || [];
  const queriedMeters = (data.meters || []).filter((m) => (!query.office_id || String(m.office_id) === query.office_id) && (!query.line || String(m.line) === query.line) && (!query.meter_id || String(m.id) === query.meter_id));
  const billingOnly = queriedMeters.length > 0 && queriedMeters.every((m) => m.data_mode === "billing_only");
  const months = [...new Set(rows.map((r) => r.month))].sort();
  const sum = (field, records = rows) => {
    const values = records.map((r) => r[field]).filter(Number.isFinite);
    return values.length ? values.reduce((a, b) => a + b, 0) : null;
  };
  const meters = (data.meters || []).filter((m) => (!filters.office_id || String(m.office_id) === filters.office_id) && (!filters.line || String(m.line) === filters.line));
  const summaryBills = sum("summary_bill_count");
  return <main className="management-page statistics-page">
    <div className="management-heading"><h1>사용량·요금 통계</h1></div>
    <form className="stats-filters" onSubmit={(e) => { e.preventDefault(); if (filters.start > filters.end) { setError("시작일은 종료일보다 늦을 수 없습니다."); return; } setQuery({ ...filters }); }}>
      <label className="form-field">시작일<input type="date" required value={filters.start} max={filters.end} onChange={(e) => change("start", e.target.value)} /></label>
      <label className="form-field">종료일<input type="date" required value={filters.end} min={filters.start} onChange={(e) => change("end", e.target.value)} /></label>
      <label className="form-field">사업소<select value={filters.office_id} onChange={(e) => change("office_id", e.target.value)}><option value="">전체</option>{(data.offices || []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label className="form-field">호선<select value={filters.line} onChange={(e) => change("line", e.target.value)}><option value="">전체</option>{[1,2,3,4,5,6,7,8,9].map((l) => <option key={l} value={l}>{l}호선</option>)}</select></label>
      <label className="form-field stats-meter">계량기<select value={filters.meter_id} onChange={(e) => change("meter_id", e.target.value)}><option value="">전체</option>{meters.map((m) => <option key={m.id} value={m.id}>{m.station_name} {m.line ? `${m.line}호선 ` : ""}{m.display_name || "기본 계량기"} ({m.customer_number})</option>)}</select></label>
      <button className="primary-button" disabled={loading}>{loading ? "조회 중…" : "조회"}</button>
    </form>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div aria-live="polite" aria-busy={loading}>
      {!loading && result && <>
        <dl className="stats-totals">
          {!billingOnly && <div><dt>일일 사용량 합계</dt><dd>{ton(sum("usage_ton"))} 톤</dd><dd className="sub">검침 {won(sum("observation_count"))}건</dd></div>}
          <div><dt>청구 사용량 합계</dt><dd>{ton(sum("billed_usage_ton"))} 톤</dd><dd className="sub">청구서 {won(sum("bill_count"))}건</dd></div>
          <div><dt>청구 요금 합계</dt><dd>{won(sum("billed_won"))} 원</dd><dd className="sub">{summaryBills ? `상세 내역이 없는 청구서 ${won(summaryBills)}건 포함` : "청구월 기준"}</dd></div>
        </dl>
        {result.note && <p className="form-hint">{result.note}</p>}
        <div className={`stats-charts ${billingOnly ? "stats-charts--billing" : ""}`}>
          {!billingOnly && <Card title="월별 일일 사용량"><LineChart series={[{ color: CHART_COLORS.usage, values: months.map((m) => sum("usage_ton", rows.filter((r) => r.month === m))) }]} xLabels={months} yUnit="톤" formatY={ton} height={220} /></Card>}
          <Card title="월별 청구 요금"><LineChart series={[{ color: CHART_COLORS.fee, values: months.map((m) => sum("billed_won", rows.filter((r) => r.month === m))) }]} xLabels={months} yUnit="원" formatY={won} height={220} /></Card>
        </div>
        <section className="table-panel">
          <SectionTitle as="h2" right={<>
            {!billingOnly && <FileLink href={exportUrl({ ...query, kind: "usage" })} filename={`사용량_${query.start}_${query.end}.xlsx`}>사용량 Excel</FileLink>}
            <FileLink href={exportUrl({ ...query, kind: "bills" })} filename={`청구내역_${query.start}_${query.end}.xlsx`}>청구내역 Excel</FileLink>
          </>}>월별 내역</SectionTitle>
          <div className="table-wrap"><table className="data-table"><caption className="sr-only">사업소·호선별 월별 통계</caption><thead><tr><th>월</th><th>사업소</th><th>호선</th>{!billingOnly && <th className="num">일일 사용량 (톤)</th>}<th className="num">청구 사용량 (톤)</th><th className="num">청구 요금 (원)</th><th className="num">{billingOnly ? "청구 건수" : "검침 / 청구 건수"}</th></tr></thead><tbody>{rows.map((r) => <tr key={`${r.month}-${r.office_id}-${r.line}`}><td>{r.month}</td><td>{r.office_name}</td><td>{r.line ? `${r.line}호선` : "—"}</td>{!billingOnly && <td className="num">{ton(r.usage_ton)}</td>}<td className="num">{ton(r.billed_usage_ton)}</td><td className="num">{won(r.billed_won)}</td><td className="num">{billingOnly ? r.bill_count : `${r.observation_count} / ${r.bill_count}`}</td></tr>)}</tbody></table></div>
          {!rows.length && <p className="empty-state">선택한 기간에 자료가 없습니다.</p>}
        </section>
      </>}
    </div>
  </main>;
}
