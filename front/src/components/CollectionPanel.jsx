import { useEffect, useRef, useState } from "react";
import { getCollection, saveCollectionSettings, startCollection } from "../api.js";
import { collectionLabel, collectionNeedsRefresh, collectionTime, isCollectionActive, isCollectionFinished, meterCollectionState } from "../collection.js";

export function useCollection(userId, onComplete) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const previous = useRef(null);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;
  const sessionRef = useRef(userId);
  sessionRef.current = userId;
  useEffect(() => { previous.current = null; setData(null); setError(""); setBusy(false); }, [userId]);
  useEffect(() => {
    if (!userId) return;
    let alive = true, loading = false, timer;
    const load = async () => {
      if (loading) return;
      loading = true;
      clearTimeout(timer);
      try {
        const next = await getCollection();
        if (!alive) return;
        if (collectionNeedsRefresh(previous.current, next)) onCompleteRef.current();
        previous.current = next;
        setData(next); setError("");
      } catch (e) { if (alive && e.status !== 401) setError(e.message); }
      loading = false;
      if (alive) timer = setTimeout(load, isCollectionActive(previous.current?.running) ? 2_000 : 60_000);
    };
    const visible = () => { if (!document.hidden) load(); };
    load(); document.addEventListener("visibilitychange", visible);
    return () => { alive = false; clearTimeout(timer); document.removeEventListener("visibilitychange", visible); };
  }, [userId, revision]);
  const refresh = () => setRevision((n) => n + 1);
  async function start(meterId) {
    setBusy(true); setError("");
    try {
      const job = await startCollection(meterId);
      if (sessionRef.current === userId) {
        previous.current = { ...previous.current, running: job };
        setData((value) => ({ ...value, running: job })); refresh();
      }
      return job;
    } catch (e) { if (sessionRef.current === userId) { setError(e.message); refresh(); } throw e; }
    finally { if (sessionRef.current === userId) setBusy(false); }
  }
  async function saveSettings(settings) {
    await saveCollectionSettings(settings); refresh();
  }
  return { data, error, busy, refresh, start, saveSettings };
}

