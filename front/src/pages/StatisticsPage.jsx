import { useEffect, useState } from "react";
import { exportUrl, request } from "../api.js";
import { ton, won, CHART_COLORS } from "./Detail/data.js";
import { Card, SectionTitle } from "./Detail/ui.jsx";
import LineChart from "./Detail/LineChart.jsx";
import FileLink from "../components/FileLink.jsx";
import Dropdown from "../components/Dropdown.jsx";
import { FilterHeader, SortHeader } from "../components/TableHeader.jsx";
import { statisticsPeriod } from "./statisticsData.js";
import { compareText, nextSortKey, sortRows } from "../sorting.js";

// 월별 내역 표의 정렬 열과 기본 방향. 월은 시간순, 수치는 큰 값이 먼저.
const TABLE_SORT_DEFAULTS = { month: "asc", usage_ton: "desc", billed_usage_ton: "desc", billed_won: "desc" };
const TABLE_COLUMNS = {
  month: { value: (r) => r.month, type: "date" },
  usage_ton: { value: (r) => r.usage_ton, type: "number" },
  billed_usage_ton: { value: (r) => r.billed_usage_ton, type: "number" },
  billed_won: { value: (r) => r.billed_won, type: "number" },
};
const NUMBER_HINTS = { asc: "작은 값부터, 누르면 큰 값부터", desc: "큰 값부터, 누르면 작은 값부터", idle: "누르면 큰 값부터" };
const MONTH_HINTS = { asc: "오래된 달부터, 누르면 최신 달부터", desc: "최신 달부터, 누르면 오래된 달부터", idle: "누르면 최신 달부터" };
const rowOrder = (a, b) => compareText(a.month, b.month) || compareText(a.office_name, b.office_name) || compareText(a.line, b.line);

export function meterOption(meter) {
  return { value: String(meter.id), keywords: `${meter.customer_number} ${meter.station_name} ${meter.display_name || ""}`,
           label: `${meter.station_name} ${meter.line ? `${meter.line}호선 ` : ""}${meter.display_name || "기본 계량기"} (${meter.customer_number})` };
}

