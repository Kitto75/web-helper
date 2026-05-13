import base64
import io
import json
import os
import subprocess
from urllib.parse import quote_plus
from datetime import datetime, timedelta
import logging

import qrcode
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer
from sqlalchemy import select

from .db import SessionLocal
from .models import Admin, AuditLog, BalanceRequest, UserAccount
from .security import hash_password, valid_username, verify_password
from .xui import XUIClient

router = APIRouter()
templates = Jinja2Templates('app/templates')
ser = URLSafeSerializer('change-me')
ADMIN_LOCK = False


LOGIN_LIMIT_WINDOW = timedelta(minutes=30)
LOGIN_MAX_ATTEMPTS = 3
FAILED_LOGIN_ATTEMPTS: dict[str, dict[str, object]] = {}
logger = logging.getLogger(__name__)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return 'unknown'


def _is_ip_limited(ip: str) -> tuple[bool, int]:
    now = datetime.utcnow()
    state = FAILED_LOGIN_ATTEMPTS.get(ip)
    if not state:
        return False, 0
    locked_until = state.get('locked_until')
    if isinstance(locked_until, datetime) and locked_until > now:
        remaining = int((locked_until - now).total_seconds() // 60) + 1
        return True, max(remaining, 1)
    if isinstance(locked_until, datetime) and locked_until <= now:
        FAILED_LOGIN_ATTEMPTS.pop(ip, None)
    return False, 0


def _register_login_failure(dbs, ip: str, username: str):
    now = datetime.utcnow()
    state = FAILED_LOGIN_ATTEMPTS.get(ip, {'count': 0, 'first_failed_at': now, 'locked_until': None})
    first_failed_at = state.get('first_failed_at')
    if not isinstance(first_failed_at, datetime) or (now - first_failed_at) > LOGIN_LIMIT_WINDOW:
        state = {'count': 0, 'first_failed_at': now, 'locked_until': None}
    state['count'] = int(state.get('count', 0)) + 1
    state['first_failed_at'] = state.get('first_failed_at') or now
    if state['count'] >= LOGIN_MAX_ATTEMPTS:
        locked_until = now + LOGIN_LIMIT_WINDOW
        state['locked_until'] = locked_until
        log(dbs, 'system', 'security', f'login_ip_limited ip={ip} username={username} reason=wrong_username_or_password locked_until={locked_until.isoformat()}')
        logger.warning('Login rate limit activated for ip=%s username=%s locked_until=%s', ip, username, locked_until.isoformat())
    else:
        state['locked_until'] = None
    FAILED_LOGIN_ATTEMPTS[ip] = state


def _clear_login_failures(ip: str):
    FAILED_LOGIN_ATTEMPTS.pop(ip, None)


def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def get_panel_config(dbs):
    setting = dbs.scalar(select(AuditLog).where(AuditLog.category == 'panel_config').order_by(AuditLog.id.desc()))
    if not setting:
        return None
    try:
        return json.loads(setting.detail)
    except Exception:
        return None


def current_admin(req, dbs):
    c = req.cookies.get('sess')
    if not c:
        return None
    try:
        uid = ser.loads(c)['uid']
    except Exception:
        return None
    return dbs.get(Admin, uid)


def log(dbs, actor, cat, detail):
    dbs.add(AuditLog(actor=actor, category=cat, detail=detail))
    dbs.commit()


def parse_allowed_inbounds(raw: str):
    ids = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return sorted(ids)


def detect_msg_type(msg: str) -> str:
    text = (msg or "").lower()
    if "error" in text or "fatal" in text or "invalid" in text or "failed" in text or "rejected" in text:
        return "error"
    return "success"


@router.get('/', response_class=HTMLResponse)
def home(request: Request, dbs=Depends(db), msg: str = '', users_page: int = 1, admins_page: int = 1):
    admin = current_admin(request, dbs)
    if not admin:
        return RedirectResponse('/login')
    users = dbs.scalars(select(UserAccount) if admin.is_super else select(UserAccount).where(UserAccount.admin_id == admin.id)).all()
    logs = dbs.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(100)).all() if admin.is_super else dbs.scalars(select(AuditLog).where(AuditLog.actor == admin.username).order_by(AuditLog.id.desc()).limit(100)).all()
    for entry in logs:
        short = (entry.detail or '').strip()
        if short.startswith('{') and short.endswith('}'):
            short = 'JSON log (hidden details)'
        if len(short) > 120:
            short = short[:117] + '...'
        entry.detail_short = short
    admins = dbs.scalars(select(Admin)).all() if admin.is_super else []
    reqs = dbs.scalars(select(BalanceRequest).where(BalanceRequest.approved == False)).all() if admin.is_super else []

    admin_name_by_id = {x.id: x.username for x in dbs.scalars(select(Admin)).all()} if admin.is_super else {}
    for u in users:
        u.creator_name = admin_name_by_id.get(u.admin_id, f"#{u.admin_id}") if admin.is_super else admin.username
    for r in reqs:
        r.admin_name = admin_name_by_id.get(r.admin_id, f"#{r.admin_id}")
    approved_reqs = dbs.scalars(select(BalanceRequest).where(BalanceRequest.approved == True)).all() if admin.is_super else dbs.scalars(select(BalanceRequest).where(BalanceRequest.admin_id == admin.id, BalanceRequest.approved == True)).all()
    total_users = len(users)
    active_users = sum(1 for u in users if u.enabled)
    disabled_users = total_users - active_users
    panel_cfg = get_panel_config(dbs)
    inbounds = []
    if panel_cfg:
        try:
            client = XUIClient(panel_cfg['url'], panel_cfg['username'], panel_cfg['password'], panel_cfg.get('path', ''))
            for ib in client.list_inbounds():
                inbounds.append({"id": ib.get("id"), "name": ib.get("remark") or ib.get("tag") or f"Inbound {ib.get('id')}"})
            tehran_now = datetime.utcnow() + timedelta(hours=3, minutes=30)
            online_map = client.build_last_online_map()
            usage_map = client.build_client_usage_map()
            for u in users:
                last_online = online_map.get((u.inbound_id, u.username))
                u.last_online_text = "-"
                u.status_state = "active" if u.enabled else "disabled"
                usage = usage_map.get((u.inbound_id, u.username)) or {}
                if usage.get("is_limited"):
                    u.status_state = "limited"
                if isinstance(last_online, int) and last_online > 0:
                    dt = datetime.utcfromtimestamp(last_online / 1000) + timedelta(hours=3, minutes=30)
                    u.last_online_text = dt.strftime('%Y-%m-%d %H:%M:%S') + " (Tehran)"
                u.last_online_fallback = tehran_now.strftime('%Y-%m-%d %H:%M:%S') + " (Tehran)"
        except Exception:
            inbounds = []
    allowed = parse_allowed_inbounds(admin.allowed_inbounds)
    usable_inbounds = [i for i in inbounds if (admin.is_super or not allowed or i["id"] in allowed)]
    page_size = 10
    users_page = max(users_page, 1)
    admins_page = max(admins_page, 1)
    users_pages = max((len(users) + page_size - 1) // page_size, 1)
    admins_pages = max((len(admins) + page_size - 1) // page_size, 1)
    users_page = min(users_page, users_pages)
    admins_page = min(admins_page, admins_pages)
    users_paginated = users[(users_page - 1) * page_size: users_page * page_size]
    admins_paginated = admins[(admins_page - 1) * page_size: admins_page * page_size]
    admin_name_by_id = {x.id: x.username for x in dbs.scalars(select(Admin)).all()}
    for r in approved_reqs:
        r.admin_name = admin_name_by_id.get(r.admin_id, f"#{r.admin_id}")
    return templates.TemplateResponse('index.html', {'request': request, 'admin': admin, 'users': users_paginated, 'logs': logs, 'admins': admins_paginated, 'reqs': reqs, 'approved_reqs': approved_reqs, 'msg': msg, 'msg_type': detect_msg_type(msg), 'panel_cfg': panel_cfg, 'inbounds': inbounds, 'usable_inbounds': usable_inbounds, 'allowed_ids': allowed, 'total_users': total_users, 'active_users': active_users, 'disabled_users': disabled_users, 'users_page': users_page, 'users_pages': users_pages, 'admins_page': admins_page, 'admins_pages': admins_pages})


@router.get('/login', response_class=HTMLResponse)
def login_page(request: Request, dbs=Depends(db), err: str = ''):
    needs_bootstrap = dbs.scalar(select(Admin)) is None
    return templates.TemplateResponse('login.html', {'request': request, 'err': err, 'needs_bootstrap': needs_bootstrap})


@router.post('/login')
def login(request: Request, username: str = Form(...), password: str = Form(...), dbs=Depends(db)):
    ip = _client_ip(request)
    limited, remaining = _is_ip_limited(ip)
    if limited:
        log(dbs, 'system', 'security', f'limited_login_attempt ip={ip} username={username} remaining_minutes={remaining}')
        return RedirectResponse(f'/login?err=Too+many+failed+attempts.+Try+again+in+{remaining}+minutes', status_code=303)

    admin = dbs.scalar(select(Admin).where(Admin.username == username))
    if admin and verify_password(password, admin.password_hash) and admin.active:
        _clear_login_failures(ip)
        resp = RedirectResponse('/', status_code=303)
        resp.set_cookie('sess', ser.dumps({'uid': admin.id}), httponly=True, samesite='lax')
        return resp

    _register_login_failure(dbs, ip=ip, username=username)
    return RedirectResponse('/login?err=Invalid+credentials', status_code=303)


@router.post('/logout')
def logout():
    resp = RedirectResponse('/login', status_code=303)
    resp.delete_cookie('sess')
    return resp


@router.post('/bootstrap')
def bootstrap(username: str = Form(...), password: str = Form(...), dbs=Depends(db)):
    if dbs.scalar(select(Admin)):
        return RedirectResponse('/login?err=Bootstrap+already+done', 303)
    dbs.add(Admin(username=username, password_hash=hash_password(password), is_super=True))
    dbs.commit()
    return RedirectResponse('/login?err=Superadmin+created.+Please+login.', 303)


@router.post('/panel/config')
def panel_config(request: Request, panel_url: str = Form(...), panel_path: str = Form(''), panel_username: str = Form(...), panel_password: str = Form(...), dbs=Depends(db)):
    a = current_admin(request, dbs)
    if not a or not a.is_super:
        return RedirectResponse('/', 303)
    conf = {'url': panel_url.strip(), 'path': panel_path.strip(), 'username': panel_username.strip(), 'password': panel_password}
    log(dbs, a.username, 'panel_config', json.dumps(conf))
    return RedirectResponse('/?msg=3x-ui+panel+saved', 303)


@router.post('/users/create')
def create_user(request: Request, username: str = Form(...), inbound_id: int = Form(...), traffic_gb: float = Form(...), expiry_days: int = Form(30), admin_comment: str = Form(''), dbs=Depends(db)):
    global ADMIN_LOCK
    a = current_admin(request, dbs)
    if not a or not a.active or ADMIN_LOCK:
        return RedirectResponse('/', 303)
    if not valid_username(username):
        log(dbs, a.username, 'user_create', f'validation_failed username={username} reason=invalid_username')
        return RedirectResponse('/?msg=Username+must+be+lowercase+and+numeric', 303)
    if len((admin_comment or '').strip()) > 300:
        return RedirectResponse('/?msg=Comment+is+too+long+(max+300+chars)', 303)
    expiry_days = min(expiry_days or 30, 30)
    if traffic_gb <= 0:
        log(dbs, a.username, 'user_create', f'validation_failed username={username} reason=invalid_traffic traffic_gb={traffic_gb}')
        return RedirectResponse('/?msg=Traffic+must+be+greater+than+0', 303)
    cost = traffic_gb * a.price_per_gb
    if cost > a.credit_toman:
        log(dbs, a.username, 'user_create', f'validation_failed username={username} reason=insufficient_credit cost={cost} credit={a.credit_toman}')
        return RedirectResponse('/?msg=Insufficient+credit', 303)
    allowed = parse_allowed_inbounds(a.allowed_inbounds)
    if (not a.is_super) and allowed and inbound_id not in allowed:
        log(dbs, a.username, 'user_create', f'validation_failed username={username} reason=inbound_not_allowed inbound_id={inbound_id} allowed={allowed}')
        return RedirectResponse('/?msg=Inbound+is+not+allowed+for+your+account', 303)

    cfg = get_panel_config(dbs)
    if not cfg:
        log(dbs, a.username, 'user_create', f'validation_failed username={username} reason=missing_panel_config')
        return RedirectResponse('/?msg=Set+3x-ui+panel+settings+first', 303)

    expiry_ms = int((datetime.utcnow() + timedelta(days=expiry_days)).timestamp() * 1000)
    client = XUIClient(cfg['url'], cfg['username'], cfg['password'], cfg.get('path', ''))
    try:
        log(dbs, a.username, 'user_create', f'request_start username={username} inbound_id={inbound_id} traffic_gb={traffic_gb} expiry_days={expiry_days}')
        api_result = client.add_client(inbound_id=inbound_id, email=username, total_gb=traffic_gb, expiry_ms=expiry_ms, comment=f'created by {a.username}')
    except Exception as e:
        log(dbs, a.username, 'user_create', f'3xui_exception username={username} error={str(e)}')
        return RedirectResponse(f'/?msg=3x-ui+error:+{str(e)}', 303)

    if not client.is_success(api_result):
        reason = (api_result or {}).get('msg') if isinstance(api_result, dict) else 'unknown_error'
        log(dbs, a.username, 'user_create', f'3xui_rejected username={username} inbound_id={inbound_id} response={json.dumps(api_result, ensure_ascii=False)}')
        return RedirectResponse(f'/?msg=3x-ui+rejected+request:+{reason}', 303)

    a.credit_toman -= cost
    panel_base = cfg['url'].rstrip('/') + cfg.get('path', '')
    links = client.get_client_links(inbound_id=inbound_id, email=username, panel_base=panel_base)
    sub = links.get("subscription") or client.apply_subscription_port(f"{panel_base}/sub/{username}")
    user_cfg = links.get("config") or f'{panel_base}/panel/inbounds'
    dbs.add(UserAccount(admin_id=a.id, username=username, inbound_id=inbound_id, traffic_gb=traffic_gb, expiry_days=expiry_days, subscription_link=sub, config_link=user_cfg, admin_comment=admin_comment.strip()))
    log(dbs, a.username, 'user', f'created {username} {traffic_gb}GB {expiry_days}d inbound_id={inbound_id}')
    dbs.commit()
    return RedirectResponse('/?msg=User+created+successfully', 303)

# unchanged endpoints below
@router.post('/admins/create')
def create_admin(request:Request, username:str=Form(...), password:str=Form(...), credit:float=Form(0), inbound_ids:list[int]=Form([]), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    allowed = ",".join(str(i) for i in sorted(set(inbound_ids)))
    try:
        dbs.add(Admin(username=username,password_hash=hash_password(password),credit_toman=credit,is_super=False,allowed_inbounds=allowed)); dbs.commit(); log(dbs,a.username,'admin',f'created {username}')
    except Exception:
        dbs.rollback()
        return RedirectResponse('/?msg=Error:+admin+username+already+exists',303)
    return RedirectResponse('/',303)

@router.post('/admins/set_price_all')
def price_all(request:Request, price:float=Form(...), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    for ad in dbs.scalars(select(Admin).where(Admin.is_super==False)): ad.price_per_gb=price
    dbs.commit(); return RedirectResponse('/',303)

@router.post('/admins/update')
def admin_update(request:Request, admin_id:int=Form(...), price:float=Form(...), credit:float=Form(...), active:str=Form("true"), inbound_ids:list[int]=Form([]), new_password:str=Form(''), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    ad=dbs.get(Admin,admin_id); ad.price_per_gb=price; ad.credit_toman=credit; ad.active=(active=="true")
    if new_password.strip():
        ad.password_hash=hash_password(new_password.strip())
    ad.allowed_inbounds=",".join(str(i) for i in sorted(set(inbound_ids))); dbs.commit(); return RedirectResponse('/',303)

@router.post('/toggle-all-admin-actions')
def toggle_all(request:Request, enabled:bool=Form(...), dbs=Depends(db)):
    global ADMIN_LOCK
    a=current_admin(request,dbs)
    if a and a.is_super: ADMIN_LOCK=not enabled
    return RedirectResponse('/',303)

@router.post('/balance/request')
def bal_req(request:Request, amount:float=Form(...), message:str=Form(''), screenshot:UploadFile|None=File(None), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or a.is_super: return RedirectResponse('/',303)
    p=''
    if screenshot:
        os.makedirs('app/uploads', exist_ok=True)
        p=f'app/uploads/{a.username}_{int(datetime.utcnow().timestamp())}_{screenshot.filename}'
        with open(p,'wb') as f: f.write(screenshot.file.read())
    dbs.add(BalanceRequest(admin_id=a.id, amount=amount, message=message, screenshot_path=p)); dbs.commit(); return RedirectResponse('/',303)

@router.post('/balance/approve')
def approve(request:Request, req_id:int=Form(...), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    r=dbs.get(BalanceRequest,req_id); ad=dbs.get(Admin,r.admin_id)
    if not r.approved:
        ad.credit_toman += r.amount; r.approved=True; log(dbs,a.username,'balance',f'approve {ad.username} {r.amount}')
        dbs.commit()
    return RedirectResponse('/',303)


@router.post('/system/restart')
def restart_services(request: Request, dbs=Depends(db)):
    a = current_admin(request, dbs)
    if not a or not a.is_super:
        return RedirectResponse('/', 303)
    panel_service = os.getenv("PANEL_SERVICE_NAME", "x-ui")
    app_service = os.getenv("APP_SERVICE_NAME", "web-helper")

    def _service_candidates(primary_name: str):
        names = [primary_name]
        if not primary_name.endswith(".service"):
            names.append(f"{primary_name}.service")
        if primary_name == "x-ui":
            names.extend(["3x-ui", "3x-ui.service"])
        return list(dict.fromkeys(names))

    def _try_restart(service_name: str):
        attempts = []
        for candidate in _service_candidates(service_name):
            attempts.extend([
                ["systemctl", "restart", candidate],
                ["service", candidate, "restart"],
            ])
        last_error = "unknown"
        for cmd in attempts:
            try:
                proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
                return True, cmd, (proc.stdout or "").strip()
            except Exception as exc:
                last_error = str(exc)
        return False, attempts[-1], last_error

    panel_ok, panel_cmd, panel_out = _try_restart(panel_service)
    app_ok, app_cmd, app_out = _try_restart(app_service)
    if panel_ok and app_ok:
        log(dbs, a.username, "system", f"restart_success panel={panel_service} app={app_service}")
        return RedirectResponse('/?msg=Restart+command+sent+successfully', 303)

    detail = f"panel_ok={panel_ok} panel_cmd={' '.join(panel_cmd)} panel_err={panel_out} app_ok={app_ok} app_cmd={' '.join(app_cmd)} app_err={app_out}"
    log(dbs, a.username, "system", f"restart_failed panel={panel_service} app={app_service} {detail}")
    msg = quote_plus("Restart failed. Check service names and system service manager.")
    return RedirectResponse(f'/?msg={msg}', 303)

@router.get('/qr/{kind}/{user_id}', response_class=HTMLResponse)
def qr(kind:str,user_id:int,request:Request,dbs=Depends(db)):
    a=current_admin(request,dbs); u=dbs.get(UserAccount,user_id)
    if not a or not u or (not a.is_super and u.admin_id!=a.id): return HTMLResponse('forbidden',403)
    link=u.subscription_link if kind=='sub' else u.config_link
    img=qrcode.make(link); b=io.BytesIO(); img.save(b,format='PNG')
    return HTMLResponse(f"<img src='data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}'/><p>{link}</p>")


@router.post('/balance/reject')
def reject(request:Request, req_id:int=Form(...), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    r=dbs.get(BalanceRequest,req_id)
    if r and not r.approved:
        dbs.delete(r)
        log(dbs,a.username,'balance',f'reject request_id={req_id}')
        dbs.commit()
    return RedirectResponse('/',303)


@router.post('/users/toggle')
def toggle_user(request:Request, user_id:int=Form(...), enabled:str=Form(...), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or a.is_super:
        return RedirectResponse('/',303)
    u=dbs.get(UserAccount,user_id)
    if not u or u.admin_id!=a.id:
        return RedirectResponse('/',303)
    next_enabled=(enabled=="true")
    cfg=get_panel_config(dbs)
    if cfg:
        try:
            client=XUIClient(cfg['url'],cfg['username'],cfg['password'],cfg.get('path',''))
            result=client.set_client_enabled(u.inbound_id,u.username,next_enabled)
            if not client.is_success(result):
                reason = str(result)
                log(dbs, a.username, 'user', f'toggle_sync_failed username={u.username} user_id={u.id} inbound_id={u.inbound_id} target_enabled={next_enabled} reason={reason}')
                msg = quote_plus(
                    f"3x-ui rejected status change for {u.username}. Status was NOT changed locally. Details: {reason}"
                )
                return RedirectResponse(f'/?msg={msg}', 303)
        except Exception as e:
            err = str(e)
            log(dbs, a.username, 'user', f'toggle_sync_error username={u.username} user_id={u.id} inbound_id={u.inbound_id} target_enabled={next_enabled} error={err}')
            msg = quote_plus(
                f"Failed to reach 3x-ui for {u.username}. Status was NOT changed locally. Error: {err}"
            )
            return RedirectResponse(f'/?msg={msg}', 303)
    u.enabled=next_enabled
    log(dbs,a.username,'user',f'toggle {u.username} enabled={u.enabled}')
    dbs.commit()
    return RedirectResponse('/?msg=User+status+updated',303)
