# Changelog

All notable changes to this project are documented in this file.

---

## [0.2.0] — 2026-02-21

### Added

- Admin HTML dashboard with action controls
- `/admin/health` status page
- Structured JSON request details storage
- Workflow state machine:
  - Pending → Approved / Rejected → Completed
- Approval audit fields:
  - approved_by
  - approved_at
  - completed_at
  - rejected_reason
- Phone UI: "My Requests" list and detail view
- Softkey navigation (Home / Back / Exit)
- Input validation for DN label requests
- Dark-mode-aware admin styling

### Changed

- Renamed database from `tickets.db` to `requests.db`
- Renamed branding to "UC Self-Service"
- Improved admin dashboard layout
- Standardized UTC timestamps
- Replaced flat detail strings with structured JSON payloads

### Fixed

- Cisco IP Phone XML compatibility issues (input screen limits)
- HTML escaping in admin views
- Unsafe SQL string construction

### Security

- Admin access restricted via Nginx Basic Auth
- Flask admin endpoints protected with allowlist authorization
