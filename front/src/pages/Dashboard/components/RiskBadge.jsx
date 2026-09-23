import { riskMeta } from "../dashboardData.js";

export default function RiskBadge({ risk }) {
  const meta = riskMeta[risk] || riskMeta.unknown;
  return <span className={`risk-badge risk-${meta.tone}`}>{meta.label}</span>;
}
