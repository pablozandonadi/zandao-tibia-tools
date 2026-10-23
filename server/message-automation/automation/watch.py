"""Alertas da guild: mortes e marcos de level, detectados no servidor e enviados um por evento ao grupo escolhido.

Só envia. Nada do que os membros escrevem no grupo é lido. Dados: apenas a lista pública da guild e a ficha pública dos personagens.
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote
from .domain import UTC, Invalid
from .store import ident
from .transport import NotDispatched

log=logging.getLogger('automation')
GUILD=re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")
MIN_INTERVAL=120       # a TibiaData atualiza a guild a cada alguns minutos; consultar mais seguido só gasta cota
MAX_FETCH=30           # fichas consultadas por varredura
SEND_PER_TICK=3        # ritmo máximo: 3 mensagens por minuto, mesmo com fila grande
EVENT_TTL=3*3600       # aviso que não coube no limite por hora e já ficou velho some em vez de chegar atrasado
EMOJI={'knight':'🛡️','paladin':'🏹','druid':'❄️','sorcerer':'🔥','monk':'👊'}

def validate_watch(data):
    """Normaliza a configuração do alerta; qualquer valor fora do contrato é recusado."""
    guild=data.get('guild')
    if not isinstance(guild,str) or not GUILD.fullmatch(' '.join(guild.split())): raise Invalid('Informe o nome da guild.')
    out={'guild':' '.join(guild.split())}
    for key,low,high,default in (('milestone',1,1000,1),('hourlyCap',1,60,20)):
        value=data.get(key,default)
        if type(value) is not int or not low<=value<=high: raise Invalid('Valor fora do limite.')
        out[key]=value
    for key in ('deaths','ups'):
        value=data.get(key,True)
        if type(value) is not bool: raise Invalid('Opção inválida.')
        out[key]=value
    if not (out['deaths'] or out['ups']): raise Invalid('Escolha mortes, level ups ou os dois.')
    return out

def tibia_json(path):
    import tibia_info
    return tibia_info._get_json(tibia_info.TIBIADATA+path)

def clean(value,limit=60):
    """Nomes vêm do jogo; sem marcadores de formatação do WhatsApp nem quebras de linha."""
    return re.sub(r'[*_~`\x00-\x1f]','',str(value))[:limit].strip()

def emoji(vocation): return EMOJI.get(next((k for k in EMOJI if k in str(vocation).casefold()),''),'')

def death_text(member,death):
    killers=[k for k in death.get('killers') or [] if isinstance(k,dict) and isinstance(k.get('name'),str)]
    by=', '.join(clean(k['name'])+(' (jogador)' if k.get('player') else '') for k in killers[:3]) or 'causa desconhecida'
    return f"💀 {emoji(member.get('vocation'))} *{clean(member['name'])}* morreu no level {pt(death['level'])} — {by}".replace('  ',' ')

def up_text(member):
    return f"🔺 {emoji(member.get('vocation'))} *{clean(member['name'])}* subiu para o level *{pt(member['level'])}*! 🎉".replace('  ',' ')

def pt(number): return f'{number:,}'.replace(',','.')

class Watcher:
    def __init__(self,store,transport,fetch=None,clock=None):
        self.store=store;self.transport=transport;self.fetch=fetch or tibia_json;self.clock=clock or (lambda:datetime.now(UTC))

    def tick(self,now=None):
        now=now or self.clock();stamp=now.timestamp()
        with self.store.tx() as db:
            rows=db.execute("SELECT id,owner,body FROM objects WHERE kind='watch' AND state='active' ORDER BY id").fetchall()
            watches=[(r['id'],r['owner'],self.store.unpack(r['owner'],r['id'],r['body'])) for r in rows]
        for key,owner,data in watches:
            try: self.scan(key,owner,data,stamp)
            except Exception as error: log.warning('watch=%s scan_failed=%s',key,type(error).__name__)
            try: self.dispatch(key,owner,data,stamp)
            except Exception as error: log.warning('watch=%s dispatch_failed=%s',key,type(error).__name__)

    def scan(self,key,owner,data,stamp):
        with self.store.tx() as db:
            meta=db.execute('SELECT * FROM watch_meta WHERE watch=?',(key,)).fetchone()
            if meta and stamp-meta['last_run']<MIN_INTERVAL: return
            db.execute('INSERT INTO watch_meta(watch,last_run,since,primed) VALUES(?,?,?,0) ON CONFLICT(watch) DO UPDATE SET last_run=excluded.last_run',(key,stamp,stamp))
            known={r['name']:dict(r) for r in db.execute('SELECT * FROM watch_members WHERE watch=?',(key,))}
        primed=bool(meta and meta['primed']);since=meta['since'] if meta else stamp
        guild=(self.fetch('/guild/'+quote(data['guild'])) or {}).get('guild') or {}
        members=[m for m in guild.get('members') or [] if isinstance(m,dict) and isinstance(m.get('name'),str) and type(m.get('level')) is int and m['level']>0]
        if not members: raise Invalid('Guild sem membros.')  # falha fechada: lista vazia nunca vira "todos saíram"
        events=[];ms=data['milestone']
        for m in members:
            prev=known.get(m['name'])
            if primed and prev is not None and data['ups'] and m['level']//ms>prev['level']//ms:
                events.append((f"up:{m['name']}:{m['level']//ms*ms}",up_text(m)))
        if data['deaths'] and primed:
            # a morte aparece na ficha quando o personagem ainda está online ou acabou de sair
            check=[m for m in members if m.get('status')=='online' or (known.get(m['name']) or {}).get('online')][:MAX_FETCH]
            def sheet(m):
                try: return m,(self.fetch('/character/'+quote(m['name'])) or {}).get('character',{}).get('deaths')
                except Exception: return m,None
            with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(sheet,check))
            for m,deaths in results:
                for death in deaths if isinstance(deaths,list) else []:
                    try:
                        at=datetime.fromisoformat(str(death['time']).replace('Z','+00:00')).timestamp()
                        if type(death.get('level')) is not int or at<since or stamp-at>EVENT_TTL: continue
                        events.append((f"death:{m['name']}:{death['time']}",death_text(m,death)))
                    except (KeyError,ValueError,TypeError): continue
        with self.store.tx() as db:
            for m in members:
                db.execute('INSERT INTO watch_members(watch,name,level,online) VALUES(?,?,?,?) ON CONFLICT(watch,name) DO UPDATE SET level=excluded.level,online=excluded.online',(key,m['name'],m['level'],1 if m.get('status')=='online' else 0))
            for event_key,text in events:
                event=ident()
                db.execute("INSERT OR IGNORE INTO watch_events(id,owner,watch,key,text,state,created) VALUES(?,?,?,?,?,'pending',?)",(event,owner,key,event_key,self.store.pack(owner,event,text),stamp))
            db.execute('UPDATE watch_meta SET primed=1 WHERE watch=?',(key,))

    def context(self,db,owner,data):
        conn=self.store.read(db,owner,data['connection'],'connection');dest=self.store.read(db,owner,data['destination'],'destination')
        if conn['state']!='active' or dest['state']!='active' or dest['data']['connection']!=conn['id']: raise Invalid('Conexão indisponível.')
        if self.transport.real and not conn['data'].get('riskAccepted'): raise Invalid('Risco não aceito.')
        return conn,dest

    def dispatch(self,key,owner,data,stamp):
        with self.store.tx() as db:
            db.execute("UPDATE watch_events SET state='expired' WHERE watch=? AND state='pending' AND created<?",(key,stamp-EVENT_TTL))
            db.execute("UPDATE watch_events SET state='uncertain',error='dispatch_interrupted' WHERE watch=? AND state='sending' AND lease<=?",(key,stamp))
            used=db.execute("SELECT count(*) FROM watch_events WHERE watch=? AND sent_at>=?",(key,stamp-3600)).fetchone()[0]
            room=min(SEND_PER_TICK,data['hourlyCap']-used)
            if room<=0: return
            pending=db.execute("SELECT id FROM watch_events WHERE watch=? AND state='pending' ORDER BY created,id LIMIT ?",(key,room)).fetchall()
        for row in pending:
            attempt=ident()
            with self.store.tx() as db:
                event=db.execute("SELECT * FROM watch_events WHERE id=? AND state='pending'",(row['id'],)).fetchone()
                if not event: continue
                try: conn,dest=self.context(db,owner,data)
                except Invalid: return  # conexão pausada ou revogada: o aviso espera (ou expira)
                text=self.store.unpack(owner,event['id'],event['text'])
                db.execute("UPDATE watch_events SET state='sending',attempt=?,lease=?,sent_at=? WHERE id=?",(attempt,stamp+60,stamp,event['id']))
            # Registrado antes do envio: uma queda no meio só pode virar "incerto", nunca repetição cega.
            try: self.transport.send(conn['id'],dest['data']['group'],text,attempt);state='accepted' if self.transport.real else 'simulated';error=None
            except NotDispatched: state='failed';error='transport_not_started'
            except Exception: state='uncertain';error='transport_uncertain'
            with self.store.tx() as db:
                db.execute("UPDATE watch_events SET state=?,error=?,lease=NULL WHERE id=? AND state='sending' AND attempt=?",(state,error,event['id'],attempt))
                if state=='failed': db.execute('UPDATE watch_events SET sent_at=NULL WHERE id=?',(event['id'],))
            log.info('watch=%s event=%s state=%s',key,event['id'],state)
