import { useEffect, useMemo, useState } from "react";
import seoulMetroLogo from "../../assets/seoulmetro.svg";
import { loadDashboard } from "./dashboardData.js";
import { averageDelta } from "./utils.js";
import AppHeader from "./components/AppHeader.jsx";
import EmptyState from "./components/EmptyState.jsx";
import FilterPanel from "./components/FilterPanel.jsx";
import MapPanel from "./components/MapPanel.jsx";
import PageHeader from "./components/PageHeader.jsx";
import SectionTitle from "./components/SectionTitle.jsx";
import StationRow from "./components/StationRow.jsx";
import StationTable from "./components/StationTable.jsx";
import SummaryTile from "./components/SummaryTile.jsx";
import SearchPanel from "./components/SearchPanel.jsx";

export default function Dashboard() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLine, setSelectedLine] = useState("all");
  const [selectedOffice, setSelectedOffice] = useState("all");
  const [selectedRisk, setSelectedRisk] = useState("all");
  const [{ stations, offices }, setData] = useState({ stations: [], offices: [] });

  useEffect(() => {
    loadDashboard().then(setData);
  }, []);

  const normalizedSearchTerm = searchTerm.trim().toLowerCase();
  const filteredStations = useMemo(
    () =>
      stations.filter((station) => {
        const searchOk = normalizedSearchTerm === "" || station.name.toLowerCase().includes(normalizedSearchTerm);
        const lineOk = selectedLine === "all" || station.lines.includes(selectedLine);
        const officeOk = selectedOffice === "all" || station.office === selectedOffice;
        const riskOk = selectedRisk === "all" || station.risk === selectedRisk;
        return searchOk && lineOk && officeOk && riskOk;
      }),
    [stations, normalizedSearchTerm, selectedLine, selectedOffice, selectedRisk],
  );

  const stationMap = useMemo(() => new Map(filteredStations.map((station) => [station.id, station])), [filteredStations]);
  const alertStations = filteredStations.filter((station) => station.risk === "alert");
  const warnStations = filteredStations.filter((station) => station.risk === "warn");
  const latestCheckedAt = filteredStations
    .map((station) => station.checkedAt)
    .sort()
    .at(-1);

  const resetFilters = () => {
    setSearchTerm("");
    setSelectedLine("all");
    setSelectedOffice("all");
    setSelectedRisk("all");
  };

  return (
    <main className="app-shell">
      <AppHeader logo={seoulMetroLogo} />
      <PageHeader latestCheckedAt={latestCheckedAt} />

      <section className="summary-grid" aria-label="요약 지표">
        <SummaryTile label="관제 대상" value={`${filteredStations.length}개 역`} sub={`전체 ${stations.length}개 역`} />
        <SummaryTile label="경고" value={`${alertStations.length}건`} sub="즉시 확인 필요" tone="alert" />
        <SummaryTile label="주의" value={`${warnStations.length}건`} sub="추이 관찰 대상" tone="warn" />
        <SummaryTile label="평균 예측대비" value={`${averageDelta(filteredStations)}%`} sub="필터 결과 기준" />
      </section>

      <SearchPanel searchTerm={searchTerm} setSearchTerm={setSearchTerm} />
      <FilterPanel
        resetFilters={resetFilters}
        selectedLine={selectedLine}
        selectedOffice={selectedOffice}
        selectedRisk={selectedRisk}
        setSelectedLine={setSelectedLine}
        setSelectedOffice={setSelectedOffice}
        setSelectedRisk={setSelectedRisk}
        stations={stations}
        offices={offices}
      />

      <section className="workspace">
        <MapPanel
          selectedLine={selectedLine}
          selectedOffice={selectedOffice}
          selectedRisk={selectedRisk}
          stationMap={stationMap}
          setSelectedLine={setSelectedLine}
        />
        <aside className="side-panel" aria-label="위험 역 목록">
          <SectionTitle title="우선 확인 대상" right={`${alertStations.length + warnStations.length}건`} />
          <div className="priority-list">
            {[...alertStations, ...warnStations].map((station) => (
              <StationRow station={station} compact key={station.id} />
            ))}
            {alertStations.length + warnStations.length === 0 ? <EmptyState text="현재 필터에서 경고·주의 역이 없습니다." /> : null}
          </div>
        </aside>
      </section>

      <StationTable stations={filteredStations} />
    </main>
  );
}
