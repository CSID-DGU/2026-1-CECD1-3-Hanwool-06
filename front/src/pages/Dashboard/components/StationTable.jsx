import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";
import { EmptyNote, SectionTitle } from "../../Detail/ui.jsx";
import { detailHref, signedPct, ton } from "../../Detail/data.js";
import { nextSort, riskMeta } from "../dashboardData.js";
import Dropdown from "../../../components/Dropdown.jsx";

// 머리글에서 바로 정렬(역명·기준일)하고 고른다(호선·영업사업소·위험도). 검색과 조건 초기화는 표 바로 위에 둔다.
// stations: 조건을 적용하고 정렬까지 끝낸 목록. total: 조건을 적용하기 전 이 보기(일일 관제·청구 전용)의 계량기 수.
export default function StationTable({ stations, total = stations.length, filtering = false, onReset, filters = {}, onFilterChange, options = {},
  sortKey = "name-asc", onSortChange, billingOnly = false, actions }) {
  const [sortColumn, sortDirection] = sortKey.split("-");
  const { offices = [], lines = [], riskCounts = {} } = options;
  const change = (key) => (event) => onFilterChange?.(key, event.target.value);
  const sortHeader = (column, label) => {
    const active = sortColumn === column;
    const ariaSort = active ? (sortDirection === "asc" ? "ascending" : "descending") : "none";
    const hint = column === "date" ? (active && sortDirection === "desc" ? "최신순, 누르면 오래된순" : "누르면 최신순") : (active && sortDirection === "asc" ? "오름차순, 누르면 내림차순" : "누르면 오름차순");
    return <th aria-sort={ariaSort} className={active ? "is-sorted" : ""}>
      <button type="button" className="th-sort" onClick={() => onSortChange?.(nextSort(sortKey, column))} title={`${label} ${hint}`}>
        {label}<span className="th-sort-mark" aria-hidden="true">{active ? (sortDirection === "asc" ? "▲" : "▼") : "⇅"}</span>
      </button>
    </th>;
  };
  // 머리글에는 고르지 않았으면 열 이름만, 골랐으면 고른 값만 보인다. 목록은 자체 드롭다운(components/Dropdown.jsx)이 그린다.
  const filterHeader = (label, key, items) => {
    const value = filters[key] ?? "all";
    const chosen = items.find((item) => item.value === value);
    return <th className={value !== "all" ? "is-filtered" : ""}>
      <Dropdown label={label} value={value} display={chosen ? chosen.label : label} active={value !== "all"} buttonClassName="th-dropdown" anchor="parent"
        options={[{ value: "all", label: "전체" }, ...items]} onChange={(next) => onFilterChange?.(key, next)} />
    </th>;
  };
  const riskItems = Object.entries(riskMeta).filter(([risk]) => !["all", "billing_only"].includes(risk))
    .map(([risk, meta]) => ({ value: risk, label: `${meta.label} ${riskCounts[risk] || 0}개` }));
  return (
    <section className="table-panel">
      <SectionTitle as="h2" right={actions}>
        {billingOnly ? "청구 전용 계량기" : "계량기 목록"}{" "}
        <span className="count" aria-live="polite">{filtering ? `${stations.length}개 (전체 ${total}개 중)` : `${stations.length}개`}</span>
      </SectionTitle>
      <div className="table-toolbar">
        <label className="form-field table-search">검색
          <input type="search" value={filters.searchTerm ?? ""} onChange={change("searchTerm")} placeholder="역명, 계량기 이름, 고객번호, 사업소" autoComplete="off" />
        </label>
        <p className="form-hint">머리글에서 역명·기준일은 정렬, 호선·영업사업소·위험도는 조건을 고를 수 있습니다. 노선도와 우선 확인 대상도 같은 조건을 따릅니다.</p>
        {filtering && <button type="button" className="text-button" onClick={onReset}>조건 초기화</button>}
      </div>
      <div className="table-wrap table-wrap--fixed">
        <table className={`data-table data-table--controls ${billingOnly ? "" : "data-table--wide"}`}>
          {/* 조건·숫자 열은 가장 긴 글("종합운동장영업사업소", "첫 수집 대기 00개")이 잘리지 않는 고정 폭,
              역명 열이 남은 폭을 가진다. 검색·조건을 바꿔도 열이 흔들리지 않는다. */}
          <colgroup>
            {(billingOnly ? [null, 120, 170, 150] : [null, 120, 170, 200, 90, 90, 150])
              .map((width, i) => <col key={i} style={width ? { width: `${width}px` } : undefined} />)}
          </colgroup>
          <thead>
            <tr>
              {sortHeader("name", "역명")}
              {filterHeader("호선", "selectedLine", lines.map((line) => ({ value: line, label: `${line}호선` })))}
              {filterHeader("영업사업소", "selectedOffice", offices.map((office) => ({ value: String(office.id), label: office.name })))}
              {!billingOnly && <>
                {filterHeader("위험도", "selectedRisk", riskItems)}
                <th className="num">일 사용량</th>
                <th className="num">예측 대비</th>
              </>}
              {sortHeader("date", billingOnly ? "최근 청구월" : "기준일")}
            </tr>
          </thead>
          <tbody>
            {stations.map((station) => (
              <tr key={station.id}>
                <td>
                  <a className="station-link" href={detailHref(station.id)}>{station.name}</a>
                  <small>{station.displayName} {station.customerNo}</small>
                </td>
                <td><LineBadges lines={station.lines} /></td>
                <td>{station.office}</td>
                {!billingOnly && <>
                  <td>
                    <RiskBadge risk={station.risk} label={station.riskLabel} />
                    {station.riskDetail && <small>{station.riskDetail}</small>}
                  </td>
                  <td className="num">{ton(station.usage)} 톤</td>
                  <td className="num">{signedPct(station.delta)}</td>
                </>}
                <td>{billingOnly ? station.latestBillMonth || "청구서 없음" : <>사용량 {station.dailyDate || "없음"}<small>분석 {station.riskDate || "대기"}</small></>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {stations.length === 0 ? <EmptyNote>
          {filtering ? "검색어·조건에 맞는 계량기가 없습니다." : "표시할 계량기가 없습니다."}
          {filtering && onReset && <> <button type="button" className="text-button" onClick={onReset}>조건 초기화</button></>}
        </EmptyNote> : null}
      </div>
    </section>
  );
}
