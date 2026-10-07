import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function DocumentsView({ onOpenDocument, onQuickUploadClick }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    let isCurrent = true;
    const fetchDocs = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await api.listDocuments(search, typeFilter);
        if (isCurrent) setDocuments(data);
      } catch (err) {
        if (isCurrent) setError(err.message || "Failed to load document history.");
      } finally {
        if (isCurrent) setLoading(false);
      }
    };

    fetchDocs();
    return () => {
      isCurrent = false;
    };
  }, [search, typeFilter]);

  const handleDelete = async (docId, filename) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}" and its extracted records?`)) {
      return;
    }

    setDeletingId(docId);
    try {
      await api.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (err) {
      alert(err.message || "Could not delete document.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <section className="documents-view-section page-width">
      <div className="section-header-row">
        <div>
          <span className="section-kicker">DOCUMENT ARCHIVE</span>
          <h2>Document History</h2>
          <p>Search, review, and manage your analyzed PDFs and compliance notices.</p>
        </div>
        <button className="primary-button" onClick={onQuickUploadClick} type="button">
          ↑ Upload New PDF
        </button>
      </div>

      <div className="filter-search-bar">
        <div className="search-input-wrapper">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search documents by filename…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button className="clear-search" onClick={() => setSearch("")} type="button">
              ✕
            </button>
          )}
        </div>

        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="type-filter-select"
        >
          <option value="">All Document Types</option>
          <option value="examination_notice">Examination Notice</option>
          <option value="placement_notice">Placement Notice</option>
          <option value="scholarship_notice">Scholarship Notice</option>
          <option value="internship_notice">Internship Notice</option>
          <option value="circular">Circular</option>
          <option value="general_notice">General Notice</option>
        </select>
      </div>

      {loading ? (
        <div className="workspace-loading">
          <span className="spinner" />
          <p>Retrieving documents…</p>
        </div>
      ) : error ? (
        <div className="upload-error" role="alert">
          ⚠ {error}
        </div>
      ) : documents.length === 0 ? (
        <div className="empty-state-card">
          <span className="empty-icon">▤</span>
          <h3>{search || typeFilter ? "No matching documents found" : "No documents saved yet"}</h3>
          <p>
            {search || typeFilter
              ? "Try adjusting your search terms or filters."
              : "Upload an institutional PDF to start building your persistent intelligence workspace."}
          </p>
          <button className="primary-button" onClick={onQuickUploadClick} type="button">
            Upload Document Now
          </button>
        </div>
      ) : (
        <div className="documents-table-wrapper">
          <table className="documents-table">
            <thead>
              <tr>
                <th>Document Name</th>
                <th>Type</th>
                <th>Pages</th>
                <th>Tasks</th>
                <th>Rules</th>
                <th>Deadlines</th>
                <th>Uploaded</th>
                <th className="actions-header">Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => {
                const completionPct = doc.task_count
                  ? Math.round((doc.completed_task_count / doc.task_count) * 100)
                  : 0;

                return (
                  <tr key={doc.id}>
                    <td className="doc-name-cell">
                      <span className="pdf-badge">PDF</span>
                      <div>
                        <strong>{doc.filename}</strong>
                        <small>{doc.summary ? doc.summary.slice(0, 75) + "…" : ""}</small>
                      </div>
                    </td>
                    <td>
                      <span className="doc-type-tag">
                        {doc.document_type.replaceAll("_", " ")}
                      </span>
                    </td>
                    <td>{doc.pages}</td>
                    <td>
                      <div className="table-task-progress">
                        <span>
                          {doc.completed_task_count}/{doc.task_count}
                        </span>
                        <div className="mini-progress-bar">
                          <span style={{ width: `${completionPct}%` }} />
                        </div>
                      </div>
                    </td>
                    <td>{doc.rule_count}</td>
                    <td>{doc.deadline_count}</td>
                    <td className="date-cell">
                      {new Date(doc.upload_timestamp).toLocaleDateString(undefined, {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </td>
                    <td className="actions-cell">
                      <button
                        className="text-button"
                        onClick={() => onOpenDocument(doc.id)}
                        type="button"
                      >
                        Open Analysis
                      </button>
                      <button
                        className="delete-button"
                        onClick={() => handleDelete(doc.id, doc.filename)}
                        disabled={deletingId === doc.id}
                        type="button"
                        title="Delete Document"
                      >
                        {deletingId === doc.id ? "…" : "🗑"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
