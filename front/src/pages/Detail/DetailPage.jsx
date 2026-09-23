import { useState, useEffect, useMemo, useRef } from "react";
import { buildStations, latestDate, kdate, ton, won, detailHref } from "./data.js";
import { Card, EmptyNote, InfoTooltip, RiskBadge, RiskGauge, Stat } from "./ui";
import LineChart from "./LineChart";
import Bill from "./Bill";
import { exportUrl } from "../../api.js";
import FileLink from "../../components/FileLink.jsx";
import CollectionPanel from "../../components/CollectionPanel.jsx";

const DAILY_TIP = "표시된 기준일의 수집 자료입니다.\n사용량과 승하차의 마지막 수집일이 다를 수 있습니다.";
const RISK_TIP = "역별 예측오차를 평소 변동폭과 비교한 위험도입니다.\n수집되지 않았거나 오래된 자료는 정상으로 간주하지 않습니다.";
const SEV_TONE = { 정상: "ok", 주의: "warn", 경고: "alert" };

export default function DetailPage({ data, hash, collection }) {
  const stations = useMemo(() => buildStations(data.bills, data.stations, data.daily, data.risk, data.meters), [data]);
  const latest = useMemo(() => latestDate(stations), [stations]);
  const meterId = new URLSearchParams(hash.split("?")[1] || "").get("meter");
  const requestedStation = stations.find((s) => s.lines.some((l) => l.meterId === meterId));
  const station = requestedStation || (meterId ? null : stations.find((s) => s.lines.some((l) => l.risk)) || stations[0]);
  if (!station) return <main className="management-page"><h1>{meterId ? "계량기를 확인할 수 없습니다" : "등록된 계량기가 없습니다"}</h1>
    <p>{meterId ? "비활성 계량기이거나 조회 권한이 없습니다." : "계량기를 등록하면 자료 수집 전에도 상세 정보를 확인할 수 있습니다."}</p><a className="secondary-button" href="#/meters">계량기 관리</a></main>;
  const line = station.lines.find((l) => l.meterId === meterId) || station.lines.find((l) => l.risk) || station.lines[0];
  const officeId = String(line.office_id || "");
  const officeStations = stations.filter((s) => s.lines.some((l) => String(l.office_id || "") === officeId));
  const selectMeter = (record) => { window.location.hash = detailHref(record.meterId).slice(1); };
  const sameLine = station.lines.filter((l) => String(l.line) === String(line.line));
  const viewStation = { ...station, 주소: line.주소, 용도: line.용도, 사용자명: station.역명 };
  const stale = Boolean(line.risk && data.status?.reference_date && line.risk.기준일 < data.status.reference_date);
  const billingOnly = line.dataMode === "billing_only";
  return <div className="dt-root">
    <div className="dt-demo" aria-label="조회할 계량기 선택">
      <label className="form-field">영업사업소<select className="dt-demo-select" value={officeId} onChange={(e) => {
        const record = stations.flatMap((s) => s.lines).find((l) => String(l.office_id) === e.target.value);
        if (record) selectMeter(record);
      }}>{(data.offices || []).map((office) => <option key={office.id} value={office.id}>{office.name}</option>)}</select></label>
      <label className="form-field">역<select className="dt-demo-select" value={station.id} onChange={(e) => {
        const next = stations.find((s) => String(s.id) === e.target.value);
        if (next) selectMeter(next.lines.find((l) => String(l.office_id || "") === officeId) || next.lines[0]);
      }}>{officeStations.map((s) => <option key={s.id} value={s.id}>{s.역명}</option>)}</select></label>
      <label className="form-field">계량기<select className="dt-demo-select" value={line.meterId} onChange={(e) => selectMeter(station.lines.find((l) => l.meterId === e.target.value))}>
        {sameLine.map((l) => <option key={l.meterId} value={l.meterId}>{l.display_name || "기본 계량기"} · {l.고객번호}</option>)}
      </select></label>
      <span className="dt-demo-note">같은 역의 모든 계약·계량기를 개별 조회합니다.</span>
    </div>
    <main className="dt-page">
      <CollectionPanel collection={collection} meters={data.meters || []} meterId={line.meterId} />
      {(stale || line.riskError) && <div className="data-notice" role="status">{line.riskError ? "최근 위험도 수집에 오류가 있습니다." : "최신 기준일보다 오래된 자료입니다."} {line.risk ? `아래 위험도는 마지막 유효 자료(${line.risk.기준일})입니다.` : "위험도 산출을 기다리고 있습니다."}</div>}
      <div className="dt-cols">
        <div className="dt-col">
          <StationHeader station={station} line={line} selectMeter={selectMeter} />
          {line.dataMode === "daily" && <DailyPanel key={line.meterId} usage={line.daily} ridership={line.ridership} latest={latest} tooltip={DAILY_TIP} />}
          {line.dataMode === "pending" && <Card title="첫 일일 수집 대기"><EmptyNote>일일 수집 대상으로 등록했습니다. 첫 사용량 자료가 들어오면 일일 관제와 분석을 시작합니다.</EmptyNote></Card>}
        </div>
        <div className="dt-col">
          {line.dataMode === "daily" && (line.risk ? <RiskPanel line={line} /> : <RiskUnavailable />)}
          <BasicInfo station={viewStation} line={line} />
        </div>
      </div>
      <Card title="청구서 · 납부 내역" right={<InfoTooltip text="저장된 청구자료로 만든 청구내역 PDF를 열람·다운로드할 수 있습니다. 공급기관의 원본 고지서와 구분됩니다." />}>
        <Bill key={line.meterId} station={viewStation} line={line} />
      </Card>
      <div className="export-toolbar detail-exports"><span>현재 계량기 자료</span>
        {!billingOnly && <FileLink href={exportUrl({ kind: "usage", meter_id: line.meterId })} filename={`${line.고객번호}_사용량.xlsx`}>일일 사용량 Excel</FileLink>}
        <FileLink href={exportUrl({ kind: "bills", meter_id: line.meterId })} filename={`${line.고객번호}_청구내역.xlsx`}>청구내역 Excel</FileLink></div>
    </main>
  </div>;
}

