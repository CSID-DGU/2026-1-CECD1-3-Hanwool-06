import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";
import { detailHref, signedPct } from "../../Detail/data.js";

export default function StationRow({ station }) {
  return (
    <a href={detailHref(station.id)} className="station-row">
      <LineBadges lines={station.lines} />
      <span className="station-row-name">
        <strong>{station.name}</strong>
        <small>{station.office}</small>
      </span>
      <span className="station-row-side">
        <RiskBadge risk={station.risk} />
        <b>{signedPct(station.delta)}</b>
      </span>
    </a>
  );
}
