import { lineMeta } from "../dashboardData.js";

export default function LineBadges({ lines }) {
  return (
    <span className="line-badges">
      {lines.map((line) => (
        <span className="line-badge" style={{ "--line-color": lineMeta[line].color }} key={line}>
          {line}
        </span>
      ))}
    </span>
  );
}
