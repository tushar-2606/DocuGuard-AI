# Deadline reminders

DocuGuard generates reminder records for saved, incomplete tasks and standalone
deadlines. The worker reads the existing task and deadline rows; it does not
reprocess PDFs or rewrite extracted records.

## Scheduling behavior

- Default stages are three days before, one day before, and at the deadline.
  Each stage can be enabled or disabled per user. Overdue reminders are opt-in
  and disabled by default.
- A deadline with no explicit time uses `DEFAULT_DATE_ONLY_REMINDER_TIME` for
  new preferences and the user's selected IANA timezone. The application
  default timezone is `APP_TIMEZONE` (`UTC` by default).
- The backend checks on `REMINDER_CHECK_INTERVAL_SECONDS` (60 seconds by
  default; values below 15 are clamped). The check runs immediately on startup.
- If the server misses a scheduled check, the next pass emits only the most
  recent eligible pre-deadline stage. At/after the deadline, a due-time reminder
  is emitted only within two check intervals (at least 120 seconds), unless the
  user opted into overdue reminders.
- Completed tasks and completed deadlines are excluded from future checks.
  When an incomplete task and a standalone deadline from the same document
  have the same date, the task is the reminder target; the standalone deadline
  is used when no incomplete task represents that date.
- Reminder keys are unique by user, target, stage, and deadline date. Date/time
  edits therefore do not create duplicate stage notifications for the same
  target/date. Already delivered notifications remain in history; no stale
  future schedule rows are maintained.

The scheduler is in-process and starts with the FastAPI lifespan. Database
uniqueness and atomic email claims prevent duplicate reminder records and
concurrent email sends across scheduler instances. For production, run the
scheduler with a deployment topology appropriate to the database and SMTP
provider; a durable external job queue is not included.

## Delivery channels

- In-app notifications are saved in the database and appear in the bell
  notification center, including when optional email delivery is disabled.
- Desktop browser notifications are requested only after the user presses
  **Enable desktop alerts**. Browser notifications are best effort and only
  delivered while the application is open. They do not work after the browser
  is closed because this project does not include Web Push or a service worker.
- Email is sent only after a user enables the email preference and the backend
  has SMTP configured. Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, and,
  when needed, both `SMTP_USERNAME` and `SMTP_PASSWORD`. Use TLS or SSL when
  using credentials; TLS and SSL options are mutually exclusive. Secrets belong
  in the deployment environment or an untracked `.env`, never in source
  control. Failed sends are recorded on the notification and logged without
  logging credentials.

## Persistence and API

The new `reminder_preferences` and `notifications` tables are created
additively by the existing SQLAlchemy `create_all` initialization. No existing
table is dropped or reset. The API is authenticated and all preference,
notification, target, and source-document queries are scoped to the current
user. Notification history is removed by the database's existing document,
task, deadline, and user cascades when the corresponding source record is
explicitly deleted.

The notification center checks for new records while the authenticated app is
open. The settings screen exposes the per-user schedule, timezone, date-only
time, email opt-in, browser permission status, SMTP configuration status, and
the scheduler interval.
