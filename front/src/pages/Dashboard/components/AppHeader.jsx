export default function AppHeader({ logo, user, hash, onLogout, onSummary }) {
  return (
    <header className="topbar">
      <div className="brand">
        <img src={logo} alt="서울교통공사" className="brand-logo" />
        <span className="brand-divider" />
        <span className="brand-text">
          <strong>상수도 이상징후 관제</strong>
        </span>
      </div>
      <nav className="topnav" aria-label="화면 구분">
        <a className={hash === "#/" || hash === "" ? "is-active" : ""} href="#/">전체 현황</a>
        <a className={hash.startsWith("#/detail") ? "is-active" : ""} href="#/detail">역 상세</a>
        <a className={hash.startsWith("#/statistics") ? "is-active" : ""} href="#/statistics">통계</a>
        <a className={hash.startsWith("#/meters") ? "is-active" : ""} href="#/meters">계량기 관리</a>
        {user.role === "superadmin" && <a className={hash.startsWith("#/users") ? "is-active" : ""} href="#/users">사용자 관리</a>}
      </nav>
      <div className="account-actions">
        <button type="button" onClick={onSummary}>업무 요약</button>
        <a href="#/account" title={user.email}>{user.name} <span>{user.role === "superadmin" ? "총괄" : "사업소"}</span></a>
        <button type="button" onClick={onLogout}>로그아웃</button>
      </div>
    </header>
  );
}
