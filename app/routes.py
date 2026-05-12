import base64, io, os
from datetime import datetime, timedelta
import pytz, qrcode
from fastapi import APIRouter, Depends, Form, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer
from sqlalchemy import select
from .db import SessionLocal
from .models import Admin, AuditLog, BalanceRequest, UserAccount
from .security import hash_password, verify_password, valid_username

router=APIRouter()
templates=Jinja2Templates('app/templates')
ser=URLSafeSerializer('change-me')
ADMIN_LOCK=False

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

def current_admin(req, dbs):
    c=req.cookies.get('sess')
    if not c: return None
    try: uid=ser.loads(c)['uid']
    except Exception: return None
    return dbs.get(Admin, uid)

def log(dbs, actor, cat, detail): dbs.add(AuditLog(actor=actor, category=cat, detail=detail)); dbs.commit()

@router.get('/', response_class=HTMLResponse)
def home(request:Request, dbs=Depends(db)):
    admin=current_admin(request,dbs)
    if not admin: return RedirectResponse('/login')
    tz=pytz.timezone('Asia/Tehran')
    users=dbs.scalars(select(UserAccount).where(UserAccount.admin_id==admin.id if not admin.is_super else True)).all()
    logs=dbs.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(100)).all() if admin.is_super else dbs.scalars(select(AuditLog).where(AuditLog.actor==admin.username).order_by(AuditLog.id.desc()).limit(100)).all()
    admins=dbs.scalars(select(Admin)).all() if admin.is_super else []
    reqs=dbs.scalars(select(BalanceRequest).where(BalanceRequest.approved==False)).all() if admin.is_super else []
    return templates.TemplateResponse('index.html', {'request':request,'admin':admin,'users':users,'logs':logs,'admins':admins,'reqs':reqs,'now':datetime.now(tz)})

@router.get('/login', response_class=HTMLResponse)
def login_page(request:Request): return templates.TemplateResponse('login.html',{'request':request})

@router.post('/login')
def login(request:Request, username:str=Form(...), password:str=Form(...), dbs=Depends(db)):
    admin=dbs.scalar(select(Admin).where(Admin.username==username))
    if admin and verify_password(password,admin.password_hash) and admin.active:
        resp=RedirectResponse('/',status_code=303); resp.set_cookie('sess',ser.dumps({'uid':admin.id}),httponly=True,samesite='lax'); return resp
    return RedirectResponse('/login',status_code=303)

@router.post('/bootstrap')
def bootstrap(username:str=Form(...), password:str=Form(...), dbs=Depends(db)):
    if dbs.scalar(select(Admin)): return {'ok':False}
    dbs.add(Admin(username=username,password_hash=hash_password(password),is_super=True)); dbs.commit(); return {'ok':True}

@router.post('/admins/create')
def create_admin(request:Request, username:str=Form(...), password:str=Form(...), credit:float=Form(0), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    dbs.add(Admin(username=username,password_hash=hash_password(password),credit_toman=credit,is_super=False)); dbs.commit(); log(dbs,a.username,'admin',f'created {username}'); return RedirectResponse('/',303)

@router.post('/users/create')
def create_user(request:Request, username:str=Form(...), inbound_id:int=Form(...), traffic_gb:float=Form(...), expiry_days:int=Form(30), dbs=Depends(db)):
    global ADMIN_LOCK
    a=current_admin(request,dbs)
    if not a or not a.active or ADMIN_LOCK: return RedirectResponse('/',303)
    if not valid_username(username): return RedirectResponse('/',303)
    expiry_days = min(expiry_days or 30, 30)
    if traffic_gb<=0: return RedirectResponse('/',303)
    cost=traffic_gb*a.price_per_gb
    if cost>a.credit_toman: return RedirectResponse('/',303)
    a.credit_toman-=cost
    sub=f'https://sub.example/{username}'; cfg=f'vless://{username}@server:443'
    dbs.add(UserAccount(admin_id=a.id,username=username,inbound_id=inbound_id,traffic_gb=traffic_gb,expiry_days=expiry_days,subscription_link=sub,config_link=cfg))
    log(dbs,a.username,'user',f'created {username} {traffic_gb}GB {expiry_days}d')
    dbs.commit(); return RedirectResponse('/',303)

@router.post('/admins/set_price_all')
def price_all(request:Request, price:float=Form(...), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    for ad in dbs.scalars(select(Admin).where(Admin.is_super==False)): ad.price_per_gb=price
    dbs.commit(); return RedirectResponse('/',303)

@router.post('/admins/update')
def admin_update(request:Request, admin_id:int=Form(...), price:float=Form(...), credit:float=Form(...), active:bool=Form(True), dbs=Depends(db)):
    a=current_admin(request,dbs)
    if not a or not a.is_super: return RedirectResponse('/',303)
    ad=dbs.get(Admin,admin_id); ad.price_per_gb=price; ad.credit_toman=credit; ad.active=active; dbs.commit(); return RedirectResponse('/',303)

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

@router.get('/qr/{kind}/{user_id}', response_class=HTMLResponse)
def qr(kind:str,user_id:int,request:Request,dbs=Depends(db)):
    a=current_admin(request,dbs); u=dbs.get(UserAccount,user_id)
    if not a or not u or (not a.is_super and u.admin_id!=a.id): return HTMLResponse('forbidden',403)
    link=u.subscription_link if kind=='sub' else u.config_link
    img=qrcode.make(link); b=io.BytesIO(); img.save(b,format='PNG')
    return HTMLResponse(f"<img src='data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}'/><p>{link}</p>")
