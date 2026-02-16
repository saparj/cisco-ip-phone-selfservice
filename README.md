![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-lab--demo-orange)
![Platform](https://img.shields.io/badge/platform-Cisco%20IP%20Phones-lightgrey)
![Version](https://img.shields.io/badge/version-0.1.0-blue)

# Cisco IP Phone Self-Service Framework

A lightweight Flask-based framework for building Cisco IP Phone XML (XSI) self-service workflows.

This project demonstrates how structured UC request workflows can be delivered directly from Cisco desk phones using standard CiscoIPPhone XML objects.

---

## Included Workflow

- Phone Name Update request (info → form → submit)
- Per-phone request history
- Admin review endpoint
- Reverse proxy + Gunicorn deployment model

---

## Architecture

Cisco IP Phones  
→ Nginx (reverse proxy)  
→ Gunicorn (WSGI)  
→ Flask application  
→ SQLite database  

---

## Design Goals

- Minimal external dependencies
- Clean separation of proxy and application layers
- Production-compatible service model (systemd + Gunicorn)
- Safe configuration via environment variables
- Easily extensible for additional UC workflows

---

## Intended Use

This repository is provided as a lab/demo reference architecture for engineers building Cisco IP Phone–based self-service tools.

## Docs
- [Architecture](docs/ARCHITECTURE.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Production Readiness](docs/PRODUCTION_READINESS.md)
- [Risk Matrix](docs/RISK_MATRIX.md)

## Security

Please review the [Security Policy](SECURITY.md) for vulnerability reporting guidelines.