# Deployment Guide

This document describes how to deploy the Cisco IP Phone Self-Service
Framework using Nginx, Gunicorn, and systemd on a Linux host.

------------------------------------------------------------------------

## 1. Install System Dependencies

``` bash
sudo apt update
sudo apt install python3 python3-venv python3-pip nginx
```

------------------------------------------------------------------------

## 2. Application Directory

Application code should reside in:

    /opt/phone-services

Create the directory and set ownership to your development user:

``` bash
sudo mkdir -p /opt/phone-services
sudo chown -R $USER:$USER /opt/phone-services
```

------------------------------------------------------------------------

## 3. Python Virtual Environment

``` bash
cd /opt/phone-services
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

------------------------------------------------------------------------

## 4. Environment Configuration

Copy the example configuration file:

``` bash
cp .env.example .env
```

Edit `.env` as needed:

    BASE_URL=http://example.local
    DB_PATH=/var/lib/phone-services/tickets.db

------------------------------------------------------------------------

## 5. Create Service Account and Data Directory

Create a dedicated non-login system user:

``` bash
sudo useradd --system              --no-create-home              --shell /usr/sbin/nologin              phone-services
```

Create the persistent data directory:

``` bash
sudo mkdir -p /var/lib/phone-services
sudo chown phone-services:phone-services /var/lib/phone-services
sudo chmod 750 /var/lib/phone-services
```

Application code lives in `/opt/phone-services`. Persistent state
(SQLite database) lives in `/var/lib/phone-services`.

------------------------------------------------------------------------

## 6. systemd Service Configuration

File: `/etc/systemd/system/phone-services.service`

``` ini
[Unit]
Description=Cisco IP Phone Self-Service (Flask/Gunicorn)
After=network.target

[Service]
User=phone-services
WorkingDirectory=/opt/phone-services
Environment="PATH=/opt/phone-services/.venv/bin"
ExecStart=/opt/phone-services/.venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

``` bash
sudo systemctl daemon-reload
sudo systemctl enable phone-services
sudo systemctl start phone-services
```

------------------------------------------------------------------------

## 7. Nginx Reverse Proxy Configuration

Example server block:

``` nginx
server {
    listen 80;
    server_name example.local;

    location /phone/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }
}
```

Validate and reload Nginx:

``` bash
sudo nginx -t
sudo systemctl reload nginx
```

------------------------------------------------------------------------

## 8. Verification

Check service status:

``` bash
sudo systemctl status phone-services --no-pager
```

Test locally:

``` bash
curl http://127.0.0.1:8000/phone/menu
```

------------------------------------------------------------------------

## Notes

-   Service runs under a dedicated non-root account.
-   Gunicorn binds to localhost only (`127.0.0.1`).
-   Nginx handles external HTTP access.
-   Application state is separated from application code.
