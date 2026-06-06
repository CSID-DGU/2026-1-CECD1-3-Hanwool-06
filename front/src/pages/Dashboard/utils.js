export function averageDelta(items) {
  if (items.length === 0) return "0.0";
  const sum = items.reduce((total, station) => total + station.delta, 0);
  return (sum / items.length).toFixed(1);
}

export function formatNumber(value) {
  return new Intl.NumberFormat("ko-KR").format(value);
}
