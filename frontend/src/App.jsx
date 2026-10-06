import { useEffect, useRef, useState } from "react";
import "./App.css";

const MAX_FILE_SIZE = 15 * 1024 * 1024;

function App() {
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [documentInfo, setDocumentInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [completedTasks, setCompletedTasks] = useState(new Set());
  const [filter, setFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("priority");
  const [isDragging, setIsDragging] = useState(false);
  const [theme, setTheme] = useState(
    () => localStorage.getItem("docuguard-theme") || "arctic",
  );
  const fileInputRef = useRef(null);
  const analysisRef = useRef(null);
  const uploadRef = useRef(null);

  const tasks = analysis?.tasks ?? [];
  const highCount = tasks.filter((task) => task.priority === "HIGH").length;
  const mediumCount = tasks.filter((task) => task.priority === "MEDIUM").length;
  const lowCount = tasks.filter((task) => task.priority === "LOW").length;
  const deadlineCount = tasks.filter((task) => task.deadline).length;
  const completionPercent = tasks.length
    ? Math.round((completedTasks.size / tasks.length) * 100)
    : 0;

  useEffect(() => {
    if (analysis) {
      analysisRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, [analysis]);

  const scrollToUpload = () => {
    uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const selectFile = (candidate) => {
    if (!candidate) return;

    if (!candidate.name.toLowerCase().endsWith(".pdf")) {
      setFile(null);
      setError("Please choose a PDF file.");
      return;
    }

    if (candidate.size > MAX_FILE_SIZE) {
      setFile(null);
      setError("This PDF is larger than 15 MB. Choose a smaller file.");
      return;
    }

    setFile(candidate);
    setError("");
    setAnalysis(null);
    setDocumentInfo(null);
    setCompletedTasks(new Set());
  };

  const uploadDocument = async () => {
    if (!file) {
      setError("Choose a PDF file before starting the analysis.");
      return;
    }

    setLoading(true);
    setError("");
    setAnalysis(null);
    setDocumentInfo(null);
    setCompletedTasks(new Set());

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/documents/upload", {
        method: "POST",
        body: formData,
      });
      const data = await response.json().catch(() => null);

      if (!response.ok) {
        throw new Error(data?.detail || "Document analysis failed.");
      }

      if (!data?.analysis || !Array.isArray(data.analysis.tasks)) {
        throw new Error("The backend returned an invalid analysis response.");
      }

      setDocumentInfo({
        filename: data.filename || file.name,
        pages: data.pages,
      });
      setAnalysis(data.analysis);
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "Cannot connect to the backend. Run run-dev.bat and keep both terminal windows open."
          : requestError.message,
      );
    } finally {
      setLoading(false);
    }
  };

  const toggleTheme = () => {
    const nextTheme = theme === "arctic" ? "cyber" : "arctic";
    setTheme(nextTheme);
    localStorage.setItem("docuguard-theme", nextTheme);
  };

  const resetDocument = () => {
    setAnalysis(null);
    setDocumentInfo(null);
    setFile(null);
    setError("");
    setCompletedTasks(new Set());
    setFilter("ALL");
    setSortBy("priority");
    scrollToUpload();
  };

  const toggleTask = (index) => {
    setCompletedTasks((previous) => {
      const updated = new Set(previous);
      if (updated.has(index)) updated.delete(index);
      else updated.add(index);
      return updated;
    });
  };

  const visibleTasks = tasks
    .map((task, originalIndex) => ({ ...task, originalIndex }))
    .filter((task) => filter === "ALL" || task.priority === filter)
    .sort((first, second) => {
      if (sortBy === "confidence") {
        return (second.confidence ?? 0) - (first.confidence ?? 0);
      }
      const priority = { HIGH: 3, MEDIUM: 2, LOW: 1 };
      return (priority[second.priority] ?? 0) - (priority[first.priority] ?? 0);
    });

  return (
    <div className={`app theme-${theme}`}>
      <header className="site-header">
        <a className="brand" href="#home" aria-label="DocuGuard AI home">
          <span className="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32">
              <path d="M16 3 27 7v8c0 7-4.5 11.7-11 14C9.5 26.7 5 22 5 15V7l11-4Z" />
              <path d="m11.5 15.8 3 3 6.5-7" />
            </svg>
          </span>
          <span className="brand-copy">
            <strong>DocuGuard AI</strong>
            <small>From documents to action.</small>
          </span>
        </a>

        <nav className="main-nav" aria-label="Main navigation">
          <a className="nav-active" href="#home">Home</a>
          <a href="#how-it-works">How It Works</a>
          <a href="#features">Features</a>
          <a href="#about">About</a>
        </nav>

        <div className="header-actions">
          <button className="theme-toggle" onClick={toggleTheme} type="button">
            {theme === "arctic" ? "◐ Cyber" : "☀ Arctic"}
          </button>
          {analysis ? (
            <button className="header-cta" onClick={resetDocument} type="button">
              + New Document
            </button>
          ) : (
            <button className="header-cta" onClick={scrollToUpload} type="button">
              Open Workspace
            </button>
          )}
        </div>
      </header>

      <main>
        <section className="hero-section page-width" id="home">
          <div className="hero-copy">
            <span className="eyebrow hero-eyebrow">
              <span className="eyebrow-spark">✦</span>
              Turning documents into real actions
            </span>
            <span className="section-kicker">DOCUMENT INTELLIGENCE</span>
            <h1>
              From notices to
              <span> actionable tasks.</span>
            </h1>
            <p className="hero-description">
              Upload a notice, circular, guideline or institutional PDF.
              DocuGuard AI finds the important actions, deadlines and
              priorities for you.
            </p>

            <div className="hero-highlights" aria-label="Key capabilities">
              <div className="hero-highlight">
                <span className="highlight-icon blue-icon">▤</span>
                <span><strong>Smart Extraction</strong><small>Finds important actions</small></span>
              </div>
              <div className="hero-highlight">
                <span className="highlight-icon pink-icon">◉</span>
                <span><strong>Priority Detection</strong><small>Shows what matters first</small></span>
              </div>
              <div className="hero-highlight">
                <span className="highlight-icon amber-icon">◷</span>
                <span><strong>Deadline Recognition</strong><small>Surfaces important dates</small></span>
              </div>
              <div className="hero-highlight">
                <span className="highlight-icon green-icon">✓</span>
                <span><strong>Action Lists</strong><small>Turn text into tasks</small></span>
              </div>
            </div>

            <div className="hero-actions">
              <button className="primary-button" onClick={scrollToUpload} type="button">
                ↑ Upload Document <span aria-hidden="true">→</span>
              </button>
              <a className="secondary-button" href="#how-it-works">
                <span aria-hidden="true">▶</span> See How It Works
              </a>
            </div>
          </div>

          <div className="hero-art" aria-hidden="true">
            <span className="art-label important-label">Important actions</span>
            <span className="art-label deadline-label">Deadlines</span>
            <div className="document-illustration">
              <div className="document-heading">Notice / Circular</div>
              <span className="document-line line-wide" />
              <span className="document-line" />
              <span className="document-highlight yellow-line" />
              <span className="document-highlight pink-line" />
              <span className="document-highlight blue-line" />
              <span className="document-line line-wide" />
              <span className="document-line line-short" />
            </div>
            <div className="action-note">
              <span>✓ Submit application</span>
              <span>✓ Attend meeting</span>
              <span>✓ Check deadline</span>
              <b>Priorities</b>
            </div>
          </div>
        </section>

        <section className="workspace-section page-width" id="workspace" ref={uploadRef}>
          <div className="workspace-card">
            <div className="workspace-heading">
              <span className="workspace-icon" aria-hidden="true">▤</span>
              <div>
                <span className="section-kicker">DOCUMENT WORKSPACE</span>
                <h2>Upload &amp; Analyze Document</h2>
                <p>Supports PDF notices, circulars, guidelines and institutional documents.</p>
              </div>
            </div>

            <label
              className={`drop-zone ${isDragging ? "dragging" : ""}`}
              onDragEnter={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragOver={(event) => event.preventDefault()}
              onDragLeave={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget)) {
                  setIsDragging(false);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragging(false);
                selectFile(event.dataTransfer.files[0]);
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => {
                  selectFile(event.target.files[0]);
                  event.target.value = "";
                }}
              />
              <span className="upload-symbol" aria-hidden="true">↑</span>
              <strong>{file ? file.name : "Drag & drop your PDF here"}</strong>
              <span>{file ? "Ready for analysis" : "or click to browse files"}</span>
              <small>PDF only · Up to 15 MB</small>
            </label>

            {file && (
              <div className="selected-file">
                <span className="pdf-badge" aria-hidden="true">PDF</span>
                <div className="selected-file-copy">
                  <strong>{file.name}</strong>
                  <small>{(file.size / (1024 * 1024)).toFixed(2)} MB · Ready for analysis</small>
                </div>
                <button
                  aria-label="Remove selected file"
                  onClick={() => {
                    setFile(null);
                    setError("");
                  }}
                  type="button"
                >
                  ×
                </button>
              </div>
            )}

            <button
              className="analyze-button"
              onClick={uploadDocument}
              disabled={loading}
              type="button"
            >
              {loading ? <><span className="spinner" /> Analyzing document…</> : "✦  Analyze Document"}
            </button>

            {error && <p className="upload-error" role="alert">⚠ {error}</p>}

            <div className="trust-row">
              <div><span>▣</span><p><strong>Secure Upload</strong><small>Your file stays private</small></p></div>
              <div><span>✦</span><p><strong>AI Analysis</strong><small>Fast document processing</small></p></div>
              <div><span>✓</span><p><strong>Clear Results</strong><small>Tasks, deadlines &amp; priorities</small></p></div>
            </div>
          </div>
        </section>

        {analysis && (
          <section className="results-section page-width" id="results" ref={analysisRef}>
            <div className="results-intro">
              <div>
                <span className="section-kicker">YOUR DOCUMENT, ORGANIZED</span>
                <h2>Your document, organized.</h2>
                <p>
                  {documentInfo?.filename}
                  {documentInfo?.pages ? ` · ${documentInfo.pages} page${documentInfo.pages === 1 ? "" : "s"}` : ""}
                </p>
              </div>
              <button className="text-button" onClick={resetDocument} type="button">
                Analyze another PDF <span aria-hidden="true">→</span>
              </button>
            </div>

            <div className="metrics">
              <article className="metric-card blue">
                <span className="metric-icon">▤</span>
                <span><small>Document Type</small><strong>{analysis.document_type.replaceAll("_", " ")}</strong></span>
              </article>
              <article className="metric-card purple">
                <span className="metric-icon">✓</span>
                <span><small>Tasks Found</small><strong>{tasks.length}</strong></span>
              </article>
              <article className="metric-card red">
                <span className="metric-icon">!</span>
                <span><small>High Priority</small><strong>{highCount}</strong></span>
              </article>
              <article className="metric-card orange">
                <span className="metric-icon">◷</span>
                <span><small>With Deadlines</small><strong>{deadlineCount}</strong></span>
              </article>
              <article className="metric-card green">
                <span className="metric-icon">✓</span>
                <span><small>Completed</small><strong>{completedTasks.size}/{tasks.length}</strong></span>
              </article>
            </div>

            <div className="summary-strip">
              <div>
                <span className="section-kicker">AI SUMMARY</span>
                <p>{analysis.summary}</p>
              </div>
              <div className="progress-box">
                <div className="progress-info">
                  <strong>Tasks completed</strong><span>{completionPercent}%</span>
                </div>
                <div
                  className="progress-bar"
                  role="progressbar"
                  aria-valuenow={completionPercent}
                  aria-valuemin="0"
                  aria-valuemax="100"
                  aria-label="Tasks completed"
                >
                  <span style={{ width: `${completionPercent}%` }} />
                </div>
              </div>
            </div>

            <div className="tasks-heading">
              <div>
                <span className="section-kicker">ACTION CENTER</span>
                <h2>Actionable Tasks</h2>
                <p>Review the actions extracted from your document.</p>
              </div>
              <label className="sort-control">
                <span className="visually-hidden">Sort tasks</span>
                <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
                  <option value="priority">Sort: Priority</option>
                  <option value="confidence">Sort: Confidence</option>
                </select>
              </label>
            </div>

            <div className="filters" aria-label="Filter tasks by priority">
              {[
                ["ALL", `All Tasks (${tasks.length})`],
                ["HIGH", `High (${highCount})`],
                ["MEDIUM", `Medium (${mediumCount})`],
                ["LOW", `Low (${lowCount})`],
              ].map(([value, label]) => (
                <button
                  className={filter === value ? `active ${value.toLowerCase()}` : ""}
                  key={value}
                  onClick={() => setFilter(value)}
                  type="button"
                >
                  {label}
                </button>
              ))}
            </div>

            {visibleTasks.length ? (
              <div className="task-grid">
                {visibleTasks.map((task) => {
                  const isCompleted = completedTasks.has(task.originalIndex);
                  const priority = ["HIGH", "MEDIUM", "LOW"].includes(task.priority)
                    ? task.priority
                    : "LOW";
                  return (
                    <article
                      className={`task-card ${isCompleted ? "completed" : ""}`}
                      key={`${task.originalIndex}-${task.task}`}
                    >
                      <div className="task-top">
                        <span className={`priority ${priority.toLowerCase()}`}>{priority}</span>
                        <span className="confidence">
                          {Math.round((task.confidence ?? 0) * 100)}% confidence
                        </span>
                      </div>
                      <h3>{task.task}</h3>
                      <div className="task-info">
                        <div><span>Deadline</span><strong>{task.deadline || "Not specified"}</strong></div>
                        <div><span>Category</span><strong>{task.category || "General"}</strong></div>
                      </div>
                      <button
                        className={`complete-button ${isCompleted ? "is-complete" : ""}`}
                        onClick={() => toggleTask(task.originalIndex)}
                        type="button"
                      >
                        {isCompleted ? "✓ Completed" : "Mark as complete"}
                      </button>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="empty-tasks">No tasks match this priority filter.</div>
            )}
          </section>
        )}

        <section className="document-types page-width" id="features">
          <span className="section-kicker">BUILT FOR REAL DOCUMENTS</span>
          <h2>Works with the documents you already receive.</h2>
          <div className="document-type-grid">
            <a href="#workspace"><span className="type-icon lavender">▤</span><span><strong>Notices</strong><small>College and institutional notices</small></span><b>→</b></a>
            <a href="#workspace"><span className="type-icon rose">◈</span><span><strong>Circulars</strong><small>Official announcements</small></span><b>→</b></a>
            <a href="#workspace"><span className="type-icon amber">▣</span><span><strong>Guidelines</strong><small>Policies and academic guidelines</small></span><b>→</b></a>
            <a href="#workspace"><span className="type-icon mint">⌂</span><span><strong>Institutional PDFs</strong><small>Official documents and instructions</small></span><b>→</b></a>
          </div>
        </section>

        <section className="how-section page-width" id="how-it-works">
          <div className="section-heading-centered">
            <span className="section-kicker">HOW IT WORKS</span>
            <h2>A clearer way to handle important documents.</h2>
            <p>No complicated workflow. Upload your document and let DocuGuard organize what needs your attention.</p>
          </div>
          <div className="steps-grid">
            <article className="step-card">
              <span className="step-number">01</span><span className="step-icon">↑</span>
              <h3>Upload</h3><p>Select the PDF you want DocuGuard to understand.</p>
            </article>
            <article className="step-card">
              <span className="step-number">02</span><span className="step-icon">✦</span>
              <h3>Analyze</h3><p>AI extracts relevant actions, priorities and available deadlines.</p>
            </article>
            <article className="step-card">
              <span className="step-number">03</span><span className="step-icon">✓</span>
              <h3>Take Action</h3><p>Review your task list and mark completed actions.</p>
            </article>
          </div>
        </section>

        <section className="about-section page-width" id="about">
          <div>
            <span className="section-kicker">ABOUT DOCUGUARD</span>
            <h2>Less time reading.<br />More time acting.</h2>
          </div>
          <p>
            DocuGuard AI turns information-heavy documents into simple,
            understandable actions. The goal is straightforward: help you notice
            what matters without making you dig through every page.
          </p>
        </section>
      </main>

      <footer className="site-footer page-width">
        <a className="footer-brand" href="#home">DocuGuard AI <span>From documents to action.</span></a>
        <span>Intelligent Document-to-Action System</span>
      </footer>
    </div>
  );
}

export default App;
