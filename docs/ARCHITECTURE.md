# Architecture

## Overview

```
Cisco IP Phones
    ↓ HTTP (CiscoIPPhone XML)
Nginx (Reverse Proxy :80)
    ↓ proxy_pass
Gunicorn (Flask WSGI App :127.0.0.1:8000)
    ↓
SQLite (requests.db)
```

---

## Components

### 1. Cisco IP Phones

- 7841 / 8841 / 9861 tested
- Consume CiscoIPPhone XML objects
- Communicate over HTTP
- Submit form data via HTTP GET

### 2. Nginx

- Terminates inbound HTTP on port 80
- Enforces Basic Auth on `/admin/` endpoints
- Disables gzip for `/phone/` endpoints (Cisco XML compatibility)
- Proxies requests to Gunicorn on localhost
- Adds `X-Real-IP` header for client tracking
- Adds `X-Remote-User` header for admin identity

### 3. Gunicorn

- 2 worker processes
- Bound to 127.0.0.1:8000 (not externally accessible)
- Runs as `www-data` under systemd
- Restarts automatically on failure

### 4. Flask Application

- Generates CiscoIPPhone XML responses for phone endpoints
- Serves HTML admin dashboard
- Validates input and enforces workflow state machine
- Persists request data to SQLite

Key endpoints:

```
/phone/menu, /phone/phonename/info, /phone/dnlabel
/phone/submit_dnlabel, /phone/recent, /phone/quit
/admin/dashboard, /admin/list, /admin/health
/admin/approve/<id>, /admin/reject/<id>, /admin/complete/<id>
/health
```

### 5. SQLite Database

Location: `/var/lib/phone-services/requests.db`

Single table (`requests`) stores:

- id, created_at, updated_at
- source_ip, user_agent
- kind, details (structured JSON), status
- approved_by, approved_at, completed_at, rejected_reason

### 6. Request Details (Structured JSON)

The `details` column stores request-specific data as JSON in a TEXT column:

- Request fields (DN, requested display name, justification)
- Requester metadata (source IP, user agent)
- `schema_version` field for forward compatibility

DN is user-supplied in v0.2.0. Future versions may validate against CUCM.

---

## Data Flow — Phone Name Update

1. User selects "Request Phone Name Update" from phone menu
2. Phone displays info screen, user selects Continue
3. Phone displays input form (DN, name, justification)
4. User submits form
5. Flask validates input and stores request (status: Pending)
6. Confirmation screen displayed on phone
7. Admin reviews and acts via `/admin/dashboard`

---

## Request Lifecycle

Valid states: Pending, Approved, Rejected, Completed

Allowed transitions:

- Pending → Approved
- Pending → Rejected
- Approved → Completed

All other transitions are rejected. Status changes are validated
server-side through a single transition function and written
atomically with audit metadata.

Audit fields recorded on transition:

- `updated_at` — all transitions
- `approved_by`, `approved_at` — on approval
- `completed_at` — on completion
- `rejected_reason` — on rejection (required)

---

## Security Model

- Nginx isolates the application from direct external access
- Gunicorn bound to localhost only
- Admin endpoints gated by Nginx Basic Auth and Flask allowlist
- No credentials stored in code — environment variables only
- Parameterized SQL for all database operations
- Phone endpoints unauthenticated (identified by source IP)

---

## Scaling Considerations

Current architecture is single-host with SQLite. For higher
availability or larger deployments:

- Replace SQLite with PostgreSQL
- Add TLS termination (Nginx or load balancer)
- Normalize the JSON `details` column into relational tables
- Add centralized logging
