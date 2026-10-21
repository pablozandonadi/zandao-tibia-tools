"""Identidade da instalação: somente hashes de segredos aleatórios de 256 bits."""
import hashlib
import re
import time
from .domain import Invalid
from .store import ident

SECRET=re.compile(r'^[a-f0-9]{64}$')
def digest(value):
    if not isinstance(value,str) or not SECRET.fullmatch(value): raise Invalid('Credencial inválida.')
    return hashlib.sha256(value.encode('ascii')).hexdigest()

class Verifier:
    def __init__(self,store,capacity=500,clock=time.time):
        self.store=store;self.capacity=capacity;self.clock=clock
        with store.tx() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS installations(owner TEXT PRIMARY KEY,credential TEXT UNIQUE NOT NULL,recovery TEXT UNIQUE NOT NULL,operation TEXT,revoked INTEGER NOT NULL DEFAULT 0,rotations INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS retired_credentials(hash TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS enrollment_rates(scope TEXT PRIMARY KEY,window INTEGER NOT NULL,count INTEGER NOT NULL);''')
    def limit(self,ip):
        now=int(self.clock());window=now//60
        # Commit counters even for requests later rejected by registration/recovery.
        with self.store.tx() as db:
            db.execute('DELETE FROM enrollment_rates WHERE window<?',(window-1,))
            scopes=[('global',60),('ip:'+hashlib.sha256(str(ip).encode()).hexdigest(),10)]
            counts=[]
            for scope,limit in scopes:
                row=db.execute('SELECT count,window FROM enrollment_rates WHERE scope=?',(scope,)).fetchone()
                count=row['count'] if row and row['window']==window else 0
                if count>=limit: return False
                counts.append((scope,count))
            for scope,count in counts:
                db.execute('INSERT INTO enrollment_rates VALUES(?,?,?) ON CONFLICT(scope) DO UPDATE SET window=excluded.window,count=excluded.count',(scope,window,count+1))
        return True
    def verify(self,token):
        value=digest(token)
        with self.store.tx() as db:
            row=db.execute('SELECT owner FROM installations WHERE credential=? AND revoked=0',(value,)).fetchone()
        if not row: raise Invalid('Acesso indisponível. Use seu código de recuperação.')
        return row['owner']
    def register(self,credential,recovery):
        key,code=digest(credential),digest(recovery)
        if key==code: raise Invalid('Credenciais independentes necessárias.')
        with self.store.tx() as db:
            row=db.execute('SELECT * FROM installations WHERE credential=?',(key,)).fetchone()
            if row and not row['revoked'] and row['recovery']==code: return {'ok':True}
            if row or db.execute('SELECT 1 FROM retired_credentials WHERE hash=?',(key,)).fetchone() or db.execute('SELECT 1 FROM installations WHERE recovery=?',(code,)).fetchone(): raise Invalid('Registro indisponível.')
            if db.execute('SELECT count(*) FROM installations').fetchone()[0]>=self.capacity: raise Invalid('Capacidade de instalações atingida.')
            db.execute('INSERT INTO installations(owner,credential,recovery) VALUES(?,?,?)',(ident(),key,code))
        return {'ok':True}
    def recover(self,recovery,credential,new_recovery,operation):
        old,key,code,op=map(digest,(recovery,credential,new_recovery,operation))
        if len({old,key,code})!=3: raise Invalid('Credenciais independentes necessárias.')
        with self.store.tx() as db:
            current=db.execute('SELECT * FROM installations WHERE credential=? AND recovery=? AND operation=? AND revoked=0',(key,code,op)).fetchone()
            if current: return {'ok':True}
            row=db.execute('SELECT * FROM installations WHERE recovery=? AND revoked=0',(old,)).fetchone()
            if not row or row['rotations']>=100: raise Invalid('Recuperação indisponível.')
            if db.execute('SELECT 1 FROM installations WHERE credential=? OR recovery=?',(key,code)).fetchone() or db.execute('SELECT 1 FROM retired_credentials WHERE hash=?',(key,)).fetchone(): raise Invalid('Recuperação indisponível.')
            db.execute('INSERT INTO retired_credentials VALUES(?)',(row['credential'],))
            db.execute('UPDATE installations SET credential=?,recovery=?,operation=?,rotations=rotations+1 WHERE owner=?',(key,code,op,row['owner']))
        return {'ok':True}
