# 3x-ui Delegated Admin Panel

A clean FastAPI web panel and Python CLI helper for managing delegated admins on top of 3x-ui.

## Highlights
- Superadmin and delegated admin roles with server-side permissions.
- Credit + per-GB pricing controls.
- User creation with traffic and expiry limits.
- Balance request workflow for admins.
- QR generation for subscription/config links.
- Light/Dark mode support in the web panel.
- Collapsible logs/requests sections for a cleaner dashboard.

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run
```bash
uvicorn app.main:app --host 0.0.0.0 --port 38291
```

## Run Helper Script (with optional SSL)
```bash
python run_web_helper.py
```

If your entered **3x-ui panel URL** starts with `https://...`, the script asks for:
- `fullchain.pem` path
- `privkey.pem` path

and starts uvicorn with SSL options.

## Recommended Setup
After starting the server:
```bash
python setup_panel.py
```

You will be asked for:
- App URL (default: `http://127.0.0.1:38291`)
- Superadmin username/password
- 3x-ui panel URL
- Optional panel path (for example `/xui`)
- 3x-ui panel credentials

## Manual Bootstrap
```bash
curl -X POST -F 'username=superadmin' -F 'password=StrongPass123!' http://127.0.0.1:38291/bootstrap
```

## CLI
```bash
python xui_cli.py --help
```

## Useful Commands
```bash
# run web panel (dev)
uvicorn app.main:app --host 0.0.0.0 --port 38291 --reload

# bootstrap superadmin from terminal
curl -X POST -F 'username=superadmin' -F 'password=StrongPass123!' http://127.0.0.1:38291/bootstrap

# initial interactive setup for panel + 3x-ui
python setup_panel.py

# interactive run helper (asks SSL cert paths if panel URL starts with https://)
python run_web_helper.py

# inspect CLI options
python xui_cli.py --help

# when running as systemd service
systemctl status web-helper
systemctl restart web-helper
journalctl -u web-helper -n 200 --no-pager
```

## Systemd Setup (full service)

### 1) Create service file
Create `/etc/systemd/system/web-helper.service`:

```ini
[Unit]
Description=web-helper FastAPI service
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/opt/web-helper
Environment=\"PATH=/opt/web-helper/.venv/bin\"
ExecStart=/opt/web-helper/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 38291
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

> Replace `User`, `Group`, and paths to match your server.

### 2) Enable and start
```bash
sudo systemctl daemon-reload
sudo systemctl enable web-helper
sudo systemctl start web-helper
```

### 3) Useful service commands
```bash
sudo systemctl status web-helper
sudo systemctl restart web-helper
sudo systemctl stop web-helper
sudo journalctl -u web-helper -f
sudo journalctl -u web-helper -n 200 --no-pager
```

## Notes
- Password hashing uses `pbkdf2_sha256`.
- Panel settings are stored through the application audit flow; keep server/database access restricted.
- If you expose this publicly, run behind HTTPS and strong credentials.

## Backup & Restore
To fully restore this panel on a new server, you mainly need the SQLite database file and (optionally) uploaded screenshots.

### What to back up
1. `panel.db` (required): contains all admins, users, balances, panel config, and logs.
2. `app/uploads/` (optional but recommended): contains balance request screenshots.

### How to restore
1. Install and run the same app version (or newer compatible version).
2. Stop the running app service before replacing data files.
3. Copy old `panel.db` into the new project root (same directory as `README.md`).
4. If you want screenshots/history attachments, copy old `app/uploads/` into new `app/uploads/`.
5. Ensure file ownership/permissions let the app user read/write `panel.db` and `app/uploads/`.
6. Start the app service again.
7. Login with your previous admin credentials and verify users/admins/history exist.

### Example commands
```bash
# on old server
tar czf panel-backup.tar.gz panel.db app/uploads

# on new server (inside project root)
systemctl stop web-helper
tar xzf panel-backup.tar.gz
chown -R <app-user>:<app-user> panel.db app/uploads
systemctl start web-helper
```

### Important notes
- If you restore only `panel.db`, the system works, but old screenshot files will be missing.
- Restore should be done while service is stopped to avoid SQLite corruption/race conditions.
- Keep backup files secure because they include panel access configuration and admin data.
