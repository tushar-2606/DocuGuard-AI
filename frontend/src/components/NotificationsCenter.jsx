import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../services/api";

const stageLabels = {
  three_days: "Due in 3 days",
  one_day: "Due tomorrow",
  at_deadline: "Due now",
  overdue: "Overdue",
};

export default function NotificationsCenter({ onOpenTarget, onOpenDocument }) {
  const [items, setItems] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState("");
  const seenIds = useRef(null);
  const containerRef = useRef(null);

  const openNotification = useCallback(async (item) => {
    try {
      if (!item.is_read) {
        await api.markNotificationRead(item.id);
        setItems((current) =>
          current.map((entry) =>
            entry.id === item.id ? { ...entry, is_read: true } : entry,
          ),
        );
        setUnreadCount((current) => Math.max(0, current - 1));
      }
      setIsOpen(false);
      onOpenTarget(item);
    } catch (requestError) {
      setError(requestError.message || "Could not open this reminder.");
    }
  }, [onOpenTarget]);

  const refresh = useCallback(async () => {
    try {
      const [nextItems, count, preferences] = await Promise.all([
        api.listNotifications(),
        api.getUnreadNotificationCount(),
        api.getReminderPreferences(),
      ]);
      const previousIds = seenIds.current;
      seenIds.current = new Set(nextItems.map((item) => item.id));
      setItems(nextItems);
      setUnreadCount(count.unread_count ?? 0);
      setError("");

      const browserNotificationsAvailable =
        typeof window !== "undefined" &&
        "Notification" in window &&
        window.Notification.permission === "granted";
      if (
        previousIds &&
        preferences.enabled &&
        preferences.desktop_enabled &&
        browserNotificationsAvailable
      ) {
        const newlyAdded = nextItems.filter(
          (item) => !previousIds.has(item.id) && !item.is_read,
        );
        for (const item of newlyAdded) {
          const claim = await api.claimDesktopNotification(item.id);
          if (!claim.delivered) continue;
          const notification = new window.Notification(item.title, {
            body: item.message,
            tag: `docuguard-${item.id}`,
          });
          notification.onclick = () => {
            window.focus();
            openNotification(item);
          };
        }
      }
    } catch (requestError) {
      setError(requestError.message || "Could not load notifications.");
    }
  }, [openNotification]);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => void refresh(), 0);
    const timer = window.setInterval(() => void refresh(), 30000);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [refresh]);

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  const markAllRead = async () => {
    try {
      await api.markAllNotificationsRead();
      await refresh();
    } catch (requestError) {
      setError(requestError.message || "Could not mark reminders as read.");
    }
  };

  return (
    <div className="notifications-center" ref={containerRef}>
      <button
        className="notification-bell"
        type="button"
        aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span aria-hidden="true">♢</span>
        {unreadCount > 0 && (
          <span className="notification-count">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <section className="notification-popover" aria-label="Notifications">
          <div className="notification-popover-header">
            <div>
              <strong>Reminders</strong>
              <small>{unreadCount} unread</small>
            </div>
            {unreadCount > 0 && (
              <button type="button" onClick={markAllRead}>
                Mark all read
              </button>
            )}
          </div>
          {error && <p className="notification-error" role="alert">{error}</p>}
          {items.length === 0 ? (
            <p className="notification-empty">No reminders yet.</p>
          ) : (
            <div className="notification-list">
              {items.map((item) => (
                <article
                  className={`notification-item ${item.is_read ? "read" : "unread"}`}
                  key={item.id}
                >
                  <button
                    className="notification-item-open"
                    type="button"
                    onClick={() => openNotification(item)}
                  >
                    <strong>{item.title}</strong>
                    <span>{stageLabels[item.stage] || "Deadline reminder"}</span>
                    <small>{item.message}</small>
                    {item.email_status === "failed" && (
                      <small className="notification-delivery-error">
                        Email delivery failed: {item.email_last_error || "check SMTP configuration"}
                      </small>
                    )}
                    {item.email_status === "not_configured" && (
                      <small>Email is not configured; this in-app reminder is available.</small>
                    )}
                  </button>
                  <button
                    className="notification-source-link"
                    type="button"
                    onClick={() => {
                      setIsOpen(false);
                      onOpenDocument(item.document_id);
                    }}
                  >
                    Source: {item.document_name}
                  </button>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
