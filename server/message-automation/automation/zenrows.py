"""Leitura opcional de páginas públicas GuildStats; desligada sem configuração explícita."""
import hashlib
import os
import re
import time
from datetime import timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from .domain import UTC

LIMIT=6_000_000
URL_BACKOFF=6*3600
GLOBAL_BACKOFF=3600


class ZenRowsUnavailable(Exception):
    """Nunca contém URL, chave, corpo remoto ou mensagem da exceção original."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):return None


def target_world(url):
    if not isinstance(url,str) or len(url)>512:raise ZenRowsUnavailable('Destino não permitido.')
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.netloc!='guildstats.eu' or parts.fragment:raise ZenRowsUnavailable('Destino não permitido.')
    query=parse_qs(parts.query,keep_blank_values=True)
    if any(len(v)!=1 for v in query.values()):raise ZenRowsUnavailable('Destino não permitido.')
    if parts.path=='/top-experience' and set(query)=={'world','time'} and query['time'][0] in ('0','7','30'):
        world=query['world'][0]
    elif parts.path=='/world-transfer' and query.get('time') in (['7'],['30']) and len(query)==2 and len(set(query)&{'worldActual','worldFormer'})==1:
        world=query[next(k for k in query if k!='time')][0]
    else:raise ZenRowsUnavailable('Destino não permitido.')
    if not re.fullmatch(r'[A-Za-z]{2,40}',world):raise ZenRowsUnavailable('Destino não permitido.')
    return world


class ZenRowsClient:
    def __init__(self,store,clock,env=None,opener=None,monotonic=None):
        self.store=store;self.clock=clock;self.env=os.environ if env is None else env
        self.opener=opener or build_opener(NoRedirect());self.monotonic=monotonic or time.monotonic

    def _key(self):
        try:
            value=self.env.get('ZENROWS_API_KEY_FILE','');path=Path(value)
            root=Path(__file__).resolve().parents[3]
            if not value or not path.is_absolute():raise ValueError()
            path=path.resolve()
            if path==root or root in path.parents:raise ValueError()
            with path.open('rb') as stream:raw=stream.read(513)
            if len(raw)>512:raise ValueError()
            key=raw.decode('ascii').strip()
            if not key or any(ord(c)<33 or ord(c)>126 for c in key):raise ValueError()
            return key
        except Exception:raise ZenRowsUnavailable('Chave não configurada corretamente.') from None

    def _reserve(self,url):
        try:limit=int(self.env.get('ZENROWS_DAILY_REQUEST_LIMIT','6'))
        except (TypeError,ValueError):limit=0
        if not 0<=limit<=1000:limit=0
        now=self.clock().astimezone(UTC);at=now.timestamp();day=now.date().isoformat();resource=hashlib.sha256(url.encode()).hexdigest()
        with self.store.tx() as db:
            blocked=db.execute('SELECT max(until) FROM zenrows_retry WHERE resource IN (?,?)',('global',resource)).fetchone()[0]
            count=db.execute('SELECT attempts FROM zenrows_budget WHERE day=?',(day,)).fetchone()
            if blocked and blocked>at or (count['attempts'] if count else 0)>=limit:return False
            db.execute('INSERT INTO zenrows_budget(day,attempts) VALUES(?,1) ON CONFLICT(day) DO UPDATE SET attempts=attempts+1',(day,))
            db.execute('INSERT INTO zenrows_retry VALUES(?,?) ON CONFLICT(resource) DO UPDATE SET until=excluded.until',(resource,at+URL_BACKOFF))
            db.execute('DELETE FROM zenrows_budget WHERE day<?',((now.date()-timedelta(days=60)).isoformat(),))
            db.execute('DELETE FROM zenrows_retry WHERE until<?',(at-86400,))
        return True

    def _block(self):
        with self.store.tx() as db:db.execute("INSERT INTO zenrows_retry VALUES('global',?) ON CONFLICT(resource) DO UPDATE SET until=max(until,excluded.until)",(self.clock().timestamp()+GLOBAL_BACKOFF,))

    def fetch(self,url):
        world=target_world(url)
        if self.env.get('ZENROWS_ENABLED')!='1':raise ZenRowsUnavailable('Consulta opcional desligada.')
        allowed=self.env.get('ZENROWS_WORLDS','').strip()
        if allowed and world.casefold() not in {w.strip().casefold() for w in allowed.split(',') if w.strip()}:
            raise ZenRowsUnavailable('Mundo fora do piloto.')
        key=self._key()
        if not self._reserve(url):raise ZenRowsUnavailable('Limite ou intervalo de consultas ativo.')
        request=Request('https://api.zenrows.com/v1/?'+urlencode({'apikey':key,'url':url,'mode':'auto'}),headers={'User-Agent':'TibiaTudo/1.0'})
        deadline=self.monotonic()+25
        try:
            with self.opener.open(request,timeout=20) as response:
                if response.getcode()!=200:raise ZenRowsUnavailable('Consulta remota indisponível.')
                raw=bytearray()
                while True:
                    remaining=deadline-self.monotonic()
                    if remaining<=0:raise TimeoutError()
                    socket=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
                    if socket:socket.settimeout(min(20,remaining))
                    chunk=response.read1(min(16384,LIMIT+1-len(raw)))
                    if self.monotonic()>deadline:raise TimeoutError()
                    if not chunk:break
                    raw.extend(chunk)
                    if len(raw)>LIMIT:raise ValueError()
                return bytes(raw)
        except HTTPError as error:
            try:
                if error.code in (401,402,429):self._block()
            except Exception:pass  # Reservation already persists; never expose the authenticated HTTP exception.
            raise ZenRowsUnavailable('Consulta remota recusada.') from None
        except Exception:raise ZenRowsUnavailable('Consulta remota indisponível.') from None
