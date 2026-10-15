import { useEffect, useState } from "react";
import {
  Sparkles,
  Download,
  Edit3,
  Trash2,
  Check,
  X,
  ExternalLink,
  AlertTriangle,
  Search,
  CheckSquare,
} from "lucide-react";
import { api } from "../services/api";

export default function TasksView({ onOpenDocument, onExplainItem, focusTaskId }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({
    task: "",
    deadline: "",
    deadline_time: "",
    priority: "LOW",
  });
  const [busyId, setBusyId] = useState(null);

  useEffect(() => {
    let isCurrent = true;
    const fetchTasks = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await api.listTasks(
          statusFilter === "all" ? "" : statusFilter,
          priorityFilter
        );
        if (isCurrent) setTasks(data);
      } catch (err) {
        if (isCurrent) setError(err.message || "Failed to load tasks.");
      } finally {
        if (isCurrent) setLoading(false);
      }
    };

    fetchTasks();
    return () => {
      isCurrent = false;
    };
  }, [statusFilter, priorityFilter]);

  useEffect(() => {
    if (loading || !focusTaskId) return undefined;
    const timer = window.setTimeout(() => {
      document
        .getElementById(`task-card-${focusTaskId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    return () => window.clearTimeout(timer);
  }, [focusTaskId, loading, tasks]);

  const visibleTasks = tasks.filter((task) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return (
      (task.task || "").toLowerCase().includes(q) ||
      (task.document_name || "").toLowerCase().includes(q) ||
      (task.category || "").toLowerCase().includes(q)
    );
  });

  const handleToggle = async (taskId) => {
    setBusyId(taskId);
    try {
      const res = await api.toggleTask(taskId);
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, is_completed: res.is_completed } : t))
      );
    } catch (err) {
      alert(err.message || "Failed to update task completion.");
    } finally {
      setBusyId(null);
    }
  };

  const startEdit = (task) => {
    setEditingId(task.id);
    setEditDraft({
      task: task.task || "",
      deadline: task.deadline || "",
      deadline_time: task.deadline_time || "",
      priority: task.priority || "LOW",
    });
  };

  const saveEdit = async (taskId) => {
    setBusyId(taskId);
    try {
      const updated = await api.updateTask(taskId, {
        task: editDraft.task.trim(),
        deadline: editDraft.deadline.trim(),
        deadline_time: editDraft.deadline_time.trim(),
        priority: editDraft.priority,
        review_status: "corrected",
      });
      setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, ...updated } : t)));
      setEditingId(null);
    } catch (err) {
      alert(err.message || "Failed to save task.");
    } finally {
      setBusyId(null);
    }
  };

  const setReview = async (taskId, review_status) => {
    setBusyId(taskId);
    try {
      const updated = await api.updateTask(taskId, { review_status });
      setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, ...updated } : t)));
    } catch (err) {
      alert(err.message || "Failed to update review status.");
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (taskId) => {
    if (!window.confirm("Delete this task permanently?")) return;
    setBusyId(taskId);
    try {
      await api.deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (err) {
      alert(err.message || "Failed to delete task.");
    } finally {
      setBusyId(null);
    }
  };

  const handleExport = async () => {
    try {
      const blob = await api.exportTasksCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "docuguard_tasks.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message || "Export failed.");
    }
  };

  return (
    <section className="tasks-view-section page-width">
      <div className="section-header-row">
        <div>
          <span className="section-kicker">CENTRAL ACTION CENTER</span>
          <h2>All Actionable Tasks</h2>
          <p>
            Unified task manager for actions extracted across your documents. Review and correct
            items before relying on them — confidence is a heuristic score, not a calibrated
            probability.
          </p>
        </div>
        <button className="secondary-button" type="button" onClick={handleExport}>
          <Download size={14} />
          <span>Export CSV</span>
        </button>
      </div>

      <div className="filters-bar-horizontal">
        <div className="tab-filters">
          {[
            ["all", "All"],
            ["pending", "Pending"],
            ["completed", "Completed"],
            ["overdue", "Overdue"],
            ["undated", "Undated"],
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

        <div className="priority-filters" style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
          <div className="search-input-wrapper mini">
            <Search size={14} className="search-icon" />
            <input
              type="search"
              placeholder="Search tasks…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search tasks"
            />
            {search && (
              <button className="clear-search" onClick={() => setSearch("")} type="button">
                <X size={12} />
              </button>
            )}
          </div>
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="sort-control-select"
            aria-label="Filter by priority"
          >
            <option value="">All Priorities</option>
            <option value="HIGH">High Priority</option>
            <option value="MEDIUM">Medium Priority</option>
            <option value="LOW">Low Priority</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className="workspace-loading">
          <span className="spinner" />
          <p>Loading tasks…</p>
        </div>
      ) : error ? (
        <div className="upload-error" role="alert">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      ) : visibleTasks.length === 0 ? (
        <div className="empty-state-card">
          <span className="empty-icon">
            <CheckSquare size={32} />
          </span>
          <h3>No tasks match your selected filter</h3>
          <p>All actions are accounted for or no documents have been analyzed yet.</p>
        </div>
      ) : (
        <div className="task-grid">
          {visibleTasks.map((task) => {
            const isCompleted = task.is_completed;
            const priority = ["HIGH", "MEDIUM", "LOW"].includes(task.priority)
              ? task.priority
              : "LOW";
            const isEditing = editingId === task.id;

            return (
              <article
                className={`task-card ${isCompleted ? "completed" : ""}`}
                id={`task-card-${task.id}`}
                key={task.id}
              >
                <div className="task-top">
                  <span className={`priority ${priority.toLowerCase()}`}>{priority}</span>
                  <div className="task-top-right">
                    <span className="confidence" title="Heuristic score, not a calibrated probability">
                      {Math.round((task.confidence ?? 0.8) * 100)}% heuristic
                    </span>
                    <button
                      className="why-link"
                      onClick={() => onExplainItem(task, "Actionable Task")}
                      type="button"
                    >
                      <Sparkles size={12} />
                      <span>Why detected?</span>
                    </button>
                  </div>
                </div>

                {isEditing ? (
                  <div className="task-edit-form" style={{ display: "grid", gap: "8px" }}>
                    <label>
                      <span className="sr-only">Task text</span>
                      <textarea
                        value={editDraft.task}
                        onChange={(e) => setEditDraft((d) => ({ ...d, task: e.target.value }))}
                        rows={3}
                        style={{ width: "100%" }}
                      />
                    </label>
                    <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                      <input
                        type="date"
                        value={editDraft.deadline}
                        onChange={(e) => setEditDraft((d) => ({ ...d, deadline: e.target.value }))}
                        aria-label="Due date"
                      />
                      <input
                        type="time"
                        value={editDraft.deadline_time}
                        onChange={(e) => setEditDraft((d) => ({ ...d, deadline_time: e.target.value }))}
                        aria-label="Due time"
                      />
                      <select
                        value={editDraft.priority}
                        onChange={(e) => setEditDraft((d) => ({ ...d, priority: e.target.value }))}
                        aria-label="Priority"
                      >
                        <option value="HIGH">HIGH</option>
                        <option value="MEDIUM">MEDIUM</option>
                        <option value="LOW">LOW</option>
                      </select>
                    </div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        className="primary-button mini"
                        type="button"
                        disabled={busyId === task.id}
                        onClick={() => saveEdit(task.id)}
                      >
                        Save
                      </button>
                      <button
                        className="secondary-button mini"
                        type="button"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <h3>{task.task}</h3>
                )}

                <div className="task-info">
                  <div>
                    <span>Deadline</span>
                    <strong>
                      {task.deadline
                        ? `${task.deadline}${task.deadline_time ? ` at ${task.deadline_time}` : ""}`
                        : "Not specified"}
                      {task.date_explicit ? " · explicit" : task.deadline ? " · associated" : ""}
                    </strong>
                  </div>
                  <div>
                    <span>Category</span>
                    <strong>{task.category || "General"}</strong>
                  </div>
                  <div>
                    <span>Review</span>
                    <strong className={`review-badge-text ${task.review_status || "pending"}`}>{task.review_status || "pending"}</strong>
                  </div>
                  {task.page_number ? (
                    <div>
                      <span>Page</span>
                      <strong>{task.page_number}</strong>
                    </div>
                  ) : null}
                </div>

                {task.source_snippet ? (
                  <p className="task-evidence">
                    Evidence: “{task.source_snippet}”
                  </p>
                ) : null}

                <div className="task-source-doc">
                  <span>Document: </span>
                  <button
                    className="doc-link-button"
                    onClick={() => onOpenDocument(task.document_id)}
                    type="button"
                  >
                    <span>{task.document_name}</span>
                    <ExternalLink size={12} />
                  </button>
                </div>

                <div className="task-card-actions">
                  <button
                    className={`complete-button ${isCompleted ? "is-complete" : ""}`}
                    onClick={() => handleToggle(task.id)}
                    type="button"
                    disabled={busyId === task.id}
                  >
                    {isCompleted ? (
                      <>
                        <Check size={14} />
                        <span>Completed</span>
                      </>
                    ) : (
                      <span>Mark as complete</span>
                    )}
                  </button>
                  {!isEditing ? (
                    <button className="secondary-button mini" type="button" onClick={() => startEdit(task)}>
                      <Edit3 size={13} />
                      <span>Edit</span>
                    </button>
                  ) : null}
                  <button
                    className="secondary-button mini accept-btn"
                    type="button"
                    disabled={busyId === task.id}
                    onClick={() => setReview(task.id, "accepted")}
                    title="Accept detection"
                  >
                    Accept
                  </button>
                  <button
                    className="secondary-button mini reject-btn"
                    type="button"
                    disabled={busyId === task.id}
                    onClick={() => setReview(task.id, "rejected")}
                    title="Reject detection"
                  >
                    Reject
                  </button>
                  <button
                    className="secondary-button mini delete-action-btn"
                    type="button"
                    disabled={busyId === task.id}
                    onClick={() => handleDelete(task.id)}
                    title="Delete task"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
