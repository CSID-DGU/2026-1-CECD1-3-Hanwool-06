import { lineMeta, offices, riskMeta, stations } from "../data.js";
import SectionTitle from "./SectionTitle.jsx";

export default function FilterPanel({
  resetFilters,
  selectedLine,
  selectedOffice,
  selectedRisk,
  setSelectedLine,
  setSelectedOffice,
  setSelectedRisk,
}) {
  return (
    <section className="control-panel" aria-label="필터">
      <SectionTitle title="필터링" />
      <div className="control-panel-body">
        <div className="field">
          <label htmlFor="office-filter">수도사업소</label>
          <select id="office-filter" value={selectedOffice} onChange={(event) => setSelectedOffice(event.target.value)}>
            <option value="all">전체 수도사업소</option>
            {offices.map((office) => (
              <option value={office} key={office}>
                {office}
              </option>
            ))}
          </select>
        </div>

        <div className="field field-wide">
          <span className="field-label">호선</span>
          <div className="line-filter" role="group" aria-label="호선 필터">
            <button className={selectedLine === "all" ? "is-on" : ""} onClick={() => setSelectedLine("all")} type="button">
              전체
            </button>
            {Object.entries(lineMeta).map(([line, meta]) => (
              <button
                className={selectedLine === line ? "is-on" : ""}
                onClick={() => setSelectedLine(line)}
                style={{ "--line-color": meta.color }}
                type="button"
                key={line}
              >
                {line}
              </button>
            ))}
          </div>
        </div>

        <div className="field field-wide">
          <span className="field-label">위험도</span>
          <div className="risk-filter" role="group" aria-label="위험도 필터">
            {Object.entries(riskMeta).map(([risk, meta]) => (
              <button className={`${selectedRisk === risk ? "is-on" : ""} risk-${meta.tone}`} onClick={() => setSelectedRisk(risk)} type="button" key={risk}>
                {meta.label}
                <span>{risk === "all" ? stations.length : stations.filter((station) => station.risk === risk).length}</span>
              </button>
            ))}
          </div>
        </div>

        <button className="reset-btn" onClick={resetFilters} type="button">
          초기화
        </button>
      </div>
    </section>
  );
}
