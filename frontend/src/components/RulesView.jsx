import { useEffect, useState } from "react";
import { api } from "../services/api";

export default function RulesView({ onOpenDocument, onExplainItem }) {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ruleTypeFilter, setRuleTypeFilter] = useState("ALL");

  useEffect(() => {
    let isCurrent = true;
    const fetchRules = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await api.listRules(ruleTypeFilter === "ALL" ? "" : ruleTypeFilter);
        if (isCurrent) setRules(data);
      } catch (err) {
        if (isCurrent) setError(err.message || "Failed to load rules.");
      } finally {
        if (isCurrent) setLoading(false);
      }
    };

    fetchRules();
    return () => {
      isCurrent = false;
    };
  }, [ruleTypeFilter]);

  return (
    <section className="rules-view-section page-width">
      <div className="section-header-row">
        <div>
          <span className="section-kicker">COMPLIANCE &amp; POLICY RADAR</span>
          <h2>Important Rules &amp; Guidelines</h2>
          <p>
            Regulatory requirements, prohibitions, and official codes extracted from institutional
            documents.
          </p>
        </div>
      </div>

      <div className="filters-bar-horizontal">
        <div className="tab-filters">
          {[
            ["ALL", "All Rules"],
            ["MANDATORY", "Mandatory"],
            ["PROHIBITED", "Prohibited"],
            ["RECOMMENDED", "Recommended"],
          ].map(([val, label]) => (
            <button
              className={`filter-pill ${ruleTypeFilter === val ? "active" : ""}`}
              key={val}
              onClick={() => setRuleTypeFilter(val)}
              type="button"
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="workspace-loading">
          <span className="spinner" />
          <p>Loading rules…</p>
        </div>
      ) : error ? (
        <div className="upload-error" role="alert">
          ⚠ {error}
        </div>
      ) : rules.length === 0 ? (
        <div className="empty-state-card">
          <span className="empty-icon">!</span>
          <h3>No rules found</h3>
          <p>No compliance requirements or prohibitions match your selected filter.</p>
        </div>
      ) : (
        <div className="rules-grid">
          {rules.map((rule) => {
            const ruleTypeClass = rule.rule_type.toLowerCase();

            return (
              <article className={`rule-card ${ruleTypeClass}`} key={rule.id}>
                <div className="rule-top">
                  <span className={`rule-type-badge ${ruleTypeClass}`}>{rule.rule_type}</span>
                  <div className="rule-top-right">
                    <span className="confidence">
                      {Math.round((rule.confidence ?? 0.85) * 100)}% confidence
                    </span>
                    <button
                      className="why-link"
                      onClick={() => onExplainItem(rule, "Compliance Rule")}
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
                  <div>
                    <span>Source Document</span>
                    <button
                      className="doc-link-button"
                      onClick={() => onOpenDocument(rule.document_id)}
                      type="button"
                    >
                      {rule.document_name}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
