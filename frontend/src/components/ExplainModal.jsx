export default function ExplainModal({ isOpen, onClose, item, type = "Task" }) {
  if (!isOpen || !item) return null;

  const title = item.task || item.rule || item.description || "Extracted Statement";
  const confidencePercent = Math.round((item.confidence ?? 0.8) * 100);
  const reason =
    item.detection_reason ||
    "Identified via institutional rule and deterministic NLP extraction heuristics.";
  const sourceSnippet = item.source_snippet || title;

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card explain-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-copy">
            <span className="section-kicker">EXPLAINABILITY &amp; AUDIT</span>
            <h2>Why Was This Detected?</h2>
            <p>Inspection details and deterministic signal breakdown.</p>
          </div>
          <button className="modal-close" onClick={onClose} type="button" aria-label="Close modal">
            ✕
          </button>
        </div>

        <div className="explain-body">
          <div className="explain-item-preview">
            <div className="explain-tags">
              <span className="explain-type-badge">{type}</span>
              {item.priority && (
                <span className={`priority ${item.priority.toLowerCase()}`}>
                  {item.priority} Priority
                </span>
              )}
              {item.rule_type && (
                <span className={`rule-type-badge ${item.rule_type.toLowerCase()}`}>
                  {item.rule_type}
                </span>
              )}
              {item.category && <span className="category-badge">{item.category}</span>}
              {item.deadline && (
                <span className="deadline-badge">Due: {item.deadline}</span>
              )}
            </div>
            <h3>"{title}"</h3>
          </div>

          <div className="explain-metric-strip">
            <div className="explain-metric-item">
              <span>Detection Confidence</span>
              <strong>{confidencePercent}%</strong>
            </div>
            <div className="explain-metric-item">
              <span>Classifier Engine</span>
              <strong>Deterministic Pattern Engine</strong>
            </div>
            <div className="explain-metric-item">
              <span>Signal Integrity</span>
              <strong>Direct Document Match</strong>
            </div>
          </div>

          <div className="explain-box">
            <div className="explain-box-heading">
              <span className="explain-icon">✦</span>
              <strong>Detection Rationale</strong>
            </div>
            <p>{reason}</p>
          </div>

          <div className="source-box">
            <div className="source-box-heading">
              <span className="source-icon">▤</span>
              <strong>Source Statement from Document</strong>
            </div>
            <blockquote>"{sourceSnippet}"</blockquote>
            <small>Direct sentence match from processed PDF text</small>
          </div>

          <div className="modal-actions-right">
            <button className="secondary-button" onClick={onClose} type="button">
              Close Inspection
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
