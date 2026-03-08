![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-lab--demo-orange)
![Platform](https://img.shields.io/badge/platform-Cisco%20IP%20Phones-lightgrey)
![Version](https://img.shields.io/badge/version-0.2.0-blue)

# UC Self-Service — Cisco IP Phone Services

Flask application that enables end users to submit administrative
requests directly from Cisco IP desk phones. Requests are tracked,
reviewed, and approved by administrators through a web-based dashboard.

Designed for Cisco UC environments running CUCM. Currently in lab
validation with production deployment as a target.

---

## Capabilities (v0.2.0)

- Phone display name update request workflow
- Per-phone request history and detail view
- Admin dashboard with approval workflow (Approve / Reject / Complete)
- Audit trail with status tracking and actor attribution
- Structured request lifecycle with validated state transitions
- Deployment model suitable for standalone or infrastructure-integrated hosts

---

## Architecture

```
Cisco IP Phones
→ Nginx (reverse proxy + authentication)
→ Gunicorn (WSGI, localhost only)
→ Flask (application logic)
→ SQLite (request storage)
```

---

## Design Principles

- Minimal dependencies — runs on a single host with no external services
- Separation of responsibilities — Nginx handles auth, Flask handles logic
- Environment-driven configuration — no credentials in code
- Controlled workflow — all state changes validated through a single transition function
- Incremental development — request collection first, automation later

---

## Phone User Workflow

### Service Menu

Users launch UC Self-Service from the phone's Services menu.

![Phone menu](docs/screenshots/v0.2.0/01-phone-menu.png)

---

### Submit Display Name Update

The user provides:

- Directory Number (DN)
- Requested display name
- Justification

![Phone dnlabel](docs/screenshots/v0.2.0/02-phone-dnlabel.png)

---

### Submission Confirmation

A Pending request is created with a unique ID.

![Phone submitted](docs/screenshots/v0.2.0/03-phone-submitted.png)

---

### View Recent Requests

Users can review their most recent submissions from the same phone/IP.

![Phone requests](docs/screenshots/v0.2.0/04-phone-requests.png)

---

### Request Details

Detailed view includes request ID, status, DN, requested name, justification, and timestamp.

![Phone details](docs/screenshots/v0.2.0/05-phone-details.png)

---

### Physical Phone Example

Tested on Cisco 8841 and 7841 handsets.

![Phone 8841](docs/screenshots/v0.2.0/06-phone-8841.png)

![Phone 7841](docs/screenshots/v0.2.0/07-phone-7841.png)

---

## Administrator Workflow

### Admin Dashboard

Administrators authenticate via Nginx Basic Auth and manage requests through a web dashboard.

- Recent request list (newest 50)
- Color-coded status indicators
- Approve / Reject / Complete actions
- Inline reject reason entry
- Audit information
- Automatic light/dark mode support

![Admin dashboard](docs/screenshots/v0.2.0/08-admin-dashboard.png)

---

## Request Lifecycle

All requests follow a validated state machine:

```
Pending → Approved → Completed
Pending → Rejected
```

Transitions are enforced server-side. Invalid transitions are rejected.

---

## Security

- Authentication: Nginx (Basic Auth)
- Authorization: Flask admin allowlist
- Network: Application bound to localhost behind reverse proxy
- Data: Parameterized queries, structured JSON payloads
- Audit: Status changes recorded with actor, timestamp, and reason

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Production Readiness](docs/PRODUCTION_READINESS.md)
- [Risk Matrix](docs/RISK_MATRIX.md)

---

## Roadmap

Planned features and milestones are tracked in the [Project Roadmap](docs/ROADMAP.md).

---

## Status

This project is in active development. Currently validated in a lab
environment against Cisco 7841, 8841, and 9861 handsets.

Not yet recommended for production use without additional hardening.
See [Production Readiness](docs/PRODUCTION_READINESS.md) for current status.

---

## Security Policy

See [SECURITY.md](SECURITY.md) for vulnerability reporting guidelines.
