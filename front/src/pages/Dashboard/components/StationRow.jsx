import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";
import { detailHref } from "../../Detail/data.js";

export default function StationRow({ station, compact }) {
  return (
    <a href={detailHref(station.id)} className={`station-row ${compact ? "is-compact" : ""}`}>
      <div>
        <div className="station-row-head">
          <strong>{station.name}</strong>
          <LineBadges lines={station.lines} />
        </div>
        <p>{station.displayName} · {station.office}</p>
      </div>
      <div className="station-row-side">
        <RiskBadge risk={station.risk} />
        <span>
          {station.delta == null ? "—" : `${station.delta > 0 ? "+" : ""}${station.delta}%`}
        </span>
      </div>
    </a>
  );
}
