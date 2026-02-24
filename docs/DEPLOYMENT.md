# Deployment Guide

This guide walks through deploying the Cisco IP Phone Self-Service application on a Linux host and integrating it with Cisco Unified Communications Manager (CUCM).

---

## 1. System Requirements

### Supported OS

- Debian 12+
- Ubuntu 22.04+
- Raspberry Pi OS (Bookworm/Trixie)

### Required Software

- Python 3.11+
- Git
- Nginx
- Network access to CUCM
- Static IP recommended

---

## 2. Install Dependencies

``` bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nginx apache2-utils
```

Verify Python:

``` bash
python3 --version
```

---

## 3. Clone the Repository

Recommended install location:

``` bash
cd /opt
sudo git clone https://github.com/saparj/cisco-ip-phone-selfservice.git phone-services
cd phone-services
```

Keep code root-owned (recommended):

``` bash
sudo chown -R root:root /opt/phone-services
sudo chmod -R 755 /opt/phone-services
```

---

## 4. Create Python Virtual Environment

``` bash
cd /opt/phone-services
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate
```

---

## 5. Create Database Directory 

The database path is:

``` file
/var/lib/phone-services/requests.db
```

Create the directory and set ownership to the service user:

``` bash
sudo mkdir -p /var/lib/phone-services
sudo chown -R www-data /var/lib/phone-services
sudo chmod -R 750 /var/lib/phone-services
```

Note: On Debian/Ubuntu-based systems, www-data is created automatically when installing Nginx.

Verify:

``` bash
id www-data
```

---

## 6. Configure systemd Services

Create the systemd unit file:

``` bash
sudo nano /etc/systemd/system/phone-services.service
```

Paste (edit BASE_URL and ADMIN_USERS):

``` ini
[Unit]
Description=UC Self-Service (Flask/Gunicorn)
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/opt/phone-services

# Runtime configuration (edit these)
Environment=BASE_URL=http://10.10.10.10
Environment=ADMIN_USERS=xadmin
# Environment=ADMIN_USERS=xadmin1,xadmin2,xadmin3

# Create /run/phone-services on start (tmpfs under /run)
RuntimeDirectory=phone-services
RuntimeDirectoryMode=0755

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

Check status:

``` bash
sudo systemctl status phone-services --no-pager
```

Verify runtime directory exists:

``` bash
ls -la /run/phone-services
```

---

## 7. Configure Nginx Reverse Proxy

Create Nginx site config:

``` bash
sudo nano /etc/nginx/sites-available/phone-services
```

Paste (edit server_name):

``` conf
server {
    listen 80;
    server_name _;
    # server_name 10.10.10.10;
    # server_name uc.selfservice.lab.local;

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
        add_header Cache-Control "no-store";
    }

    # Admin portal
    location /admin/ {
        auth_basic "Admin Portal";
        auth_basic_user_file /etc/nginx/.htpasswd-phone-services;

        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Remote-User $remote_user;
    }

    # Health endpoint
    location /health/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Everything else - 404:
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
sudo systemctl restart nginx
```

---

## 8. Configure Admin Credentials (Nginx Basic Auth)

Create the htpasswd file and an admin user (must match ADMIN_USERS in systemd):

``` bash
sudo htpasswd -c /etc/nginx/.htpasswd-phone-services xadmin
sudo systemctl restart nginx
```

If you need to add another user later:

``` bash
sudo htpasswd /etc/nginx/.htpasswd-phone-services anotheradmin
sudo systemctl restart nginx
```

Then update systemd 'ADMIN_USERS=' accordingly and restart the service.

---

## 9. Validate the Deployment

Health endpoint:

``` bash
curl http://localhost/health
```

Admin portal (from web browser; will prompt for credentials):

``` code
http://10.10.10.10/admin/dashboard
```

Phone menu endpoint (should return Cisco IP Phone XML):

``` bash
curl http://10.10.10.10/phone/menu
```

---

## 10. Configure CUCM Phone Service

### Add Phone Service

CUCM Administration:

Device -> Device Settings -> Phone Services -> Add New

Set:

- Service Name: Services
- Service URL:

``` code
http://10.10.10.10/phone/menu
```

- Service Type: XML Service
- Enable: Checked

Save.

### Subscribe Phones

Per-phone:

Device -> Phone -> select phone -> Related Links: Subscribe/Unsubscribe Services -> Add New -> Services -> Save -> Reset phone

---

## 11. Test on a Phone

On the phone:

Applications -> Services

Submit a request. Confirm it appears in:

``` code
http://10.10.10.10/admin/dashboard
```

---

## 12. Troubleshooting

Service logs:

``` bash
sudo journalctl -u phone-services -n 80 --no-pager
```

Nginx error log:

``` bash
sudo tail -f /var/log/nginx/error.log
```

Restart services:

``` bash
sudo systemctl restart phone-services
sudo systemctl restart nginx
```

Verify DB exists:

``` bash
ls -la /var/lib/phone-services/requests.db
```

Inspect schema:

``` bash
sqlite3 /var/lib/phone-services/requests.db "PRAGMA table_info(requests);"
```

---

## 13. Upgrade Procedure

Update code:

``` bash
cd /opt/phone-services
sudo git pull
sudo systemctl restart phone-services
```

---

## Deployment Complete

You now have:
- UC Self-Service Cisco IP Phone XML service
- Admin dashboard protected by Nginx Basic Auth
- Flask allowlist authorization ('ADMIN_USERS')
- Gunicorn bound to localhost only
- SQLite persistent storage under /var/lib

---

