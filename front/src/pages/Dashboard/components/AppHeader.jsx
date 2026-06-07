export default function AppHeader({ logo }) {
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
        <a className="is-active" href="#/">전체 현황</a>
        <a href="#/detail">역 상세</a>
      </nav>
    </header>
  );
}
