import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function TasksView({ onOpenDocument, onExplainItem }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("");

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

  const handleToggle = async (taskId) => {
    try {
      const res = await api.toggleTask(taskId);
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, is_completed: res.is_completed } : t))
      );
    } catch (err) {
      alert(err.message || "Failed to update task completion.");
    }
  };

  return (
    <section className="tasks-view-section page-width">
      <div className="section-header-row">
        <div>
          <span className="section-kicker">CENTRAL ACTION CENTER</span>
          <h2>All Actionable Tasks</h2>
          <p>Unified task manager tracking actions extracted across all your uploaded documents.</p>
        </div>
      </div>

      <div className="filters-bar-horizontal">
        <div className="tab-filters">
          {[
            ["all", "All Tasks"],
            ["pending", "Pending"],
            ["completed", "Completed"],
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

        <div className="priority-filters">
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="sort-control-select"
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
      ) : tasks.length === 0 ? (
        <div className="empty-state-card">
          <span className="empty-icon">✓</span>
          <h3>No tasks match your selected filter</h3>
          <p>All actions are accounted for or no documents have been analyzed yet.</p>
        </div>
      ) : (
        <div className="task-grid">
          {tasks.map((task) => {
            const isCompleted = task.is_completed;
            const priority = ["HIGH", "MEDIUM", "LOW"].includes(task.priority)
              ? task.priority
              : "LOW";

            return (
              <article
                className={`task-card ${isCompleted ? "completed" : ""}`}
                key={task.id}
              >
                <div className="task-top">
                  <span className={`priority ${priority.toLowerCase()}`}>{priority}</span>
                  <div className="task-top-right">
                    <span className="confidence">
                      {Math.round((task.confidence ?? 0.8) * 100)}% confidence
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

                <h3>{task.task}</h3>

                <div className="task-info">
                  <div>
                    <span>Deadline</span>
                    <strong>{task.deadline || "Not specified"}</strong>
                  </div>
                  <div>
                    <span>Category</span>
                    <strong>{task.category || "General"}</strong>
                  </div>
                </div>

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

                <button
                  className={`complete-button ${isCompleted ? "is-complete" : ""}`}
                  onClick={() => handleToggle(task.id)}
                  type="button"
                >
                  {isCompleted ? "✓ Completed" : "Mark as complete"}
                </button>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