export default function CollectionPanel({ collection, user, meters = [], meterId, showSettings = false }) {
  const [notice, setNotice] = useState("");
  const [noticeJobId, setNoticeJobId] = useState(null);
  const [actionError, setActionError] = useState("");
  const [expanded, setExpanded] = useState(false);
  useEffect(() => { setNotice(""); setNoticeJobId(null); setActionError(""); setExpanded(false); }, [meterId]);
  useEffect(() => {
    const snapshot = collection?.data;
    const result = [snapshot?.latest, snapshot?.running, ...(snapshot?.history || [])].find((item) => item?.id === noticeJobId && isCollectionFinished(item));
    if (result) { setNotice(""); setNoticeJobId(null); }
  }, [collection?.data, noticeJobId]);
  if (!collection) return null;
  const { data, error, busy } = collection;
  const meter = meterId ? meters.find((m) => String(m.id) === String(meterId)) : null;
  const billsOnly = meter && !meter.daily_enabled;
  const dailySelected = meter ? meter.provider === "arisu" && Boolean(meter.daily_enabled) : meters.some((m) => m.provider === "arisu" && m.active && !m.deleted_at && m.daily_enabled);
  const meterState = meterId ? data?.meters?.find((m) => String(m.meter_id) === String(meterId)) : null;
  const job = data?.running || data?.latest;
  const active = isCollectionActive(data?.running);
  const meterBusy = isCollectionActive(meterState);
  const meterLabel = meter ? meterCollectionState(meter, meterState) : "";
  const statusLabel = collectionLabel(meterState?.status);
  const canUpdate = meter ? meter.provider === "arisu" && Boolean(meter.active) && !meter.deleted_at : meters.some((m) => m.provider === "arisu" && m.active && !m.deleted_at);
  async function update() {
    setActionError(""); setNotice(""); setNoticeJobId(null); setExpanded(true);
    try { const next = await collection.start(meterId); setNoticeJobId(next.id); setNotice(next.status === "queued" ? "정보 업데이트를 예약했습니다. 순서대로 수집합니다." : "정보 업데이트를 시작했습니다."); }
    catch (e) { setActionError(e.message); }
  }
  const content = <>
    {!data && !error && <p className="form-hint" role="status">수집 상태를 확인하는 중…</p>}
    {data && <>
      {dailySelected && !data.configured?.water && <p className="collection-note">일일 사용량 로그인 설정이 완료되지 않았습니다. 청구내역은 고객번호와 고지서상 성명으로 조회할 수 있습니다. 기존 저장 자료는 계속 확인할 수 있습니다.</p>}
      {data.worker_enabled === false && <p className="collection-note">수집 실행이 꺼져 있습니다. 예약한 작업은 서버에서 수집 실행을 켜면 처리합니다.</p>}
      {meter && <div className="collection-meter-summary"><strong>{meterLabel}</strong><span>최근 시도 {collectionTime(meterState?.last_attempt_at)}</span><span>최근 성공 {collectionTime(meterState?.last_success_at)}</span>{statusLabel !== meterLabel && <span>{statusLabel}</span>}{meterState?.message && <p>{meterState.message}</p>}</div>}
      {job && <div className={`collection-job collection-job--${job.status}`}>
        <div className="collection-job-title"><strong>{meterId ? "담당 범위 " : ""}{active ? "현재 작업" : "최근 작업"} · {collectionLabel(job.status)}</strong><span>{job.completed || 0} / {job.total || 0}개 처리</span></div>
        {active && <progress aria-label="정보 업데이트 진행률" max={Math.max(job.total || 0, 1)} value={job.completed || 0} />}
        <p>{job.message || (job.status === "queued" ? "앞선 작업이 끝나면 자동으로 수집합니다." : "수집 결과를 확인하세요.")}</p>
        <small>시작 {collectionTime(job.started_at)}{job.finished_at ? ` · 종료 ${collectionTime(job.finished_at)}` : ""}</small>
        {job.items?.length > 0 && <details><summary>계량기별 결과 {job.items.length}건</summary><JobItems items={job.items} meters={meters} /></details>}
      </div>}
      {!job && <p className="form-hint">아직 정보 업데이트 이력이 없습니다. 조회 결과가 비어 있어도 고객번호 오류로 단정하지 않습니다.</p>}
      <div className="collection-schedule"><span>하루 1회 자동 수집 <strong>{data.settings?.enabled ? `매일 ${String(data.settings.hour).padStart(2, "0")}:00` : "꺼짐"}</strong> (한국시간)</span><span>다음 자동 수집 <strong>{data.settings?.enabled ? data.settings.next_run_at ? collectionTime(data.settings.next_run_at) : data.worker_enabled === false ? "실행 대기 · 수집 실행 확인" : "실행 대기 · 계정 설정 확인" : "예약 없음"}</strong></span><button type="button" className="text-button" onClick={collection.refresh}>수집 상태 확인</button></div>
      {showSettings && user?.role === "superadmin" && <CollectionSettings key={`${data.settings?.enabled}-${data.settings?.hour}`} settings={data.settings || {}} onSave={collection.saveSettings} />}
      {showSettings && data.history?.length > 0 && <details className="collection-history"><summary>최근 수집·실패 이력 {data.history.length}건</summary><p className="form-hint">담당 범위의 최근 20개 작업입니다. 작업을 펼치면 계량기별 결과와 실패 사유를 확인할 수 있습니다.</p>{data.history.map((entry) => <details key={entry.id} className={`collection-job collection-job--${entry.status}`}><summary><strong>{collectionLabel(entry.status)}</strong> · {collectionTime(entry.started_at || entry.created_at)} · {entry.completed || 0}/{entry.total || 0}개</summary><p>{entry.message}</p><small>종료 {collectionTime(entry.finished_at)}</small><JobItems items={entry.items || []} meters={meters} /></details>)}</details>}
    </>}
    {notice && <p className="form-message" role="status">{notice}</p>}
  </>;
  return <section className={`collection-panel ${showSettings ? "" : "collection-panel--compact"} ${meterId ? "collection-panel--meter" : ""}`} aria-label={meterId ? "현재 계량기 정보 업데이트" : "정보 업데이트"}>
    <div className="collection-heading"><div><h2>{meterId ? "계량기 정보 업데이트" : "정보 업데이트"}</h2>
      {showSettings ? <p>담당 범위의 활성 아리수 계량기를 수집합니다. 화면의 검색·호선 필터와 관계없이 적용됩니다.<br />청구·사용량을 갱신합니다. 분석 결과는 별도 기준일을 따릅니다.</p> : <p>{billsOnly ? "청구내역 수집" : "청구·사용량 수집 · 분석 결과는 별도 기준일 적용"}</p>}
    </div><button className="primary-button" type="button" disabled={busy || !canUpdate || meterBusy || (!meterId && active)} onClick={update}>{busy ? "요청 중…" : meterBusy || (!meterId && active) ? "수집 작업 진행 중" : meterId ? "정보 업데이트" : "전체 담당 정보 업데이트"}</button></div>
    {!showSettings && <>
      <p className="collection-brief">{!data ? "수집 상태 확인 중…" : meter ? <>{meterLabel}{statusLabel !== meterLabel ? ` · ${statusLabel}` : ""} · 최근 성공 {collectionTime(meterState?.last_success_at)}</> : job ? <>최근 작업 {collectionLabel(job.status)} · {collectionTime(job.finished_at || job.started_at || job.created_at)}{!active && isCollectionFinished(job) && job.message ? ` · ${job.message}` : ""}</> : "수집 이력 없음"}</p>
      {active && <div className="collection-inline-progress" role="status"><span>담당 범위 {collectionLabel(job.status)} · {job.completed || 0}/{job.total || 0}개 처리</span><progress aria-label="정보 업데이트 진행률" max={Math.max(job.total || 0, 1)} value={job.completed || 0} /></div>}
      <details className="collection-details" open={expanded} onToggle={(e) => setExpanded(e.currentTarget.open)}><summary>수집 상태·내역</summary><p className="form-hint">{meterId ? billsOnly ? "이 고객번호의 청구내역을 확인합니다. 일일 사용량은 수집하지 않습니다." : "이 고객번호의 청구내역과 일일 사용량을 확인합니다." : "업데이트는 화면 필터와 관계없이 담당 범위의 활성 아리수 계량기에 적용됩니다."}</p>{content}</details>
    </>}
    {showSettings && content}
    {(actionError || error) && <p className="form-error" role="alert">{actionError || error} <button className="text-button" type="button" onClick={collection.refresh}>상태 다시 확인</button></p>}
  </section>;
}

