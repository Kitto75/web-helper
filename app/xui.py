import httpx, uuid, json
from urllib.parse import quote

class XUIClient:
    def __init__(self, base_url:str, username:str, password:str, web_base_path:str=''):
        self.base=base_url.rstrip('/')+web_base_path
        self.username=username; self.password=password
        self.client=httpx.Client(follow_redirects=True, timeout=20)
        self.auth=False
    def login(self):
        r=self.client.post(f'{self.base}/login', json={'username':self.username,'password':self.password})
        self.auth=r.status_code<400
        return self.auth
    def call(self, method, path, **kwargs):
        if not self.auth: self.login()
        r=self.client.request(method, f'{self.base}/panel/api{path}', **kwargs)
        r.raise_for_status(); return r.json()
    def add_client(self,inbound_id:int,email:str,total_gb:float,expiry_ms:int,comment:str):
        payload={"clients":[{"id":str(uuid.uuid4()),"email":email,"limitIp":0,"totalGB":int(total_gb*1024**3),"expiryTime":expiry_ms,"enable":True,"subId":uuid.uuid4().hex[:16],"comment":comment,"flow":"","reset":0}]}
        return self.call('POST','/inbounds/addClient',data={'id':inbound_id,'settings':json.dumps(payload)})
    def list_inbounds(self):
        data = self.call('GET', '/inbounds/list')
        return data.get('obj') or []

    @staticmethod
    def is_success(resp:dict) -> bool:
        if not isinstance(resp, dict):
            return False
        return bool(resp.get('success') is True)

    def get_inbound(self, inbound_id:int):
        data = self.call('GET', f'/inbounds/get/{inbound_id}')
        return data.get('obj') if isinstance(data, dict) else None

    def get_client_sub_id(self, inbound_id:int, email:str):
        inbound = self.get_inbound(inbound_id)
        settings_raw = (inbound or {}).get('settings')
        if not settings_raw:
            return None
        try:
            settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
            clients = (settings or {}).get('clients') or []
            for c in clients:
                if c.get('email') == email:
                    return c.get('subId')
        except Exception:
            return None
        return None

    def get_client_last_online(self, inbound_id: int, email: str):
        inbound = self.get_inbound(inbound_id) or {}
        stats = inbound.get("clientStats") or []
        for st in stats:
            if st.get("email") == email:
                value = st.get("lastOnlineTime")
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return None


    def get_client_links(self, inbound_id:int, email:str, panel_base:str):
        inbound = self.get_inbound(inbound_id) or {}
        settings_raw = inbound.get("settings")
        stream_raw = inbound.get("streamSettings")
        remark = inbound.get("remark") or f"inbound-{inbound_id}"
        if not settings_raw:
            return {"subscription": f"{panel_base}/sub/{email}", "config": ""}
        try:
            settings = json.loads(settings_raw) if isinstance(settings_raw, str) else (settings_raw or {})
            clients = settings.get("clients") or []
        except Exception:
            clients = []
        client = next((c for c in clients if c.get("email") == email), None)
        sub_id = (client or {}).get("subId")
        subscription = f"{panel_base}/sub/{sub_id}" if sub_id else f"{panel_base}/sub/{email}"

        config = ""
        if client:
            try:
                stream = json.loads(stream_raw) if isinstance(stream_raw, str) else (stream_raw or {})
            except Exception:
                stream = {}
            net = stream.get("network") or "tcp"
            security = stream.get("security") or "none"
            xhttp = stream.get("xhttpSettings") or {}
            path = xhttp.get("path") or "/"
            host = (xhttp.get("host") or "")
            mode = xhttp.get("mode") or "auto"
            host_port = inbound.get("port") or 443
            host_addr = inbound.get("listen") or "127.0.0.1"
            cid = client.get("id")
            if cid:
                tag = quote(f"{remark}-{email}")
                config = f"vless://{cid}@{host_addr}:{host_port}?type={net}&encryption=none&path={quote(path)}&host={quote(host)}&mode={mode}&security={security}#{tag}"
        return {"subscription": subscription, "config": config}