function StationHeader({ station, line, selectMeter }) {
  const lines = [...new Set(station.lines.map((l) => l.line))];
  const risk = line.risk;
  return <section className="dt-card dt-station">
    <div className="dt-station-info">
      <div className="dt-station-lines">{lines.map((number) => <button key={number} className={`dt-line dt-line--${number} dt-line-btn ${number === line.line ? "is-on" : "is-off"}`} onClick={() => selectMeter(station.lines.find((l) => l.line === number))} aria-pressed={number === line.line}>{number}호선</button>)}</div>
      <h1>{station.역명}</h1><p className="dt-meter-label">{line.display_name || "기본 계량기"} · {line.고객번호}</p>
      <div className="dt-station-cov"><span className="dt-cov">{line.dataMode === "billing_only" ? "청구 전용 · 요금·청구 사용량 제공" : line.dataMode === "pending" ? "첫 일일 수집 대기" : risk ? "일일·위험도 제공" : "일일 사용량 제공 · 분석 대기"}</span></div>
    </div>
    {risk && <div className="dt-station-risk"><RiskGauge text={risk.pct == null ? "—" : `${risk.pct > 0 ? "+" : ""}${risk.pct}%`} fillPct={Math.min(Math.abs(risk.pct || 0) / 100, 1)} level={risk.severity} label="예측대비" /><RiskBadge level={risk.severity} size="lg" /></div>}
  </section>;
}

function BasicInfo({ station, line }) {
  const rows = [
    ["고객번호", line.고객번호],
    ["사용자명", station.사용자명],
    ["위치", station.주소],
    ["호선", `${line.line}호선`],
    ["영업사업소", line.영업사업소],
    ["계량기", line.display_name || line.계량기번호 || "—"],
    ["제공 자료", line.dataMode === "billing_only" ? "청구 전용" : line.dataMode === "pending" ? "첫 일일 수집 대기" : "일일 사용량·청구서"],
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
    : `예측보다 ${ton(Math.abs(rk.error))}톤(${rk.pct == null ? "비율 산출 불가" : `${rk.pct > 0 ? "+" : ""}${rk.pct}%`}) ${
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
          <Stat label="예측 대비" value={rk.pct == null ? "산출 불가" : `${rk.pct > 0 ? "+" : ""}${rk.pct}%`} tone={tone} />
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
                    {h.pct == null ? "—" : `${h.pct > 0 ? "+" : ""}${h.pct}%`}
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
    <Card title="위험도 · 분석 대기">
      <EmptyNote>
        일일 사용량은 수집되어 있으며
        <br />
        <strong>위험도 분석을 기다리고 있습니다.</strong>
      </EmptyNote>
    </Card>
  );
}

// 일일 사용량 + 승하차를 한 카드에. 날짜 하나로 둘 동시 조회.
function DailyPanel({ usage, ridership, latest, tooltip }) {
  const series = [usage, ridership].filter(Boolean);
  const maxDate = series.length
    ? series
        .map((s) => s[s.length - 1].date)
        .sort()
        .slice(-1)[0]
    : latest;
  const [date, setDate] = useState(maxDate);
  const previousMax = useRef(maxDate);
  useEffect(() => {
    setDate((current) => !current || current === previousMax.current ? maxDate : current);
    previousMax.current = maxDate;
  }, [maxDate]);

  if (series.length === 0) {
    return (
      <Card title="일일 사용량 · 승하차" right={<InfoTooltip text={tooltip} />}>
        <EmptyNote>
          일일 자료가 아직 없습니다.
          <br />
          <strong>수집 설정과 최근 수집 상태를 확인하세요.</strong>
        </EmptyNote>
      </Card>
    );
  }

  const minDate = series.map((s) => s[0].date).sort()[0];

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
          <span className="dt-daily-none">자료 없음</span>
        </div>
      </div>
    );
  }
  const maxDate = series[series.length - 1].date;
  const point = series.find((p) => p.date === date);
  const cutoff = date <= maxDate ? date : maxDate;
  const before = new Date(`${cutoff}T00:00:00Z`);
  before.setUTCDate(before.getUTCDate() - 6);
  const start = Number.isNaN(before.getTime()) ? "" : before.toISOString().slice(0, 10);
  const recent = series.filter((p) => p.date >= start && p.date <= cutoff);

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
      {!point ? <p className="dt-daily-hint">선택일의 자료가 없습니다. 마지막 수집일: {maxDate}</p> : null}
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
