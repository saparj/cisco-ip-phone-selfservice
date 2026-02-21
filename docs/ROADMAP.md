# Roadmap

This project is in early development. Planned work is grouped by milestone.

## v0.3.0 (operations + admin usability)

- Install/upgrade script for automated deployment
- Admin dashboard improvements:
  - Filtering and pagination
  - Request detail view
- Loggin improvements + log rotation
- Backup and restore procedures
- Optional data retention controls

---

## v0.4.0 (identity improvements)

- Better device identification (hostname/device name vs IP)
- Improved "My Requests behavior for shared networks
- Enhanced request metadata capture

---

## v0.5.0 (read-only CUCM integration)

- CUCM lookups for validation (AXL)
- Derive partition automatically from DN
- Display current CUCM values for context
- Secure credential handling

---

## v1.0.0 (controlled execution)

- Execute approved requests against CUCM on completion
- Robust failure handling and retry safety
- Expanded audit/event logging
- Production-ready workflows

---

## Future (enterprise hardening)

- External database support (e.g., PostgreSQL)
- Reporting and export capabilities
- Additional UC workflows (Unity, etc.)
- Centralized logging/monitoring integration