function JobItems({ items, meters }) {
  return <div className="table-wrap"><table className="management-table"><thead><tr><th>계량기 / 고객번호</th><th>결과</th><th>일일 / 청구</th><th>상세</th></tr></thead><tbody>{items.map((item) => {
    const record = meters.find((m) => String(m.id) === String(item.meter_id));
    return <tr key={item.meter_id}><td>{record?.station_name || item.station_name || item.display_name || "계량기"}<small>{record?.customer_number || item.customer_number || item.meter_id}</small></td><td>{collectionLabel(item.status)}</td><td>{item.daily_rows ?? "—"} / {item.bill_rows ?? "—"}</td><td>{item.message || "—"}</td></tr>;
  })}</tbody></table></div>;
}

function CollectionSettings({ settings, onSave }) {
  const [enabled, setEnabled] = useState(Boolean(settings.enabled));
  const [hour, setHour] = useState(settings.hour ?? 8);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(e) {
    e.preventDefault(); setBusy(true); setMessage(""); setError("");
    try { await onSave({ enabled, hour: Number(hour) }); setMessage("자동 수집 설정을 저장했습니다."); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <details className="collection-settings"><summary>자동 수집 설정 · 총괄 관리자</summary><form onSubmit={submit}><label className="check-field"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />하루 1회 자동 수집</label><label className="form-field">한국시간<select value={hour} onChange={(e) => setHour(e.target.value)}>{Array.from({ length: 24 }, (_, h) => <option key={h} value={h}>{String(h).padStart(2, "0")}:00</option>)}</select></label><button className="secondary-button" disabled={busy}>{busy ? "저장 중…" : "설정 저장"}</button><p className="form-hint">서버가 실행 중일 때 전체 활성 아리수 계량기를 수집합니다.</p>{message && <p className="form-message" role="status">{message}</p>}{error && <p className="form-error" role="alert">{error}</p>}</form></details>;
}
