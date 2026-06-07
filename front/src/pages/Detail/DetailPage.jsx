import { useState, useEffect } from "react";
import { STATIONS, YESTERDAY, kdate, ton, won } from "./mock";
import { Card, EmptyNote, InfoTooltip, LineBadge, Pending, RiskBadge, RiskGauge, Stat } from "./ui";
import LineChart from "./LineChart";
import Bill from "./Bill";
import smLogo from "./sm-logo.svg";

const DAILY_TIP =
  "일일 사용량·승하차는\n전날 데이터를 매일 오전 8시에 자동으로 가져옵니다.\n(8시 실패 시 9·10시 재시도)";

const RISK_TIP =
  "어제 실제 사용량이 예측값에서\n평소 변동폭의 몇 배나 벗어났는지로 판단합니다.\n\n· 정상: 2배 미만\n· 주의: 2배 ~ 3.5배\n· 경고: 3.5배 이상";

const COVERAGE = {
  full74: "일일·위험도 제공",
  cut3: "일일 승하차만 제공 · 사용량 수집 중단",
  billonly: "청구서·기본정보만",
};

// 영업사업소 목록 (선택 → 해당 사업소 역만 노출). 영업사업소는 호선별 필드라 역의 첫 호선 값으로 그룹핑.
const OFFICES = [...new Set(STATIONS.map((s) => s.lines[0].영업사업소))];

const SEV_TONE = { 정상: "ok", 주의: "warn", 경고: "alert" };

