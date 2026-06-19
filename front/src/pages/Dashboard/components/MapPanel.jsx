import { useRef, useState } from "react";
import RiskBadge from "./RiskBadge.jsx";
import SectionTitle from "./SectionTitle.jsx";

// 역 위치(이미지 기준 %). #cal 보정 모드로 클릭 측정한 값(75역).
const STATION_POS = {
  "000013307": { x: 53.5, y: 25.2 }, // 동대문역
  "035270286": { x: 58.3, y: 25.2 }, // 동묘앞역
  "000252579": { x: 41, y: 30.7 }, // 시청역
  "006240178": { x: 53.5, y: 28.1 }, // 동대문역사문화공원역
  "022277395": { x: 65.9, y: 69 }, // 삼성역
  "035438586": { x: 43.6, y: 77.1 }, // 서울대입구역
  "000390183": { x: 41, y: 31.1 }, // 시청역
  "000262188": { x: 58.3, y: 30.9 }, // 신당역
  "023011906": { x: 32.5, y: 66.8 }, // 신도림역
  "020681438": { x: 23.5, y: 57 }, // 신정네거리역
  "035833138": { x: 64.3, y: 35.8 }, // 왕십리역
  "000315938": { x: 45.9, y: 29.2 }, // 을지로3가역
  "024635854": { x: 33.9, y: 37.5 }, // 이대역
  "024583082": { x: 69.3, y: 61.7 }, // 잠실새내역
  "000017682": { x: 45.2, y: 20.6 }, // 경복궁역
  "036081434": { x: 77.5, y: 73.6 }, // 경찰병원역
  "024691164": { x: 56.2, y: 65.2 }, // 고속터미널역
  "022652784": { x: 69, y: 80.4 }, // 대청역
  "024655212": { x: 65.4, y: 80.4 }, // 대치역
  "000266613": { x: 53.5, y: 39.6 }, // 동대입구역
  "000214696": { x: 45.9, y: 22.4 }, // 안국역
  "000362246": { x: 56.2, y: 43.8 }, // 약수역
  "000316239": { x: 45.8, y: 28.5 }, // 을지로3가역
  "000137601": { x: 45.9, y: 24.3 }, // 종로3가역
  "022357530": { x: 67, y: 80.4 }, // 학여울역
  "001703793": { x: 60.1, y: 16.8 }, // 길음역
  "006240196": { x: 53.5, y: 28.1 }, // 동대문역사문화공원역
  "000399808": { x: 48.8, y: 37.4 }, // 명동역
  "002296399": { x: 77.5, y: 9.8 }, // 상계역
  "001506473": { x: 57.4, y: 19.9 }, // 성신여대입구역
  "021205524": { x: 48.8, y: 52 }, // 신용산역
  "001895650": { x: 66.8, y: 9.7 }, // 쌍문역
  "024630785": { x: 48.8, y: 71 }, // 총신대입구역
  "000248906": { x: 54.9, y: 22.9 }, // 혜화역
  "024666597": { x: 78.3, y: 54.2 }, // 강동역
  "041559288": { x: 86.5, y: 44.5 }, // 강일역
  "001159721": { x: 75.9, y: 35.8 }, // 군자역
  "024167685": { x: 81.3, y: 50.6 }, // 굽은다리역
  "030632270": { x: 79.9, y: 52.3 }, // 길동역
  "027579083": { x: 22.8, y: 52.2 }, // 까치산역
  "004769658": { x: 72.2, y: 35.8 }, // 답십리역
  "006205316": { x: 53.6, y: 29.7 }, // 동대문역사문화공원역
  "026547747": { x: 38.6, y: 54.2 }, // 마포역
  "023654087": { x: 78.3, y: 68.4 }, // 방이역
  "021091226": { x: 14.6, y: 29.3 }, // 방화역
  "000978203": { x: 78.3, y: 39.1 }, // 아차산역
  "029689088": { x: 30.1, y: 61 }, // 영등포구청역
  "000451150": { x: 65.7, y: 36 }, // 왕십리역
  "000342971": { x: 49.9, y: 28.1 }, // 을지로4가역
  "004779648": { x: 74.1, y: 36 }, // 장한평역
  "006390427": { x: 61.6, y: 35.8 }, // 행당역
  "032082173": { x: 50.7, y: 49.7 }, // 녹사평역
  "031928061": { x: 67.5, y: 17.7 }, // 돌곶이역
  "032121991": { x: 53.9, y: 45.5 }, // 버티고개역
  "032086710": { x: 59.9, y: 22.4 }, // 보문역
  "032072396": { x: 48.7, y: 50.2 }, // 삼각지역
  "031914399": { x: 69, y: 17.9 }, // 석계역
  "032144824": { x: 55.9, y: 43.1 }, // 약수역
  "032864224": { x: 25.7, y: 39.6 }, // 월드컵경기장역
  "031921584": { x: 36.8, y: 17 }, // 응암역
  "032125776": { x: 51.6, y: 48.7 }, // 이태원역
  "032013846": { x: 28.7, y: 26.9 }, // 증산역
  "032026818": { x: 58.8, y: 23.6 }, // 창신역
  "006743375": { x: 70.4, y: 48.2 }, // 건대입구역
  "006735213": { x: 75.5, y: 19.8 }, // 먹골역
  "006499412": { x: 75.5, y: 29.7 }, // 사가정역
  "000828353": { x: 75.4, y: 24.3 }, // 상봉역
  "031834359": { x: 37.2, y: 70.6 }, // 신풍역
  "006742276": { x: 74.1, y: 44 }, // 어린이대공원역
  "031829466": { x: 24.5, y: 67.7 }, // 온수역
  "030154123": { x: 76.8, y: 77.1 }, // 문정역
  "030179738": { x: 78.7, y: 79.3 }, // 복정역
  "023726393": { x: 73.8, y: 64.7 }, // 석촌역
  "031750442": { x: 79.7, y: 47.6 }, // 암사역
  "042547672": { x: 81, y: 45.9 }, // 암사역사공원역
};

