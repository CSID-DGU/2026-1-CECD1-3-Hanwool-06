export default function SummaryTile({ label, value, sub, tone }) {
  return (
    <article className={`summary-tile ${tone ? `summary-${tone}` : ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{sub}</small>
    </article>
  );
}
