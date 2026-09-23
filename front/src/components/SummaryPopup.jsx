import { useEffect, useRef, useState } from "react";
import { analyzeCause, getSummary, sendAlert } from "../api.js";
import { detailHref, ton } from "../pages/Detail/data.js";
import "./agent.css";

const SEV_TONE = { 경고: "alert", 주의: "warn", 정상: "ok", "자료 확인": "unknown" };
const formatStationName = (name = "") => name.replace(/^(.+역)(\d+)$/, "$1 $2호선");
const formatStationNames = (text = "") => text.replace(/([가-힣A-Za-z]+역)(\d+)/g, "$1 $2호선");
function extractUrl(text) {
  const match = /https?:\/\/[^\s<>]+/.exec(text || "");
  return match ? match[0] : null;
}

export default function SummaryPopup({ date, onClose }) {
  const dialog = useRef(null);
  const [state, setState] = useState({ loading: true });
  const [revision, setRevision] = useState(0);
  useEffect(() => { dialog.current.showModal(); }, []);
  useEffect(() => {
    let alive = true;
    setState({ loading: true });
    getSummary(date, revision > 0).then((data) => { if (alive) setState({ data }); })
      .catch((error) => { if (alive) setState({ error: error.message }); });
    return () => { alive = false; };
  }, [date, revision]);
  const { loading, data, error } = state;
  return <dialog ref={dialog} className="ag-modal ag-dialog" onCancel={onClose} aria-labelledby="summary-title">
    <header className="ag-modal-head"><div><span className="ag-eyebrow">물샘이 · 업무 요약</span>
      <h2 id="summary-title">{loading ? "이상징후를 확인하는 중…" : error ? "요약을 불러오지 못했습니다" : formatStationNames(data.headline)}</h2></div>
      <button className="ag-x" onClick={onClose} aria-label="닫기">×</button></header>
    {loading ? <div className="ag-body ag-center" role="status"><div className="ag-spinner" /><p>조회 권한 내 자료를 확인하고 있습니다.</p></div>
      : error ? <div className="ag-body"><p className="ag-err" role="alert">{error}</p><button className="ag-btn" onClick={() => setRevision((n) => n + 1)}>다시 시도</button></div>
      : <SummaryBody data={data} onClose={onClose} />}
    <footer className="ag-modal-foot"><span className="ag-by">수집된 자료를 바탕으로 정리한 요약</span><button className="ag-btn ag-btn--primary" onClick={onClose}>확인</button></footer>
  </dialog>;
}

function SummaryBody({ data, onClose }) {
  const cal = data.calendar || {};
  const tag = cal.holiday ? `공휴일${cal.holiday_name ? ` (${cal.holiday_name})` : ""}` : cal.weekend ? "주말" : "평일";
  return <div className="ag-body">
    <div className="ag-meta"><span className="ag-chip">{data.기준일} 기준</span><span className="ag-chip">{tag}</span><span className="ag-chip ag-chip--alert">경고 {data.counts?.경고 ?? 0}</span><span className="ag-chip ag-chip--warn">주의 {data.counts?.주의 ?? 0}</span>{data.counts?.["자료 확인"] > 0 && <span className="ag-chip">자료 확인 {data.counts["자료 확인"]}</span>}</div>
    {data.items?.length ? <ul className="ag-list">{data.items.map((item) => <AnomalyItem key={item.meter_id} item={item} date={data.기준일} onClose={onClose} />)}</ul>
      : <p className="ag-muted">{data.counts?.분석 ? "확인된 분석 범위에 새로운 이상징후가 없습니다." : "이 날짜의 분석 자료가 없습니다. 수집 상태를 확인하세요."}</p>}
    {data.actions?.length > 0 && <div className="ag-actions"><h3>확인할 사항</h3><ol>{data.actions.map((action, i) => <li key={i}>{formatStationNames(action)}</li>)}</ol></div>}
  </div>;
}

