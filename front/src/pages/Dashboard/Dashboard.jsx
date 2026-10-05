import { useMemo, useState } from "react";
import { buildDashboard } from "./dashboardData.js";
import FilterPanel from "./components/FilterPanel.jsx";
import MapPanel from "./components/MapPanel.jsx";
import PageHeader from "./components/PageHeader.jsx";
import StationRow from "./components/StationRow.jsx";
import StationTable from "./components/StationTable.jsx";
import { EmptyNote, SectionTitle } from "../Detail/ui.jsx";
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
  // The headline describes everything the user may see, independent of the filters below.
  const monitored = stations.filter((s) => s.dataMode !== "billing_only");
  const resetFilters = () => { setSearchTerm(""); setSelectedLine("all"); setSelectedOffice("all"); setSelectedRisk("all"); };
  const switchView = (next) => { setView(next); setSelectedRisk("all"); };
  const exportParams = { office_id: selectedOffice, line: selectedLine };
  return <main className="app-shell">
    <PageHeader status={data.status || {}} daily={monitored.length} alerts={monitored.filter((s) => s.risk === "alert").length} warnings={monitored.filter((s) => s.risk === "warn").length} />
    <CollectionPanel collection={collection} meters={data.meters || []} />
    <div className="view-tabs" role="group" aria-label="제공 자료 종류">
      <button type="button" aria-pressed={!billingOnly} onClick={() => switchView("daily")} title="일일 사용량을 수집하는 계량기">일일 관제 <span>{dailyStations.length}</span></button>
      <button type="button" aria-pressed={billingOnly} onClick={() => switchView("billing")} title="청구서만 수집하는 계량기">청구 전용 <span>{billingStations.length}</span></button>
    </div>
    <FilterPanel {...{ searchTerm, setSearchTerm, resetFilters, selectedLine, selectedOffice, selectedRisk, setSelectedLine, setSelectedOffice, setSelectedRisk, offices, billingOnly }} stations={viewStations} />
    <section className={`workspace ${billingOnly ? "workspace--billing" : ""}`}>
      <MapPanel stationMap={new Map(filteredStations.map((s) => [s.id, s]))} locations={data.locations || {}} billingOnly={billingOnly} />
      {!billingOnly && <aside className="side-panel" aria-label="우선 확인할 계량기">
        <SectionTitle as="h2">우선 확인 대상 <span className="count">{alerts.length + warnings.length}개</span></SectionTitle>
        <div className="priority-list">
          {[...alerts, ...warnings].map((station) => <StationRow station={station} key={station.id} />)}
          {!alerts.length && !warnings.length && <EmptyNote>경고·주의 계량기가 없습니다.</EmptyNote>}
        </div>
        {unknowns.length > 0 && <button type="button" className="text-button" onClick={() => setSelectedRisk("unknown")}>자료 확인이 필요한 계량기 {unknowns.length}개 보기</button>}
      </aside>}
    </section>
    <StationTable stations={filteredStations} billingOnly={billingOnly} actions={<>
      <span className="export-note">사업소·호선 조건으로 내려받기</span>
      {!billingOnly && <FileLink href={exportUrl({ ...exportParams, kind: "usage" })} filename="사용량.xlsx">사용량 Excel</FileLink>}
      <FileLink href={exportUrl({ ...exportParams, kind: "bills" })} filename="청구내역.xlsx">청구내역 Excel</FileLink>
    </>} />
  </main>;
}
