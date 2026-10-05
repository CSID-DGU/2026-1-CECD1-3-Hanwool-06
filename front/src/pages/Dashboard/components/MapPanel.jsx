import { useRef, useState } from "react";
import { buildMapGroups, riskMeta } from "../dashboardData.js";
import { detailHref } from "../../Detail/data.js";
import { SectionTitle } from "../../Detail/ui.jsx";
import RiskBadge from "./RiskBadge.jsx";

export default function MapPanel({ stationMap, locations, billingOnly = false }) {
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
  return <section className="map-panel" aria-label="지하철 노선도">
    <SectionTitle as="h2" right={<div className="zoom-controls">
      <button type="button" onClick={() => setZoom((v) => Math.max(1, v - .5))} disabled={zoom <= 1} aria-label="노선도 축소">−</button>
      <span>{Math.round(zoom * 100)}%</span>
      <button type="button" onClick={() => setZoom((v) => Math.min(4, v + .5))} disabled={zoom >= 4} aria-label="노선도 확대">+</button>
      <button type="button" onClick={fit}>전체 보기</button>
    </div>}>노선도</SectionTitle>
    <div ref={viewport} className="metro-viewport" tabIndex={0} aria-label="노선도. 확대한 뒤 스크롤하거나 끌어서 옮길 수 있습니다." onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}>
      <svg className="metro-canvas" viewBox="0 0 2551 2123" style={{ width: `${zoom * 100}%` }} role="group" aria-label="서울 지하철 노선도와 계량기가 있는 역">
        <image href="/metro_map_rectangle.png" width="2551" height="2123" aria-hidden="true" />
        {mapped.map((station) => {
          const x = station.position.x * 25.51, y = station.position.y * 21.23;
          const label = `${station.name}, 계량기 ${station.meters.length}개, ${riskMeta[station.risk].label}`;
          return <g key={station.id} transform={`translate(${x} ${y})`} className={`metro-node metro-node--${station.risk}`} data-station={station.id} role="button" tabIndex={0} aria-label={label} aria-pressed={selected === station.id} onClick={() => setSelected(station.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setSelected(station.id); } }}>
            <title>{label}</title><circle className="metro-node-hit" r="33" /><circle className="metro-node-dot" r="18" />
            <text y="7" textAnchor="middle" className="metro-node-symbol">{station.risk === "billing_only" ? "청" : ["pending", "analysis_pending"].includes(station.risk) ? "·" : station.risk === "unknown" ? "?" : station.risk === "alert" ? "!" : station.meters.length > 1 ? station.meters.length : ""}</text>
          </g>;
        })}
      </svg>
    </div>
    <div className="map-legend">
      {(billingOnly ? ["billing_only"] : ["alert", "warn", "ok", "unknown", "analysis_pending", "pending"]).map((risk) => <RiskBadge key={risk} risk={risk} />)}
      <span>역을 누르면 그 역의 계량기가 아래에 나옵니다.</span>
    </div>
    {active && <div className="map-selection" aria-live="polite">
      <div><strong>{active.name}</strong><button type="button" className="text-button" onClick={() => setSelected(null)}>닫기</button></div>
      {active.meters.map((meter) => <a key={meter.id} href={detailHref(meter.id)}><span>{meter.lines.filter(Boolean).map((line) => `${line}호선`).join(", ")} {meter.displayName}<small>{meter.customerNo}</small></span><RiskBadge risk={meter.risk} /></a>)}
    </div>}
    {unplaced.length > 0 && <details className="map-unplaced"><summary>노선도에 위치가 없는 역 {unplaced.length}개</summary><ul>{unplaced.map((station) => <li key={station.id}><button type="button" className="text-button" onClick={() => setSelected(station.id)}>{station.name} ({station.meters.length}개)</button></li>)}</ul></details>}
    <p className="map-source">노선도 출처: 서울교통공사</p>
  </section>;
}
