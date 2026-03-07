# Risk Register

Risk tracking for the UC Self-Service application.

## Scale

**Likelihood:** Low / Medium / High
**Impact:** Low / Medium / High
**Rating:** Low = acceptable, Medium = needs mitigation plan, High = must mitigate before production

---

## Current Risks (v0.2.0)

Items marked *Future* relate to planned integrations or scaling beyond the lab environment.

| ID | Risk | Likelihood | Impact | Rating | Mitigation / Control | Owner | Status |
|----|------|------------|--------|--------|----------------------|-------|--------|
| R1 | Admin endpoints exposed due to misconfiguration | Low | High | Medium | Nginx Basic Auth + Flask admin allowlist; verify configuration during deployment | UC Self-Service Maintainer | Mitigated |
| R2 | SQLite file corruption or data loss | Low | Medium | Medium | Regular backups and tested restore procedure; consider PostgreSQL for production | UC Self-Service Maintainer | Open |
| R3 | Cisco IP Phone XML parsing regressions across firmware | Medium | Medium | Medium | Maintain test phones; validate XML responses; avoid unsupported elements | UC Self-Service Maintainer | Open |
| R4 | Credential leakage when adding CUCM/Unity integration (Future) | Medium | High | High | Use environment variables or secret store; never commit credentials; rotate secrets | UC Self-Service Maintainer | Open |
| R5 | Single host failure (Raspberry Pi) | Low | High | Medium | Maintain system image backup; document recovery steps; consider VM or HA for production | UC Self-Service Maintainer | Open |
| R6 | Nginx misconfiguration exposing backend directly | Low | High | Medium | Bind Gunicorn to localhost only; restrict firewall; validate reverse proxy rules | UC Self-Service Maintainer | Open |
| R7 | Log growth exhausting disk space | Medium | Medium | Medium | Configure log rotation (logrotate/systemd); monitor disk usage | UC Self-Service Maintainer | Open |
| R8 | Backup exists but restore procedure untested | Medium | High | High | Perform periodic restore tests and document recovery time | UC Self-Service Maintainer | Open |
| R9 | Physical access to device enabling tampering or data theft | Low | Medium | Medium | Secure device location; restrict console access; encrypt backups if offsite | UC Self-Service Maintainer | Open |
| R10 | Time drift affecting audit timestamps | Low | Medium | Low | Ensure NTP synchronization; monitor system time | UC Self-Service Maintainer | Open |
| R11 | Unauthorized internal access if Basic Auth credentials shared | Medium | Medium | Medium | Enforce strong passwords; rotate credentials; consider per-user auth in future | UC Self-Service Maintainer | Open |
| R12 | Lack of rate limiting enabling abuse or overload | Low | Medium | Low | Add Nginx rate limiting if exposed to larger user base | UC Self-Service Maintainer | Future |
| R13 | Malformed or unexpected input causing application errors | Low | Medium | Medium | Input validation implemented; continue fuzz testing | UC Self-Service Maintainer | Mitigated |
| R14 | Disclosure of sensitive data in logs or error messages | Low | High | Medium | Avoid logging secrets; sanitize error output; restrict log access | UC Self-Service Maintainer | Open |
| R15 | Software supply chain vulnerabilities (dependencies) | Medium | Medium | Medium | Pin versions; run periodic vulnerability scans; update dependencies | UC Self-Service Maintainer | Open |
| R16 | Future CUCM API integration introducing privilege escalation paths | Medium | High | High | Use least-privilege service accounts; isolate credentials; audit API actions | UC Self-Service Maintainer | Future |
