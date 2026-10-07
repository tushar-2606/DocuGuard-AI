export default function DashboardView({
  user,
  stats,
  loading,
  onQuickUploadClick,
  onOpenDocument,
  onNavigate,
  onExplainItem,
}) {
  const firstName = user?.full_name ? user.full_name.split(" ")[0] : "there";

  if (loading && !stats) {
    return (
      <div className="workspace-loading page-width">
        <span className="spinner" />
        <p>Loading your document workspace…</p>
      </div>
    );
  }

  const hasData = (stats?.total_documents ?? 0) > 0;

  return (
    <section className="dashboard-section page-width">
      <div className="dashboard-hero-strip">
        <div>
          <span className="section-kicker">PERSONALIZED WORKSPACE</span>
          <h1>Welcome back, {firstName}</h1>
          <p className="dashboard-subtitle">
            Overview of your active notices, extracted actions, and compliance obligations.
          </p>
        </div>
        <div className="dashboard-hero-actions">
          <button className="primary-button" onClick={onQuickUploadClick} type="button">
            ↑ Analyze New Document
          </button>
        </div>
      </div>

      {/* Real Statistics Metrics */}
      <div className="metrics dashboard-metrics">
        <article
          className="metric-card blue"
          onClick={() => onNavigate("documents")}
          style={{ cursor: "pointer" }}
        >
          <span className="metric-icon">▤</span>
          <span>
            <small>Total Documents</small>
            <strong>{stats?.total_documents ?? 0}</strong>
          </span>
        </article>
        <article
          className="metric-card purple"
          onClick={() => onNavigate("tasks")}
          style={{ cursor: "pointer" }}
        >
          <span className="metric-icon">✓</span>
          <span>
            <small>Pending Tasks</small>
            <strong>{stats?.pending_tasks ?? 0}</strong>
          </span>
        </article>
        <article
          className="metric-card orange"
          onClick={() => onNavigate("deadlines")}
          style={{ cursor: "pointer" }}
        >
          <span className="metric-icon">◷</span>
          <span>
            <small>Upcoming Deadlines</small>
            <strong>{stats?.upcoming_deadlines ?? 0}</strong>
          </span>
        </article>
        <article
          className="metric-card red"
          onClick={() => onNavigate("rules")}
          style={{ cursor: "pointer" }}
        >
          <span className="metric-icon">!</span>
          <span>
            <small>Mandatory Rules</small>
            <strong>{stats?.mandatory_rules ?? 0}</strong>
          </span>
        </article>
        <article
          className="metric-card green"
          onClick={() => onNavigate("rules")}
          style={{ cursor: "pointer" }}
        >
          <span className="metric-icon">◈</span>
          <span>
            <small>Prohibited Rules</small>
            <strong>{stats?.prohibited_rules ?? 0}</strong>
          </span>
        </article>
      </div>

      {!hasData ? (
        <div className="empty-state-card">
          <span className="empty-icon">▤</span>
          <h3>No documents in your workspace yet</h3>
          <p>
            Upload your first circular, university notice, or compliance PDF above to automatically
            extract tasks, deadlines, and mandatory rules.
          </p>
          <button className="primary-button" onClick={onQuickUploadClick} type="button">
            Upload Your First Document
          </button>
        </div>
      ) : (
        <div className="dashboard-grid">
          {/* Recent Documents Column */}
          <div className="dashboard-card">
            <div className="dashboard-card-header">
              <div>
                <span className="section-kicker">DOCUMENTS</span>
                <h3>Recent Documents</h3>
              </div>
              <button
                className="text-button"
                onClick={() => onNavigate("documents")}
                type="button"
              >
                View All ({stats.total_documents}) →
              </button>
            </div>

            <div className="recent-docs-list">
              {stats.recent_documents.map((doc) => (
                <article className="recent-doc-item" key={doc.id}>
                  <div className="recent-doc-left">
                    <span className="pdf-badge">PDF</span>
                    <div>
                      <strong>{doc.filename}</strong>
                      <small>
                        {doc.document_type.replaceAll("_", " ")} · {doc.pages} page
                        {doc.pages === 1 ? "" : "s"} ·{" "}
                        {new Date(doc.upload_timestamp).toLocaleDateString()}
                      </small>
                    </div>
                  </div>
                  <div className="recent-doc-right">
                    <span className="doc-pill">
                      {doc.completed_task_count}/{doc.task_count} tasks
                    </span>
                    <button
                      className="secondary-button mini-button"
                      onClick={() => onOpenDocument(doc.id)}
                      type="button"
                    >
                      Open
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </div>

          {/* Upcoming Deadlines Column */}
          <div className="dashboard-card">
            <div className="dashboard-card-header">
              <div>
                <span className="section-kicker">TIMELINE</span>
                <h3>Upcoming Deadlines</h3>
              </div>
              <button
                className="text-button"
                onClick={() => onNavigate("deadlines")}
                type="button"
              >
                View All →
              </button>
            </div>

            {stats.upcoming_deadline_items?.length ? (
              <div className="upcoming-deadlines-list">
                {stats.upcoming_deadline_items.map((dl) => (
                  <article className="deadline-item-row" key={dl.id}>
                    <div className="deadline-date-pill">
                      <strong>{dl.deadline_date}</strong>
                      <small>{dl.is_overdue ? "OVERDUE" : "UPCOMING"}</small>
                    </div>
                    <div className="deadline-copy">
                      <p>{dl.description}</p>
                      <small>From: {dl.document_name}</small>
                    </div>
                    <button
                      className="why-link"
                      onClick={() => onExplainItem(dl, "Deadline")}
                      type="button"
                    >
                      Why detected?
                    </button>
                  </article>
                ))}
              </div>
            ) : (
              <div className="empty-substate">
                <span>✓</span>
                <p>No pending deadlines right now. You're all caught up!</p>
              </div>
            )}

            {/* Quick Rules Snapshot */}
            <div className="rules-snapshot-footer">
              <span className="section-kicker">RULES SNAPSHOT</span>
              <div className="rules-snapshot-counts">
                <div>
                  <strong>{stats.mandatory_rules}</strong>
                  <small>Mandatory Requirements</small>
                </div>
                <div>
                  <strong>{stats.prohibited_rules}</strong>
                  <small>Strict Prohibitions</small>
                </div>
                <div>
                  <strong>{stats.recommended_rules}</strong>
                  <small>Recommended Guidelines</small>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
