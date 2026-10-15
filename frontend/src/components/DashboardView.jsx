import {
  AlertTriangle,
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock3,
  FileText,
  ListTodo,
  RefreshCw,
  Sparkles,
  UploadCloud,
} from "lucide-react";

export default function DashboardView({
  user,
  stats,
  loading,
  error,
  onRetry,
  onQuickUploadClick,
  onOpenDocument,
  onNavigate,
  onExplainItem,
}) {
  const firstName = user?.full_name?.trim().split(/\s+/)[0] || "there";
  const recentDocuments = stats?.recent_documents ?? [];
  const upcomingDeadlines = stats?.upcoming_deadline_items ?? [];
  const pendingTasks = stats?.pending_tasks ?? 0;
  const completedTasks = stats?.completed_tasks ?? 0;
  const totalTasks = pendingTasks + completedTasks;
  const completionPercent = totalTasks
    ? Math.round((completedTasks / totalTasks) * 100)
    : 0;
  const hasDocuments = (stats?.total_documents ?? 0) > 0;

  if (loading && !stats) {
    return (
      <div className="workspace-loading page-width" role="status" aria-live="polite">
        <span className="spinner" />
        <p>Loading your document workspace…</p>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <section className="dashboard-section page-width">
        <div className="dashboard-error" role="alert">
          <span className="dashboard-error-icon"><AlertTriangle size={20} /></span>
          <div>
            <h2>Your workspace didn’t load</h2>
            <p>{error}</p>
          </div>
          <button className="secondary-button" onClick={onRetry} type="button">
            <RefreshCw size={15} />
            <span>Try again</span>
          </button>
        </div>
      </section>
    );
  }

  return (
    <section className="dashboard-section page-width">
      <header className="dashboard-hero-strip">
        <div>
          <span className="section-kicker">YOUR WORKSPACE</span>
          <h1>Welcome back, {firstName}</h1>
          <p className="dashboard-subtitle">
            Keep track of the documents, actions, and deadlines that need your attention.
          </p>
        </div>
        <div className="dashboard-hero-actions">
          <button className="primary-button" onClick={onQuickUploadClick} type="button">
            <UploadCloud size={16} />
            <span>Analyze a document</span>
          </button>
          <button
            className="dashboard-secondary-action"
            onClick={() => onNavigate("tasks")}
            type="button"
          >
            View tasks <ArrowRight size={15} />
          </button>
        </div>
      </header>

      {error && (
        <div className="dashboard-inline-error" role="alert">
          <AlertTriangle size={16} />
          <span>Some workspace data may be out of date. {error}</span>
          <button onClick={onRetry} type="button">Retry</button>
        </div>
      )}

      <div className="metrics dashboard-metrics" aria-label="Workspace summary">
        <button
          className="metric-card dashboard-metric"
          onClick={() => onNavigate("documents")}
          type="button"
        >
          <span className="metric-icon"><FileText size={19} /></span>
          <span><small>Documents</small><strong>{stats?.total_documents ?? 0}</strong></span>
          <ChevronRight size={16} className="dashboard-metric-arrow" />
        </button>
        <button
          className="metric-card dashboard-metric"
          onClick={() => onNavigate("tasks")}
          type="button"
        >
          <span className="metric-icon"><ListTodo size={19} /></span>
          <span><small>Tasks to do</small><strong>{pendingTasks}</strong></span>
          <ChevronRight size={16} className="dashboard-metric-arrow" />
        </button>
        <button
          className="metric-card dashboard-metric"
          onClick={() => onNavigate("deadlines")}
          type="button"
        >
          <span className="metric-icon"><CalendarDays size={19} /></span>
          <span><small>Upcoming deadlines</small><strong>{stats?.upcoming_deadlines ?? 0}</strong></span>
          <ChevronRight size={16} className="dashboard-metric-arrow" />
        </button>
        <button
          className={`metric-card dashboard-metric ${stats?.overdue_deadlines ? "is-overdue" : ""}`}
          onClick={() => onNavigate("deadlines")}
          type="button"
        >
          <span className="metric-icon"><AlertTriangle size={19} /></span>
          <span><small>Overdue</small><strong>{stats?.overdue_deadlines ?? 0}</strong></span>
          <ChevronRight size={16} className="dashboard-metric-arrow" />
        </button>
      </div>

      <section className="dashboard-progress-panel" aria-labelledby="task-progress-heading">
        <div className="dashboard-progress-copy">
          <div>
            <span className="section-kicker">TASK PROGRESS</span>
            <h2 id="task-progress-heading">
              {totalTasks ? `${completedTasks} of ${totalTasks} tasks complete` : "Your task list is clear"}
            </h2>
          </div>
          <strong className="dashboard-progress-percent">{completionPercent}%</strong>
        </div>
        <div
          className="dashboard-progress-track"
          role="progressbar"
          aria-label="Tasks completed"
          aria-valuenow={completionPercent}
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <span style={{ width: `${completionPercent}%` }} />
        </div>
        <p>
          {totalTasks
            ? `${pendingTasks} ${pendingTasks === 1 ? "task" : "tasks"} still need${pendingTasks === 1 ? "s" : ""} attention.`
            : "Tasks extracted from your documents will appear here."}
        </p>
      </section>

      {!hasDocuments ? (
        <div className="empty-state-card dashboard-empty-state">
          <span className="empty-icon"><FileText size={28} /></span>
          <h2>Your workspace starts with a document</h2>
          <p>
            Upload a notice, circular, or policy PDF to organize its tasks, deadlines, and requirements here.
          </p>
          <button className="primary-button" onClick={onQuickUploadClick} type="button">
            <UploadCloud size={16} />
            <span>Analyze your first document</span>
          </button>
        </div>
      ) : (
        <div className="dashboard-grid">
          <section className="dashboard-card dashboard-documents-card" aria-labelledby="recent-documents-heading">
            <div className="dashboard-card-header">
              <div>
                <span className="section-kicker">DOCUMENTS</span>
                <h2 id="recent-documents-heading">Recently added</h2>
              </div>
              <button className="text-button" onClick={() => onNavigate("documents")} type="button">
                <span>All documents</span><ArrowRight size={14} />
              </button>
            </div>

            {recentDocuments.length ? (
              <ul className="recent-docs-list">
                {recentDocuments.map((doc) => (
                  <li className="recent-doc-item" key={doc.id}>
                    <span className="pdf-badge" aria-hidden="true">PDF</span>
                    <div className="recent-doc-copy">
                      <strong title={doc.filename}>{doc.filename}</strong>
                      <small>
                        {doc.document_type.replaceAll("_", " ")} · {doc.pages} page
                        {doc.pages === 1 ? "" : "s"} ·{" "}
                        {new Date(doc.upload_timestamp).toLocaleDateString()}
                      </small>
                    </div>
                    <span className="doc-pill" aria-label={`${doc.completed_task_count} of ${doc.task_count} tasks complete`}>
                      {doc.completed_task_count}/{doc.task_count} done
                    </span>
                    <button
                      className="recent-doc-open"
                      onClick={() => onOpenDocument(doc.id)}
                      type="button"
                      aria-label={`Open ${doc.filename}`}
                    >
                      <ChevronRight size={17} />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="dashboard-list-empty">No recent documents to show.</p>
            )}
          </section>

          <section className="dashboard-card dashboard-deadlines-card" aria-labelledby="upcoming-deadlines-heading">
            <div className="dashboard-card-header">
              <div>
                <span className="section-kicker">WHAT’S NEXT</span>
                <h2 id="upcoming-deadlines-heading">Upcoming deadlines</h2>
              </div>
              <button className="text-button" onClick={() => onNavigate("deadlines")} type="button">
                <span>All deadlines</span><ArrowRight size={14} />
              </button>
            </div>

            {upcomingDeadlines.length ? (
              <ul className="upcoming-deadlines-list">
                {upcomingDeadlines.map((deadline) => (
                  <li className="deadline-item-row" key={deadline.id}>
                    <span className={`dashboard-deadline-date ${deadline.is_overdue ? "is-overdue" : ""}`}>
                      <Clock3 size={15} />
                      <span>{deadline.deadline_date}{deadline.deadline_time ? ` · ${deadline.deadline_time}` : ""}</span>
                    </span>
                    <div className="deadline-copy">
                      <p>{deadline.description}</p>
                      <small>{deadline.document_name}</small>
                    </div>
                    <button
                      className="why-link"
                      onClick={() => onExplainItem(deadline, "Deadline")}
                      type="button"
                    >
                      <Sparkles size={13} />
                      <span>Why detected?</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-substate">
                <CheckCircle2 size={20} className="empty-check-icon" />
                <p>No pending deadlines. You’re all caught up.</p>
              </div>
            )}

            <div className="dashboard-rules-summary">
              <span className="section-kicker">REQUIREMENTS FOUND</span>
              <div>
                <span><strong>{stats?.mandatory_rules ?? 0}</strong> Mandatory</span>
                <span><strong>{stats?.prohibited_rules ?? 0}</strong> Prohibited</span>
                <span><strong>{stats?.recommended_rules ?? 0}</strong> Recommended</span>
              </div>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
