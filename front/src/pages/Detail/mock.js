// 디테일 화면 목업 데이터.
// 실데이터는 아직 없음 → 그럴듯하게 생성. 단, 위험도 지표는 back/ml/lightgbm 산출물
// (예측/실제/예측오차/deviation_score/임계값/방향)과 같은 의미로 구성.
// 호선마다 고객번호·계량기·청구·일일이 달라서 호선별 데이터를 따로 둔다.
// tier: full74(일일+위험도) / cut3(승하차 live·사용량 끊김, 위험도 N/A) / billonly(청구·기본정보만)

// 이상탐지 임계값 (lightgbm valid |deviation_score| 의 q95/q99 에 해당, 목업값)
const THRESH = { warn: 2.0, alert: 3.5 };

// ── 결정적 난수 ──────────────────────────────────────────────────
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
function seedFromStr(str) {
  let h = 2166136261 >>> 0;
  for (const c of str) {
    h ^= c.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// ── 날짜 (어제 = 2026-06-07) ──────────────────────────────────────
export const TODAY = "2026-06-08";
export const YESTERDAY = "2026-06-07";
const KDOW = ["일", "월", "화", "수", "목", "금", "토"];
function parse(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function iso(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}
function addDays(date, n) {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}
export function kdate(isoStr) {
  const d = parse(isoStr);
  return `${d.getMonth() + 1}/${d.getDate()} (${KDOW[d.getDay()]})`;
}
export const won = (n) => Math.round(n).toLocaleString("ko-KR");
export const ton = (n) => n.toLocaleString("ko-KR", { maximumFractionDigits: 1 });

function median(arr) {
  const s = [...arr].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

// ── 일일 시계열 ──────────────────────────────────────────────────
function dailySeries({ seed, base, weekendDrop, endIso, days, integer }) {
  const r = rng(seed);
  const end = parse(endIso);
  const round = (v) => (integer ? Math.round(v) : Math.round(v * 10) / 10);
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = addDays(end, -i);
    const dow = d.getDay();
    const wk = dow === 0 || dow === 6 ? 1 - weekendDrop : 1;
    out.push({ date: iso(d), value: round(base * wk * (0.82 + r() * 0.34)) });
  }
  return out;
}

// 위험도: lightgbm 방식과 같은 의미의 지표 산출.
// 어제 실측을 targetDev 만큼 벗어나게 만들어 예측오차·deviation_score 가 일관되게 나오도록.
function riskFromSeries(daily, targetDev) {
  const vals = daily.map((d) => d.value);
  const med = median(vals);
  const mad = median(vals.map((v) => Math.abs(v - med))) || 1;
  const actual = Math.round((med + targetDev * 1.4826 * mad) * 10) / 10;
  daily[daily.length - 1] = { ...daily[daily.length - 1], value: actual }; // 어제 = 이상 반영
  const predicted = Math.round(med * 10) / 10;
  const error = Math.round((actual - predicted) * 10) / 10;
  const dev = Math.abs(Math.round((error / (1.4826 * mad)) * 100) / 100);
  const severity = dev >= THRESH.alert ? "경고" : dev >= THRESH.warn ? "주의" : "정상";
  // 최근 5일 위험도 이력 (일별 심각도 + 예측 대비 %)
  const history = daily.slice(-5).map((d) => {
    const err = d.value - predicted;
    const dv = Math.abs(err / (1.4826 * mad));
    return {
      date: d.date,
      severity: dv >= THRESH.alert ? "경고" : dv >= THRESH.warn ? "주의" : "정상",
      pct: Math.round((err / predicted) * 100),
    };
  });

  return {
    predicted,
    actual,
    error,
    dev,
    pct: Math.round((error / predicted) * 100), // 예측 대비 편차 %
    방향: error >= 0 ? "과다" : "과소",
    severity,
    warnT: THRESH.warn,
    alertT: THRESH.alert,
    기준일: YESTERDAY,
    history,
  };
}

// ── 청구서(격월: 홀수월) + 청구서 부가필드 ───────────────────────
function makeBilling({ seed, baseUsage, 고객번호 }) {
  const r = rng(seed + 99);
  const list = [];
  let meter = 100000 + Math.floor(r() * 40000);
  for (let year = 2017; year <= 2026; year++) {
    for (const month of [1, 3, 5, 7, 9, 11]) {
      if (year === 2026 && month > 5) break;
      // 계절성: 여름(납기 7·9=5~8월 사용) 높고 겨울(납기 1·3) 낮게
      const seasonF = { 1: 0.85, 3: 0.82, 5: 1.0, 7: 1.18, 9: 1.24, 11: 1.02 }[month];
      const q = Math.round(baseUsage * seasonF * (0.86 + r() * 0.28));
      const prevMeter = meter;
      meter += q;
      const 상수도_사용료 = q * 900;
      const 상수도_기본료 = 2000;
      const 하수도_사용료 = q * 620;
      const 물이용부담금 = q * 170;
      list.push({
        ym: `${year}-${String(month).padStart(2, "0")}`,
        year,
        month,
        납기일: `${year}-${String(month).padStart(2, "0")}-30`,
        사용량: q,
        납부금액: 상수도_사용료 + 상수도_기본료 + 하수도_사용료 + 물이용부담금,
        상수도_기본료,
        상수도_사용료,
        하수도_사용료,
        물이용부담금,
        전월지침: prevMeter,
        당월지침: meter,
        periodStart: iso(new Date(year, month - 3, 21)),
        periodEnd: iso(new Date(year, month - 2, 20)),
        정기검침일: 21,
      });
    }
  }
  const bills = list.map((b, i) => ({
    ...b,
    전납기사용량: i > 0 ? list[i - 1].사용량 : b.사용량,
    전년동기사용량: i >= 6 ? list[i - 6].사용량 : b.사용량,
  }));
  const r2 = rng(seed + 555);
  return {
    bills,
    전자수용가번호: `112301-${고객번호}`,
    전자납부번호: `1123001026-${Math.floor(r2() * 900000000) + 100000000}`,
    계량기번호: String(Math.floor(r2() * 9000000) + 1000000),
    구경: `${[13, 20, 25, 40, 50][Math.floor(r2() * 5)]}mm`,
    가구수: 0,
  };
}

// ── 데모 역 (호선별 라인 포함) ───────────────────────────────────
const RAW = [
  {
    역명: "신당역",
    주소: "서울시 중구 퇴계로 374",
    용도: "시민용",
    tier: "full74",
    lines: [
      { line: 2, 고객번호: "000262188", 영업사업소: "동대문영업사업소", base: 26, rider: 88000, targetDev: 3.9 },
      { line: 6, 고객번호: "035470112", 영업사업소: "동대문영업사업소", base: 21, rider: 47000, targetDev: 0.5 },
    ],
  },
  {
    역명: "약수역",
    주소: "서울시 중구 다산로 지하 134",
    용도: "시민용",
    tier: "full74",
    lines: [
      { line: 3, 고객번호: "001020304", 영업사업소: "경복궁영업사업소", base: 19, rider: 41000, targetDev: 2.6 },
      { line: 6, 고객번호: "035471890", 영업사업소: "경복궁영업사업소", base: 16, rider: 33000, targetDev: 0.7 },
    ],
  },
  {
    역명: "대치역",
    주소: "서울시 강남구 남부순환로 지하 2916",
    용도: "시민용",
    tier: "full74",
    lines: [{ line: 3, 고객번호: "024655212", 영업사업소: "도곡영업사업소", base: 24, rider: 36000, targetDev: 0.4 }],
  },
  {
    역명: "미아역",
    주소: "서울시 강북구 도봉로 지하 145",
    용도: "시민용",
    tier: "cut3",
    dailyEndIso: "2026-05-25", // 사용량 stream 끊김 (승하차는 live)
    lines: [{ line: 4, 고객번호: "002956726", 영업사업소: "상계영업사업소", base: 17, rider: 33000 }],
  },
  {
    역명: "사당역",
    주소: "서울시 동작구 동작대로 지하 3",
    용도: "시민용",
    tier: "billonly",
    lines: [
      { line: 2, 고객번호: "030771188", 영업사업소: "동작영업사업소", base: 28, rider: 0 },
      { line: 4, 고객번호: "030779042", 영업사업소: "동작영업사업소", base: 25, rider: 0 },
    ],
  },
];

const RANK = { 정상: 0, 주의: 1, 경고: 2 };

export const STATIONS = RAW.map((st) => {
  const hasDaily = st.tier === "full74" || st.tier === "cut3";
  const dailyEnd = st.dailyEndIso || YESTERDAY;
  const lines = st.lines.map((ln) => {
    const seed = seedFromStr(st.역명 + ln.고객번호);
    const daily = hasDaily
      ? dailySeries({ seed, base: ln.base, weekendDrop: 0.28, endIso: dailyEnd, days: 180 })
      : null;
    // 승하차는 cut3 도 매일 들어옴 → 항상 어제까지
    const ridership = hasDaily
      ? dailySeries({ seed: seed + 7, base: ln.rider, weekendDrop: 0.42, endIso: YESTERDAY, days: 180, integer: true })
      : null;
    const risk = st.tier === "full74" ? riskFromSeries(daily, ln.targetDev) : null;
    return {
      line: ln.line,
      고객번호: ln.고객번호,
      영업사업소: ln.영업사업소,
      daily,
      ridership,
      risk,
      ...makeBilling({ seed, baseUsage: ln.base * 30, 고객번호: ln.고객번호 }),
    };
  });
  const severities = lines.map((l) => l.risk?.severity).filter(Boolean);
  const risk = severities.sort((a, b) => RANK[b] - RANK[a])[0] || null;
  return { ...st, 사용자명: st.역명, lines, risk, dailyEndIso: dailyEnd };
});
