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
