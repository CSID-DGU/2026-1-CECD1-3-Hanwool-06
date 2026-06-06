import { lineMeta, riskMeta, routes, stations } from "../data.js";
import RiskBadge from "./RiskBadge.jsx";
import SectionTitle from "./SectionTitle.jsx";

export default function MapPanel({ selectedLine, selectedOffice, selectedRisk, stationMap, setSelectedLine }) {
  const hasOfficeFilter = selectedOffice !== "all";
  const hasRiskFilter = selectedRisk !== "all";

  return (
    <section className="map-panel" aria-label="지하철 노선 관제도">
      <SectionTitle
        title="서울 지하철 노선 관제도"
        right={selectedLine === "all" ? "전체 호선" : `${selectedLine}호선 집중 보기`}
      />
      <div className="metro-map">
        <div className="map-legend" aria-label="위험도 범례">
          <RiskBadge risk="alert" />
          <RiskBadge risk="warn" />
          <RiskBadge risk="ok" />
        </div>
        <svg viewBox="0 0 980 620" role="img" aria-label="서울 지하철 노선 기반 이상징후 지도">
          <defs>
            <filter id="soft-blur">
              <feGaussianBlur stdDeviation="1.35" />
            </filter>
          </defs>
          <rect className="map-bg" x="0" y="0" width="980" height="620" rx="10" />
          <path className="river" d="M0 468 C130 420 188 540 322 490 C420 452 494 430 588 474 C704 526 786 470 980 418 L980 620 L0 620 Z" />
          <text className="river-label" x="470" y="500">
            Hangang River
          </text>
          <g className="district-lines">
            <path d="M126 52 L236 168 L226 310 L340 430 L318 584" />
            <path d="M402 40 L398 184 L510 258 L498 570" />
            <path d="M682 54 L654 206 L782 354 L850 574" />
            <path d="M46 278 L210 254 L384 284 L574 232 L930 248" />
          </g>

          {routes.map((route) => {
            const routeHasFilteredStation = stations.some((station) => station.lines.includes(route.line) && stationMap.has(station.id));
            const isLineFocused = selectedLine === "all" || selectedLine === route.line;
            const isMuted = !isLineFocused || ((hasOfficeFilter || hasRiskFilter) && !routeHasFilteredStation);
            return (
              <g className={`route-layer ${isMuted ? "is-muted" : "is-active"}`} key={route.line}>
                <path className="route-shadow" d={route.d} />
                <path
                  className="route-hit"
                  d={route.d}
                  onClick={() => setSelectedLine(route.line)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedLine(route.line);
                    }
                  }}
                  role="button"
                  aria-label={`${route.line}호선 선택`}
                  tabIndex="0"
                />
                <path className="route-line" d={route.d} style={{ "--line-color": lineMeta[route.line].color }} />
                <text className="route-label" x={routeLabelPosition(route.line).x} y={routeLabelPosition(route.line).y} style={{ "--line-color": lineMeta[route.line].color }}>
                  {route.line}
                </text>
              </g>
            );
          })}

          <g className="station-layer">
            {stations.map((station) => {
              const isVisible = stationMap.has(station.id);
              return <MapStation station={station} muted={!isVisible} key={station.id} />;
            })}
          </g>
        </svg>
      </div>
    </section>
  );
}

function MapStation({ station, muted }) {
  return (
    <g className={`map-station ${muted ? "is-muted" : ""}`} transform={`translate(${station.x} ${station.y})`}>
      <circle className="station-halo" r="13" />
      <circle className={`station-dot risk-${riskMeta[station.risk].tone}`} r="8" />
      <circle className="station-core" r="3.5" />
      <text className="station-name" x="13" y="-11">
        {station.name}
      </text>
    </g>
  );
}

function routeLabelPosition(line) {
  const positions = {
    1: { x: 462, y: 372 },
    2: { x: 708, y: 438 },
    3: { x: 914, y: 510 },
    4: { x: 692, y: 70 },
    5: { x: 926, y: 232 },
    6: { x: 724, y: 486 },
    7: { x: 884, y: 88 },
    8: { x: 928, y: 304 },
    9: { x: 930, y: 522 },
  };
  return positions[line];
}
