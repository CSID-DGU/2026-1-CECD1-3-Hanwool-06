import LineBadges from "./LineBadges.jsx";
import RiskBadge from "./RiskBadge.jsx";

export default function StationRow({ station, compact }) {
  return (
    <article className={`station-row ${compact ? "is-compact" : ""}`}>
      <div>
        <div className="station-row-head">
          <strong>{station.name}</strong>
          <LineBadges lines={station.lines} />
        </div>
        <p>{station.office}</p>
      </div>
      <div className="station-row-side">
        <RiskBadge risk={station.risk} />
        <span>
          {station.delta > 0 ? "+" : ""}
          {station.delta}%
        </span>
      </div>
    </article>
  );
}
