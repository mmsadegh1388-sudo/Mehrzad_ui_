import json, tempfile, unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from threading import Thread
import app

class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(); app.DB=Path(cls.tmp.name)/'test.db'; app.SESSIONS.clear(); app.setup('admin','this-is-a-long-test-password')
  cls.srv=ThreadingHTTPServer(('127.0.0.1',0),app.Handler); Thread(target=cls.srv.serve_forever,daemon=True).start(); cls.base=f'http://127.0.0.1:{cls.srv.server_port}'
 @classmethod
 def tearDownClass(cls): cls.srv.shutdown(); cls.tmp.cleanup()
 def call(self,path,body=None,cookie=None,method=None):
  data=None if body is None else json.dumps(body,ensure_ascii=False).encode(); req=Request(self.base+path,data=data,method=method,headers={'Content-Type':'application/json',**({'Cookie':cookie} if cookie else {})})
  try:
   with urlopen(req) as r:return r.status,r.headers,r.read()
  except HTTPError as e:return e.code,e.headers,e.read()
 def login(self):
  code,h,_=self.call('/api/login',{'username':'admin','password':'this-is-a-long-test-password'}); self.assertEqual(code,200); return h['Set-Cookie'].split(';')[0]
 def test_health_and_protected_routes(self):
  self.assertEqual(self.call('/api/health')[0],200); self.assertEqual(self.call('/api/clients')[0],401)
 def test_ui_served(self): self.assertIn('mehrzad_ui'.encode(),self.call('/')[2])
 def test_create_persian_record_list_and_delete(self):
  cookie=self.login(); code,_,body=self.call('/api/clients',{'name':'کاربر می‌شود','protocol':'VLESS','quota_gb':123},cookie); self.assertEqual(code,201); row=json.loads(body); self.assertEqual(row['name'],'کاربر می‌شود'); self.assertEqual(row['quota_gb'],123)
  self.assertEqual(len(json.loads(self.call('/api/clients',cookie=cookie)[2])),1)
  self.assertEqual(self.call(f"/api/clients/{row['id']}",cookie=cookie,method='DELETE')[0],200)
 def test_invalid_protocol_quota_and_bad_json(self):
  cookie=self.login(); self.assertEqual(self.call('/api/clients',{'name':'x','protocol':'bogus'},cookie)[0],400); self.assertEqual(self.call('/api/clients',{'name':'x','protocol':'VLESS','quota_gb':-1},cookie)[0],400)
  req=Request(self.base+'/api/login',data=b'{',headers={'Content-Type':'application/json'})
  try:urlopen(req)
  except HTTPError as e:self.assertEqual(e.code,400)
 def test_logout_invalidates_session(self):
  cookie=self.login(); self.assertEqual(self.call('/api/logout',{},cookie)[0],200); self.assertEqual(self.call('/api/clients',cookie=cookie)[0],401)
if __name__=='__main__':unittest.main()
  
