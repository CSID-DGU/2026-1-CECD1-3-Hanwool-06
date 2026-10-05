import { lineColors, riskMeta } from "../dashboardData.js";

export default function FilterPanel({
  searchTerm,
  setSearchTerm,
  resetFilters,
  selectedLine,
  selectedOffice,
  selectedRisk,
  setSelectedLine,
  setSelectedOffice,
  setSelectedRisk,
  stations,
  offices,
  billingOnly = false,
}) {
  return (
    <section className="filter-bar" aria-label="조회 조건">
      <label className="form-field filter-search">
        검색
        <input type="search" value={searchTerm} onChange={(event) => setSearchTerm(event.target.value)} placeholder="역명, 고객번호, 계량기 이름" autoComplete="off" />
      </label>
      <label className="form-field">
        영업사업소
        <select value={selectedOffice} onChange={(event) => setSelectedOffice(event.target.value)}>
          <option value="all">전체</option>
          {offices.map((office) => (
            <option value={office.id} key={office.id}>{office.name}</option>
          ))}
        </select>
      </label>
      <div className="filter-group">
        <span className="filter-label">호선</span>
        <div className="line-filter" role="group" aria-label="호선 필터">
          <button className="line-filter-all" onClick={() => setSelectedLine("all")} aria-pressed={selectedLine === "all"} type="button">전체</button>
          {Object.entries(lineColors).map(([line, color]) => (
            <button onClick={() => setSelectedLine(line)} aria-pressed={selectedLine === line} aria-label={`${line}호선`} style={{ "--line-color": color }} type="button" key={line}>
              {line}
            </button>
          ))}
        </div>
      </div>
      {!billingOnly && (
        <div className="filter-group">
          <span className="filter-label">위험도</span>
          <div className="risk-filter" role="group" aria-label="위험도 필터">
            {Object.entries(riskMeta).filter(([risk]) => risk !== "billing_only").map(([risk, meta]) => (
              <button className={`risk-${meta.tone}`} onClick={() => setSelectedRisk(risk)} aria-pressed={selectedRisk === risk} type="button" key={risk}>
                {meta.label}
                <span>{risk === "all" ? stations.length : stations.filter((station) => station.risk === risk).length}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <button className="text-button filter-reset" onClick={resetFilters} type="button">조건 초기화</button>
    </section>
  );
}
