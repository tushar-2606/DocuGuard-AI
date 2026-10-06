import { useState } from "react";
import "./App.css";

function App() {
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [completedTasks, setCompletedTasks] = useState(new Set());
  const [filter, setFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("priority");

  const [theme, setTheme] = useState(
    localStorage.getItem("docuguard-theme") || "arctic"
  );

  const uploadDocument = async () => {
    if (!file) {
      setError("Please select a PDF first.");
      return;
    }

    setLoading(true);
    setError("");
    setAnalysis(null);
    setCompletedTasks(new Set());

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/documents/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Document analysis failed."
        );
      }

      setAnalysis(data.analysis);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const priorityValue = {
    HIGH: 3,
    MEDIUM: 2,
    LOW: 1,
  };

  const priorityClass = (priority) => {
    if (priority === "HIGH") return "priority high";
    if (priority === "MEDIUM") return "priority medium";
    return "priority low";
  };

  const toggleTask = (index) => {
    setCompletedTasks((previous) => {
      const updated = new Set(previous);

      if (updated.has(index)) {
        updated.delete(index);
      } else {
        updated.add(index);
      }

      return updated;
    });
  };

  const toggleTheme = () => {
    const nextTheme =
      theme === "arctic" ? "cyber" : "arctic";

    setTheme(nextTheme);
    localStorage.setItem("docuguard-theme", nextTheme);
  };

  const resetDocument = () => {
    setAnalysis(null);
    setFile(null);
    setError("");
    setCompletedTasks(new Set());
    setFilter("ALL");
    setSortBy("priority");
  };

  const getVisibleTasks = () => {
    if (!analysis) return [];

    let tasks = analysis.tasks
      .map((task, index) => ({
        ...task,
        originalIndex: index,
      }))
      .filter((task) => {
        if (filter === "ALL") return true;
        return task.priority === filter;
      });

    if (sortBy === "priority") {
      tasks.sort(
        (a, b) =>
          priorityValue[b.priority] -
          priorityValue[a.priority]
      );
    }

    if (sortBy === "confidence") {
      tasks.sort(
        (a, b) => b.confidence - a.confidence
      );
    }

    return tasks;
  };

  const highCount =
    analysis?.tasks.filter(
      (task) => task.priority === "HIGH"
    ).length || 0;

  const mediumCount =
    analysis?.tasks.filter(
      (task) => task.priority === "MEDIUM"
    ).length || 0;

  const lowCount =
    analysis?.tasks.filter(
      (task) => task.priority === "LOW"
    ).length || 0;

  const deadlineCount =
    analysis?.tasks.filter(
      (task) => task.deadline
    ).length || 0;

  const totalTasks = analysis?.tasks.length || 0;

  const completionPercent =
    totalTasks > 0
      ? Math.round(
          (completedTasks.size / totalTasks) * 100
        )
      : 0;

  return (
    <div className={`app theme-${theme}`}>

      {/* ================= HEADER ================= */}

      <header className="header">

        <div className="brand">

          <div className="brand-icon">
            🛡️
          </div>

          <div>
            <h1>DocuGuard AI</h1>
            <p>
              Turn documents into actionable tasks.
            </p>
          </div>

        </div>

        <div className="header-right">

          <button
            className="theme-toggle"
            onClick={toggleTheme}
            type="button"
          >
            {theme === "arctic"
              ? "◐ Cyber"
              : "☀ Arctic"}
          </button>

          <div className="status">
            <span></span>
            AI Ready
          </div>

          {analysis && (
            <button
              className="new-document"
              onClick={resetDocument}
              type="button"
            >
              + New Document
            </button>
          )}

        </div>

      </header>

      {/* ================= MAIN ================= */}

      <main className="container">

        {/* ================= TOP SECTION ================= */}

        <section className="top-grid">

          {/* HERO */}

          <div className="hero">

            <div className="hero-badge">
              ✦ Smart Document Analysis
            </div>

            <h2>
              Document Intelligence
              <span> Dashboard</span>
            </h2>

            <p>
              Upload a notice, circular, or institutional
              PDF and DocuGuard AI will identify important
              actions, deadlines and priorities.
            </p>

          </div>

          {/* UPLOAD */}

          <section className="upload-card">

            <div className="upload-title">

              <span>📄</span>

              <div>
                <h3>
                  Upload & Analyze Document
                </h3>

                <p>
                  Supports PDF files • notices,
                  circulars, guidelines, etc.
                </p>
              </div>

            </div>

            <label className="drop-zone">

              <input
                type="file"
                accept=".pdf"
                onChange={(e) => {
                  setFile(e.target.files[0]);
                  setError("");
                }}
              />

              <div className="upload-icon">
                ↑
              </div>

              <strong>
                {file
                  ? file.name
                  : "Drag & drop your PDF here"}
              </strong>

              <span>
                {file
                  ? "Ready for analysis"
                  : "or click to browse"}
              </span>

            </label>

            {file && (
              <div className="selected-file">

                <span>📕</span>

                <div>
                  <strong>
                    {file.name}
                  </strong>

                  <small>
                    Ready to analyze
                  </small>
                </div>

                <button
                  type="button"
                  onClick={() => setFile(null)}
                >
                  ×
                </button>

              </div>
            )}

            <button
              className="analyze-btn"
              onClick={uploadDocument}
              disabled={loading}
              type="button"
            >
              {loading
                ? "Analyzing..."
                : "✦ Analyze Document"}
            </button>

            {error && (
              <div className="error">
                ⚠️ {error}
              </div>
            )}

          </section>

        </section>

        {/* ================= ANALYSIS ================= */}

        {analysis && (
          <>

            {/* METRICS */}

            <section className="metrics">

              <div className="metric-card blue">

                <div className="metric-icon">
                  📄
                </div>

                <div>
                  <span>Document Type</span>
                  <strong>
                    {analysis.document_type}
                  </strong>
                </div>

              </div>

              <div className="metric-card purple">

                <div className="metric-icon">
                  ☑
                </div>

                <div>
                  <span>Tasks Found</span>
                  <strong>
                    {totalTasks}
                  </strong>
                </div>

              </div>

              <div className="metric-card red">

                <div className="metric-icon">
                  !
                </div>

                <div>
                  <span>High Priority</span>
                  <strong>
                    {highCount}
                  </strong>
                </div>

              </div>

              <div className="metric-card orange">

                <div className="metric-icon">
                  ◷
                </div>

                <div>
                  <span>With Deadlines</span>
                  <strong>
                    {deadlineCount}
                  </strong>
                </div>

              </div>

              <div className="metric-card green">

                <div className="metric-icon">
                  ✓
                </div>

                <div>
                  <span>Completed</span>
                  <strong>
                    {completedTasks.size}/{totalTasks}
                  </strong>
                </div>

              </div>

            </section>

            {/* SUMMARY */}

            <section className="summary-strip">

              <div>
                <strong>
                  AI Summary
                </strong>

                <p>
                  {analysis.summary}
                </p>
              </div>

              <div className="progress-box">

                <div className="progress-info">

                  <strong>
                    Tasks Completed
                  </strong>

                  <span>
                    {completionPercent}%
                  </span>

                </div>

                <div className="progress-bar">

                  <div
                    style={{
                      width: `${completionPercent}%`,
                    }}
                  ></div>

                </div>

              </div>

            </section>

            {/* TASK SECTION */}

            <section className="tasks-section">

              <div className="tasks-heading">

                <div>

                  <h2>
                    Actionable Tasks
                  </h2>

                  <p>
                    Important actions extracted
                    from the document.
                  </p>

                </div>

                <select
                  value={sortBy}
                  onChange={(e) =>
                    setSortBy(e.target.value)
                  }
                >

                  <option value="priority">
                    Sort: Priority
                  </option>

                  <option value="confidence">
                    Sort: Confidence
                  </option>

                </select>

              </div>

              {/* FILTERS */}

              <div className="filters">

                <button
                  type="button"
                  className={
                    filter === "ALL"
                      ? "active"
                      : ""
                  }
                  onClick={() =>
                    setFilter("ALL")
                  }
                >
                  ▦ All Tasks ({totalTasks})
                </button>

                <button
                  type="button"
                  className={
                    filter === "HIGH"
                      ? "active high-filter"
                      : ""
                  }
                  onClick={() =>
                    setFilter("HIGH")
                  }
                >
                  ● High ({highCount})
                </button>

                <button
                  type="button"
                  className={
                    filter === "MEDIUM"
                      ? "active medium-filter"
                      : ""
                  }
                  onClick={() =>
                    setFilter("MEDIUM")
                  }
                >
                  ● Medium ({mediumCount})
                </button>

                <button
                  type="button"
                  className={
                    filter === "LOW"
                      ? "active low-filter"
                      : ""
                  }
                  onClick={() =>
                    setFilter("LOW")
                  }
                >
                  ● Low ({lowCount})
                </button>

              </div>

              {/* TASK CARDS */}

              <div className="task-grid">

                {getVisibleTasks().map((task) => {

                  const isCompleted =
                    completedTasks.has(
                      task.originalIndex
                    );

                  return (
                    <div
                      className={`task-card ${
                        isCompleted
                          ? "completed"
                          : ""
                      }`}
                      key={task.originalIndex}
                    >

                      <div className="task-top">

                        <span
                          className={priorityClass(
                            task.priority
                          )}
                        >
                          {task.priority}
                        </span>

                        <span className="confidence">
                          {Math.round(
                            task.confidence * 100
                          )}
                          % confidence
                        </span>

                      </div>

                      <h3>
                        {task.task}
                      </h3>

                      <div className="task-info">

                        <div>

                          <span>
                            ▣ Deadline
                          </span>

                          <strong>
                            {task.deadline ||
                              "Not specified"}
                          </strong>

                        </div>

                        <div>

                          <span>
                            ◆ Category
                          </span>

                          <strong>
                            {task.category}
                          </strong>

                        </div>

                      </div>

                      <button
                        type="button"
                        className={`complete-btn ${
                          isCompleted
                            ? "completed-btn"
                            : ""
                        }`}
                        onClick={() =>
                          toggleTask(
                            task.originalIndex
                          )
                        }
                      >
                        {isCompleted
                          ? "✓ Completed"
                          : "◉ Mark as Complete"}
                      </button>

                    </div>
                  );
                })}

              </div>

            </section>

          </>
        )}

      </main>

      <footer>
        DocuGuard AI • Intelligent Document-to-Action System
      </footer>

    </div>
  );
}

export default App;