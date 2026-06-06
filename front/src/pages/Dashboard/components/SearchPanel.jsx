import SectionTitle from "./SectionTitle.jsx";

export default function SearchPanel({ searchTerm, setSearchTerm }) {
  return (
    <section className="search-panel" aria-label="역명 검색">
      <SectionTitle title="역명 검색" />
      <div className="search-panel-body">
        <div className="field search-field">
          <label htmlFor="station-search">검색어</label>
          <input
            id="station-search"
            type="search"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="예: 강남, 서울역"
            autoComplete="off"
          />
        </div>
      </div>
    </section>
  );
}