export default function StatisticsPage({ data }) {
  const [filters, setFilters] = useState(() => ({ ...statisticsPeriod(), office_id: "", line: "", meter_id: "" }));
  const [query, setQuery] = useState(filters);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  // 표 안에서만 쓰는 정렬·조건. 조회 조건(query)과 Excel 내려받기에는 영향을 주지 않는다.
  const [sortKey, setSortKey] = useState("month-asc");
  const [tableOffice, setTableOffice] = useState("all");
  const [tableLine, setTableLine] = useState("all");
  const change = (key, value) => setFilters((f) => ({ ...f, [key]: value, ...(["office_id", "line"].includes(key) ? { meter_id: "" } : {}) }));
  useEffect(() => {
    let alive = true;
    setLoading(true); setError("");
    const params = new URLSearchParams(Object.entries(query).filter(([, value]) => value));
    request(`/stats?${params}`).then((value) => { if (alive) { setResult(value); setTableOffice("all"); setTableLine("all"); } })
      .catch((e) => { if (alive) { setError(e.message); setResult(null); } })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [query, data]);
  const rows = result?.rows || [];
  const queriedMeters = (data.meters || []).filter((m) => (!query.office_id || String(m.office_id) === query.office_id) && (!query.line || String(m.line) === query.line) && (!query.meter_id || String(m.id) === query.meter_id));
  const billingOnly = queriedMeters.length > 0 && queriedMeters.every((m) => m.data_mode === "billing_only");
  const months = [...new Set(rows.map((r) => r.month))].sort();
  const monthLabels = months.map((m) => m.slice(2).replace("-", "/"));   // "2026-03" → "26/03": 역 상세 청구 차트와 같은 표기
  const sum = (field, records = rows) => {
    const values = records.map((r) => r[field]).filter(Number.isFinite);
    return values.length ? values.reduce((a, b) => a + b, 0) : null;
  };
  const meters = (data.meters || []).filter((m) => (!filters.office_id || String(m.office_id) === filters.office_id) && (!filters.line || String(m.line) === filters.line));
  const meterOptions = [{ value: "", label: "전체" }, ...meters.map(meterOption)];
  const summaryBills = sum("summary_bill_count");
  // 표 머리글의 조건(사업소·호선)과 정렬. 선택지는 조회 결과에 실제로 있는 값만.
  const officeItems = [...new Map(rows.map((r) => [String(r.office_id), r.office_name])).entries()].sort((a, b) => compareText(a[1], b[1])).map(([value, label]) => ({ value, label }));
  const lineItems = [...new Set(rows.map((r) => r.line).filter(Boolean))].sort((a, b) => Number(a) - Number(b)).map((line) => ({ value: String(line), label: `${line}호선` }));
  const visibleRows = sortRows(rows.filter((r) => (tableOffice === "all" || String(r.office_id) === tableOffice) && (tableLine === "all" || String(r.line) === tableLine)), sortKey, TABLE_COLUMNS, rowOrder);
  const tableFiltering = tableOffice !== "all" || tableLine !== "all";
  const resetTable = () => { setTableOffice("all"); setTableLine("all"); setSortKey("month-asc"); };
  return <main className="management-page statistics-page">
    <div className="management-heading"><h1>사용량·요금 통계</h1></div>
    <form className="stats-filters" onSubmit={(e) => { e.preventDefault(); if (filters.start > filters.end) { setError("시작일은 종료일보다 늦을 수 없습니다."); return; } setQuery({ ...filters }); }}>
      <label className="form-field">시작일<input type="date" required value={filters.start} max={filters.end} onChange={(e) => change("start", e.target.value)} /></label>
      <label className="form-field">종료일<input type="date" required value={filters.end} min={filters.start} onChange={(e) => change("end", e.target.value)} /></label>
      <label className="form-field">사업소<select value={filters.office_id} onChange={(e) => change("office_id", e.target.value)}><option value="">전체</option>{(data.offices || []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label className="form-field">호선<select value={filters.line} onChange={(e) => change("line", e.target.value)}><option value="">전체</option>{[1,2,3,4,5,6,7,8].map((l) => <option key={l} value={l}>{l}호선</option>)}</select></label>
      <div className="form-field stats-meter"><span>계량기</span>
        <Dropdown label="계량기" value={filters.meter_id} options={meterOptions} onChange={(next) => change("meter_id", next)} buttonClassName="dd-field"
          searchable searchPlaceholder="역명, 계량기 이름, 고객번호 검색" emptyText="일치하는 계량기가 없습니다." />
      </div>
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
          {!billingOnly && <Card title="월별 일일 사용량"><LineChart series={[{ color: CHART_COLORS.usage, values: months.map((m) => sum("usage_ton", rows.filter((r) => r.month === m))) }]} xLabels={monthLabels} yUnit="톤" xUnit="연/월" formatY={ton} height={220} /></Card>}
          <Card title="월별 청구 요금"><LineChart series={[{ color: CHART_COLORS.fee, values: months.map((m) => sum("billed_won", rows.filter((r) => r.month === m))) }]} xLabels={monthLabels} yUnit="원" xUnit="연/월" formatY={won} height={220} /></Card>
        </div>
        <section className="table-panel">
          <SectionTitle as="h2" right={<>
            {tableFiltering && <button type="button" className="text-button" onClick={resetTable}>조건 초기화</button>}
            {billingOnly && <span className="export-note">청구 전용 계량기라 일일 사용량 자료가 없습니다</span>}
            {!billingOnly && <FileLink href={exportUrl({ ...query, kind: "usage" })} filename={`사용량_${query.start}_${query.end}.xlsx`}>사용량 Excel</FileLink>}
            <FileLink href={exportUrl({ ...query, kind: "bills" })} filename={`청구내역_${query.start}_${query.end}.xlsx`}>청구내역 Excel</FileLink>
          </>}>월별 내역 <span className="count">{tableFiltering ? `${visibleRows.length}행 (전체 ${rows.length}행 중)` : `${rows.length}행`}</span></SectionTitle>
          <div className="table-wrap table-wrap--fixed"><table className="data-table data-table--controls"><caption className="sr-only">사업소·호선별 월별 통계</caption>
            <thead><tr>
              <SortHeader column="month" label="월" sortKey={sortKey} onSort={(c) => setSortKey(nextSortKey(sortKey, c, TABLE_SORT_DEFAULTS))} hints={MONTH_HINTS} />
              <FilterHeader label="사업소" value={tableOffice} onChange={setTableOffice} items={officeItems} />
              <FilterHeader label="호선" value={tableLine} onChange={setTableLine} items={lineItems} />
              {!billingOnly && <SortHeader column="usage_ton" label="일일 사용량 (톤)" sortKey={sortKey} onSort={(c) => setSortKey(nextSortKey(sortKey, c, TABLE_SORT_DEFAULTS))} className="num" hints={NUMBER_HINTS} />}
              <SortHeader column="billed_usage_ton" label="청구 사용량 (톤)" sortKey={sortKey} onSort={(c) => setSortKey(nextSortKey(sortKey, c, TABLE_SORT_DEFAULTS))} className="num" hints={NUMBER_HINTS} />
              <SortHeader column="billed_won" label="청구 요금 (원)" sortKey={sortKey} onSort={(c) => setSortKey(nextSortKey(sortKey, c, TABLE_SORT_DEFAULTS))} className="num" hints={NUMBER_HINTS} />
              <th className="num">{billingOnly ? "청구 건수" : "검침 / 청구 건수"}</th>
            </tr></thead>
            <tbody>{visibleRows.map((r) => <tr key={`${r.month}-${r.office_id}-${r.line}`}><td>{r.month}</td><td>{r.office_name}</td><td>{r.line ? `${r.line}호선` : "—"}</td>{!billingOnly && <td className="num">{ton(r.usage_ton)}</td>}<td className="num">{ton(r.billed_usage_ton)}</td><td className="num">{won(r.billed_won)}</td><td className="num">{billingOnly ? r.bill_count : `${r.observation_count} / ${r.bill_count}`}</td></tr>)}</tbody></table>
            {!rows.length && <p className="empty-state">선택한 기간에 자료가 없습니다.</p>}
            {rows.length > 0 && !visibleRows.length && <p className="empty-state">조건에 맞는 행이 없습니다. <button type="button" className="text-button" onClick={resetTable}>조건 초기화</button></p>}
          </div>
        </section>
      </>}
    </div>
  </main>;
}
