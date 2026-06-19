// 사이트 접속 시 뜨는 '당일 업무 요약' 팝업.
// 에이전트(/api/summary)가 실데이터(이상탐지 CSV)를 보고 스스로 요약한다.
// 각 이상 항목에서 [원인 분석](web_search) · [알림 발송](메일) 을 바로 실행.
import { useEffect, useState } from "react";
import { analyzeCause, getSummary, sendAlert } from "../api";
import "./agent.css";

const SEV_TONE = { 경고: "alert", 주의: "warn", 정상: "ok" };

// 표시용: "왕십리역5" → "왕십리역 5호선" (역명에 붙은 호선 숫자를 분리). API 호출엔 원본 역명을 그대로 쓴다.
function formatStationName(name) {
  const m = /^(.+역)(\d+)$/.exec(name);
  return m ? `${m[1]} ${m[2]}호선` : name;
}

// source 에 출처명+URL 이 섞여 와도(예: "서울시설공단 … https://…") 실제 URL 만 뽑는다.
function extractUrl(text) {
  const m = /https?:\/\/[^\s]+/.exec(text || "");
  return m ? m[0] : null;
}

export default function SummaryPopup() {
  const [open, setOpen] = useState(true);
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    // 정적 HTML(단일파일)에서는 백엔드 대신 주입된 요약을 사용
    if (typeof window !== "undefined" && window.__SUMMARY__) {
      setState({ loading: false, error: null, data: window.__SUMMARY__ });
      return;
    }
    let alive = true;
    getSummary()
      .then((data) => alive && setState({ loading: false, error: null, data }))
      .catch((e) => alive && setState({ loading: false, error: e.message, data: null }));
    return () => {
      alive = false;
    };
  }, []);

  if (!open) return null;
  const { loading, error, data } = state;

  return (
    <div className="ag-overlay" role="dialog" aria-modal="true">
      <div className="ag-modal">
        <header className="ag-modal-head">
          <div>
            <span className="ag-eyebrow">물샘이 · 당일 업무 요약</span>
            <h2>{loading ? "물샘이가 오늘의 이상징후를 정리하는 중…" : error ? "요약을 불러오지 못했습니다" : data.headline}</h2>
          </div>
          <button className="ag-x" onClick={() => setOpen(false)} aria-label="닫기">
            ×
          </button>
        </header>

        {loading ? (
          <div className="ag-body ag-center">
            <div className="ag-spinner" />
            <p className="ag-muted">물샘이가 실데이터를 분석하고 있어요.</p>
          </div>
        ) : error ? (
          <div className="ag-body">
            <p className="ag-err">{error}</p>
            <p className="ag-muted">
              에이전트 서버가 켜져 있는지 확인하세요.
              <br />
              <code>uvicorn back.api.main:app --reload --port 8000</code>
            </p>
          </div>
        ) : (
          <SummaryBody data={data} />
        )}

        <footer className="ag-modal-foot">
          {data?.generated_by ? <span className="ag-by">생성: {data.generated_by}</span> : <span />}
          <button className="ag-btn ag-btn--primary" onClick={() => setOpen(false)}>
            확인
          </button>
        </footer>
      </div>
    </div>
  );
}

function SummaryBody({ data }) {
  const cal = data.calendar || {};
  const calTag = cal.holiday ? `공휴일${cal.holiday_name ? `(${cal.holiday_name})` : ""}` : cal.weekend ? "주말" : "평일";
  return (
    <div className="ag-body">
      <div className="ag-meta">
        <span className="ag-chip">{data.기준일} 기준</span>
        <span className="ag-chip">{calTag}</span>
        <span className="ag-chip ag-chip--alert">경고 {data.counts?.경고 ?? 0}</span>
        <span className="ag-chip ag-chip--warn">주의 {data.counts?.주의 ?? 0}</span>
      </div>

      {data.items?.length ? (
        <ul className="ag-list">
          {data.items.map((it, i) => (
            <AnomalyItem key={`${it.역명}-${i}`} item={it} date={data.기준일} />
          ))}
        </ul>
      ) : (
        <p className="ag-muted">새로운 이상징후가 없습니다. 정기 점검만 진행하세요.</p>
      )}

      {data.actions?.length ? (
        <div className="ag-actions">
          <h3>오늘 할 일</h3>
          <ol>
            {data.actions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}

// 이상 수치 한 줄: 과다▲/과소▼ + 수치만 bold. deviation 은 표시하지 않는다.
function MetricLine({ item }) {
  if (item.pct == null) {
    // 구형 응답 호환: one_line 에서 deviation 표기만 제거해 노출.
    return <>{(item.one_line || "").replace(/[,·]?\s*deviation\s*-?[\d.]+/i, "")}</>;
  }
  const up = item.dir === "과다";
  const err = item.err_ton;
  const errStr = `${err > 0 ? "+" : ""}${err}톤`;
  const cls = up ? "ag-metric--up" : "ag-metric--down";
  return (
    <>
      예측 대비 <span className={cls}>{up ? "▲" : "▼"}<strong>{Math.abs(item.pct)}%</strong></span> (<strong>{errStr}</strong>)
    </>
  );
}

function AnomalyItem({ item, date }) {
  const tone = SEV_TONE[item.심각도] || "warn";
  const [cause, setCause] = useState(null); // {loading, data, error}
  const [mail, setMail] = useState(null); // {loading, msg, ok}

  const runAnalyze = async () => {
    setCause({ loading: true });
    try {
      const res = await analyzeCause(item.역명, date);
      setCause({ loading: false, data: res.analysis });
    } catch (e) {
      setCause({ loading: false, error: e.message });
    }
  };

  const runAlert = async () => {
    setMail({ loading: true });
    try {
      const res = await sendAlert(item.역명, date);
      setMail({
        loading: false,
        ok: res.sent,
        msg: res.sent ? `발송됨 → ${(res.to || []).join(", ")}` : `미발송: ${res.reason || "오류"}`,
      });
    } catch (e) {
      setMail({ loading: false, ok: false, msg: e.message });
    }
  };

  return (
    <li className={`ag-item ag-item--${tone}`}>
      <div className="ag-item-main">
        <span className={`ag-sev ag-sev--${tone}`}>{item.심각도}</span>
        <strong className="ag-item-name">{formatStationName(item.역명)}</strong>
        <span className="ag-item-line"><MetricLine item={item} /></span>
      </div>
      {item.action ? <p className="ag-item-action">→ {item.action}</p> : null}

      <div className="ag-item-btns">
        <button className="ag-btn" onClick={runAnalyze} disabled={cause?.loading}>
          {cause?.loading ? "분석 중…" : "이상 원인 분석"}
        </button>
        <button className="ag-btn" onClick={runAlert} disabled={mail?.loading}>
          {mail?.loading ? "발송 중…" : "알림 발송"}
        </button>
        {mail && !mail.loading ? (
          <span className={mail.ok ? "ag-tag ag-tag--ok" : "ag-tag ag-tag--err"}>{mail.msg}</span>
        ) : null}
      </div>

      {cause && !cause.loading ? <CauseResult cause={cause} /> : null}
    </li>
  );
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
