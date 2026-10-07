import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function DeadlinesView({ onOpenDocument, onExplainItem }) {
  const [deadlines, setDeadlines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    let isCurrent = true;
    const fetchDeadlines = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await api.listDeadlines(statusFilter === "all" ? "" : statusFilter);
        if (isCurrent) setDeadlines(data);
      } catch (err) {
        if (isCurrent) setError(err.message || "Failed to load deadlines.");
      } finally {
        if (isCurrent) setLoading(false);
      }
    };

    fetchDeadlines();
    return () => {
      isCurrent = false;
    };
  }, [statusFilter]);

  const handleToggle = async (dlId) => {
    try {
      const res = await api.toggleDeadline(dlId);
      setDeadlines((prev) =>
        prev.map((d) => (d.id === dlId ? { ...d, is_completed: res.is_completed } : d))
      );
    } catch (err) {
      alert(err.message || "Failed to toggle deadline.");
    }
  };

  return (
    <section className="deadlines-view-section page-width">
      <div className="section-header-row">
        <div>
          <span className="section-kicker">CHRONOLOGICAL RADAR</span>
          <h2>Institutional Deadlines</h2>
          <p>Time-sensitive submissions, payment due dates, and registration windows.</p>
        </div>
      </div>

      <div className="filters-bar-horizontal">
        <div className="tab-filters">
          {[
            ["all", "All Deadlines"],
            ["upcoming", "Upcoming"],
            ["overdue", "Overdue"],
          ].map(([val, label]) => (
            <button
              className={`filter-pill ${statusFilter === val ? "active" : ""}`}
              key={val}
              onClick={() => setStatusFilter(val)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="workspace-loading">
          <span className="spinner" />
          <p>Loading deadlines…</p>
        </div>
      ) : error ? (
        <div className="upload-error" role="alert">
          ⚠ {error}
        </div>
      ) : deadlines.length === 0 ? (
        <div className="empty-state-card">
          <span className="empty-icon">◷</span>
          <h3>No deadlines found</h3>
          <p>No time-sensitive deadlines match your current filter.</p>
        </div>
      ) : (
        <div className="deadlines-list-grid">
          {deadlines.map((dl) => (
            <article
              className={`deadline-card ${dl.is_completed ? "completed" : dl.is_overdue ? "overdue" : ""}`}
              key={dl.id}
            >
              <div className="deadline-card-header">
                <div className="deadline-date-pill large">
                  <strong>{dl.deadline_date}</strong>
                  <span className={dl.is_overdue ? "badge-overdue" : "badge-upcoming"}>
                    {dl.is_completed ? "COMPLETED" : dl.is_overdue ? "OVERDUE" : "UPCOMING"}
                  </span>
                </div>
                <button
                  className="why-link"
                  onClick={() => onExplainItem(dl, "Deadline")}
                  type="button"
                >
                  Why detected?
                </button>
              </div>

              <h3>{dl.description}</h3>

              <div className="deadline-card-footer">
                <div>
                  <span>Source Document: </span>
                  <button
                    className="doc-link-button"
                    onClick={() => onOpenDocument(dl.document_id)}
                    type="button"
                  >
                    {dl.document_name}
                  </button>
                </div>
                <button
                  className={`complete-button mini ${dl.is_completed ? "is-complete" : ""}`}
                  onClick={() => handleToggle(dl.id)}
                  type="button"
                >
                  {dl.is_completed ? "✓ Met" : "Mark as Met"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
