export default function ProfileModal({ isOpen, onClose, user, onLogout }) {
  if (!isOpen || !user) return null;

  const initials = user.full_name
    ? user.full_name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "DG";

  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : "Active";

  return (
    <div className="modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="modal-card profile-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-header-copy">
            <span className="section-kicker">USER PROFILE</span>
            <h2>Account Details</h2>
          </div>
          <button className="modal-close" onClick={onClose} type="button" aria-label="Close modal">
            ✕
          </button>
        </div>

        <div className="profile-body">
          <div className="profile-identity-card">
            <div className="profile-avatar-large">{initials}</div>
            <div className="profile-identity-text">
              <strong>{user.full_name}</strong>
              <span>{user.email}</span>
              <small>Member since {memberSince}</small>
            </div>
          </div>

          <div className="profile-info-grid">
            <div className="profile-info-item">
              <label>Workspace Plan</label>
              <strong>Enterprise Intelligence (Standard)</strong>
            </div>
            <div className="profile-info-item">
              <label>Security &amp; Auth</label>
              <strong>JWT Session Active</strong>
            </div>
          </div>

          <div className="profile-actions">
            <button
              className="logout-button"
              onClick={() => {
                onLogout();
                onClose();
              }}
              type="button"
            >
              Sign Out of DocuGuard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
