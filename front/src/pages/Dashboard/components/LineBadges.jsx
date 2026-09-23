import { lineMeta } from "../dashboardData.js";

export default function LineBadges({ lines }) {
  return (
    <span className="line-badges">
      {lines.map((line) => (
        <span className="line-badge" style={{ "--line-color": lineMeta[line]?.color || "#667085" }} key={line} aria-label={`${line}호선`}>
          {line}
        </span>
      ))}
    </span>
  );
}
