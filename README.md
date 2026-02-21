![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-lab--demo-orange)
![Platform](https://img.shields.io/badge/platform-Cisco%20IP%20Phones-lightgrey)
![Version](https://img.shields.io/badge/version-0.2.0-blue)

# UC Self-Service — Cisco IP Phone Framework

A lightweight Flask-based framework for building Cisco IP Phone XML self-service workflows delivered directly to desk phones.

This project demonstrates how structured Unified Communications (UC) request workflows can be initiated from Cisco IP phones and processed through a secure web-based administrative interface.

---

## Included Workflow (v0.2.0)

- Phone display name update request
- Per-phone request history
- Request detail view
- Administrator dashboard with approval workflow
- Structured audit trail and lifecycle management
- Reverse proxy + Gunicorn deployment model

---

## Architecture

``` code
Cisco IP Phones
→ Nginx (authentication + reverse proxy)
→ Gunicorn (WSGI)
→ Flask application
→ SQLite database
```

---

## Design Goals

- Minimal external dependencies
- Clear separation of proxy and application responsibilities
- Production-compatible service model (systemd + Gunicorn)
- Safe configuration via environment variables
- Extensible foundation for additional UC workflows
- Safe operation behind a reverse proxy

---

## Phone User Workflow

### Service Menu

Users launch UC Self-Service -> Requests from the phone's Services menu.

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

Detailed information includes:

- Request ID
- Status
- DN and requested name
- Justification
- Timestamp

![Phone details](docs/screenshots/v0.2.0/05-phone-details.png)

---

### Physical Phone Example

Cisco IP phone models such as the 8841 and 7841 support XML services used by this framework.

![Phone 8841](docs/screenshots/v0.2.0/06-phone-8841.png)

![Phone 7841](docs/screenshots/v0.2.0/07-phone-7841.png)

---

## Administrator Workflow

### Admin Dashboard

Administrators authenticate via Nginx Basic Auth and manage requests through a web interface.

Features:

- Recent request list (newest 50)
- Color-coded status indicators
- Approve / Reject / Complete actions
- Inline reject reason entry
- Audit information
- Automatic light/dark mode support

![Admin dashboard](docs/screenshots/v0.2.0/08-admin-dashboard.png)

---

## Request Lifecycle

All requests follow a strict state machine:

``` code
Pending -> Approved -> Completed
Pending -> Rejected
```

State transitions are validated and applied atomically.

---

## Security Model

- Authentication handled by Nginx (Basic Auth)
- Authorization enforced by Flask ('require_admin' allowlist)
- Application bound to localhost behind reverse proxy
- SQLite datastore for v0.2.0
- Structured JSON request payloads with embedded metadata
- Parameterized SQL queries used for database operations

---

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Production Readiness](docs/PRODUCTION_READINESS.md)
- [Risk Matrix](docs/RISK_MATRIX.md)

---

## Roadmap

Planned features and future work are tracked in the [Project Roadmap](docs/ROADMAP.md).

## Intended Use

This repository is provided as a lab/demo reference architecture for engineers building Cisco IP Phone based self-service tools or evaluating phone-driven workflows.

---

## Security Policy

Please review the [Security Policy](SECURITY.md) for vulnerability reporting guidelines.
