# 3x-ui Delegated Admin Panel

FastAPI-based server-side panel plus Python CLI wrapper for 3x-ui APIs.

## Features
- Superadmin + admin roles, with server-side permission checks.
- Admin credit, per-GB pricing, global pricing override, and manual balance edits.
- Prevent unlimited traffic and enforce max 30-day expiry (default 30 days).
- Username validation: lowercase letters and numbers only.
- Admin balance top-up request workflow with screenshot/message approval.
- QR rendering for subscription/config links.
- Tehran timezone shown in UI.
- Customizable web path/port/SSL in uvicorn startup command.
- Interactive setup script for superadmin + 3x-ui panel credentials.

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 38291
```

## One-command interactive setup (recommended)
After the server is running, execute:
```bash
python setup_panel.py
```
The script asks for:
- App URL (default: `http://127.0.0.1:38291`)
- Superadmin username/password
- 3x-ui panel URL
- 3x-ui panel web base path (example: `/xui`, leave empty if not used)
- 3x-ui panel username/password

It will:
1. Create the initial superadmin (bootstrap).
2. Log in automatically.
3. Save your 3x-ui panel connection settings.

## Manual setup (alternative)
Create initial superadmin:
```bash
curl -X POST -F 'username=superadmin' -F 'password=StrongPass123!' http://127.0.0.1:38291/bootstrap
```
Then log in to the web UI and fill **3x-ui Panel Settings**:
- panel link address (`panel_url`)
- panel username
- panel password
- optional panel web path (`panel_path`)

## Password hashing note
This project uses `pbkdf2_sha256` for password hashing to avoid bcrypt runtime issues on some environments.

## Change superadmin username/password later
After the app is already running and initialized, you can update superadmin credentials directly in the SQLite DB:

```bash
python - <<'PY'
from sqlalchemy import select
from app.db import SessionLocal
from app.models import Admin
from app.security import hash_password

NEW_USERNAME = "superadmin2"
NEW_PASSWORD = "NewStrongPass123!"

s = SessionLocal()
try:
    admin = s.scalar(select(Admin).where(Admin.is_super == True))
    if not admin:
        raise SystemExit("No superadmin found")

    admin.username = NEW_USERNAME
    admin.password_hash = hash_password(NEW_PASSWORD)
    s.commit()
    print("Superadmin credentials updated.")
finally:
    s.close()
PY
```

Then log in using the new credentials.

## SSL + custom path + custom port (no nginx)
Use a reverse-compatible base path by mounting app behind your own path via `--root-path`:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 45173 --root-path /my-panel \
  --ssl-certfile /path/fullchain.pem --ssl-keyfile /path/privkey.pem
```

## CLI
Use the helper CLI:
```bash
python xui_cli.py --help
```
