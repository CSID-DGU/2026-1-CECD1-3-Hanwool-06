import { useMemo, useState } from "react";
import { buildDashboard, defaultSort, riskMeta, sortStations } from "./dashboardData.js";
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
  const [sortKey, setSortKey] = useState(defaultSort);
  const { stations, offices } = useMemo(() => buildDashboard(data), [data]);
  const term = searchTerm.trim().toLowerCase();
  // 검색어·호선·사업소·위험도 조건은 계량기 목록 머리글에서 바꾸고, 노선도와 우선 확인 대상도 같은 조건을 따른다.
  const scopedStations = stations.filter((station) =>
    (!term || `${station.name} ${station.customerNo} ${station.displayName} ${station.office}`.toLowerCase().includes(term))
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
  // 표는 조건을 적용한 뒤 정렬한 사본을 받는다. 원본 배열과 노선도·우선 확인 대상의 순서는 그대로다.
  const sortedStations = sortStations(filteredStations, sortKey, billingOnly);
  const filtering = Boolean(term) || selectedLine !== "all" || selectedOffice !== "all" || (!billingOnly && selectedRisk !== "all");
  const resetFilters = () => { setSearchTerm(""); setSelectedLine("all"); setSelectedOffice("all"); setSelectedRisk("all"); setSortKey(defaultSort); };
  const switchView = (next) => { setView(next); setSelectedRisk("all"); };
  const exportParams = { office_id: selectedOffice, line: selectedLine };
  // 머리글 선택 상자의 선택지: 이 보기(일일 관제·청구 전용)에 실제로 있는 호선과, 위험도별 계량기 수.
  const allViewStations = billingOnly ? stations.filter((s) => s.dataMode === "billing_only") : monitored;
  const lines = [...new Set(allViewStations.flatMap((s) => s.lines).filter(Boolean))].sort((a, b) => Number(a) - Number(b));
  const riskCounts = viewStations.reduce((counts, station) => ({ ...counts, [station.risk]: (counts[station.risk] || 0) + 1 }), { all: viewStations.length });
  const filters = { searchTerm, selectedLine, selectedOffice, selectedRisk };
  // 노선도 위에 보여 줄 현재 조건. 어디서 바꿨든(표 머리글·범례·검색) 같은 상태를 읽는다.
  const conditions = [
    term && `검색 "${searchTerm.trim()}"`,
    selectedLine !== "all" && `${selectedLine}호선`,
    selectedOffice !== "all" && (offices.find((o) => String(o.id) === selectedOffice)?.name || selectedOffice),
    !billingOnly && selectedRisk !== "all" && (riskMeta[selectedRisk]?.label || selectedRisk),
  ].filter(Boolean);
  const setters = { searchTerm: setSearchTerm, selectedLine: setSelectedLine, selectedOffice: setSelectedOffice, selectedRisk: setSelectedRisk };
  return <main className="app-shell">
    <PageHeader daily={monitored.length} alerts={monitored.filter((s) => s.risk === "alert").length} warnings={monitored.filter((s) => s.risk === "warn").length} />
    <CollectionPanel collection={collection} meters={data.meters || []} />
    <div className="view-tabs" role="group" aria-label="제공 자료 종류">
      <button type="button" aria-pressed={!billingOnly} onClick={() => switchView("daily")} title="일일 사용량을 수집하는 계량기">일일 관제 <span>{dailyStations.length}</span></button>
      <button type="button" aria-pressed={billingOnly} onClick={() => switchView("billing")} title="청구서만 수집하는 계량기">청구 전용 <span>{billingStations.length}</span></button>
    </div>
    <section className="workspace">
      <MapPanel stationMap={new Map(filteredStations.map((s) => [s.id, s]))} locations={data.locations || {}} billingOnly={billingOnly}
        selectedRisk={selectedRisk} onSelectRisk={setSelectedRisk} riskCounts={riskCounts} conditions={conditions} onReset={resetFilters}>
        {!billingOnly && <section className="side-block" aria-label="우선 확인할 계량기">
          <SectionTitle as="h2">우선 확인 대상 <span className="count">{alerts.length + warnings.length}개</span></SectionTitle>
          <div className="priority-list">
            {[...alerts, ...warnings].map((station) => <StationRow station={station} key={station.id} />)}
            {!alerts.length && !warnings.length && <EmptyNote>경고·주의 계량기가 없습니다.</EmptyNote>}
          </div>
          {selectedRisk === "unknown"
            ? <button type="button" className="text-button" onClick={() => setSelectedRisk("all")}>자료 확인 계량기 {unknowns.length}개만 보는 중 · 전체 위험도 보기</button>
            : unknowns.length > 0 && <button type="button" className="text-button" onClick={() => setSelectedRisk("unknown")}>자료 확인이 필요한 계량기 {unknowns.length}개 보기</button>}
        </section>}
      </MapPanel>
    </section>
    <StationTable stations={sortedStations} total={viewStations.length} filtering={filtering} onReset={resetFilters}
      filters={filters} onFilterChange={(key, value) => setters[key](value)} options={{ offices, lines, riskCounts }}
      sortKey={sortKey} onSortChange={setSortKey} billingOnly={billingOnly} actions={<>
      <span className="export-note">사업소·호선 조건으로 내려받기</span>
      {!billingOnly && <FileLink href={exportUrl({ ...exportParams, kind: "usage" })} filename="사용량.xlsx">사용량 Excel</FileLink>}
      <FileLink href={exportUrl({ ...exportParams, kind: "bills" })} filename="청구내역.xlsx">청구내역 Excel</FileLink>
    </>} />
  </main>;
}
