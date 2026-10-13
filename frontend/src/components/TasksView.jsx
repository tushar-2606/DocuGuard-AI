import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function TasksView({ onOpenDocument, onExplainItem }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editDraft, setEditDraft] = useState({ task: "", deadline: "", priority: "LOW" });
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
      priority: task.priority || "LOW",
    });
  };

  const saveEdit = async (taskId) => {
    setBusyId(taskId);
    try {
      const updated = await api.updateTask(taskId, {
        task: editDraft.task.trim(),
        deadline: editDraft.deadline.trim(),
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
          Export CSV
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

        <div className="priority-filters" style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <input
            className="sort-control-select"
            type="search"
            placeholder="Search tasks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search tasks"
          />
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
          ⚠ {error}
        </div>
      ) : visibleTasks.length === 0 ? (
        <div className="empty-state-card">
          <span className="empty-icon">✓</span>
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
                      Why detected?
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
                        className="primary-button"
                        type="button"
                        disabled={busyId === task.id}
                        onClick={() => saveEdit(task.id)}
                      >
                        Save
                      </button>
                      <button
                        className="secondary-button"
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
                      {task.deadline || "Not specified"}
                      {task.date_explicit ? " · explicit" : task.deadline ? " · associated" : ""}
                    </strong>
                  </div>
                  <div>
                    <span>Category</span>
                    <strong>{task.category || "General"}</strong>
                  </div>
                  <div>
                    <span>Review</span>
                    <strong>{task.review_status || "pending"}</strong>
                  </div>
                  {task.page_number ? (
                    <div>
                      <span>Page</span>
                      <strong>{task.page_number}</strong>
                    </div>
                  ) : null}
                </div>

                {task.source_snippet ? (
                  <p className="task-evidence" style={{ fontSize: "12px", opacity: 0.85 }}>
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
                    {task.document_name}
                  </button>
                </div>

                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginTop: "10px" }}>
                  <button
                    className={`complete-button ${isCompleted ? "is-complete" : ""}`}
                    onClick={() => handleToggle(task.id)}
                    type="button"
                    disabled={busyId === task.id}
                  >
                    {isCompleted ? "✓ Completed" : "Mark as complete"}
                  </button>
                  {!isEditing ? (
                    <button className="secondary-button" type="button" onClick={() => startEdit(task)}>
                      Edit
                    </button>
                  ) : null}
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busyId === task.id}
                    onClick={() => setReview(task.id, "accepted")}
                  >
                    Accept
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busyId === task.id}
                    onClick={() => setReview(task.id, "rejected")}
                  >
                    Reject
                  </button>
                  <button
                    className="secondary-button"
                    type="button"
                    disabled={busyId === task.id}
                    onClick={() => handleDelete(task.id)}
                  >
                    Delete
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