// 지도에서 역을 클릭해 좌표를 측정하는 1회성 보정 도구 (#cal 로 진입)
function Calibrator({ stations }) {
  const [idx, setIdx] = useState(0);
  const [pos, setPos] = useState({});
  const wrapRef = useRef(null);
  const cur = stations[idx];

  const place = (e) => {
    if (!cur || !wrapRef.current) return;
    const r = wrapRef.current.getBoundingClientRect();
    const x = +(((e.clientX - r.left) / r.width) * 100).toFixed(1);
    const y = +(((e.clientY - r.top) / r.height) * 100).toFixed(1);
    setPos((p) => ({ ...p, [cur.id]: { x, y } }));
    setIdx((i) => i + 1);
  };

  const out = stations
    .filter((s) => pos[s.id])
    .map((s) => `  "${s.id}": { x: ${pos[s.id].x}, y: ${pos[s.id].y} }, // ${s.name}`)
    .join("\n");

  return (
    <section className="map-panel" aria-label="위치 보정">
      <SectionTitle title="위치 보정 모드 (#cal)" right={`${Object.keys(pos).length} / ${stations.length}`} />
      <div className="metro-map">
        <div className="map-image-wrap" ref={wrapRef} onClick={place} style={{ cursor: "crosshair" }}>
          <img className="metro-map-img" src="/metro_map_rectangle.png" alt="" />
          {stations.filter((s) => pos[s.id]).map((s) => (
            <div key={s.id} className="map-pin map-pin--warn" style={{ left: `${pos[s.id].x}%`, top: `${pos[s.id].y}%` }}>
              <span className="map-pin-dot" />
            </div>
          ))}
        </div>
      </div>
      <div className="cal-bar">
        <strong>
          {cur ? `클릭하세요 → ${cur.name} (${cur.lines.join("·")}호선)` : "✅ 완료! 아래 좌표를 복사해 전달하세요."}
        </strong>
        <div className="cal-btns">
          <button type="button" onClick={() => setIdx((i) => Math.max(0, i - 1))}>← 이전</button>
          <button type="button" onClick={() => setIdx((i) => i + 1)} disabled={!cur}>건너뛰기 →</button>
          <button type="button" onClick={() => navigator.clipboard?.writeText(out)}>좌표 복사</button>
        </div>
        <textarea className="cal-out" readOnly value={out} />
      </div>
    </section>
  );
}

export default function MapPanel({ selectedLine, stationMap, allStations = [] }) {
  if (typeof window !== "undefined" && window.location.hash.includes("cal")) {
    return <Calibrator stations={allStations} />;
  }

  const pins = [...stationMap.values()].filter((s) => s.risk !== "ok" && STATION_POS[s.id]);

  return (
    <section className="map-panel" aria-label="지하철 노선 관제도">
      <SectionTitle title="서울 지하철 노선 관제도" right={selectedLine === "all" ? "전체 호선" : `${selectedLine}호선`} />
      <div className="metro-map">
        <div className="map-legend" aria-label="위험도 범례">
          <RiskBadge risk="alert" />
          <RiskBadge risk="warn" />
        </div>
        <div className="map-image-wrap">
          <img className="metro-map-img" src="/metro_map_rectangle.png" alt="서울 지하철 노선도" />
          {pins.map((s) => {
            const p = STATION_POS[s.id];
            return (
              <div
                key={s.id}
                className={`map-pin map-pin--hoverable map-pin--${s.risk}`}
                style={{ left: `${p.x}%`, top: `${p.y}%` }}
              >
                <span className="map-pin-dot" />
                <span className="map-pin-label">{s.name}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
