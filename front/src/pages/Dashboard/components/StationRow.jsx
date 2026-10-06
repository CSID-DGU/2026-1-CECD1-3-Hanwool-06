import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";
import { detailHref, signedPct } from "../../Detail/data.js";

// byMeter: 한 역 안의 계량기를 늘어놓을 때. 역 이름 대신 계량기 이름과 고객번호로 구분한다.
export default function StationRow({ station, byMeter = false }) {
  return (
    <a href={detailHref(station.id)} className="station-row">
      <LineBadges lines={station.lines} />
      <span className="station-row-name">
        <strong>{byMeter ? station.displayName : station.name}</strong>
        <small>{byMeter ? `고객번호 ${station.customerNo}` : station.office}</small>
      </span>
      <span className="station-row-side">
        <RiskBadge risk={station.risk} />
        <b>{signedPct(station.delta)}</b>
      </span>
    </a>
  );
}
