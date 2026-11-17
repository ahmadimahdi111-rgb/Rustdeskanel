#!/usr/bin/env python3
"""HCU RustDesk management panel. Python standard library only."""
import base64, hashlib, hmac, json, os, secrets, shutil, sqlite3, ssl, subprocess, tempfile, time, urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

VERSION='3.2.0'
HOST=os.getenv('PANEL_BIND','172.16.2.99'); PORT=int(os.getenv('PANEL_PORT','8765'))
DATA=Path(os.getenv('PANEL_DATA','/var/lib/rustdeskpanel')); DB_PATH=DATA/'panel.sqlite3'
STATUS=Path(os.getenv('PANEL_STATUS_FILE','/var/lib/mizyar-panel/status.json'))
CERT=os.getenv('PANEL_CERT','/etc/rustdeskpanel/tls.crt'); KEY=os.getenv('PANEL_KEY','/etc/rustdeskpanel/tls.key')
DEVICE_KEY=os.getenv('PANEL_DEVICE_KEY',''); REPO='ahmadimahdi111-rgb/Rustdeskanel'
ROOT=Path(__file__).resolve().parent

def utcnow(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
@contextmanager
def conn():
    c=sqlite3.connect(DB_PATH,timeout=20); c.row_factory=sqlite3.Row
    try: yield c; c.commit()
    except Exception: c.rollback(); raise
    finally: c.close()
def password_hash(password,salt=None):
    salt=salt or secrets.token_bytes(16)
    return salt.hex()+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt,260000).hex()
def password_ok(password,stored):
    try:
        s,h=stored.split(':'); got=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(s),260000).hex()
        return hmac.compare_digest(got,h)
    except Exception: return False
def sqlite_backup(src_path,dst_path):
    src=sqlite3.connect(src_path,timeout=20); dst=sqlite3.connect(dst_path)
    try: src.backup(dst)
    finally: dst.close(); src.close()
