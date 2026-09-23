// Archived unused frontend exports; not imported by the application.

/* Source: front/src/pages/Dashboard/utils.js — unreferenced export; formatNumber remains live */
export function averageDelta(items) {
  const values = items.map((station) => station.delta).filter(Number.isFinite);
  return values.length ? (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1) : "—";
}

/* Source: front/src/pages/Detail/ui.jsx — unreferenced LineBadge and Pending exports */
export function LineBadge({ line }) {
  return <span className={`dt-line dt-line--${line}`}>{line}호선</span>;
}

// 데이터 아직 없음 표시 (placeholder + TODO)
export function Pending({ children = "데이터 예정" }) {
  return <span className="dt-pending">{children}</span>;
}
