import httpx, uuid, json

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
