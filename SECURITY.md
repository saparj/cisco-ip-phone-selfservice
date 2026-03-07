# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly.

- Do not open a public GitHub issue for security-sensitive findings.
- Report via direct contact through GitHub or repository owner contact methods.

Include:

- Description of the vulnerability
- Steps to reproduce (if applicable)
- Impact assessment (if known)
- Suggested mitigation (optional)

Reports will be reviewed and acknowledged as promptly as possible.

---

## Supported Versions

Only the latest version on the `main` branch is supported.

Older commits and experimental branches may not receive security updates.

---

## Scope

This application is currently in lab validation. Production deployment
requires additional controls:

- Authentication and authorization hardening
- Reverse proxy configuration review
- TLS termination
- Database access controls
- Network segmentation
- Operational monitoring

Deployment guidance is provided in `docs/DEPLOYMENT.md` and
`docs/PRODUCTION_READINESS.md`.

---

## Responsible Disclosure

Please allow reasonable time for review and remediation before
public disclosure of any vulnerability.
