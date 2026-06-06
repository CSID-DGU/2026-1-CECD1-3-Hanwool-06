import { riskMeta } from "../data.js";

export default function RiskBadge({ risk }) {
  return <span className={`risk-badge risk-${riskMeta[risk].tone}`}>{riskMeta[risk].label}</span>;
}
