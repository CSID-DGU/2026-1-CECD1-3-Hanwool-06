// 디테일 화면 데이터 빌더.
// 실데이터(고객번호 키) 4종을 합쳐 STATIONS(물리역 단위, 호선별 lines) 로 만든다.
//   bills.json    : 청구서·기본정보(역명/주소/영업사업소/용도/계량기…)        [368]
//   stations.json : 정규화 역명 + 호선 + 영업사업소                            [368]
//   daily.json    : 일사용량·승하차 시계열 {usage:[],ridership:[]}            [~80]
//   risk.json     : 위험도(예측/실제/잔차/z/심각도/방향) 라이브 이력           [74]
// 조인은 전부 고객번호. 표시 역명은 호선 접미를 뗀 base(예: 신당역2→신당역, 호선은 배지).

const KDOW = ["일", "월", "화", "수", "목", "금", "토"];
function parse(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
export function kdate(iso) {
  const d = parse(iso);
  return `${d.getMonth() + 1}/${d.getDate()} (${KDOW[d.getDay()]})`;
}
export const won = (n) => Math.round(n).toLocaleString("ko-KR");
export const ton = (n) => n.toLocaleString("ko-KR", { maximumFractionDigits: 1 });

const baseName = (name) => String(name || "").replace(/\d+$/, ""); // 신당역2→신당역, 종로3가역3→종로3가역
const pctOf = (residual, pred) => (pred > 0 ? Math.round((residual / pred) * 100) : 0);

// risk.json 의 라이브 이력 배열 → 위험도 패널이 쓰는 객체. 데이터오류행(err)은 제외.
function buildRisk(arr) {
  const clean = (arr || []).filter((r) => !r.err);
  if (!clean.length) return null;
  const last = clean[clean.length - 1];
  return {
    predicted: last.pred,
    actual: last.actual,
    error: last.residual,
    pct: pctOf(last.residual, last.pred),
    방향: last.dir || (last.residual >= 0 ? "과다" : "과소"),
    severity: last.severity,
    기준일: last.date,
    history: clean.slice(-5).map((r) => ({ date: r.date, severity: r.severity, pct: pctOf(r.residual, r.pred) })),
  };
}

// 고객번호 1개 = 한 호선의 한 계약 → line 레코드
function lineRecord(cust, bills, meta, daily) {
  const b = bills[cust] || {};
  const m = meta[cust] || {};
  const d = daily[cust] || {};
  const usage = d.usage && d.usage.length ? d.usage : null;
  const ridership = d.ridership && d.ridership.length ? d.ridership : null;
  const risk = buildRisk(d.__risk);
  return {
    line: m.호선 ?? null,
    고객번호: cust,
    영업사업소: m.영업사업소 || b.사업소명 || "—",
    base: baseName(m.역명 || b.역명),
    주소: b.주소,
    용도: b.용도,
    사용자명: baseName(m.역명 || b.역명),
    bills: b.bills || [],
    전자수용가번호: b.전자수용가번호,
    전자납부번호: b.전자납부번호,
    계량기번호: b.계량기번호,
    구경: b.구경,
    가구수: b.가구수,
    daily: usage,
    ridership,
    risk,
    _score: (risk ? 4 : 0) + (usage ? 2 : 0) + (ridership ? 1 : 0), // 데이터 풍부도(대표 선택용)
  };
}

export function buildStations(bills, meta, daily, risk) {
  // risk 를 daily 에 합쳐 lineRecord 가 한 번에 보게
  const dailyR = {};
  for (const cust of new Set([...Object.keys(daily), ...Object.keys(risk)])) {
    dailyR[cust] = { ...(daily[cust] || {}), __risk: risk[cust] };
  }

  const recs = Object.keys(bills).map((cust) => lineRecord(cust, bills, meta, dailyR));

  const byBase = {};
  for (const r of recs) (byBase[r.base] ||= []).push(r);

  const stations = Object.entries(byBase).map(([base, group]) => {
    // 호선별 대표 1개(데이터 풍부한 고객번호). 복수계약은 추후 케이스별 정리.
    const byLine = {};
    for (const r of group) {
      const L = r.line ?? 0;
      if (!byLine[L] || r._score > byLine[L]._score) byLine[L] = r;
    }
    const lines = Object.values(byLine).sort((a, b) => (a.line ?? 0) - (b.line ?? 0));
    const rep = [...group].sort((a, b) => b._score - a._score)[0];
    const hasRisk = lines.some((l) => l.risk);
    const hasDaily = lines.some((l) => l.daily || l.ridership);
    return {
      역명: base,
      사용자명: base,
      주소: rep.주소,
      용도: rep.용도,
      tier: hasRisk ? "full74" : hasDaily ? "cut3" : "billonly",
      lines,
    };
  });

  stations.sort((a, b) => a.역명.localeCompare(b.역명, "ko"));
  return stations;
}

// 시계열들의 최신 날짜(데이터 가용 마지막 날) — 일일 패널 기본 날짜·기준일용
export function latestDate(stations) {
  let max = "";
  for (const s of stations)
    for (const l of s.lines)
      for (const series of [l.daily, l.ridership])
        if (series && series.length) {
          const d = series[series.length - 1].date;
          if (d > max) max = d;
        }
  return max || "2026-06-13";
}
