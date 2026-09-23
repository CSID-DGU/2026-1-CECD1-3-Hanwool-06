import { useRef, useState } from "react";
import { buildMapGroups, riskMeta } from "../dashboardData.js";
import { detailHref } from "../../Detail/data.js";
import RiskBadge from "./RiskBadge.jsx";
import SectionTitle from "./SectionTitle.jsx";

export default function MapPanel({ selectedLine, stationMap, locations, billingOnly = false }) {
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState(null);
  const viewport = useRef(null);
  const drag = useRef(null);
  const groups = buildMapGroups([...stationMap.values()], locations);
  const mapped = groups.filter((s) => s.position);
  const unplaced = groups.filter((s) => !s.position);
  const active = groups.find((s) => s.id === selected);
  const fit = () => { setZoom(1); viewport.current?.scrollTo(0, 0); };
  const startDrag = (e) => {
    if (e.pointerType !== "mouse" || e.target.closest("[data-station]")) return;
    drag.current = { x: e.clientX, y: e.clientY, left: viewport.current.scrollLeft, top: viewport.current.scrollTop };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const moveDrag = (e) => {
    if (!drag.current) return;
    viewport.current.scrollLeft = drag.current.left - e.clientX + drag.current.x;
    viewport.current.scrollTop = drag.current.top - e.clientY + drag.current.y;
  };
  return <section className="map-panel" aria-label="지하철 노선 관제도">
    <SectionTitle title="지하철 노선 관제도" right={selectedLine === "all" ? "전체 호선" : `${selectedLine}호선`} />
    <div className="map-controls">
      <div className="map-risk-legend">{(billingOnly ? ["billing_only"] : ["alert", "warn", "ok", "unknown", "analysis_pending", "pending"]).map((risk) => <RiskBadge key={risk} risk={risk} />)}</div>
      <div className="zoom-controls"><button onClick={() => setZoom((v) => Math.max(1, v - .5))} disabled={zoom <= 1} aria-label="노선도 축소">−</button><span>{Math.round(zoom * 100)}%</span><button onClick={() => setZoom((v) => Math.min(4, v + .5))} disabled={zoom >= 4} aria-label="노선도 확대">+</button><button onClick={fit}>전체 보기</button></div>
    </div>
    <div ref={viewport} className="metro-viewport" tabIndex={0} aria-label="노선도. 확대 후 스크롤하거나 드래그해 이동합니다." onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <svg className="metro-canvas" viewBox="0 0 2551 2123" style={{ width: `${zoom * 100}%` }} role="group" aria-label="서울 수도권 지하철 노선도와 관제 대상 역">
        <image href="/metro_map_rectangle.png" width="2551" height="2123" aria-hidden="true" />
        {mapped.map((station) => {
          const x = station.position.x * 25.51, y = station.position.y * 21.23;
          const label = `${station.name}, 계량기 ${station.meters.length}개, ${riskMeta[station.risk].label}. 선택하면 계량기 목록을 표시합니다.`;
          return <g key={station.id} transform={`translate(${x} ${y})`} className={`metro-node metro-node--${station.risk}`} data-station={station.id} role="button" tabIndex={0} aria-label={label} aria-pressed={selected === station.id} onClick={() => setSelected(station.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(station.id); } }}>
            <title>{label}</title><circle className="metro-node-hit" r="33" /><circle className="metro-node-dot" r="18" />
            <text y="7" textAnchor="middle" className="metro-node-symbol">{station.risk === "billing_only" ? "청" : ["pending", "analysis_pending"].includes(station.risk) ? "·" : station.risk === "unknown" ? "?" : station.risk === "alert" ? "!" : station.meters.length > 1 ? station.meters.length : ""}</text>
          </g>;
        })}
      </svg>
    </div>
    <p className="map-help">역 표식을 선택하면 호선·계량기별 상세로 이동할 수 있습니다. 지도 밖 대상은 아래 목록에서 확인하세요.</p>
    {active && <div className="map-selection" aria-live="polite">
      <div><strong>{active.name}</strong><button className="text-button" onClick={() => setSelected(null)} aria-label="역 선택 닫기">×</button></div>
      {active.meters.map((meter) => <a key={meter.id} href={detailHref(meter.id)}><span>{meter.lines.join("·")}호선 · {meter.displayName}<small>{meter.customerNo}</small></span><RiskBadge risk={meter.risk} /><span aria-hidden="true">→</span></a>)}
    </div>}
    {unplaced.length > 0 && <details className="map-unplaced"><summary>노선도 배치 대기 {unplaced.length}개 역</summary><p>계량기와 수집 자료는 등록되어 있습니다. 지도 위치가 연결되면 표식이 표시됩니다.</p><ul>{unplaced.map((station) => <li key={station.id}><button className="text-button" onClick={() => setSelected(station.id)}>{station.name} · {station.meters.length}개 계량기</button></li>)}</ul></details>}
    <p className="map-source">기본 노선도: 서울교통공사 · 표식은 현재 조회 권한과 필터를 기준으로 표시합니다.</p>
  </section>;
}