def init_db():
    DATA.mkdir(parents=True,exist_ok=True)
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'operator',active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL,kind TEXT NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS favorites(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,target_id TEXT NOT NULL,name TEXT NOT NULL DEFAULT '',UNIQUE(user_id,target_id));
        CREATE TABLE IF NOT EXISTS devices(target_id TEXT PRIMARY KEY,name TEXT NOT NULL,ip TEXT NOT NULL,seen_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL,username TEXT NOT NULL,source_host TEXT NOT NULL,source_ip TEXT NOT NULL,target_id TEXT NOT NULL,target_name TEXT,target_ip TEXT,started_at TEXT NOT NULL,ended_at TEXT,duration INTEGER,result TEXT NOT NULL DEFAULT 'در حال اجرا');
        CREATE INDEX IF NOT EXISTS events_date_idx ON events(started_at);''')
        if not c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
            pw=os.getenv('PANEL_ADMIN_PASSWORD','')
            if len(pw)<8: raise SystemExit('PANEL_ADMIN_PASSWORD must be at least 8 characters')
            c.execute('INSERT INTO users(username,password,role,created_at) VALUES(?,?,?,?)',('admin',password_hash(pw),'admin',utcnow()))
        c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',('title','پنل ریموت به کاربران - فناوری اطلاعات دانشگاه حضرت معصومه س'))
        c.execute('INSERT OR IGNORE INTO settings VALUES(?,?)',('logo',''))

class Handler(BaseHTTPRequestHandler):
    server_version='RustDeskPanel/3'
    def log_message(self,*a): pass
    def send_json(self,obj,status=200,headers=None):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b)))
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers(); self.wfile.write(b)
    def read_json(self,limit=30*1024*1024):
        n=int(self.headers.get('Content-Length','0'))
        if n>limit: raise ValueError('حجم درخواست از حد مجاز بیشتر است')
        return json.loads(self.rfile.read(n) or b'{}')
    def token(self):
        a=self.headers.get('Authorization','')
        if a.startswith('Bearer '): return a[7:]
        ck=SimpleCookie(); ck.load(self.headers.get('Cookie','')); m=ck.get('hcu')
        return m.value if m else ''
    def user(self):
        t=self.token()
        if not t: return None
        with conn() as c:
            r=c.execute('SELECT u.*,s.kind,s.expires FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?',(hashlib.sha256(t.encode()).hexdigest(),)).fetchone()
            return r if r and r['active'] and r['expires']>int(time.time()) else None
    def require(self,admin=False,kind=None):
        u=self.user()
        if not u: self.send_json({'error':'ابتدا وارد شوید'},401); return None
        if admin and u['role']!='admin': self.send_json({'error':'دسترسی مدیر لازم است'},403); return None
        if kind and u['kind']!=kind: self.send_json({'error':'از کلاینت ویندوز وارد شوید'},403); return None
        return u
    def do_GET(self):
        p=urlparse(self.path).path
        if p in ('/','/index.html'): return self.file(ROOT/'index.html','text/html; charset=utf-8')
        if p=='/api/me':
            u=self.require()
            if not u:return
            return self.send_json({'username':u['username'],'role':u['role']})
        if p=='/api/settings':
            u=self.require();
            if u:
                with conn() as c: s={r['key']:r['value'] for r in c.execute('SELECT key,value FROM settings')}
                self.send_json({'title':s.get('title',''),'logo':s.get('logo','')})
            return
        if p=='/api/status':
            if not self.require(): return
            try: d=json.loads(STATUS.read_text())
            except Exception: d={'containers':[],'error':'دادهٔ وضعیت RustDesk هنوز دریافت نشده است'}
            return self.send_json(d)
        if p=='/api/favorites':
            u=self.require();
            if u:
                with conn() as c: rows=[dict(x) for x in c.execute('SELECT target_id,name FROM favorites WHERE user_id=? ORDER BY name,target_id',(u['id'],))]
                self.send_json({'items':rows})
            return
        if p=='/api/devices':
            if not self.require(): return
            with conn() as c: rows=[dict(x) for x in c.execute('SELECT target_id,name,ip,seen_at FROM devices ORDER BY name')]
            return self.send_json({'devices':rows})
        if p=='/api/events':
            if not self.require(): return
            q=parse_qs(urlparse(self.path).query); term=q.get('q',[''])[0].strip(); start=q.get('from',[''])[0]; end=q.get('to',[''])[0]
            sql='SELECT * FROM events WHERE 1=1'; args=[]
            if term: sql+=' AND (username LIKE ? OR source_ip LIKE ? OR source_host LIKE ? OR target_id LIKE ? OR target_name LIKE ? OR target_ip LIKE ?)'; args += [f'%{term}%']*6
            if start: sql+=' AND date(started_at)>=date(?)'; args.append(start)
            if end: sql+=' AND date(started_at)<=date(?)'; args.append(end)
            sql+=' ORDER BY id DESC LIMIT 1000'
            with conn() as c: rows=[dict(x) for x in c.execute(sql,args)]
            return self.send_json({'events':rows})
        if p=='/api/admin/users':
            if not self.require(admin=True): return
            with conn() as c: rows=[dict(x) for x in c.execute('SELECT id,username,role,active,created_at FROM users ORDER BY username')]
            return self.send_json({'users':rows})
        if p=='/api/admin/device-key':
            if not self.require(admin=True): return
            return self.send_json({'key':DEVICE_KEY})
        if p=='/api/admin/backup':
            if not self.require(admin=True): return
            return self.backup()
        if p=='/api/admin/update/check':
            if not self.require(admin=True): return
            try:
                req=urllib.request.Request(f'https://raw.githubusercontent.com/{REPO}/main/panel/VERSION',headers={'User-Agent':'RustDeskPanel-Updater'})
                latest=urllib.request.urlopen(req,timeout=8).read(100).decode().strip()
                return self.send_json({'current':VERSION,'latest':latest,'available':latest!=VERSION})
            except Exception as e: return self.send_json({'current':VERSION,'error':str(e)},502)
        self.send_error(404)
    def file(self,path,typ):
        try: b=path.read_bytes()
        except OSError: self.send_error(404); return
        self.send_response(200); self.send_header('Content-Type',typ); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
    def backup(self):
        temp=DATA/'panel-backup-download.sqlite3'
        try:
            src=sqlite3.connect(DB_PATH); dst=sqlite3.connect(temp); src.backup(dst); dst.close(); src.close(); b=temp.read_bytes()
            self.send_response(200); self.send_header('Content-Type','application/vnd.sqlite3'); self.send_header('Content-Disposition',f'attachment; filename="rustdeskpanel-backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}.sqlite3"'); self.send_header('Content-Length',str(len(b))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(b)
        finally: temp.unlink(missing_ok=True)
    def do_POST(self):
        p=urlparse(self.path).path
        try: x=self.read_json()
        except Exception as e: return self.send_json({'error':str(e)},400)
        if p in ('/api/login','/api/client/login'):
            with conn() as c: u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(str(x.get('username','')).strip(),)).fetchone()
            if not u or not password_ok(str(x.get('password','')),u['password']): return self.send_json({'error':'نام کاربری یا رمز عبور نادرست است'},401)
            kind='client' if p.endswith('/client/login') else 'web'; t=secrets.token_urlsafe(36)
            with conn() as c: c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(hashlib.sha256(t.encode()).hexdigest(),u['id'],kind,int(time.time())+43200))
            if kind=='client': return self.send_json({'token':t,'username':u['username']})
            return self.send_json({'username':u['username'],'role':u['role']},headers={'Set-Cookie':f'hcu={t}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=43200'})
        if p=='/api/logout':
            u=self.require();
            if not u:return
            t=self.token()
            with conn() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(t.encode()).hexdigest(),))
            return self.send_json({'ok':True},headers={'Set-Cookie':'hcu=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0'})
        if p=='/api/password':
            u=self.require();
            if not u:return
            new=str(x.get('new',''))
            if len(new)<8 or not password_ok(str(x.get('old','')),u['password']):return self.send_json({'error':'رمز فعلی اشتباه است یا رمز جدید کمتر از ۸ نویسه است'},400)
            with conn() as c:c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(new),u['id']))
            return self.send_json({'ok':True})
        if p=='/api/admin/users':
            if not self.require(admin=True):return
            name=str(x.get('username','')).strip(); pw=str(x.get('password',''))
            if not name or len(pw)<8:return self.send_json({'error':'نام کاربری لازم است؛ رمز باید حداقل ۸ نویسه باشد'},400)
            try:
                with conn() as c:c.execute('INSERT INTO users(username,password,role,created_at) VALUES(?,?,?,?)',(name,password_hash(pw),'operator',utcnow()))
            except sqlite3.IntegrityError:return self.send_json({'error':'نام کاربری تکراری است'},409)
            return self.send_json({'ok':True},201)
        if p.startswith('/api/admin/users/') and p.endswith('/password'):
            if not self.require(admin=True):return
            uid=int(p.split('/')[-2]); new=str(x.get('password',''))
            if len(new)<8:return self.send_json({'error':'رمز جدید باید حداقل ۸ نویسه باشد'},400)
            with conn() as c:
                target=c.execute("SELECT id,role FROM users WHERE id=?",(uid,)).fetchone()
                if not target or target['role']=='admin':return self.send_json({'error':'تغییر رمز این کاربر از این بخش مجاز نیست'},404)
                c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(new),uid))
                c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
            return self.send_json({'ok':True})
        if p.startswith('/api/admin/users/') and p.endswith('/toggle'):
            if not self.require(admin=True):return
            uid=int(p.split('/')[-2])
            with conn() as c:c.execute("UPDATE users SET active=1-active WHERE id=? AND role<>'admin'",(uid,)); c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
            return self.send_json({'ok':True})
        if p=='/api/admin/settings':
            if not self.require(admin=True):return
            title=str(x.get('title','')).strip()[:120]; logo=str(x.get('logo',''))
            if len(logo)>2_000_000:return self.send_json({'error':'لوگو بیش از حد بزرگ است'},400)
            if logo and not logo.startswith('data:image/'):return self.send_json({'error':'فایل لوگو باید تصویر باشد'},400)
            with conn() as c:c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('title',title)); c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('logo',logo))
            return self.send_json({'ok':True})
        if p=='/api/favorites':
            u=self.require(kind='client');
            if not u:return
            tid=str(x.get('target_id','')).strip(); name=str(x.get('name','')).strip()[:100]
            if not tid:return self.send_json({'error':'شناسه مقصد لازم است'},400)
            with conn() as c:c.execute('INSERT INTO favorites(user_id,target_id,name) VALUES(?,?,?) ON CONFLICT(user_id,target_id) DO UPDATE SET name=excluded.name',(u['id'],tid,name))
            return self.send_json({'ok':True})
        if p=='/api/favorites/delete':
            u=self.require(kind='client');
            if not u:return
            with conn() as c:c.execute('DELETE FROM favorites WHERE user_id=? AND target_id=?',(u['id'],str(x.get('target_id',''))))
            return self.send_json({'ok':True})
        if p=='/api/client/events/start':
            u=self.require(kind='client');
            if not u:return
            tid=str(x.get('target_id','')).strip(); host=str(x.get('source_host',''))[:150]
            if not tid:return self.send_json({'error':'شناسه مقصد لازم است'},400)
            with conn() as c:
                d=c.execute('SELECT name,ip FROM devices WHERE target_id=?',(tid,)).fetchone()
                cur=c.execute('INSERT INTO events(user_id,username,source_host,source_ip,target_id,target_name,target_ip,started_at) VALUES(?,?,?,?,?,?,?,?)',(u['id'],u['username'],host,self.client_address[0],tid,d['name'] if d else '',d['ip'] if d else '',utcnow()))
            return self.send_json({'event_id':cur.lastrowid},201)
        if p=='/api/client/events/finish':
            u=self.require(kind='client');
            if not u:return
            eid=int(x.get('event_id',0)); result=str(x.get('result','پایان‌یافته'))[:60]
            with conn() as c:
                e=c.execute('SELECT * FROM events WHERE id=? AND user_id=? AND ended_at IS NULL',(eid,u['id'])).fetchone()
                if not e:return self.send_json({'error':'نشست پیدا نشد'},404)
                end=datetime.now(timezone.utc); dur=max(0,int((end-datetime.fromisoformat(e['started_at'])).total_seconds()))
                c.execute('UPDATE events SET ended_at=?,duration=?,result=? WHERE id=?',(end.isoformat(timespec='seconds'),dur,result,eid))
            return self.send_json({'ok':True})
        if p=='/api/agent/heartbeat':
            if not DEVICE_KEY or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+DEVICE_KEY):return self.send_json({'error':'کلید Agent نادرست است'},401)
            tid=str(x.get('target_id','')).strip(); name=str(x.get('name',''))[:120]; ip=str(x.get('ip',''))[:64]
            if not tid or not name or not ip:return self.send_json({'error':'شناسه، نام و IP لازم است'},400)
            with conn() as c:c.execute('INSERT INTO devices VALUES(?,?,?,?) ON CONFLICT(target_id) DO UPDATE SET name=excluded.name,ip=excluded.ip,seen_at=excluded.seen_at',(tid,name,ip,utcnow()))
            return self.send_json({'ok':True})
        if p=='/api/admin/restore':
            if not self.require(admin=True):return
            raw=x.get('backup','')
            try:
                if not isinstance(raw,str) or ';base64,' not in raw:raise ValueError('فایل پشتیبان معتبر نیست')
                content=base64.b64decode(raw.split(',',1)[1],validate=True)
                if len(content)>25*1024*1024:raise ValueError('حجم بکاپ بیشتر از ۲۵ مگابایت است')
                if not content.startswith(b'SQLite format 3\x00'):raise ValueError('فایل انتخاب‌شده پایگاه‌داده SQLite نیست')
                tmp=DATA/'restore-check.sqlite3'; tmp.write_bytes(content)
                c=sqlite3.connect(tmp); result=c.execute('PRAGMA integrity_check').fetchone()[0]
                tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; c.close()
                if result!='ok' or not {'users','events','settings','favorites'}.issubset(tables):raise ValueError('ساختار یا سلامت فایل پشتیبان معتبر نیست')
                auto=DATA/f'pre-restore-{datetime.now().strftime("%Y%m%d-%H%M%S")}.sqlite3'; sqlite_backup(DB_PATH,auto)
                os.replace(tmp,DB_PATH); return self.send_json({'ok':True,'automatic_backup':auto.name})
            except Exception as e:return self.send_json({'error':str(e)},400)
        if p=='/api/admin/update/apply':
            if not self.require(admin=True):return
            try:
                r=subprocess.run(['sudo','-n','/usr/local/sbin/rustdeskpanel-launch-update'],capture_output=True,text=True,timeout=15)
                output=(r.stdout+'\n'+r.stderr).strip()[-4000:]
                if r.returncode: return self.send_json({'ok':False,'error':output or 'اجرای سرویس به‌روزرسانی مجاز نشد'},500)
                return self.send_json({'ok':True,'output':'درخواست به‌روزرسانی در پس‌زمینه اجرا شد. چند لحظه صبر کن و صفحه را تازه‌سازی کن.'})
            except Exception as e:return self.send_json({'ok':False,'error':str(e)},500)
        return self.send_error(404)

def main():
    init_db(); ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.load_cert_chain(CERT,KEY)
    s=ThreadingHTTPServer((HOST,PORT),Handler); s.socket=ctx.wrap_socket(s.socket,server_side=True); s.serve_forever()
if __name__=='__main__':main()