function AnomalyItem({ item, date, onClose }) {
  const [cause, setCause] = useState(null);
  const [mail, setMail] = useState(null);
  const dataError = item.likely_data_error || item.심각도 === "자료 확인";
  const tone = dataError ? "unknown" : SEV_TONE[item.심각도] || "unknown";
  async function analyze() {
    setCause({ loading: true });
    try { const result = await analyzeCause(item.meter_id, date); setCause({ data: result.analysis || result }); }
    catch (e) { setCause({ error: e.message }); }
  }
  async function alert() {
    if (!window.confirm(`${formatStationName(item.역명)}의 ${date} 이상징후를 해당 사업소에 등록된 담당자에게 이메일로 발송합니다.`)) return;
    setMail({ loading: true });
    try {
      const result = await sendAlert(item.meter_id, date);
      setMail({ ok: Boolean(result.sent), message: result.sent ? `발송 완료${result.to?.length ? ` · ${result.to.join(", ")}` : ""}` : result.reason || "발송되지 않았습니다." });
    } catch (e) { setMail({ ok: false, message: e.message }); }
  }
  return <li className={`ag-item ag-item--${tone}`}>
    <div className="ag-item-main"><span className={`ag-sev ag-sev--${tone}`}>{dataError ? "자료 확인" : item.심각도}</span>
      <a className="ag-item-name station-link" href={detailHref(item.meter_id)} onClick={onClose}>{formatStationName(item.역명)}</a>
      <span className="ag-item-line">{dataError ? "원자료 확인 필요 · 위험도 미산출" : <>예측 대비 <strong>{item.pct == null ? "산출 불가" : `${item.pct > 0 ? "+" : ""}${item.pct}%`}</strong> ({ton(item.err_ton ?? item.error_ton)}톤)</>}</span></div>
    {item.action && <p className="ag-item-action">{formatStationNames(item.action)}</p>}
    {dataError ? <p className="ag-muted">원자료를 확인한 후 분석·알림을 사용할 수 있습니다.</p> : <div className="ag-item-btns"><button className="ag-btn" disabled={cause?.loading || !item.meter_id} onClick={analyze}>{cause?.loading ? "분석 중…" : "이상 원인 분석"}</button>
      <button className="ag-btn" disabled={mail?.loading || !item.meter_id} onClick={alert}>{mail?.loading ? "발송 중…" : "담당자에게 알림"}</button></div>}
    {mail?.message && <p className={mail.ok ? "ag-tag ag-tag--ok" : "ag-err"} role="status">{mail.message}</p>}
    {cause && !cause.loading && <CauseResult cause={cause} />}
  </li>;
}

function CauseResult({ cause }) {
  if (cause.error) return <p className="ag-err">분석 실패: {cause.error}</p>;
  const a = cause.data || {};
  if (a.error) return <p className="ag-err">{a.error}</p>;
  return (
    <div className="ag-cause">
      <p className="ag-cause-main">
        <strong>{a.primary_cause}</strong>
        {a.confidence ? <span className="ag-muted"> · 확신도 {a.confidence}</span> : null}
      </p>
      {a.reasons?.length ? (
        <ul className="ag-cause-reasons">
          {a.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      ) : null}
      {a.events?.length ? (
        <div className="ag-cause-events">
          <span className="ag-muted">관련 정보</span>
          <ul>
            {a.events.map((e, i) => {
              const url = extractUrl(e.source);
              return (
                <li key={i}>
                  {url ? (
                    <a href={url} target="_blank" rel="noreferrer">
                      {e.title || url}
                    </a>
                  ) : (
                    e.title || e.source
                  )}{" "}
                  {e.date ? <span className="ag-muted">{e.date}</span> : null}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
      {a.recommendation ? <p className="ag-cause-rec">권장 조치: {a.recommendation}</p> : null}
    </div>
  );
}
