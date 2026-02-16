# Deployment Guide

## Overview

This project provides Cisco IP Phone XML services for:

-   Request Phone Name Update workflow
-   My Recent Requests directory
-   Service exit handling via CiscoIPPhoneExecute
-   Admin review portal

See ARCHITECTURE.md for system design overview.

------------------------------------------------------------------------

# Server Environment

-   OS: Raspberry Pi OS (Debian-based)
-   Python venv: `.venv`
-   App path: `/opt/phone-services`
-   Port exposed to phones: `80`
-   Internal app bind: `127.0.0.1:8000`

------------------------------------------------------------------------

# systemd Service Configuration

File: `/etc/systemd/system/phone-services.service`

``` ini
[Unit]
Description=Phone Services (Flask/Gunicorn)
After=network.target

[Service]
User=xroot
WorkingDirectory=/opt/phone-services/
Environment="PATH=/opt/phone-services/.venv/bin"
ExecStart=/opt/phone-services/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Notes

-   2 Gunicorn workers
-   Bound to localhost only (security best practice)
-   Auto-restarts on crash
-   Runs under non-root user

------------------------------------------------------------------------

# Nginx Configuration

File: `/etc/nginx/sites-available/phone-services`

``` nginx
server {
    listen 80;
    server_name _;

    server_tokens off;

    location /phone/ {
        gzip off;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        add_header Cache-Control "no-store";
    }

    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        return 404;
    }
}
```

### Notes

-   gzip disabled for `/phone/` (Cisco XML compatibility)
-   Reverse proxy to Gunicorn on localhost
-   Caching disabled for phone endpoints
-   Everything else returns 404

------------------------------------------------------------------------

# Deployment Commands

## Restart Application

``` bash
sudo systemctl restart phone-services
```

## Check Application Status

``` bash
sudo systemctl status phone-services
```

## View Application Logs

``` bash
sudo journalctl -u phone-services -f
```

## Reload Nginx

``` bash
sudo systemctl reload nginx
```

## Check Nginx Config

``` bash
sudo nginx -t
```

------------------------------------------------------------------------

# First-Time Setup

``` bash
cd /opt/phone-services

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Create environment configuration
cp .env.example .env

sudo systemctl daemon-reload
sudo systemctl enable phone-services
sudo systemctl start phone-services
```

------------------------------------------------------------------------

# Security Considerations

-   Gunicorn bound to localhost only
-   Nginx acts as reverse proxy
-   No external exposure of app port
-   SQLite stored locally
-   No credentials stored in repo (future AXL/Unity integrations should
    use environment variables)

------------------------------------------------------------------------

# Troubleshooting

### XML Parse Error on Phone

-   Ensure gzip is disabled in Nginx
-   Ensure `Content-Type: text/xml`
-   Validate XML via curl

### 502 Bad Gateway

-   Check `journalctl -u phone-services`
-   Ensure Gunicorn workers are running

### 504 Timeout

-   Check upstream connectivity
-   Confirm Gunicorn bind is `127.0.0.1:8000`

------------------------------------------------------------------------

# Future Improvements

-   TLS termination
-   Admin authentication
-   Role-based approval workflow
-   Structured JSON storage instead of flat details
-   CUCM AXL automation
-   Unity Connection REST integration
