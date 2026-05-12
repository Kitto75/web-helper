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

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## First run
```bash
uvicorn app.main:app --host 0.0.0.0 --port 38291
```
Then create initial superadmin:
```bash
curl -X POST -F 'username=superadmin' -F 'password=StrongPass123!' http://127.0.0.1:38291/bootstrap
```

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
