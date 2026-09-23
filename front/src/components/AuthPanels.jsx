import { useState } from "react";
import { changePassword, login } from "../api.js";
import logo from "../assets/seoulmetro.svg";

export function LoginPage({ setupRequired, onLogin, error: connectionError, onRetry }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    setBusy(true); setError("");
    try { await onLogin(await login(email.trim(), password)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <main className="auth-page">
    <section className="auth-card">
      <img src={logo} className="auth-logo" alt="서울교통공사" />
      <span className="auth-eyebrow">상수도 이상징후 관제</span>
      <h1>{setupRequired ? "관리자 설정이 필요합니다" : "담당자 로그인"}</h1>
      {setupRequired ? <>
        <p>서버 관리자가 환경 설정을 완료하면 사용할 수 있습니다.</p>
        <p className="setup-note"><code>.env</code>에 <code>ADMIN_EMAIL</code>과 <code>ADMIN_PASSWORD</code>를 설정한 뒤 서버를 다시 시작하세요.</p>
        <button type="button" className="primary-button" onClick={onRetry}>설정 다시 확인</button>
      </> : <form onSubmit={submit}>
        <p>등록된 직원 계정으로 소속 사업소의 자료를 확인하세요.</p>
        <label className="form-field">이메일<input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="form-field">비밀번호<input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="primary-button" disabled={busy}>{busy ? "로그인 중…" : "로그인"}</button>
        <p className="auth-note">계정 발급·비밀번호 초기화는 총괄 관리자에게 요청하세요.</p>
      </form>}
      {connectionError && <div className="form-error" role="alert">{connectionError} <button className="text-button" onClick={onRetry}>다시 연결</button></div>}
    </section>
  </main>;
}

export function PasswordPage({ user, onChanged }) {
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault();
    if (password !== confirm) { setMessage("새 비밀번호가 서로 일치하지 않습니다."); return; }
    setBusy(true); setMessage("");
    try {
      await changePassword({ current_password: current, new_password: password });
      setCurrent(""); setPassword(""); setConfirm("");
      setMessage("비밀번호를 변경했습니다.");
      await onChanged();
    } catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  }
  return <main className="management-page"><section className="management-card account-card">
    <h1>내 계정</h1><p>{user.name} · {user.email}</p>
    {user.must_change_password && <p className="data-notice">처음 로그인했거나 비밀번호가 초기화되었습니다. 새 비밀번호를 설정한 뒤 관제 화면을 사용할 수 있습니다.</p>}
    <form onSubmit={submit}>
      <label className="form-field">현재 비밀번호<input type="password" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} /></label>
      <label className="form-field">새 비밀번호<input type="password" minLength={12} autoComplete="new-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
      <label className="form-field">새 비밀번호 확인<input type="password" minLength={12} autoComplete="new-password" required value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
      <p className="form-hint">12자 이상으로 입력하세요.</p>
      {message && <p role="status" className="form-message">{message}</p>}
      <button className="primary-button" disabled={busy}>{busy ? "변경 중…" : "비밀번호 변경"}</button>
    </form>
  </section></main>;
}
