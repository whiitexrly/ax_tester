import { useMemo, useState } from "react";
import rawReports from "../results.json";
import FilterBar from "./components/FilterBar";
import Header from "./components/Header";
import IssuesTable from "./components/IssuesTable";
import KpiGrid from "./components/KpiGrid";
import PourChart from "./components/PourChart";
import IssueByWcagChart from "./components/IssueByWcagChart";
import { buildDashboardData, normalizeReports } from "./lib/reportUtils";

function App() {
  const reports = useMemo(() => normalizeReports(rawReports), []);
  const [selectedPage, setSelectedPage] = useState("all");
  const [searchTerm, setSearchTerm] = useState("");

  const dashboard = useMemo(
    () => buildDashboardData(reports, selectedPage, searchTerm),
    [reports, selectedPage, searchTerm],
  );

  return (
    <div className="app-shell">
      <Header generatedAt={dashboard.generatedAt} />

      <main className="content-wrap">
        <FilterBar
          pageOptions={dashboard.pageOptions}
          selectedPage={selectedPage}
          onPageChange={setSelectedPage}
        />

        <KpiGrid kpis={dashboard.kpis} score={dashboard.score} />

        <section className="chart-grid">
          <IssueByWcagChart score={dashboard.score} />
          <PourChart items={dashboard.principleDistribution} />
        </section>

        <IssuesTable rows={dashboard.visibleIssues} searchTerm={searchTerm} onSearchChange={setSearchTerm} />
      </main>
    </div>
  );
}

export default App;
