"""SQLite transacional e cifragem autenticada de conteúdo com chave externa."""
import hashlib
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager, closing
from pathlib import Path
from cryptography.fernet import Fernet
from .domain import Invalid

# Comandos que o administrador pode ligar/desligar e reescrever. cmd -> rótulo mostrado no Admin.
BOT_COMMANDS={
    'whatsapp':{'help':'!help','duelo':'!duelo','evolucao':'!evolucao','precocoin':'!precocoin','pt':'!pt','char':'!char','online':'!online','xptop':'!xptop'},
    'assistente':{'bomdia':'bom dia','kill':'kill','boss':'boss','online':'online','char':'char','death':'death','guild':'guild','exp':'exp'}}

def ident(): return uuid.uuid4().hex

class Store:
    def __init__(self, path, key, open_access=False):
        self.open_access=open_access  # só para testes e para a demonstração; o servidor real nunca liga isto
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.cipher=Fernet(key)
        with self.tx() as db:
            first_time=not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='entitlements'").fetchone()
            db.executescript('''
            CREATE TABLE IF NOT EXISTS entitlements(owner TEXT PRIMARY KEY,since REAL NOT NULL,note TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS claim_codes(hash TEXT PRIMARY KEY,note TEXT NOT NULL DEFAULT '',uses INTEGER,created REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS admins(owner TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY,owner TEXT NOT NULL,kind TEXT NOT NULL,state TEXT NOT NULL,body BLOB NOT NULL,version INTEGER NOT NULL DEFAULT 1);
            CREATE INDEX IF NOT EXISTS owners ON objects(owner,kind);
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,owner TEXT NOT NULL,subscription TEXT NOT NULL,destination TEXT NOT NULL,reference TEXT NOT NULL,generation REAL,send REAL,state TEXT NOT NULL,snapshot BLOB,receipt BLOB,attempt TEXT,lease REAL,error TEXT,version INTEGER NOT NULL,generation_attempts INTEGER NOT NULL DEFAULT 0,retry_after REAL NOT NULL DEFAULT 0,
              UNIQUE(owner,subscription,destination,reference));
            CREATE TABLE IF NOT EXISTS watch_members(watch TEXT NOT NULL,name TEXT NOT NULL,level INTEGER NOT NULL,online INTEGER NOT NULL DEFAULT 0,vocation TEXT,checked REAL NOT NULL DEFAULT 0,PRIMARY KEY(watch,name));
            CREATE TABLE IF NOT EXISTS watch_meta(watch TEXT PRIMARY KEY,last_run REAL NOT NULL DEFAULT 0,since REAL NOT NULL DEFAULT 0,primed INTEGER NOT NULL DEFAULT 0,world TEXT,roster_at REAL NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS command_use(botgroup TEXT NOT NULL,sender TEXT NOT NULL,last REAL NOT NULL,PRIMARY KEY(botgroup,sender));
            CREATE TABLE IF NOT EXISTS command_seen(botgroup TEXT NOT NULL,msg TEXT NOT NULL,at REAL NOT NULL,PRIMARY KEY(botgroup,msg));
            CREATE TABLE IF NOT EXISTS rank_history(world TEXT NOT NULL,day TEXT NOT NULL,name TEXT NOT NULL,level INTEGER NOT NULL,xp INTEGER NOT NULL,PRIMARY KEY(world,day,name));
            CREATE TABLE IF NOT EXISTS bot_settings(scope TEXT NOT NULL,cmd TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,text TEXT NOT NULL DEFAULT '',PRIMARY KEY(scope,cmd));
            CREATE TABLE IF NOT EXISTS rank_meta(world TEXT PRIMARY KEY,last_day TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS watch_events(id TEXT PRIMARY KEY,owner TEXT NOT NULL,watch TEXT NOT NULL,key TEXT NOT NULL,text BLOB NOT NULL,state TEXT NOT NULL,created REAL NOT NULL,sent_at REAL,attempt TEXT,lease REAL,error TEXT,UNIQUE(watch,key));
            ''')
            columns={r['name'] for r in db.execute('PRAGMA table_info(runs)')}
            for name,definition in [('generation_attempts','INTEGER NOT NULL DEFAULT 0'),('retry_after','REAL NOT NULL DEFAULT 0')]:
                if name not in columns: db.execute('ALTER TABLE runs ADD COLUMN '+name+' '+definition)
            # Bancos criados antes do vigia usar a lista online do mundo ganham as colunas novas sem perder dados.
            for table,additions in (('watch_members',[('vocation','TEXT'),('checked','REAL NOT NULL DEFAULT 0')]),('watch_meta',[('world','TEXT'),('roster_at','REAL NOT NULL DEFAULT 0')]),('claim_codes',[('created','REAL NOT NULL DEFAULT 0')])):
                have={r['name'] for r in db.execute('PRAGMA table_info('+table+')')}
                for name,definition in additions:
                    if name not in have: db.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)
            # Recurso fechado: só contas liberadas usam o serviço. Quem já tinha dados antes desta regra continua liberado.
            if first_time: db.execute("INSERT OR IGNORE INTO entitlements(owner,since,note) SELECT DISTINCT owner,strftime('%s','now'),'existente' FROM objects")
        if os.name!='nt': os.chmod(self.path,0o600)

    def entitled_in(self,db,owner):
        return self.open_access or db.execute('SELECT 1 FROM entitlements WHERE owner=?',(owner,)).fetchone() is not None

    def entitled(self,owner):
        with self.tx() as db: return self.entitled_in(db,owner)

    def grant(self,owner,note=''):
        with self.tx() as db:
            has_installations=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='installations'").fetchone()
            if not (has_installations and db.execute('SELECT 1 FROM installations WHERE owner=?',(owner,)).fetchone()) and not db.execute('SELECT 1 FROM objects WHERE owner=?',(owner,)).fetchone(): raise Invalid('Conta não encontrada.')
            db.execute("INSERT OR IGNORE INTO entitlements(owner,since,note) VALUES(?,strftime('%s','now'),?)",(owner,str(note)[:80]))

    def create_claim(self,note='',uses=None):
        """Gera um código de liberação (mostrado uma única vez; só o hash fica guardado). uses=None vale sem limite (código do dono)."""
        code=secrets.token_urlsafe(32)
        with self.tx() as db: db.execute('INSERT INTO claim_codes(hash,note,uses,created) VALUES(?,?,?,?)',(hashlib.sha256(code.encode()).hexdigest(),str(note)[:80],uses,time.time()))
        return code

    # ---- administração (só contas administradoras chegam aqui, pela API) ----
    def is_admin(self,owner):
        with self.tx() as db: return db.execute('SELECT 1 FROM admins WHERE owner=?',(owner,)).fetchone() is not None

    def admin_claims(self):
        """Códigos de cliente (nunca o código em si, só quantos usos restam). O código do dono não aparece."""
        with self.tx() as db: return [{'id':r['hash'][:16],'note':r['note'],'uses':r['uses'],'created':r['created']} for r in db.execute("SELECT hash,note,uses,created FROM claim_codes WHERE note!='dono' ORDER BY created DESC,hash")]

    def admin_new_claim(self,note,uses=1):
        note=' '.join(str(note).split())
        if not note or len(note)>60 or note.casefold()=='dono': raise Invalid('Informe o nome do cliente (até 60 caracteres).')
        if type(uses) is not int or not 1<=uses<=1000: raise Invalid('Usos de 1 a 1000.')
        return self.create_claim(note,uses)

    def admin_revoke_claim(self,claim_id):
        if not isinstance(claim_id,str) or not re.fullmatch(r'[a-f0-9]{16}',claim_id): raise Invalid('Código não encontrado.')
        with self.tx() as db:
            if db.execute("DELETE FROM claim_codes WHERE substr(hash,1,16)=? AND note!='dono'",(claim_id,)).rowcount==0: raise Invalid('Código não encontrado.')

    def admin_accounts(self):
        with self.tx() as db: return [{'owner':r['owner'],'note':r['note'],'since':r['since'],'admin':bool(r['admin'])} for r in db.execute('SELECT e.owner AS owner,e.note AS note,e.since AS since,(SELECT 1 FROM admins a WHERE a.owner=e.owner) AS admin FROM entitlements e ORDER BY e.since DESC,e.owner')]

    def admin_remove_account(self,owner):
        if not isinstance(owner,str) or not re.fullmatch(r'[a-f0-9]{32}',owner): raise Invalid('Conta não encontrada.')
        with self.tx() as db:
            if db.execute('SELECT 1 FROM admins WHERE owner=?',(owner,)).fetchone(): raise Invalid('Não é possível remover uma conta de administrador.')
            if db.execute('DELETE FROM entitlements WHERE owner=?',(owner,)).rowcount==0: raise Invalid('Conta não encontrada.')

    # ---- Ajustes dos comandos dos bots (WhatsApp e assistente): ligar/desligar e texto da resposta, definidos pelo administrador ----
    def bot_settings(self,scope):
        """{comando: {'enabled': bool, 'text': str}} só dos comandos que o administrador mexeu."""
        if scope not in BOT_COMMANDS: raise Invalid('Bot desconhecido.')
        with self.tx() as db: return {r['cmd']:{'enabled':bool(r['enabled']),'text':r['text']} for r in db.execute('SELECT cmd,enabled,text FROM bot_settings WHERE scope=?',(scope,))}

    def bot_set(self,scope,cmd,enabled,text):
        if scope not in BOT_COMMANDS or cmd not in BOT_COMMANDS[scope]: raise Invalid('Comando desconhecido.')
        if type(enabled) is not bool: raise Invalid('Informe se o comando fica ligado.')
        if not isinstance(text,str): raise Invalid('Texto inválido.')
        text=re.sub(r'[\x00-\x08\x0b-\x1f\x7f]','',text.replace('\r\n','\n')).strip()
        if len(text)>1500: raise Invalid('Texto de até 1500 caracteres.')
        with self.tx() as db:
            if enabled and not text: db.execute('DELETE FROM bot_settings WHERE scope=? AND cmd=?',(scope,cmd))  # ligado e sem texto = padrão
            else: db.execute('INSERT INTO bot_settings(scope,cmd,enabled,text) VALUES(?,?,?,?) ON CONFLICT(scope,cmd) DO UPDATE SET enabled=excluded.enabled,text=excluded.text',(scope,cmd,int(enabled),text))

    def bot_reset(self,scope,cmd):
        if scope not in BOT_COMMANDS or cmd not in BOT_COMMANDS[scope]: raise Invalid('Comando desconhecido.')
        with self.tx() as db: db.execute('DELETE FROM bot_settings WHERE scope=? AND cmd=?',(scope,cmd))

    def claim(self,owner,code):
        """Libera a conta de quem apresenta um código válido (e ainda com usos)."""
        if not isinstance(code,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',code): raise Invalid('Código inválido.')
        digest=hashlib.sha256(code.encode()).hexdigest()
        with self.tx() as db:
            row=db.execute('SELECT note,uses FROM claim_codes WHERE hash=?',(digest,)).fetchone()
            if not row or (row['uses'] is not None and row['uses']<=0): raise Invalid('Código inválido ou já usado.')
            if row['uses'] is not None: db.execute('UPDATE claim_codes SET uses=uses-1 WHERE hash=?',(digest,))
            db.execute("INSERT OR IGNORE INTO entitlements(owner,since,note) VALUES(?,strftime('%s','now'),?)",(owner,row['note']))
            if row['note']=='dono': db.execute('INSERT OR IGNORE INTO admins(owner) VALUES(?)',(owner,))  # o código do dono também torna a conta administradora

    def ungrant(self,owner):
        with self.tx() as db: return db.execute('DELETE FROM entitlements WHERE owner=?',(owner,)).rowcount

    def owners(self):
        """Contas conhecidas (id interno, nunca segredos) com o que cada uma tem e se está liberada."""
        with self.tx() as db:
            rows=db.execute("SELECT i.owner AS owner,(SELECT count(*) FROM objects o WHERE o.owner=i.owner AND o.state!='revoked') AS objetos,(SELECT 1 FROM entitlements e WHERE e.owner=i.owner) AS liberada FROM installations i ORDER BY objetos DESC,i.owner").fetchall() if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='installations'").fetchone() else []
            return [{'owner':r['owner'],'objetos':r['objetos'],'liberada':bool(r['liberada'])} for r in rows]

    @contextmanager
    def tx(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        db.row_factory=sqlite3.Row
        try:
            db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA busy_timeout=10000');db.execute('BEGIN IMMEDIATE')
            yield db
            if db.in_transaction: db.commit()
        except Exception:
            if db.in_transaction: db.rollback()
            raise
        finally: db.close()

    def pack(self,owner,key,value):
        return self.cipher.encrypt(json.dumps({'owner':owner,'id':key,'value':value},ensure_ascii=False).encode())

    def unpack(self,owner,key,body):
        value=json.loads(self.cipher.decrypt(body))
        if value.get('owner')!=owner or value.get('id')!=key: raise Invalid('Registro inválido.')
        return value['value']

    def read(self,db,owner,key,kind):
        row=db.execute('SELECT * FROM objects WHERE id=? AND owner=? AND kind=?',(key,owner,kind)).fetchone()
        if not row: raise Invalid('Registro não encontrado.')
        return {**dict(row),'data':self.unpack(owner,key,row['body'])}

    def create(self,owner,kind,data,state='inactive',limit=10):
        key=ident()
        with self.tx() as db:
            count=db.execute("SELECT count(*) FROM objects WHERE owner=? AND kind=? AND state!='revoked'",(owner,kind)).fetchone()[0]
            if count>=limit: raise Invalid('Limite de configurações atingido.')
            total=db.execute("SELECT count(*) FROM objects WHERE kind=? AND state!='revoked'",(kind,)).fetchone()[0]
            if total>=(50 if kind=='connection' else 500): raise Invalid('Capacidade do serviço atingida.')
            db.execute('INSERT INTO objects(id,owner,kind,state,body) VALUES(?,?,?,?,?)',(key,owner,kind,state,self.pack(owner,key,data)))
        return key

    def get(self,owner,key,kind):
        with self.tx() as db: return self.read(db,owner,key,kind)

    def list(self,owner,kind):
        with self.tx() as db:
            return [self.read(db,owner,r['id'],kind) for r in db.execute('SELECT id FROM objects WHERE owner=? AND kind=? ORDER BY id',(owner,kind)).fetchall()]

    def update(self,owner,key,kind,data,state):
        with self.tx() as db:
            self.read(db,owner,key,kind)
            db.execute('UPDATE objects SET body=?,state=?,version=version+1 WHERE id=? AND owner=?',(self.pack(owner,key,data),state,key,owner))
            if kind=='subscription': db.execute("UPDATE runs SET state='cancelled',error='configuration_changed' WHERE owner=? AND subscription=? AND state IN ('pending','preparing','ready')",(owner,key))
            if kind=='watch': db.execute("UPDATE watch_events SET state='cancelled',error='configuration_changed' WHERE owner=? AND watch=? AND state='pending'",(owner,key))

    def revoke(self,owner,key):
        # Commit before network logout: failure to contact bridge must never permit new sends.
        with self.tx() as db:
            row=self.read(db,owner,key,'connection')
            db.execute("UPDATE objects SET state='revoked',version=version+1 WHERE id=? AND owner=?",(key,owner))
            for sub in db.execute("SELECT id FROM objects WHERE owner=? AND kind='subscription'",(owner,)).fetchall():
                item=self.read(db,owner,sub['id'],'subscription')
                if item['data'].get('connection')==key:
                    db.execute("UPDATE objects SET state='inactive',version=version+1 WHERE id=?",(sub['id'],))
                    db.execute("UPDATE runs SET state='cancelled',error='revoked' WHERE owner=? AND subscription=? AND state IN ('pending','preparing','ready')",(owner,sub['id']))
                    db.execute("UPDATE runs SET state='uncertain',error='revoked_during_dispatch' WHERE owner=? AND subscription=? AND state='sending'",(owner,sub['id']))
            for group in db.execute("SELECT id FROM objects WHERE owner=? AND kind='botgroup'",(owner,)).fetchall():
                if self.read(db,owner,group['id'],'botgroup')['data'].get('connection')==key: db.execute("UPDATE objects SET state='inactive',version=version+1 WHERE id=?",(group['id'],))
            for watch in db.execute("SELECT id FROM objects WHERE owner=? AND kind='watch'",(owner,)).fetchall():
                item=self.read(db,owner,watch['id'],'watch')
                if item['data'].get('connection')==key:
                    db.execute("UPDATE objects SET state='inactive',version=version+1 WHERE id=?",(watch['id'],))
                    db.execute("UPDATE watch_events SET state='cancelled',error='revoked' WHERE watch=? AND state='pending'",(watch['id'],))
                    db.execute("UPDATE watch_events SET state='uncertain',error='revoked_during_dispatch' WHERE watch=? AND state='sending'",(watch['id'],))
            return row['data']

    def backup(self,destination):
        # SQLite backup API includes a consistent snapshot, including committed WAL content.
        destination=Path(destination)
        if destination.resolve()==self.path.resolve() or (destination.exists() and destination.samefile(self.path)): raise Invalid('Backup não pode substituir o banco ativo.')
        temporary=Path(str(destination)+'.'+ident()+'.tmp')
        try:
            with closing(sqlite3.connect(self.path)) as src, closing(sqlite3.connect(':memory:')) as dst:
                src.backup(dst);ciphertext=self.cipher.encrypt(dst.serialize())
            # Only ciphertext touches the filesystem, with private permissions from creation.
            with os.fdopen(os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as output:
                output.write(ciphertext);output.flush();os.fsync(output.fileno())
            os.replace(temporary,destination)
        finally: temporary.unlink(missing_ok=True)

    def restore_offline(self,source):
        # Always invalidate ALL sessions/subscriptions; a backup can never resurrect revocation.
        raw=self.cipher.decrypt(Path(source).read_bytes())
        if not raw.startswith(b'SQLite format 3\x00'): raise Invalid('Backup inválido.')
        with closing(sqlite3.connect(':memory:')) as db:
            db.deserialize(raw)
            db.execute("UPDATE objects SET state=CASE WHEN kind='connection' THEN 'revoked' ELSE 'inactive' END,version=version+1")
            db.execute("UPDATE runs SET state=CASE WHEN state='sending' THEN 'uncertain' ELSE 'cancelled' END,error='offline_restore' WHERE state NOT IN ('accepted','simulated','uncertain','failed','expired','cancelled')")
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='watch_events'").fetchone():
                db.execute("UPDATE watch_events SET state=CASE WHEN state='sending' THEN 'uncertain' ELSE 'cancelled' END,error='offline_restore' WHERE state IN ('pending','sending')")
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='installations'").fetchone(): db.execute('UPDATE installations SET revoked=1')
            db.commit()
            with closing(sqlite3.connect(self.path)) as destination: db.backup(destination)
