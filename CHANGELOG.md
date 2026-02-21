# Changelog

All notable changes to this project will be documented in this file.

This project follows a simple semantic versioning approach.

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
- Phone UI: “My Requests” list and detail view
- Softkey navigation improvements (Home / Back / Exit)
- Input validation for DN label requests
- Dark-mode-aware admin styling
- Documentation improvements and workflow screenshots

### Changed

- Renamed database from `tickets.db` to `requests.db`
- Refined branding to “UC Self-Service”
- Improved admin dashboard layout and usability
- Standardized UTC timestamps
- Replaced flat detail strings with structured JSON payloads

### Fixed

- Cisco IP Phone XML compatibility issues (input screen limits)
- HTML escaping issues in admin views
- Removed unsafe SQL string construction

### Security

- Admin access restricted via Nginx Basic Auth
- Flask admin endpoints protected with allowlist authorization
