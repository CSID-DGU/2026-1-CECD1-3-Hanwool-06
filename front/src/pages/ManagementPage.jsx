import { useEffect, useRef, useState } from "react";
import { deleteMeter, getMeters, getUsers, restoreMeter, saveMeter, saveUser } from "../api.js";
import { detailHref } from "./Detail/data.js";
import CollectionPanel from "../components/CollectionPanel.jsx";
import { collectionLabel, collectionTime, isCollectionActive, meterCollectionState } from "../collection.js";

export default function ManagementPage({ data, user, kind, onSaved, collection }) {
  const [users, setUsers] = useState([]);
  const [editor, setEditor] = useState(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [revision, setRevision] = useState(0);
  const [showDeleted, setShowDeleted] = useState(false);
  const [allMeters, setAllMeters] = useState([]);
  const [archiveLoading, setArchiveLoading] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [actionBusy, setActionBusy] = useState(false);
  const isUsers = kind === "users";
  const allowed = !isUsers || user.role === "superadmin";
  useEffect(() => {
    setEditor(null); setSearch(""); setMessage(""); setError(""); setShowDeleted(false); setDeleting(null);
  }, [kind]);
  useEffect(() => {
    if (!isUsers || !allowed) return;
    let alive = true;
    getUsers().then((result) => { if (alive) setUsers(Array.isArray(result) ? result : result.users || []); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [isUsers, allowed, revision, data]);
  useEffect(() => {
    if (isUsers || !showDeleted) return;
    let alive = true;
    setArchiveLoading(true);
    getMeters(true).then((result) => { if (alive) { setAllMeters(result); setError(""); } })
      .catch((e) => { if (alive) setError(e.message); })
      .finally(() => { if (alive) setArchiveLoading(false); });
    return () => { alive = false; };
  }, [isUsers, showDeleted, revision, data]);
  if (!allowed) return <main className="management-page"><h1>접근 권한이 없습니다</h1><p>사용자 관리는 총괄 관리자만 사용할 수 있습니다.</p></main>;
  const meterRecords = showDeleted ? allMeters.filter((m) => m.deleted_at) : (data.meters || []).filter((m) => !m.deleted_at);
  const records = (isUsers ? users : meterRecords).filter((item) => (
    isUsers ? `${item.name} ${item.email}` : `${item.station_name} ${item.customer_number} ${item.display_name || ""} ${item.office_name || ""}`
  ).toLowerCase().includes(search.trim().toLowerCase()));
  const offices = data.offices || [];
  const officeNames = (ids = []) => ids.map((id) => offices.find((o) => String(o.id) === String(id))?.name || "미지정").join(", ");
  async function saved(result) {
    setEditor(null); setMessage(result?.created ? "등록했습니다. 아리수 계량기는 곧 연결을 확인합니다." : "저장했습니다."); setRevision((n) => n + 1); onSaved(); collection?.refresh();
  }
  async function updateMeter(item) {
    setError(""); setMessage("");
    try { await collection.start(item.id); setMessage(`${item.station_name}(${item.customer_number}) 정보 업데이트를 요청했습니다.`); }
    catch (e) { setError(e.message); }
  }
  async function changeDeleted(item, remove) {
    setActionBusy(true); setError("");
    try {
      if (remove) await deleteMeter(item.id); else await restoreMeter(item.id);
      setDeleting(null); setEditor(null); setRevision((n) => n + 1); onSaved(); collection?.refresh();
      setMessage(remove ? `${item.station_name}(${item.customer_number}) 계량기를 삭제했습니다. 이력은 삭제 보관함에 남습니다.` : `${item.station_name}(${item.customer_number}) 계량기를 복원했습니다.`);
    } catch (e) { setError(e.message); }
    finally { setActionBusy(false); }
  }
  return <main className="management-page">
    <div className="management-heading"><div><h1>{isUsers ? "사용자 관리" : "계량기 관리"}</h1>
      {isUsers && <p>사업소마다 활성 담당자를 2명까지 둘 수 있습니다.</p>}</div>
      <button className="primary-button" type="button" onClick={() => { setEditor({}); setMessage(""); }}>{isUsers ? "사용자 추가" : "계량기 추가"}</button></div>
    {error && <p className="form-error" role="alert">{error} <button onClick={() => setRevision((n) => n + 1)}>다시 시도</button></p>}
    {message && <p className="form-message" role="status">{message}</p>}
    {!isUsers && <CollectionPanel collection={collection} user={user} meters={data.meters || []} showSettings />}
    <section className="management-card">
      {!isUsers && <div className="management-tabs" role="group" aria-label="계량기 보관 상태"><button aria-pressed={!showDeleted} onClick={() => setShowDeleted(false)}>등록 계량기</button><button aria-pressed={showDeleted} onClick={() => setShowDeleted(true)}>삭제 보관함</button>{showDeleted && <p>복원하면 다시 관제와 수집 대상이 됩니다.</p>}</div>}
      <label className="form-field management-search">{isUsers ? "이름·이메일 검색" : "역명·고객번호·사업소 검색"}<input type="search" value={search} onChange={(e) => setSearch(e.target.value)} /></label>
      <div className="table-wrap"><table className="data-table"><caption className="sr-only">{isUsers ? "사용자 목록" : "계량기 목록"}</caption>
        <thead><tr>{(isUsers ? ["이름 / 이메일", "역할", "담당 사업소", "상태", "관리"] : ["역 / 호선", "계량기 / 고객번호", "사업소", "제공 자료", "수집 상태", "상태", "관리"]).map((label) => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{records.map((item) => { const state = collection?.data?.meters?.find((m) => String(m.meter_id) === String(item.id)); return <tr key={item.id}>
          {isUsers ? <><td><strong>{item.name}</strong><small>{item.email}</small></td><td>{item.role === "superadmin" ? "총괄 관리자" : "사업소 관리자"}</td><td>{item.role === "superadmin" ? "전체" : officeNames(item.office_ids)}</td></>
          : <><td>{item.deleted_at || !item.active ? <strong>{item.station_name}</strong> : <a className="station-link" href={detailHref(item.id)}>{item.station_name}</a>}{item.line && <small>{item.line}호선</small>}</td><td>{item.display_name || "기본 계량기"}<small>{item.customer_number}</small></td><td>{item.office_name || officeNames([item.office_id])}</td><td>{item.data_mode === "daily" ? "일일 사용량, 청구서" : item.data_mode === "pending" ? "첫 수집 대기" : "청구서"}</td><td className="meter-collection-cell">{item.deleted_at ? <span>삭제 {collectionTime(item.deleted_at)}</span> : <><strong>{meterCollectionState(item, state)}</strong>{item.provider === "arisu" && <><small>최근 성공 {collectionTime(state?.last_success_at)}</small>{state && <details><summary>{collectionLabel(state.status)}</summary><p>최근 시도 {collectionTime(state.last_attempt_at)}{state.message ? `. ${state.message}` : ""}</p></details>}</>}</>}</td></>}
          <td><span className={`status-label ${!item.active || item.deleted_at ? "status-label--off" : ""}`}>{item.deleted_at ? "삭제됨" : !item.active ? "비활성" : "활성"}</span></td>
          <td><div className="table-actions">{item.deleted_at ? <button type="button" className="secondary-button" disabled={actionBusy} onClick={() => changeDeleted(item, false)}>복원</button> : <>
            <button type="button" className="secondary-button" onClick={() => setEditor(item)} aria-label={`${item.name || item.station_name} 수정`}>수정</button>
            {!isUsers && <><button type="button" className="secondary-button" disabled={collection?.busy || isCollectionActive(state) || !item.active || item.provider !== "arisu"} onClick={() => updateMeter(item)}>{isCollectionActive(state) ? collectionLabel(state.status) : "정보 업데이트"}</button><button type="button" className="text-button danger-text" disabled={actionBusy} onClick={() => { setError(""); setDeleting(item); }} aria-label={`${item.station_name} ${item.customer_number} 삭제`}>삭제</button></>}
          </>}</div></td>
        </tr>; })}</tbody>
      </table></div>
      {!records.length && <p className="empty-state">{archiveLoading ? "삭제 보관함을 불러오는 중…" : search ? "검색 조건에 맞는 항목이 없습니다." : showDeleted ? "삭제 보관된 계량기가 없습니다." : "등록된 항목이 없습니다."}</p>}
      {!isUsers && <p className="form-hint">비활성 계량기는 관제 목록에 나오지 않습니다. 이력은 그대로 남습니다.</p>}
    </section>
    {editor && <EditorDialog key={`${kind}-${editor.id || "new"}`} title={`${isUsers ? "사용자" : "계량기"} ${editor.id ? "수정" : "추가"}`} onClose={() => setEditor(null)}>
      {isUsers ? <UserForm item={editor} offices={offices} onSaved={saved} /> : <MeterForm item={editor} data={data} onSaved={saved} canPosition={user.role === "superadmin"} onExisting={(item) => { setEditor(null); if (item.deleted_at) changeDeleted(item, false); else if (item.active && item.provider === "arisu") updateMeter(item); else setEditor(item); }} />}
    </EditorDialog>}
    {deleting && <EditorDialog title="계량기 삭제" onClose={() => { if (!actionBusy) setDeleting(null); }}><div className="editor-form"><p><strong>{deleting.station_name}{deleting.line ? ` ${deleting.line}호선` : ""}</strong><br />{deleting.display_name}<br />고객번호 {deleting.customer_number}</p><p className="form-hint">관제 목록과 수집 대상에서 빠집니다. 청구·사용량 이력은 남아 있어 삭제 보관함에서 복원할 수 있습니다.</p>{error && <p className="form-error" role="alert">{error}</p>}<div className="dialog-actions"><button className="secondary-button" disabled={actionBusy} onClick={() => setDeleting(null)}>취소</button><button className="danger-button" disabled={actionBusy} onClick={() => changeDeleted(deleting, true)}>{actionBusy ? "삭제 중…" : "삭제"}</button></div></div></EditorDialog>}
  </main>;
}

function EditorDialog({ title, children, onClose }) {
  const ref = useRef(null);
  useEffect(() => { ref.current.showModal(); }, []);
  return <dialog ref={ref} className="editor-dialog" onCancel={(e) => { e.preventDefault(); onClose(); }} aria-labelledby="editor-title">
    <header className="dialog-head"><h2 id="editor-title">{title}</h2><button type="button" className="dialog-close" onClick={onClose} aria-label="닫기">×</button></header>
    {children}
  </dialog>;
}

function UserForm({ item, offices, onSaved }) {
  const [form, setForm] = useState({ email: "", name: "", role: "office_admin", office_ids: [], active: true, ...item, password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const field = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError("");
    try {
      const body = { email: form.email.trim(), name: form.name.trim(), role: form.role, office_ids: form.role === "superadmin" ? [] : form.office_ids, active: form.active };
      if (form.password) body.password = form.password;
      if (form.role === "office_admin" && !form.office_ids.length) throw new Error("담당 사업소를 하나 이상 선택하세요.");
      await saveUser(item.id, body); await onSaved();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <form onSubmit={submit} className="editor-form">
    <label className="form-field">이름<input autoFocus required maxLength={80} value={form.name} onChange={(e) => field("name", e.target.value)} /></label>
    <label className="form-field">이메일<input type="email" required autoComplete="off" value={form.email} onChange={(e) => field("email", e.target.value)} /></label>
    <label className="form-field">{item.id ? "비밀번호 초기화 (변경할 때만 입력)" : "초기 비밀번호"}<input type="password" required={!item.id} minLength={12} autoComplete="new-password" value={form.password} onChange={(e) => field("password", e.target.value)} /></label>
    <label className="form-field">역할<select value={form.role} onChange={(e) => field("role", e.target.value)}><option value="office_admin">사업소 관리자</option><option value="superadmin">총괄 관리자</option></select></label>
    {form.role === "office_admin" && <fieldset><legend>담당 사업소</legend><div className="office-checkboxes">{offices.map((office) => <label key={office.id} className="check-field"><input type="checkbox" checked={form.office_ids.some((id) => String(id) === String(office.id))} onChange={(e) => field("office_ids", e.target.checked ? [...form.office_ids, office.id] : form.office_ids.filter((id) => String(id) !== String(office.id)))} />{office.name}</label>)}</div></fieldset>}
    <label className="check-field"><input type="checkbox" checked={form.active} onChange={(e) => field("active", e.target.checked)} />활성 계정</label>
    {error && <p className="form-error" role="alert">{error}</p>}
    <button className="primary-button" disabled={busy}>{busy ? "저장 중…" : "저장"}</button>
  </form>;
}

function MeterForm({ item, data, onSaved, canPosition, onExisting }) {
  const stations = [...new Map((data.meters || []).map((m) => [String(m.station_id), { id: m.station_id, name: m.station_name }])).values()].filter((s) => s.id);
  const [isNewStation, setIsNewStation] = useState(!stations.length);
  const [form, setForm] = useState({ provider: "arisu", customer_number: "", station_id: stations[0]?.id || "", station_name: "", line: "1", office_id: data.offices?.[0]?.id || "", display_name: "", address: "", purpose: "", tariff: "", active: true, daily_enabled: false, ...item });
  const [meterNumber, setMeterNumber] = useState(item.metadata?.계량기번호 || "");
  const [arisuCustomerName, setArisuCustomerName] = useState(item.metadata?.arisu_customer_name || "");
  const [position, setPosition] = useState(null);
  const [pickPosition, setPickPosition] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [duplicate, setDuplicate] = useState(null);
  const field = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError(""); setDuplicate(null);
    try {
      if (form.provider === "arisu" && (!arisuCustomerName.trim() || arisuCustomerName.includes("*"))) throw new Error("별표(*)로 가려지지 않은 아리수 고지서상 성명을 입력하세요.");
      const body = {
        provider: form.provider, customer_number: form.customer_number.trim(),
        station_name: isNewStation ? form.station_name.trim() : stations.find((s) => String(s.id) === String(form.station_id))?.name || form.station_name,
        line: Number(form.line), office_id: form.office_id, display_name: form.display_name.trim(),
        purpose: form.purpose.trim(), tariff: form.tariff.trim(), address: form.address.trim(),
        active: form.active,
        daily_enabled: form.provider === "arisu" && Boolean(form.daily_enabled),
        metadata: { 계량기번호: meterNumber.trim(), ...(form.provider === "arisu" ? { arisu_customer_name: arisuCustomerName.trim() } : {}) },
      };
      body.station_id = isNewStation ? "" : form.station_id;
      if (position) {
        if (position.x === "" || position.y === "") throw new Error("지도 X·Y 위치를 모두 입력하세요.");
        body.map_x = Number(position.x); body.map_y = Number(position.y);
      }
      const meter = await saveMeter(item.id, body); await onSaved({ meter, created: !item.id });
    } catch (e) {
      setError(e.message);
      if (e.status === 409 && !item.id) {
        const existing = await getMeters(true).catch(() => data.meters || []);
        setDuplicate(existing.find((m) => m.provider === form.provider && m.customer_number === form.customer_number.trim()) || null);
      }
    }
    finally { setBusy(false); }
  }
  return <form className="editor-form" onSubmit={submit}>
    <label className="form-field">공급기관<select disabled={Boolean(item.id)} value={form.provider} onChange={(e) => { field("provider", e.target.value); if (e.target.value !== "arisu") field("daily_enabled", false); }}><option value="arisu">서울 아리수</option><option value="other">기타 공급기관</option></select></label>
    <label className="form-field">고객번호<input autoFocus required readOnly={Boolean(item.id)} pattern={form.provider === "arisu" ? "[0-9]{9}" : undefined} maxLength={100} inputMode={form.provider === "arisu" ? "numeric" : "text"} value={form.customer_number} onChange={(e) => field("customer_number", e.target.value)} /><small>{form.provider === "arisu" ? "앞자리 0을 포함한 9자리" : "공급기관의 계약번호"}</small></label>
    {form.provider === "arisu" && <>
      <label className="form-field">아리수 고지서상 성명<input required maxLength={100} pattern="[^*]*" title="별표(*)로 가려지지 않은 고지서상 성명을 입력하세요." value={arisuCustomerName} onChange={(e) => setArisuCustomerName(e.target.value)} /><small>고지서에 적힌 그대로 입력하세요. 별표(*)로 가려진 이름은 쓸 수 없습니다.</small></label>
      <label className="form-field">수집할 자료<select value={form.daily_enabled ? "daily" : "bills"} onChange={(e) => field("daily_enabled", e.target.value === "daily")}><option value="bills">청구서만</option><option value="daily">일일 사용량 및 청구서</option></select></label>
    </>}
    {item.id && <p className="form-hint">고객번호가 바뀌었다면 새 계량기로 등록하세요.</p>}
    <label className="check-field"><input type="checkbox" checked={isNewStation} onChange={(e) => { setIsNewStation(e.target.checked); setPosition(null); }} />목록에 없는 새 역</label>
    {isNewStation ? <label className="form-field">역명<input required value={form.station_name} onChange={(e) => field("station_name", e.target.value)} placeholder="예: 동대문역" /></label>
      : <label className="form-field">역<select required value={form.station_id} onChange={(e) => { field("station_id", e.target.value); setPosition(null); }}>{stations.map((s) => <option value={s.id} key={s.id}>{s.name}</option>)}</select></label>}
    <div className="form-grid"><label className="form-field">호선<select value={form.line} onChange={(e) => field("line", e.target.value)}>{[1,2,3,4,5,6,7,8,9].map((line) => <option key={line} value={line}>{line}호선</option>)}</select></label>
      <label className="form-field">담당 사업소<select required value={form.office_id} onChange={(e) => field("office_id", e.target.value)}>{(data.offices || []).map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label></div>
    <label className="form-field">계량기 이름 / 설치 위치<input required maxLength={100} value={form.display_name} onChange={(e) => field("display_name", e.target.value)} placeholder="예: 대합실 화장실" /></label>
    <label className="form-field">계량기번호<input value={meterNumber} onChange={(e) => setMeterNumber(e.target.value)} /></label>
    <label className="form-field">주소<input value={form.address} onChange={(e) => field("address", e.target.value)} /></label>
    <div className="form-grid"><label className="form-field">용도<input value={form.purpose} onChange={(e) => field("purpose", e.target.value)} /></label><label className="form-field">요금 업종<input value={form.tariff} onChange={(e) => field("tariff", e.target.value)} /></label></div>
    <label className="check-field"><input type="checkbox" checked={form.active} onChange={(e) => field("active", e.target.checked)} />활성 계량기</label>
    <p className="form-hint">{form.provider === "arisu" ? "새로 등록하면 아리수 연결을 바로 확인합니다." : "기타 공급기관 계량기는 자동으로 수집하지 않습니다."}{isNewStation ? " 새 역은 위치를 지정하기 전까지 노선도에 표시되지 않습니다." : ""}</p>
    {canPosition && <fieldset><legend>노선도 위치</legend><p className="form-hint">같은 역의 계량기는 위치를 함께 씁니다.</p><button type="button" className="secondary-button" onClick={() => setPickPosition((v) => !v)}>{pickPosition ? "노선도 닫기" : "노선도에서 고르기"}</button>
      {pickPosition && <div className="map-picker" onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); setPosition({ x: ((e.clientX - r.left) / r.width * 100).toFixed(2), y: ((e.clientY - r.top) / r.height * 100).toFixed(2) }); }}><img src="/metro_map_rectangle.png" alt="위치 지정용 노선도. 키보드 사용 시 아래 X·Y 입력을 사용하세요." />{position && <span className="map-picker-dot" style={{ left: `${position.x}%`, top: `${position.y}%` }} />}</div>}
      <div className="form-grid"><label className="form-field">가로 X (%)<input type="number" min="0" max="100" step="0.01" value={position?.x ?? ""} placeholder={String(item.map_x ?? "")} onChange={(e) => setPosition((p) => ({ x: e.target.value, y: p?.y ?? "" }))} /></label><label className="form-field">세로 Y (%)<input type="number" min="0" max="100" step="0.01" value={position?.y ?? ""} placeholder={String(item.map_y ?? "")} onChange={(e) => setPosition((p) => ({ x: p?.x ?? "", y: e.target.value }))} /></label></div>
      {position && <button type="button" className="text-button" onClick={() => setPosition(null)}>위치 그대로 두기</button>}</fieldset>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {duplicate && <div className="duplicate-meter"><p>{duplicate.station_name}({duplicate.customer_number}) 계량기가 이미 {duplicate.deleted_at ? "삭제 보관함에 있습니다." : "등록되어 있습니다."}</p><button type="button" className="secondary-button" disabled={busy} onClick={() => onExisting(duplicate)}>{duplicate.deleted_at ? "복원하기" : duplicate.active && duplicate.provider === "arisu" ? "기존 계량기 정보 업데이트" : "기존 계량기 수정"}</button></div>}
    <button className="primary-button" disabled={busy}>{busy ? "저장 중…" : "저장"}</button>
  </form>;
}
