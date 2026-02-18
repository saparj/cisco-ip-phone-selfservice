# Cisco IP Phone Services -- Architecture

## High-Level Architecture

Cisco IP Phones
    ↓ HTTP (CiscoIPPhone XML)
Nginx (Reverse Proxy :80)
    ↓ proxy_pass
Gunicorn (Flask WSGI App :127.0.0.1:8000)
    ↓
SQLite (tickets.db)

------------------------------------------------------------------------

## Components

### 1. Cisco IP Phones

-   7841 / 8841 / 9861 tested
-   Consume CiscoIPPhone XML objects
-   Communicate over HTTP
-   Submit form data via HTTP GET

### 2. Nginx

-   Terminates inbound HTTP on port 80
-   Disables gzip for /phone/ endpoints (Cisco XML compatibility)
-   Proxies requests to Gunicorn
-   Prevents direct exposure of backend service
-   Adds X-Real-IP header for client tracking

### 3. Gunicorn

-   2 worker processes
-   Bound to 127.0.0.1:8000
-   Runs under non-root user
-   Managed via systemd
-   Automatically restarts on failure

### 4. Flask Application

Responsibilities:
- Generate CiscoIPPhone XML responses
- Persist request data
- Provide admin review endpoints
- Handle validation and error conditions

Key Endpoints: - /phone/menu - /phone/phonename/info - /phone/dnlabel -
/phone/submit_dnlabel - /phone/recent - /phone/quit - /admin/list - 
/admin/approve/<id> - /admin/reject/<id> - /admin/complete/<id>

### 5. SQLite Database

-   Local file: /var/lib/phone-services/tickets.db
-   Stores:
    -   id
    -   created_at
    -   source_ip
    -   user_agent
    -   kind
    -   details
    -   status
    -   updated_at
    -   approved_by
    -   approved_at
    -   completed_at
    -   rejected_reason

### 6. requests.details (Structured JSON)

-   'requests.details' stores structured request data as JSON (serialized into a TEXT column).
-   This field contains:
    -   Request-specific fields (e.g., DN, requested display name, justification)
    -   Embedded requester metadata (e.g., source IP, user agent)
    -   A 'schema_version' field for future compatibility
-   Notes:
    -   DN remains user-supplied in v0.2.0
    -   Future versions may normalize this JSON into a relational schema

------------------------------------------------------------------------

## Data Flow -- Phone Name Update

1.  User selects "Request Phone Name Update"
2.  Phone loads Info screen
3.  User selects Continue
4.  Phone loads CiscoIPPhoneInput form
5.  User submits form
6.  Flask stores request (status=Pending)
7.  Confirmation screen displayed
8.  Admin reviews via /admin/list

------------------------------------------------------------------------

## Request Lifecycle

Requests follow a validated state machine.

Valid states:

- Pending
- Approved
- Rejected
- Completed

Allowed transitions:

- Pending → Approved
- Pending → Rejected
- Approved → Completed

All other transitions are rejected by the application.

Status changes are validated server-side and written atomically
with audit metadata (updated_at and relevant audit fields).

Audit fields:

- updated_at
- approved_by
- approved_at
- completed_at
- rejected_reason

------------------------------------------------------------------------

## Security Model

-   Backend not exposed externally
-   Reverse proxy isolates app
-   No credentials stored in code
-   Local data storage (no external database exposure)
-   Controlled service restarts via systemd
-   Admin endpoints protected by Nginx Basic Authentication
-   Admin endpoints require valid username in ADMIN_USERS configuration

------------------------------------------------------------------------

## Scaling Considerations

For enterprise deployment:

-   Replace SQLite with PostgreSQL
-   Add TLS (HTTPS)
-   Replace JSON-in-TEXT with normalized relational schema (PostgreSQL)
-   Add logging aggregation
-   Add health-check endpoint
