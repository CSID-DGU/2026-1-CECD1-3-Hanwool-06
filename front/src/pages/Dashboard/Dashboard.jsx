import { useMemo, useState } from "react";
import { buildDashboard } from "./dashboardData.js";
import EmptyState from "./components/EmptyState.jsx";
import FilterPanel from "./components/FilterPanel.jsx";
import MapPanel from "./components/MapPanel.jsx";
import PageHeader from "./components/PageHeader.jsx";
import SectionTitle from "./components/SectionTitle.jsx";
import StationRow from "./components/StationRow.jsx";
import StationTable from "./components/StationTable.jsx";
import SummaryTile from "./components/SummaryTile.jsx";
import SearchPanel from "./components/SearchPanel.jsx";
import { exportUrl } from "../../api.js";
import FileLink from "../../components/FileLink.jsx";
import CollectionPanel from "../../components/CollectionPanel.jsx";

export default function Dashboard({ data, collection }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLine, setSelectedLine] = useState("all");
  const [selectedOffice, setSelectedOffice] = useState("all");
  const [selectedRisk, setSelectedRisk] = useState("all");
  const [view, setView] = useState("daily");
  const { stations, offices } = useMemo(() => buildDashboard(data), [data]);
  const term = searchTerm.trim().toLowerCase();
  const scopedStations = stations.filter((station) =>
    (!term || `${station.name} ${station.customerNo} ${station.displayName}`.toLowerCase().includes(term))
    && (selectedLine === "all" || station.lines.includes(selectedLine))
    && (selectedOffice === "all" || station.officeId === selectedOffice)
  );
  const billingStations = scopedStations.filter((s) => s.dataMode === "billing_only");
  const dailyStations = scopedStations.filter((s) => s.dataMode !== "billing_only");
  const billingOnly = view === "billing";
  const viewStations = billingOnly ? billingStations : dailyStations;
  const filteredStations = viewStations.filter((station) => billingOnly || selectedRisk === "all" || station.risk === selectedRisk);
  const alerts = filteredStations.filter((s) => s.risk === "alert");
  const warnings = filteredStations.filter((s) => s.risk === "warn");
  const unknowns = filteredStations.filter((s) => s.risk === "unknown");
  const resetFilters = () => { setSearchTerm(""); setSelectedLine("all"); setSelectedOffice("all"); setSelectedRisk("all"); };
  const exportParams = { office_id: selectedOffice, line: selectedLine };
  return <main className="app-shell">
    <PageHeader status={data.status || {}} />
    <section className="summary-grid" aria-label="검색·사업소·호선 범위의 요약 지표">
      <SummaryTile label="일일 사용량 제공" value={`${dailyStations.filter((s) => s.dataMode === "daily").length}개`} sub={`전체 등록 계량기 ${stations.length}개`} />
      <SummaryTile label="경고 / 주의" value={`${dailyStations.filter((s) => s.risk === "alert").length} / ${dailyStations.filter((s) => s.risk === "warn").length}`} sub="일일 관제 대상의 위험도" tone={dailyStations.some((s) => s.risk === "alert") ? "alert" : "warn"} />
      <SummaryTile label="청구 전용" value={`${billingStations.length}개`} sub="청구·요금·기간별 비교 제공" />
      <SummaryTile label="첫 수집 대기" value={`${dailyStations.filter((s) => s.risk === "pending").length}개`} sub={`일일 자료 수집 후 분석 대기 ${dailyStations.filter((s) => s.risk === "analysis_pending").length}개`} />
    </section>
    <CollectionPanel collection={collection} meters={data.meters || []} />
    <SearchPanel searchTerm={searchTerm} setSearchTerm={setSearchTerm} />
    <div className="data-mode-switch" role="group" aria-label="제공 자료 종류"><button aria-pressed={!billingOnly} onClick={() => { setView("daily"); setSelectedRisk("all"); }}>일일 관제 <span>{dailyStations.length}</span></button><button aria-pressed={billingOnly} onClick={() => { setView("billing"); setSelectedRisk("all"); }}>청구 전용 <span>{billingStations.length}</span></button><p>{billingOnly ? "일일 사용량 수집 대상이 아닌 계량기입니다. 청구서와 사용량·요금 비교를 제공합니다." : "실제 일일 사용량이 있는 계량기와 첫 수집을 기다리는 대상을 표시합니다."}</p></div>
    <FilterPanel {...{resetFilters, selectedLine, selectedOffice, selectedRisk, setSelectedLine, setSelectedOffice, setSelectedRisk, offices, billingOnly}} stations={viewStations} />
    <section className={`workspace ${billingOnly ? "workspace--billing" : ""}`}>
      <MapPanel selectedLine={selectedLine} stationMap={new Map(filteredStations.map((s) => [s.id, s]))} locations={data.locations || {}} billingOnly={billingOnly} />
      {!billingOnly && <aside className="side-panel" aria-label="우선 확인할 계량기">
        <SectionTitle title="우선 확인 대상" right={`${alerts.length + warnings.length}개`} />
        <div className="priority-list">
          {[...alerts, ...warnings].map((station) => <StationRow station={station} compact key={station.id} />)}
          {!alerts.length && !warnings.length && <EmptyState text="현재 필터에서 경고·주의 계량기가 없습니다." />}
        </div>
        {unknowns.length > 0 && <button className="text-button unknown-summary" onClick={() => setSelectedRisk("unknown")}>기존 분석 자료 확인 {unknowns.length}개 보기 →</button>}
      </aside>}
    </section>
    <div className="export-toolbar">
      <span>선택한 사업소·호선의 자료 내보내기</span>
      {!billingOnly && <FileLink href={exportUrl({ ...exportParams, kind: "usage" })} filename="사용량.xlsx">사용량 Excel</FileLink>}
      <FileLink href={exportUrl({ ...exportParams, kind: "bills" })} filename="청구내역.xlsx">청구내역 Excel</FileLink>
      <a className="text-button" href="#/statistics">기간별 통계 →</a>
    </div>
    <StationTable stations={filteredStations} billingOnly={billingOnly} />
  </main>;
}