export default function DetailPage() {
  const [stationId, setStationId] = useState(0);
  const [lineIdx, setLineIdx] = useState(0);
  const station = STATIONS[stationId];
  const line = station.lines[Math.min(lineIdx, station.lines.length - 1)];

  // 청구서 실데이터(고객번호 키). 일일·승하차·위험도는 별도 소스라 아직 mock.
  const [billMap, setBillMap] = useState(null);
  useEffect(() => {
    if (window.__BILLS__) {
      setBillMap(window.__BILLS__); // 단일 HTML 데모: 인라인 데이터 사용(file:// 에서 fetch 불가)
      return;
    }
    fetch(`${import.meta.env.BASE_URL}bills.json`)
      .then((r) => (r.ok ? r.json() : null))
      .then(setBillMap)
      .catch(() => {});
  }, []);
  const realBill = billMap?.[line.고객번호];
  // 실데이터 있으면 청구서용 station/line 에만 실값 주입(없으면 mock 유지 → 데모 안 깨짐)
  const billStation = realBill ? { ...station, 주소: realBill.주소, 용도: realBill.용도 } : station;
  const billLine = realBill
    ? {
        ...line,
        bills: realBill.bills,
        전자수용가번호: realBill.전자수용가번호,
        전자납부번호: realBill.전자납부번호,
        계량기번호: realBill.계량기번호,
        구경: realBill.구경,
        가구수: realBill.가구수,
      }
    : line;

  const selectStation = (i) => {
    setStationId(i);
    setLineIdx(0);
  };

  const office = station.lines[0].영업사업소; // 선택된 역의 영업사업소
  const selectOffice = (o) => {
    const idx = STATIONS.findIndex((s) => s.lines[0].영업사업소 === o);
    if (idx >= 0) selectStation(idx); // 그 사업소의 첫 역으로
  };

  // 카드를 좌/우 칸에 직접 배치해 높이 차로 인한 빈틈을 최소화
  const headerEl = <StationHeader key="header" station={station} line={line} lineIdx={lineIdx} setLineIdx={setLineIdx} />;
  const basicEl = <BasicInfo key="basic" station={station} line={line} />;
  const dailyEl = <DailyPanel key="daily" usage={line.daily} ridership={line.ridership} tooltip={DAILY_TIP} />;
  const riskEl = line.risk ? (
    <RiskPanel key="risk" line={line} />
  ) : station.tier === "cut3" ? (
    <RiskUnavailable key="risk" />
  ) : null;

  let leftCol, rightCol;
  if (station.tier === "billonly") {
    // 청구서·기본정보만: 좌 헤더+일일(확인 불가) / 우 기본정보
    leftCol = [headerEl, dailyEl];
    rightCol = [basicEl];
  } else if (station.tier === "cut3") {
    // 위험도가 짧은 안내라, 좌에 헤더+기본정보+안내 / 우에 일일(긴 쪽) → 높이 균형, 기본정보 여백 해소
    leftCol = [headerEl, basicEl, riskEl];
    rightCol = [dailyEl];
  } else {
    // full74: 좌 헤더+일일 / 우 위험도(지표+5일 이력)+기본정보
    leftCol = [headerEl, dailyEl];
    rightCol = [riskEl, basicEl];
  }

  return (
    <div className="dt-root">
      <DetailTopBar />

      <div className="dt-demo">
        <span className="dt-demo-label">영업사업소</span>
        <select className="dt-demo-select" value={office} onChange={(e) => selectOffice(e.target.value)}>
          {OFFICES.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <span className="dt-demo-label">역</span>
        <select className="dt-demo-select" value={stationId} onChange={(e) => selectStation(Number(e.target.value))}>
          {STATIONS.map((s, i) => (s.lines[0].영업사업소 === office ? <option key={i} value={i}>{s.역명}</option> : null))}
        </select>
        <span className="dt-demo-note">데모 5역 · 추후 전체 역 연동</span>
      </div>

      <main className="dt-page">
        <div className="dt-cols">
          <div className="dt-col">{leftCol}</div>
          <div className="dt-col">{rightCol}</div>
        </div>

        <Card title="청구서" right={<InfoTooltip text={"청구서는 격월로 업데이트됩니다.\n해당 안내는 모든 역에 대해 표시됩니다."} />}>
          <Bill key={line.고객번호} station={billStation} line={billLine} />
        </Card>
      </main>
    </div>
  );
}

function DetailTopBar() {
  return (
    <header className="dt-topbar">
      <div className="dt-brand">
        <img src={smLogo} alt="서울교통공사" className="dt-brand-logo" />
        <span className="dt-brand-divider" />
        <span className="dt-brand-text">
          <strong>상수도 이상징후 관제</strong>
        </span>
      </div>
      <nav className="dt-topnav">
        <a href="#/">전체 현황</a>
        <a className="is-active" href="#/detail">역 상세</a>
      </nav>
    </header>
  );
}

function StationHeader({ station, line, lineIdx, setLineIdx }) {
  const multi = station.lines.length > 1;
  const risk = line.risk;
  return (
    <section className="dt-card dt-station">
      <div className="dt-station-info">
        <div className="dt-station-lines">
          {station.lines.map((l, i) =>
            multi ? (
              <button
                key={l.line}
                className={`dt-line dt-line--${l.line} dt-line-btn ${i === lineIdx ? "is-on" : "is-off"}`}
                onClick={() => setLineIdx(i)}
              >
                {l.line}호선
              </button>
            ) : (
              <LineBadge key={l.line} line={l.line} />
            )
          )}
          {multi ? <span className="dt-line-hint">← 호선 선택</span> : null}
        </div>
        <h1>{station.역명}</h1>
        <div className="dt-station-cov">
          <span className={`dt-cov dt-cov--${station.tier}`}>{COVERAGE[station.tier]}</span>
        </div>
      </div>
      {risk ? (
        <div className="dt-station-risk">
          <RiskGauge
            text={`${risk.pct > 0 ? "+" : ""}${risk.pct}%`}
            fillPct={Math.min(Math.abs(risk.pct) / 100, 1)}
            level={risk.severity}
            label="예측대비"
          />
          <RiskBadge level={risk.severity} size="lg" />
        </div>
      ) : null}
    </section>
  );
}

function BasicInfo({ station, line }) {
  const rows = [
    ["고객번호", line.고객번호],
    ["사용자명", station.사용자명],
    ["위치", station.주소],
    ["호선", `${line.line}호선`],
    ["영업사업소", line.영업사업소],
    ["담당자 연락처", <Pending key="c">데이터 예정</Pending>],
    ["아리수 담당자 연락처", <Pending key="a">데이터 예정</Pending>],
  ];
  return (
    <Card title="기본정보" className="dt-fill-center">
      <table className="dt-kv">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th>{k}</th>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function RiskPanel({ line }) {
  const rk = line.risk;
  const alert = rk.severity !== "정상";
  const tone = rk.severity === "경고" ? "alert" : rk.severity === "주의" ? "warn" : null;
  const msg = !alert
    ? "예측값과 실측이 기준선 안에서 일치합니다."
    : `예측보다 ${ton(Math.abs(rk.error))}톤(${rk.pct > 0 ? "+" : ""}${rk.pct}%) ${
        rk.방향 === "과다" ? "많이" : "적게"
      } 사용 · 기준선을 ${rk.severity === "경고" ? "크게 " : ""}벗어났습니다.`;
  return (
    <Card
      title="위험도"
      right={
        <>
          <span className="dt-risk-date">{kdate(rk.기준일)} 기준</span>
          <InfoTooltip text={RISK_TIP} />
        </>
      }
    >
      <div className="dt-risk">
        <div className="dt-risk-head">
          <RiskBadge level={rk.severity} size="lg" />
          <span className="dt-risk-msg">{msg}</span>
        </div>
        <div className="dt-risk-stats">
          <Stat label="예측값" value={`${ton(rk.predicted)} 톤`} />
          <Stat label="실제값" value={`${ton(rk.actual)} 톤`} />
          <Stat label="예측오차" value={`${rk.error > 0 ? "+" : ""}${ton(rk.error)} 톤`} tone={tone} />
          <Stat label="예측 대비" value={`${rk.pct > 0 ? "+" : ""}${rk.pct}%`} tone={tone} />
        </div>
        <div className="dt-risk-hist">
          <table className="dt-risk-history">
            <thead>
              <tr>
                <th>날짜</th>
                <th>심각도</th>
                <th>예측 대비</th>
              </tr>
            </thead>
            <tbody>
              {[...rk.history].reverse().map((h) => (
                <tr key={h.date}>
                  <td>{kdate(h.date)}</td>
                  <td>
                    <span className={`dt-sevdot dt-sevdot--${SEV_TONE[h.severity]}`} />
                    {h.severity}
                  </td>
                  <td className={h.severity !== "정상" ? `dt-hist-pct--${SEV_TONE[h.severity]}` : ""}>
                    {h.pct > 0 ? "+" : ""}
                    {h.pct}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

// cut3(사용량 수집 중단) 역: 위험도 자리에 산출 불가 안내
function RiskUnavailable() {
  return (
    <Card title="위험도" right={<span className="dt-risk-date">{kdate(YESTERDAY)} 기준</span>}>
      <EmptyNote>
        {kdate(YESTERDAY)} 일일 사용량이 수집되지 않아
        <br />
        <strong>위험도 산출이 불가합니다.</strong>
      </EmptyNote>
    </Card>
  );
}

// 일일 사용량 + 승하차를 한 카드에. 날짜 하나로 둘 동시 조회.
function DailyPanel({ usage, ridership, tooltip }) {
  const [date, setDate] = useState(YESTERDAY);
  const series = [usage, ridership].filter(Boolean);

  if (series.length === 0) {
    return (
      <Card title="일일 사용량 · 승하차" right={<InfoTooltip text={tooltip} />}>
        <EmptyNote>
          일일데이터를 수집하지 않는 역입니다.
          <br />
          <strong>일일 사용량·승하차 확인 불가</strong>
        </EmptyNote>
      </Card>
    );
  }

  const minDate = series.map((s) => s[0].date).sort()[0];
  const maxDate = series
    .map((s) => s[s.length - 1].date)
    .sort()
    .slice(-1)[0];

  return (
    <Card title="일일 사용량 · 승하차" right={<InfoTooltip text={tooltip} />}>
      <label className="dt-field dt-daily-date">
        날짜
        <input type="date" value={date} min={minDate} max={maxDate} onChange={(e) => setDate(e.target.value)} />
      </label>
      <DailySub label="일일 사용량" unit="톤" color="#283891" series={usage} date={date} fmt={ton} />
      <DailySub label="일일 승하차" unit="명" color="#0e7c7b" series={ridership} date={date} fmt={won} />
    </Card>
  );
}

function DailySub({ label, unit, color, series, date, fmt }) {
  if (!series) {
    return (
      <div className="dt-daily-sub">
        <div className="dt-daily-sub-head">
          <span className="dt-daily-sub-label">{label}</span>
          <span className="dt-daily-none">수집 안 함</span>
        </div>
      </div>
    );
  }
  const maxDate = series[series.length - 1].date;
  const point = series.find((p) => p.date === date);
  const cutoff = date <= maxDate ? date : maxDate;
  const recent = series.filter((p) => p.date <= cutoff).slice(-7); // 선택일로부터 최근 1주

  return (
    <div className="dt-daily-sub">
      <div className="dt-daily-sub-head">
        <span className="dt-daily-sub-label">{label}</span>
        <span className="dt-daily-sub-val">
          {point ? (
            <>
              <strong>{fmt(point.value)}</strong> {unit}
            </>
          ) : (
            <span className="dt-daily-none">해당 날짜 없음</span>
          )}
        </span>
      </div>
      {!point ? <p className="dt-daily-hint">수집이 {maxDate} 까지만 들어와 있어요.</p> : null}
      <LineChart
        series={[{ color, values: recent.map((p) => p.value), fill: true }]}
        xLabels={recent.map((p) => p.date.slice(5))}
        height={200}
        labelEvery={1}
        showValues
        formatValue={fmt}
        formatY={fmt}
        yUnit={unit}
        xUnit="월/일"
      />
    </div>
  );
}
