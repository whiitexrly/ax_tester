import { formatDateLabel } from "../lib/reportUtils";

function Header({ generatedAt }) {
  return (
    <header className="topbar">
      <div className="title-group">
        <p className="eyebrow">Accessibility Audit</p>
        <h1>Issues Dashboard</h1>
        <p className="subtitle">Aggregated view of issues detected by AX Tester agent</p>
      </div>
      <div className="topbar-meta">
        <span className="meta-label">Generated</span>
        <strong>{formatDateLabel(generatedAt)}</strong>
      </div>
    </header>
  );
}

export default Header;
