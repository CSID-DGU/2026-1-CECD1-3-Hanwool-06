import { lineMeta, riskMeta } from "../dashboardData.js";
import SectionTitle from "./SectionTitle.jsx";

export default function FilterPanel({
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
    <section className="control-panel" aria-label="필터">
      <SectionTitle title="필터링" />
      <div className="control-panel-body">
        <div className="field">
          <label htmlFor="office-filter">영업사업소</label>
          <select id="office-filter" value={selectedOffice} onChange={(event) => setSelectedOffice(event.target.value)}>
            <option value="all">전체 영업사업소</option>
            {offices.map((office) => (
              <option value={office.id} key={office.id}>
                {office.name}
              </option>
            ))}
          </select>
        </div>

        <div className="field field-wide">
          <span className="field-label">호선</span>
          <div className="line-filter" role="group" aria-label="호선 필터">
            <button className={selectedLine === "all" ? "is-on" : ""} onClick={() => setSelectedLine("all")} aria-pressed={selectedLine === "all"} type="button">
              전체
            </button>
            {Object.entries(lineMeta).map(([line, meta]) => (
              <button
                className={selectedLine === line ? "is-on" : ""}
                onClick={() => setSelectedLine(line)}
                aria-pressed={selectedLine === line}
                style={{ "--line-color": meta.color }}
                type="button"
                key={line}
              >
                {line}
              </button>
            ))}
          </div>
        </div>

        {!billingOnly && <div className="field field-wide">
          <span className="field-label">위험도 · 수집 상태</span>
          <div className="risk-filter" role="group" aria-label="위험도 필터">
            {Object.entries(riskMeta).filter(([risk]) => risk !== "billing_only").map(([risk, meta]) => (
              <button className={`${selectedRisk === risk ? "is-on" : ""} risk-${meta.tone}`} onClick={() => setSelectedRisk(risk)} aria-pressed={selectedRisk === risk} type="button" key={risk}>
                {meta.label}
                <span>{risk === "all" ? stations.length : stations.filter((station) => station.risk === risk).length}</span>
              </button>
            ))}
          </div>
        </div>}

        <button className="reset-btn" onClick={resetFilters} type="button">
          초기화
        </button>
      </div>
    </section>
  );
}
