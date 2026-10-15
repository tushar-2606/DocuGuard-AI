import { useEffect, useState } from "react";
import { Bell, Clock, Globe, Mail, Monitor, CheckCircle2, AlertTriangle } from "lucide-react";
import { api } from "../services/api";

const reminderOptions = [
  ["remind_three_days", "3 days before"],
  ["remind_one_day", "1 day before"],
  ["remind_at_deadline", "At the deadline"],
  ["remind_overdue", "When an item becomes overdue"],
];

export default function ReminderSettingsView() {
  const [preferences, setPreferences] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [desktopMessage, setDesktopMessage] = useState("");
  const [desktopPermission, setDesktopPermission] = useState(() =>
    typeof window !== "undefined" && "Notification" in window
      ? window.Notification.permission
      : "unsupported",
  );

  useEffect(() => {
    let active = true;
    api.getReminderPreferences()
      .then((data) => {
        if (active) setPreferences(data);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || "Could not load reminder settings.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const save = async (updates) => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const updated = await api.updateReminderPreferences(updates);
      setPreferences(updated);
      setSaved(true);
    } catch (requestError) {
      setError(requestError.message || "Could not save reminder settings.");
    } finally {
      setSaving(false);
    }
  };

  const setToggle = (field, checked) => {
    setPreferences((current) => ({ ...current, [field]: checked }));
    save({ [field]: checked });
  };

  const enableDesktopNotifications = async () => {
    if (!("Notification" in window)) {
      setDesktopMessage("This browser does not support desktop notifications.");
      return;
    }
    try {
      const permission = await window.Notification.requestPermission();
      setDesktopPermission(permission);
      if (permission === "granted") {
        setDesktopMessage("Desktop notifications are enabled while this app is open.");
        setToggle("desktop_enabled", true);
      } else {
        setDesktopMessage(
          permission === "denied"
            ? "Permission was denied. Update this site's notification permission in your browser settings."
            : "Permission was not granted.",
        );
        if (preferences.desktop_enabled) setToggle("desktop_enabled", false);
      }
    } catch (requestError) {
      setDesktopMessage(requestError.message || "Could not request desktop notification permission.");
    }
  };

  const saveDeviceTimezone = () => {
    const deviceTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    if (deviceTimezone) {
      setPreferences((current) => ({ ...current, timezone: deviceTimezone }));
      save({ timezone: deviceTimezone });
    }
  };

  if (loading) {
    return (
      <div className="workspace-loading page-width">
        <span className="spinner" />
        <p>Loading reminder settings…</p>
      </div>
    );
  }

  if (!preferences) {
    return (
      <section className="reminder-settings page-width">
        <p className="upload-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </p>
      </section>
    );
  }

  return (
    <section className="reminder-settings page-width">
      <div className="section-header-row">
        <div>
          <span className="section-kicker">PERSONAL PREFERENCES</span>
          <h2>Deadline Reminders &amp; Delivery</h2>
          <p>Choose when DocuGuard reminds you about your incomplete tasks and deadlines.</p>
        </div>
      </div>

      {error && (
        <div className="upload-error" role="alert">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}
      {saved && !saving && (
        <div className="settings-saved" role="status">
          <CheckCircle2 size={15} />
          <span>Settings saved successfully.</span>
        </div>
      )}

      <div className="reminder-settings-card">
        <label className="reminder-setting-row highlight-row">
          <span>
            <strong className="setting-title-with-icon">
              <Bell size={16} />
              <span>Enable In-App Reminders</span>
            </strong>
            <small>Active alerts surface directly in your notification center.</small>
          </span>
          <input
            type="checkbox"
            checked={preferences.enabled}
            onChange={(event) => setToggle("enabled", event.target.checked)}
            disabled={saving}
          />
        </label>

        <fieldset disabled={!preferences.enabled || saving} className="reminder-fieldset">
          <legend>
            <Clock size={14} />
            <span>Reminder Schedule</span>
          </legend>
          {reminderOptions.map(([field, label]) => (
            <label className="reminder-setting-row" key={field}>
              <span>{label}</span>
              <input
                type="checkbox"
                checked={preferences[field]}
                onChange={(event) => setToggle(field, event.target.checked)}
              />
            </label>
          ))}

          <div className="reminder-timezone-fields">
            <label>
              <span>Date-only reminder time</span>
              <input
                type="time"
                value={preferences.date_only_time}
                onChange={(event) =>
                  setPreferences((current) => ({
                    ...current,
                    date_only_time: event.target.value,
                  }))
                }
                onBlur={(event) => save({ date_only_time: event.target.value })}
              />
            </label>
            <label>
              <span>Timezone (IANA)</span>
              <span className="timezone-input-row">
                <input
                  type="text"
                  value={preferences.timezone}
                  onChange={(event) =>
                    setPreferences((current) => ({
                      ...current,
                      timezone: event.target.value,
                    }))
                  }
                  onBlur={(event) => save({ timezone: event.target.value })}
                />
                <button type="button" onClick={saveDeviceTimezone} className="secondary-button mini">
                  <Globe size={13} />
                  <span>Use device</span>
                </button>
              </span>
            </label>
          </div>

          <label className="reminder-setting-row">
            <span>
              <strong className="setting-title-with-icon">
                <Mail size={16} />
                <span>Email Notifications</span>
              </strong>
              <small>
                {preferences.email_configured
                  ? "Uses the server's configured SMTP service for delivery."
                  : "Email is not configured on the server; in-app reminders will still work."}
              </small>
            </span>
            <input
              type="checkbox"
              checked={preferences.email_enabled}
              onChange={(event) => setToggle("email_enabled", event.target.checked)}
            />
          </label>

          <div className="desktop-reminder-setting">
            <div>
              <strong className="setting-title-with-icon">
                <Monitor size={16} />
                <span>Desktop Browser Alerts</span>
              </strong>
              <small>
                Delivered while DocuGuard is active in your browser.
              </small>
              <small className="browser-perm-info">Browser permission: <b>{desktopPermission}</b></small>
              {desktopMessage && <small className="desktop-feedback-msg" role="status">{desktopMessage}</small>}
            </div>
            {preferences.desktop_enabled ? (
              <button
                type="button"
                className="secondary-button"
                onClick={() => setToggle("desktop_enabled", false)}
              >
                Disable desktop alerts
              </button>
            ) : (
              <button
                type="button"
                className="secondary-button"
                onClick={enableDesktopNotifications}
              >
                Enable desktop alerts
              </button>
            )}
          </div>
        </fieldset>
      </div>

      <p className="reminder-settings-note">
        Checks run about every {preferences.scheduler_interval_seconds} seconds. If the server is offline, it catches up to the most recent eligible pre-deadline reminder; overdue reminders are sent only when enabled. Date-only deadlines use the selected local time.
      </p>
    </section>
  );
}
