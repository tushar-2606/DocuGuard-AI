import { useEffect, useRef, useState } from "react";
import "./App.css";
import AuthModal from "./components/AuthModal";
import DashboardView from "./components/DashboardView";
import DeadlinesView from "./components/DeadlinesView";
import DocumentsView from "./components/DocumentsView";
import ExplainModal from "./components/ExplainModal";
import ProfileModal from "./components/ProfileModal";
import RulesView from "./components/RulesView";
import TasksView from "./components/TasksView";
import { api, getStoredToken } from "./services/api";

const MAX_FILE_SIZE = 15 * 1024 * 1024;

function App() {
  // Document state
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [documentInfo, setDocumentInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [completedTasks, setCompletedTasks] = useState(new Set());
  const [filter, setFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("priority");
  const [isDragging, setIsDragging] = useState(false);
  const [analysisActiveTab, setAnalysisActiveTab] = useState("tasks");

  // SaaS Workspace & Auth State
  const [currentUser, setCurrentUser] = useState(null);
  const [activeView, setActiveView] = useState("home"); // home | workspace | documents | tasks | deadlines | rules
  const [dashboardStats, setDashboardStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Modals state
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState("login");
  const [profileModalOpen, setProfileModalOpen] = useState(false);
  const [explainModalOpen, setExplainModalOpen] = useState(false);
  const [explainItem, setExplainItem] = useState(null);
  const [explainType, setExplainType] = useState("Task");
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  // Theme
  const [theme, setTheme] = useState(
    () => localStorage.getItem("docuguard-theme") || "arctic",
  );

  const fileInputRef = useRef(null);
  const analysisRef = useRef(null);
  const uploadRef = useRef(null);
  const userMenuRef = useRef(null);
  const loadDashboardStats = async () => {
    setStatsLoading(true);
    try {
      const stats = await api.getDashboardStats();
      setDashboardStats(stats);
    } catch {
      // Handled silently
    } finally {
      setStatsLoading(false);
    }
  };

  // Check auth session on load
  useEffect(() => {
    const initAuth = async () => {
      const token = getStoredToken();
      if (!token) return;
      try {
        const user = await api.getMe();
        if (user) {
          setCurrentUser(user);
          setActiveView("workspace");
          loadDashboardStats();
        }
      } catch {
        // Token invalid or expired
      }
    };
    initAuth();
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target)) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const tasks = analysis?.tasks ?? [];
  const rules = analysis?.rules ?? [];
  const deadlines = analysis?.deadlines ?? [];

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
    if (activeView !== "home" && activeView !== "workspace") {
      setActiveView("workspace");
    }
    setTimeout(() => {
      uploadRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
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

    try {
      const data = await api.uploadDocument(file);

      if (!data?.analysis || !Array.isArray(data.analysis.tasks)) {
        throw new Error("The backend returned an invalid analysis response.");
      }

      setDocumentInfo({
        id: data.document_id,
        filename: data.filename || file.name,
        pages: data.pages,
        is_saved: data.is_saved,
      });
      setAnalysis(data.analysis);

      if (currentUser) {
        loadDashboardStats();
      }
    } catch (requestError) {
      setError(
        requestError instanceof TypeError
          ? "Cannot connect to the backend. Please ensure the backend server is running on port 8000."
          : requestError.message,
      );
    } finally {
      setLoading(false);
    }
  };

  const handleOpenSavedDocument = async (docId) => {
    try {
      setLoading(true);
      const doc = await api.getDocument(docId);
      setDocumentInfo({
        id: doc.id,
        filename: doc.filename,
        pages: doc.pages,
        is_saved: true,
      });
      setAnalysis(doc.analysis);

      // Populate completed tasks
      const completedSet = new Set();
      doc.analysis.tasks.forEach((t, idx) => {
        if (t.is_completed) completedSet.add(idx);
      });
      setCompletedTasks(completedSet);

      setActiveView("home"); // Show in home/analysis view
    } catch (err) {
      alert(err.message || "Could not open document.");
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

  const toggleTask = async (originalIndex, taskId) => {
    setCompletedTasks((previous) => {
      const updated = new Set(previous);
      if (updated.has(originalIndex)) updated.delete(originalIndex);
      else updated.add(originalIndex);
      return updated;
    });

    if (taskId && currentUser) {
      try {
        await api.toggleTask(taskId);
        loadDashboardStats();
      } catch {
        // Silently keep optimistic update
      }
    }
  };

  const handleExplain = (item, itemType) => {
    setExplainItem(item);
    setExplainType(itemType);
    setExplainModalOpen(true);
  };

  const handleAuthSuccess = (user) => {
    setCurrentUser(user);
    setActiveView("workspace");
    loadDashboardStats();
  };

  const handleLogout = async () => {
    await api.logout();
    setCurrentUser(null);
    setActiveView("home");
    setDashboardStats(null);
    setUserMenuOpen(false);
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
        <a
          className="brand"
          href="#home"
          onClick={(e) => {
            e.preventDefault();
            setActiveView(currentUser ? "workspace" : "home");
          }}
          aria-label="DocuGuard AI home"
        >
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

        {/* Dynamic Navigation */}
        <nav className="main-nav" aria-label="Main navigation">
          {currentUser ? (
            <>
              <button
                className={`nav-tab-btn ${activeView === "workspace" ? "active" : ""}`}
                onClick={() => setActiveView("workspace")}
                type="button"
              >
                Workspace
              </button>
              <button
                className={`nav-tab-btn ${activeView === "documents" ? "active" : ""}`}
                onClick={() => setActiveView("documents")}
                type="button"
              >
                Documents
              </button>
              <button
                className={`nav-tab-btn ${activeView === "tasks" ? "active" : ""}`}
                onClick={() => setActiveView("tasks")}
                type="button"
              >
                Tasks
              </button>
              <button
                className={`nav-tab-btn ${activeView === "deadlines" ? "active" : ""}`}
                onClick={() => setActiveView("deadlines")}
                type="button"
              >
                Deadlines
              </button>
              <button
                className={`nav-tab-btn ${activeView === "rules" ? "active" : ""}`}
                onClick={() => setActiveView("rules")}
                type="button"
              >
                Rules
              </button>
            </>
          ) : (
            <>
              <a
                className={activeView === "home" ? "nav-active" : ""}
                href="#home"
                onClick={() => setActiveView("home")}
              >
                Home
              </a>
              <a href="#how-it-works">How It Works</a>
              <a href="#features">Features</a>
              <a href="#about">About</a>
            </>
          )}
        </nav>

        <div className="header-actions">
          <button className="theme-toggle" onClick={toggleTheme} type="button">
            {theme === "arctic" ? "◐ Cyber" : "☀ Arctic"}
          </button>

          {currentUser ? (
            <div className="user-menu-wrapper" ref={userMenuRef}>
              <button
                className="user-menu-btn"
                onClick={() => setUserMenuOpen((prev) => !prev)}
                type="button"
              >
                <span className="user-avatar-mini">
                  {currentUser.full_name
                    ? currentUser.full_name.slice(0, 1).toUpperCase()
                    : "U"}
                </span>
                <strong>{currentUser.full_name.split(" ")[0]}</strong>
                <span style={{ fontSize: "9px" }}>▾</span>
              </button>

              {userMenuOpen && (
                <div className="user-dropdown-menu">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveView("workspace");
                      setUserMenuOpen(false);
                    }}
                  >
                    📊 Workspace Dashboard
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setProfileModalOpen(true);
                      setUserMenuOpen(false);
                    }}
                  >
                    👤 My Profile
                  </button>
                  <hr />
                  <button className="logout-item" onClick={handleLogout} type="button">
                    🚪 Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              className="secondary-button"
              onClick={() => {
                setAuthModalMode("login");
                setAuthModalOpen(true);
              }}
              type="button"
            >
              Login / Sign Up
            </button>
          )}

          {analysis ? (
            <button className="header-cta" onClick={resetDocument} type="button">
              + New Document
            </button>
          ) : (
            <button className="header-cta" onClick={scrollToUpload} type="button">
              Upload PDF
            </button>
          )}
        </div>
      </header>

      <main>
        {/* VIEW 1: USER DASHBOARD */}
        {currentUser && activeView === "workspace" && (
          <DashboardView
            user={currentUser}
            stats={dashboardStats}
            loading={statsLoading}
            onQuickUploadClick={scrollToUpload}
            onOpenDocument={handleOpenSavedDocument}
            onNavigate={(v) => setActiveView(v)}
            onExplainItem={handleExplain}
          />
        )}

        {/* VIEW 2: SAVED DOCUMENTS HISTORY */}
        {currentUser && activeView === "documents" && (
          <DocumentsView
            onOpenDocument={handleOpenSavedDocument}
            onQuickUploadClick={scrollToUpload}
          />
        )}

        {/* VIEW 3: GLOBAL TASKS */}
        {currentUser && activeView === "tasks" && (
          <TasksView
            onOpenDocument={handleOpenSavedDocument}
            onExplainItem={handleExplain}
          />
        )}

        {/* VIEW 4: GLOBAL DEADLINES */}
        {currentUser && activeView === "deadlines" && (
          <DeadlinesView
            onOpenDocument={handleOpenSavedDocument}
            onExplainItem={handleExplain}
          />
        )}

        {/* VIEW 5: GLOBAL RULES */}
        {currentUser && activeView === "rules" && (
          <RulesView
            onOpenDocument={handleOpenSavedDocument}
            onExplainItem={handleExplain}
          />
        )}

        {/* VIEW 6: HOME / HERO (Shown for Guests or when on Home tab) */}
        {(!currentUser || activeView === "home" || activeView === "workspace") && (
          <>
            {activeView === "home" && !currentUser && (
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
                      <span>
                        <strong>Smart Extraction</strong>
                        <small>Finds important actions</small>
                      </span>
                    </div>
                    <div className="hero-highlight">
                      <span className="highlight-icon pink-icon">◉</span>
                      <span>
                        <strong>Priority Detection</strong>
                        <small>Shows what matters first</small>
                      </span>
                    </div>
                    <div className="hero-highlight">
                      <span className="highlight-icon amber-icon">◷</span>
                      <span>
                        <strong>Deadline Recognition</strong>
                        <small>Surfaces important dates</small>
                      </span>
                    </div>
                    <div className="hero-highlight">
                      <span className="highlight-icon green-icon">✓</span>
                      <span>
                        <strong>Action Lists</strong>
                        <small>Turn text into tasks</small>
                      </span>
                    </div>
                  </div>

                  <div className="hero-actions">
                    <button
                      className="primary-button"
                      onClick={scrollToUpload}
                      type="button"
                    >
                      ↑ Upload Document <span aria-hidden="true">→</span>
                    </button>
                    <button
                      className="secondary-button"
                      onClick={() => {
                        setAuthModalMode("signup");
                        setAuthModalOpen(true);
                      }}
                      type="button"
                    >
                      ✦ Create Free Account
                    </button>
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
            )}

            {/* Document Workspace Upload & Drop Zone */}
            <section
              className="workspace-section page-width"
              id="workspace"
              ref={uploadRef}
            >
              <div className="workspace-card">
                <div className="workspace-heading">
                  <span className="workspace-icon" aria-hidden="true">
                    ▤
                  </span>
                  <div>
                    <span className="section-kicker">DOCUMENT WORKSPACE</span>
                    <h2>Upload &amp; Analyze Document</h2>
                    <p>
                      Supports PDF notices, circulars, guidelines and institutional documents.
                      {currentUser
                        ? " Your analysis will be saved to your personal history."
                        : " Sign in to persist your documents and deadlines."}
                    </p>
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
                  <span className="upload-symbol" aria-hidden="true">
                    ↑
                  </span>
                  <strong>{file ? file.name : "Drag & drop your PDF here"}</strong>
                  <span>{file ? "Ready for analysis" : "or click to browse files"}</span>
                  <small>PDF only · Up to 15 MB</small>
                </label>

                {file && (
                  <div className="selected-file">
                    <span className="pdf-badge" aria-hidden="true">
                      PDF
                    </span>
                    <div className="selected-file-copy">
                      <strong>{file.name}</strong>
                      <small>
                        {(file.size / (1024 * 1024)).toFixed(2)} MB · Ready for analysis
                      </small>
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
                  {loading ? (
                    <>
                      <span className="spinner" /> Analyzing document…
                    </>
                  ) : (
                    "✦  Analyze Document"
                  )}
                </button>

                {error && (
                  <p className="upload-error" role="alert">
                    ⚠ {error}
                  </p>
                )}

                <div className="trust-row">
                  <div>
                    <span>▣</span>
                    <p>
                      <strong>Secure Upload</strong>
                      <small>Private to your account</small>
                    </p>
                  </div>
                  <div>
                    <span>✦</span>
                    <p>
                      <strong>Explainable AI</strong>
                      <small>Clear audit trail</small>
                    </p>
                  </div>
                  <div>
                    <span>✓</span>
                    <p>
                      <strong>Clear Results</strong>
                      <small>Tasks, deadlines &amp; rules</small>
                    </p>
                  </div>
                </div>
              </div>
            </section>
          </>
        )}

        {/* ANALYSIS RESULTS SECTION */}
        {analysis && (
          <section
            className="results-section page-width"
            id="results"
            ref={analysisRef}
          >
            <div className="results-intro">
              <div>
                <span className="section-kicker">DOCUMENT INTELLIGENCE</span>
                <h2>Your document, organized.</h2>
                <p>
                  {documentInfo?.filename}
                  {documentInfo?.pages
                    ? ` · ${documentInfo.pages} page${documentInfo.pages === 1 ? "" : "s"}`
                    : ""}
                  {documentInfo?.is_saved
                    ? " · Saved to your workspace"
                    : " · Ephemeral (Sign in to save)"}
                </p>
              </div>
              <button className="text-button" onClick={resetDocument} type="button">
                Analyze another PDF <span aria-hidden="true">→</span>
              </button>
            </div>

            <div className="metrics">
              <article className="metric-card blue">
                <span className="metric-icon">▤</span>
                <span>
                  <small>Document Type</small>
                  <strong>{analysis.document_type.replaceAll("_", " ")}</strong>
                </span>
              </article>
              <article className="metric-card purple">
                <span className="metric-icon">✓</span>
                <span>
                  <small>Tasks Found</small>
                  <strong>{tasks.length}</strong>
                </span>
              </article>
              <article className="metric-card red">
                <span className="metric-icon">!</span>
                <span>
                  <small>High Priority</small>
                  <strong>{highCount}</strong>
                </span>
              </article>
              <article className="metric-card orange">
                <span className="metric-icon">◷</span>
                <span>
                  <small>Deadlines</small>
                  <strong>{deadlines.length || deadlineCount}</strong>
                </span>
              </article>
              <article className="metric-card green">
                <span className="metric-icon">◈</span>
                <span>
                  <small>Rules Detected</small>
                  <strong>{rules.length}</strong>
                </span>
              </article>
            </div>

            <div className="summary-strip">
              <div>
                <span className="section-kicker">AI SUMMARY</span>
                <p>{analysis.summary}</p>
              </div>
              <div className="progress-box">
                <div className="progress-info">
                  <strong>Tasks completed</strong>
                  <span>{completionPercent}%</span>
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

            {/* Analysis Category Tabs */}
            <div className="analysis-tab-bar">
              <button
                className={`analysis-tab-btn ${analysisActiveTab === "tasks" ? "active" : ""}`}
                onClick={() => setAnalysisActiveTab("tasks")}
                type="button"
              >
                Actionable Tasks ({tasks.length})
              </button>
              <button
                className={`analysis-tab-btn ${analysisActiveTab === "rules" ? "active" : ""}`}
                onClick={() => setAnalysisActiveTab("rules")}
                type="button"
              >
                Important Rules ({rules.length})
              </button>
              <button
                className={`analysis-tab-btn ${analysisActiveTab === "deadlines" ? "active" : ""}`}
                onClick={() => setAnalysisActiveTab("deadlines")}
                type="button"
              >
                Key Deadlines ({deadlines.length})
              </button>
            </div>

            {/* TAB 1: ACTIONABLE TASKS */}
            {analysisActiveTab === "tasks" && (
              <>
                <div className="tasks-heading">
                  <div>
                    <span className="section-kicker">ACTION CENTER</span>
                    <h2>Actionable Tasks</h2>
                    <p>Things you need to do extracted directly from the document.</p>
                  </div>
                  <label className="sort-control">
                    <span className="visually-hidden">Sort tasks</span>
                    <select
                      value={sortBy}
                      onChange={(event) => setSortBy(event.target.value)}
                    >
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
                            <span className={`priority ${priority.toLowerCase()}`}>
                              {priority}
                            </span>
                            <div className="task-top-right">
                              <span className="confidence">
                                {Math.round((task.confidence ?? 0) * 100)}% confidence
                              </span>
                              <button
                                className="why-link"
                                onClick={() => handleExplain(task, "Actionable Task")}
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
                          <button
                            className={`complete-button ${isCompleted ? "is-complete" : ""}`}
                            onClick={() => toggleTask(task.originalIndex, task.id)}
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
              </>
            )}

            {/* TAB 2: IMPORTANT RULES */}
            {analysisActiveTab === "rules" && (
              <div>
                <div className="tasks-heading">
                  <div>
                    <span className="section-kicker">COMPLIANCE &amp; POLICY</span>
                    <h2>Important Rules</h2>
                    <p>
                      Mandatory obligations, prohibitions, and guidelines to be aware of.
                    </p>
                  </div>
                </div>

                {rules.length ? (
                  <div className="rules-grid">
                    {rules.map((rule, idx) => {
                      const ruleTypeClass = rule.rule_type.toLowerCase();
                      return (
                        <article
                          className={`rule-card ${ruleTypeClass}`}
                          key={rule.id || idx}
                        >
                          <div className="rule-top">
                            <span className={`rule-type-badge ${ruleTypeClass}`}>
                              {rule.rule_type}
                            </span>
                            <div className="rule-top-right">
                              <span className="confidence">
                                {Math.round((rule.confidence ?? 0.85) * 100)}% confidence
                              </span>
                              <button
                                className="why-link"
                                onClick={() => handleExplain(rule, "Compliance Rule")}
                                type="button"
                              >
                                Why detected?
                              </button>
                            </div>
                          </div>
                          <h3>"{rule.rule}"</h3>
                          <div className="rule-meta">
                            <div>
                              <span>Category</span>
                              <strong>{rule.category || "General"}</strong>
                            </div>
                          </div>
                        </article>
                      );
                    })}
                  </div>
                ) : (
                  <div className="empty-tasks">
                    No explicit compliance rules or prohibitions detected in this document.
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: KEY DEADLINES */}
            {analysisActiveTab === "deadlines" && (
              <div>
                <div className="tasks-heading">
                  <div>
                    <span className="section-kicker">IMPORTANT DATES</span>
                    <h2>Key Deadlines</h2>
                    <p>Time-sensitive milestones recognized from this document.</p>
                  </div>
                </div>

                {deadlines.length ? (
                  <div className="deadlines-list-grid">
                    {deadlines.map((dl, idx) => (
                      <article className="deadline-card" key={dl.id || idx}>
                        <div className="deadline-card-header">
                          <div className="deadline-date-pill large">
                            <strong>{dl.deadline_date}</strong>
                            <small>OFFICIAL DEADLINE</small>
                          </div>
                          <button
                            className="why-link"
                            onClick={() => handleExplain(dl, "Deadline")}
                            type="button"
                          >
                            Why detected?
                          </button>
                        </div>
                        <h3>{dl.description}</h3>
                      </article>
                    ))}
                  </div>
                ) : (
                  <div className="empty-tasks">
                    No explicit deadline dates found in this document.
                  </div>
                )}
              </div>
            )}
          </section>
        )}

        {/* Informational Marketing Sections (Always present for reference) */}
        {activeView === "home" && (
          <>
            <section className="document-types page-width" id="features">
              <span className="section-kicker">BUILT FOR REAL DOCUMENTS</span>
              <h2>Works with the documents you already receive.</h2>
              <div className="document-type-grid">
                <a href="#workspace" onClick={scrollToUpload}>
                  <span className="type-icon lavender">▤</span>
                  <span>
                    <strong>Notices</strong>
                    <small>College and institutional notices</small>
                  </span>
                  <b>→</b>
                </a>
                <a href="#workspace" onClick={scrollToUpload}>
                  <span className="type-icon rose">◈</span>
                  <span>
                    <strong>Circulars</strong>
                    <small>Official announcements</small>
                  </span>
                  <b>→</b>
                </a>
                <a href="#workspace" onClick={scrollToUpload}>
                  <span className="type-icon amber">▣</span>
                  <span>
                    <strong>Guidelines</strong>
                    <small>Policies and academic guidelines</small>
                  </span>
                  <b>→</b>
                </a>
                <a href="#workspace" onClick={scrollToUpload}>
                  <span className="type-icon mint">⌂</span>
                  <span>
                    <strong>Institutional PDFs</strong>
                    <small>Official documents and instructions</small>
                  </span>
                  <b>→</b>
                </a>
              </div>
            </section>

            <section className="how-section page-width" id="how-it-works">
              <div className="section-heading-centered">
                <span className="section-kicker">HOW IT WORKS</span>
                <h2>A clearer way to handle important documents.</h2>
                <p>
                  No complicated workflow. Upload your document and let DocuGuard organize
                  what needs your attention.
                </p>
              </div>
              <div className="steps-grid">
                <article className="step-card">
                  <span className="step-number">01</span>
                  <span className="step-icon">↑</span>
                  <h3>Upload</h3>
                  <p>Select the PDF you want DocuGuard to understand.</p>
                </article>
                <article className="step-card">
                  <span className="step-number">02</span>
                  <span className="step-icon">✦</span>
                  <h3>Analyze</h3>
                  <p>AI extracts relevant actions, priorities and available deadlines.</p>
                </article>
                <article className="step-card">
                  <span className="step-number">03</span>
                  <span className="step-icon">✓</span>
                  <h3>Take Action</h3>
                  <p>Review your task list and mark completed actions.</p>
                </article>
              </div>
            </section>

            <section className="about-section page-width" id="about">
              <div>
                <span className="section-kicker">ABOUT DOCUGUARD</span>
                <h2>
                  Less time reading.
                  <br />
                  More time acting.
                </h2>
              </div>
              <p>
                DocuGuard AI turns information-heavy documents into simple, understandable
                actions. The goal is straightforward: help you notice what matters without
                making you dig through every page.
              </p>
            </section>
          </>
        )}
      </main>

      <footer className="site-footer page-width">
        <a className="footer-brand" href="#home">
          DocuGuard AI <span>From documents to action.</span>
        </a>
        <span>Intelligent Document-to-Action SaaS Platform</span>
      </footer>

      {/* MODALS */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        initialMode={authModalMode}
        onAuthSuccess={handleAuthSuccess}
      />

      <ProfileModal
        isOpen={profileModalOpen}
        onClose={() => setProfileModalOpen(false)}
        user={currentUser}
        onLogout={handleLogout}
      />

      <ExplainModal
        isOpen={explainModalOpen}
        onClose={() => setExplainModalOpen(false)}
        item={explainItem}
        type={explainType}
      />
    </div>
  );
}

export default App;
