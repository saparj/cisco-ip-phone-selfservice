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
sudo useradd --system --no-create-home --shell /usr/sbin/nologin phone-services
```

Create the persistent data directory:

``` bash
sudo mkdir -p /var/lib/phone-services
sudo chown phone-services:phone-services /var/lib/phone-services
sudo chmod 750 /var/lib/phone-services
```

This directory stores the SQLite database file (tickets.db).
It must exist before the service is started.

The database file itself is created automatically on first launch.

The directory is persistent across reboots. The database file is not stored alongside application code.

Application code lives in `/opt/phone-services`.

------------------------------------------------------------------------

## 5.1 Database Initialization and Migrations

The application uses a SQLite database located at:

    /var/lib/phone-services/tickets.db

The application performs additive schema migrations automatically at startup.

On first launch, the database and required tables are created.
On subsequent launches, missing columns are added if required
(e.g., audit fields introduced in newer versions).

Before upgrading between versions, it is recommended to back up
the database file.

```bash
sudo cp /var/lib/phone-services/tickets.db \
        /var/lib/phone-services/tickets.db.bak.$(date +%F)
```

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

# Create /run/phone-services at service start (tmpfs; recreated on reboot)
RuntimeDirectory=phone-services
RuntimeDirectoryMode=0750

# Gunicorn 25.x may create a control socket; place it in /run with proper perms
ExecStart=/opt/phone-services/.venv/bin/gunicorn --control-socket /run/phone-services/gunicorn.ctl -w 2 -b 127.0.0.1:8000 app:app

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

Create the site config file:

``` bash
sudo nano /etc/nginx/sites-available/phone-services
```

Paste the server{...} block into that file:

``` nginx
server {
    listen 80;
    server_name _;

    # Basic hardening
    server_tokens off;

    # Phone services (Cisco IP Phone XML)
    location /phone/ {
        gzip off;
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Phones are sensitive to caching sometimes
        add_header Cache-Control "no-store";
    }

    # Admin portal
    location /admin/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Health endpoint
    location /health/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # If you want everything else to 404:
    location / {
        return 404;
    }
}
```

Enable the site:

``` bash
sudo ln -s /etc/nginx/sites-available/phone-services /etc/nginx/sites-enabled/phone-services
```

Disable the default site (optional but common):

``` bash
sudo rm -f /etc/nginx/sites-enabled/default
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
curl http://127.0.0.1:8000/health
```

------------------------------------------------------------------------

## Notes

-   Service runs under a dedicated non-root account.
-   Gunicorn binds to localhost only (`127.0.0.1`).
-   Nginx handles external HTTP access.
-   Application state is separated from application code.
