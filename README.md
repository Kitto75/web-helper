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

## Notes
- Password hashing uses `pbkdf2_sha256`.
- Panel settings are stored through the application audit flow; keep server/database access restricted.
- If you expose this publicly, run behind HTTPS and strong credentials.
