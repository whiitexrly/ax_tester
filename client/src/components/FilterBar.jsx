function FilterBar({ pageOptions, selectedPage, onPageChange }) {
  return (
    <section className="panel filter-panel" aria-label="Report filters">
      <div className="field-group">
        <label htmlFor="page-filter">Page</label>
        <select id="page-filter" value={selectedPage} onChange={(event) => onPageChange(event.target.value)}>
          <option value="all">All pages</option>
          {pageOptions.map((page) => (
            <option key={page} value={page}>
              {page}
            </option>
          ))}
        </select>
      </div>
    </section>
  );
}

export default FilterBar;
