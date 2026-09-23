import { useEffect, useState } from "react";
import { exportUrl, request } from "../api.js";
import { ton, won } from "./Detail/data.js";
import { Card } from "./Detail/ui.jsx";
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
  return <main className="management-page statistics-page">
    <div className="management-heading"><div><h1>사용량 · 요금 통계</h1><p>사업소와 호선, 계량기별로 월별 자료를 비교합니다.</p></div></div>
    <form className="management-card stats-filters" onSubmit={(e) => { e.preventDefault(); if (filters.start > filters.end) { setError("시작일은 종료일보다 늦을 수 없습니다."); return; } setQuery({ ...filters }); }}>
      <label className="form-field">시작일<input type="date" required value={filters.start} max={filters.end} onChange={(e) => change("start", e.target.value)} /></label>
      <label className="form-field">종료일<input type="date" required value={filters.end} min={filters.start} onChange={(e) => change("end", e.target.value)} /></label>
      <label className="form-field">사업소<select value={filters.office_id} onChange={(e) => change("office_id", e.target.value)}><option value="">전체 사업소</option>{(data.offices || []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label className="form-field">호선<select value={filters.line} onChange={(e) => change("line", e.target.value)}><option value="">전체 호선</option>{[1,2,3,4,5,6,7,8,9].map((l) => <option key={l} value={l}>{l}호선</option>)}</select></label>
      <label className="form-field stats-meter">계량기<select value={filters.meter_id} onChange={(e) => change("meter_id", e.target.value)}><option value="">전체 계량기</option>{meters.map((m) => <option key={m.id} value={m.id}>{m.station_name} {m.line}호선 · {m.display_name || "기본 계량기"} · {m.customer_number}{m.purpose ? ` · ${m.purpose}` : ""}</option>)}</select></label>
      <button className="primary-button" disabled={loading}>{loading ? "조회 중…" : "통계 조회"}</button>
    </form>
    {error && <p className="form-error" role="alert">{error}</p>}
    <div aria-live="polite" aria-busy={loading}>
      {!loading && result && <>
        <div className={`stats-totals ${billingOnly ? "stats-totals--billing" : ""}`}>{!billingOnly && <Card title="일일 관측 사용량 합계"><strong>{ton(sum("usage_ton"))} 톤</strong><p>관측 {won(sum("observation_count"))}건</p></Card>}<Card title="청구 사용량 합계"><strong>{ton(sum("billed_usage_ton"))} 톤</strong><p>청구 {won(sum("bill_count"))}건</p></Card><Card title="청구 요금 합계"><strong>{won(sum("billed_won"))} 원</strong><p>청구월 기준{sum("summary_bill_count") ? ` · 요약 자료 ${won(sum("summary_bill_count"))}건 포함` : ""}</p></Card></div>
        <p className="form-hint">{result.note || "일일 사용량은 관측일, 청구 사용량·요금은 청구월 기준입니다. 결측값을 0으로 간주하지 않습니다."}</p>
        <div className={`stats-charts ${billingOnly ? "stats-charts--billing" : ""}`}>{!billingOnly && <Card title="월별 일일 관측 사용량"><LineChart series={[{ color: "#283891", values: months.map((m) => sum("usage_ton", rows.filter((r) => r.month === m))) }]} xLabels={months} yUnit="톤" formatY={ton} height={220} /></Card>}<Card title="월별 청구 요금"><LineChart series={[{ color: "#0e7c7b", values: months.map((m) => sum("billed_won", rows.filter((r) => r.month === m))) }]} xLabels={months} yUnit="원" formatY={won} height={220} /></Card></div>
        <section className="management-card"><div className="export-toolbar"><span>조회한 기간·조건의 원자료</span>{!billingOnly && <FileLink href={exportUrl({ ...query, kind: "usage" })} filename={`사용량_${query.start}_${query.end}.xlsx`}>사용량 Excel</FileLink>}<FileLink href={exportUrl({ ...query, kind: "bills" })} filename={`청구내역_${query.start}_${query.end}.xlsx`}>청구내역 Excel</FileLink></div>
          <div className="table-wrap"><table className="management-table"><caption className="sr-only">사업소·호선별 월별 통계</caption><thead><tr><th>월</th><th>사업소</th><th>호선</th>{!billingOnly && <th>관측 사용량 (톤)</th>}<th>청구 사용량 (톤)</th><th>청구 요금 (원)</th><th>{billingOnly ? "청구 건수" : "관측 / 청구 건수"}</th></tr></thead><tbody>{rows.map((r) => <tr key={`${r.month}-${r.office_id}-${r.line}`}><td>{r.month}</td><td>{r.office_name}</td><td>{r.line}호선</td>{!billingOnly && <td>{ton(r.usage_ton)}</td>}<td>{ton(r.billed_usage_ton)}</td><td>{won(r.billed_won)}</td><td>{billingOnly ? r.bill_count : `${r.observation_count} / ${r.bill_count}`}</td></tr>)}</tbody></table></div>
          {!rows.length && <p className="empty-state">선택한 기간과 조건의 자료가 없습니다.</p>}
        </section>
      </>}
    </div>
  </main>;
}
