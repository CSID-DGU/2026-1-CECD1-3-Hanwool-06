export function statisticsPeriod(now = new Date()) {
  const end = new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  return { start: `${end.slice(0, 4)}-01-01`, end };
}
