#!/usr/bin/env python3
"""mehrzad_ui: Persian RTL admin prototype API. No VPN engine is integrated."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from pathlib import Path
import sqlite3, os, json, secrets, hashlib, hmac, time, argparse, re
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('MEHRZAD_DB',ROOT/'data/mehrzad.sqlite3'))
SESSIONS={}
PROTOCOLS=('VLESS','VMess','Trojan','Shadowsocks','WireGuard','OpenVPN')
def db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=5000')
    c.executescript('''CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt BLOB NOT NULL, digest BLOB NOT NULL);
    CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY, name TEXT NOT NULL, protocol TEXT NOT NULL, uuid TEXT NOT NULL UNIQUE, enabled INTEGER NOT NULL DEFAULT 1, quota_gb INTEGER NOT NULL DEFAULT 0, expires_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS profiles(id INTEGER PRIMARY KEY, name TEXT NOT NULL, protocol TEXT NOT NULL, listen_port INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
    return c
def pw_hash(p,s): return hashlib.pbkdf2_hmac('sha256',p.encode(),s,310000)
def setup(u,p):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',u): raise ValueError('Username must be 1-64 safe ASCII characters')
    if len(p)<14: raise ValueError('Password must be at least 14 characters')
    c=db()
    try:
        if c.execute('select count(*) from admins').fetchone()[0]: raise ValueError('Admin already initialized')
        salt=secrets.token_bytes(16); c.execute('insert into admins(username,salt,digest) values(?,?,?)',(u,salt,pw_hash(p,salt))); c.commit()
    finally: c.close()
def valid_protocol(p): return p in PROTOCOLS
class Handler(BaseHTTPRequestHandler):
    server_version='mehrzad_ui'
    def log_message(self,*args): pass
    def send(self,code,obj,extra=None):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self' 'unsafe-inline'; img-src 'self' data:")
        for k,v in (extra or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def body(self):
        raw=self.headers.get('Content-Length','0')
        if not raw.isdigit() or int(raw)>65536: raise ValueError('Request too large or invalid length')
        b=self.rfile.read(int(raw))
        d=json.loads(b or b'{}')
        if not isinstance(d,dict): raise ValueError('JSON object required')
        return d
    def sid(self):
        for item in self.headers.get('Cookie','').split(';'):
            k,sep,v=item.strip().partition('=')
            if sep and k=='mehrzad_session': return v
        return ''
    def auth(self):
        sid=self.sid(); exp=SESSIONS.get(sid)
        if exp and exp>time.time(): return True
        SESSIONS.pop(sid,None); return False
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/' or path=='/index.html':
            try: b=(ROOT/'index.html').read_bytes()
            except OSError: return self.send(500,{'error':'UI unavailable'})
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Cache-Control','no-cache'); self.end_headers(); return self.wfile.write(b)
        if path=='/api/health': return self.send(200,{'ok':True,'app':'mehrzad_ui','mode':'prototype'})
        if not self.auth(): return self.send(401,{'error':'Authentication required'})
        c=db()
        try:
            if path=='/api/dashboard': return self.send(200,{'clients':c.execute('select count(*) from clients').fetchone()[0],'active_clients':c.execute('select count(*) from clients where enabled=1').fetchone()[0],'profiles':c.execute('select count(*) from profiles').fetchone()[0]})
            if path=='/api/clients': return self.send(200,[dict(r) for r in c.execute('select * from clients order by id desc')])
            if path=='/api/profiles': return self.send(200,[dict(r) for r in c.execute('select * from profiles order by id desc')])
            return self.send(404,{'error':'Not found'})
        finally: c.close()
    def do_POST(self):
        path=urlparse(self.path).path
        try: data=self.body()
        except (ValueError,json.JSONDecodeError) as e: return self.send(400,{'error':str(e)})
        if path=='/api/login':
            c=db()
            try: row=c.execute('select * from admins where username=?',(str(data.get('username','')),)).fetchone()
            finally: c.close()
            password=str(data.get('password',''))
            digest=pw_hash(password,row['salt']) if row else pw_hash(password,b'\0'*16)
            if not row or not hmac.compare_digest(digest,row['digest']): return self.send(401,{'error':'Invalid credentials'})
            sid=secrets.token_urlsafe(32); SESSIONS[sid]=time.time()+8*3600
            secure='; Secure' if self.headers.get('X-Forwarded-Proto','').lower()=='https' else ''
            return self.send(200,{'ok':True},{'Set-Cookie':f'mehrzad_session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800{secure}'})
        if not self.auth(): return self.send(401,{'error':'Authentication required'})
        if path=='/api/logout':
            SESSIONS.pop(self.sid(),None); return self.send(200,{'ok':True},{'Set-Cookie':'mehrzad_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
        if path!='/api/clients': return self.send(404,{'error':'Not found'})
        name=str(data.get('name','')).strip(); proto=data.get('protocol'); quota=data.get('quota_gb',0); expires=data.get('expires_at')
        if not name or len(name)>100 or not isinstance(proto,str) or not valid_protocol(proto): return self.send(400,{'error':'Valid name and supported protocol required'})
        try: quota=int(quota)
        except (ValueError,TypeError): return self.send(400,{'error':'quota_gb must be a non-negative integer'})
        if quota<0 or quota>100000000: return self.send(400,{'error':'quota_gb out of range'})
        if expires is not None and (not isinstance(expires,str) or len(expires)>40): return self.send(400,{'error':'Invalid expires_at'})
        c=db()
        try:
            cur=c.execute('insert into clients(name,protocol,uuid,quota_gb,expires_at) values(?,?,?,?,?)',(name,proto,secrets.token_hex(16),quota,expires)); c.commit(); row=c.execute('select * from clients where id=?',(cur.lastrowid,)).fetchone(); return self.send(201,dict(row))
        finally: c.close()
    def do_DELETE(self):
        if not self.auth(): return self.send(401,{'error':'Authentication required'})
        p=urlparse(self.path).path.split('/')
        if len(p)!=4 or p[:2]!=['','api'] or p[2]!='clients' or not p[3].isdigit(): return self.send(404,{'error':'Not found'})
        c=db()
        try: cur=c.execute('delete from clients where id=?',(int(p[3]),)); c.commit(); return self.send(200,{'deleted':cur.rowcount>0})
        finally: c.close()
def main():
    p=argparse.ArgumentParser(); p.add_argument('--setup-admin',nargs=2,metavar=('USER','PASSWORD')); p.add_argument('--host',default='127.0.0.1'); p.add_argument('--port',type=int,default=8080); a=p.parse_args()
    if a.setup_admin:
        try: setup(*a.setup_admin)
        except ValueError as e: raise SystemExit(str(e))
        print('Admin initialized.'); return
    if a.host not in ('127.0.0.1','::1','localhost'): raise SystemExit('Unsafe direct bind refused; place behind a TLS reverse proxy and add a reviewed deployment config first.')
    print(f'mehrzad_ui prototype listening at http://{a.host}:{a.port}'); ThreadingHTTPServer((a.host,a.port),Handler).serve_forever()
if __name__=='__main__': main()
