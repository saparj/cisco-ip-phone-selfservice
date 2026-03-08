# Roadmap

Planned work by milestone.

## v0.3.0 — Operations + Admin Usability

- Install/upgrade script for automated deployment
- Admin dashboard: filtering, pagination, request detail view
- Application logging and log rotation
- Backup and restore procedures
- Data retention controls

---

## v0.4.0 — Device Identity

- Identify phones by hostname/device name instead of IP
- Improve "My Requests" behavior for shared/NAT networks
- Capture additional request metadata (device model, firmware)
- Automated test suite (pytest + Flask test client)

---

## v0.5.0 — Read-Only CUCM Integration

- AXL lookups to validate DN against CUCM
- Derive partition from DN automatically
- Display current CUCM configuration values for context
- Secure credential handling for CUCM API access

---

## v1.0.0 — Controlled Execution

- Execute approved requests against CUCM on admin completion
- Failure handling and retry safety
- Expanded audit and event logging
- Production-ready workflow validation

---

## Future — Enterprise Hardening

- External database support (PostgreSQL)
- Reporting and data export
- Additional UC workflows (Unity Connection, etc.)
- Centralized logging and monitoring integration
