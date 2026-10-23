"""Alertas da guild: mortes e marcos de level, detectados no servidor e enviados um por evento ao grupo escolhido.

Só envia. Nada do que os membros escrevem no grupo é lido. Dados: apenas a lista pública da guild e a ficha pública dos personagens.
"""
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import quote
from .domain import UTC, Invalid
from .store import ident
from .transport import NotDispatched

log=logging.getLogger('automation')
GUILD=re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")
MIN_INTERVAL=15        # varredura a cada 20 s (3 por tick de 1 min): level up e mortes
ROSTER_TTL=900         # a pertença à guild muda pouco: renova a cada 15 min
MAX_FETCH=30           # fichas consultadas por varredura, em rodízio entre os membros online
DEFAULT_PER_MINUTE=3   # ritmo padrão; o dono escolhe de 1 a 120 por minuto
EVENT_TTL=3*3600       # aviso que não coube no limite por hora e já ficou velho some em vez de chegar atrasado
EMOJI={'knight':'🛡️','paladin':'🏹','druid':'❄️','sorcerer':'🔥','monk':'👊'}

def validate_watch(data):
    """Normaliza a configuração do alerta; qualquer valor fora do contrato é recusado."""
    guild=data.get('guild')
    if not isinstance(guild,str) or not GUILD.fullmatch(' '.join(guild.split())): raise Invalid('Informe o nome da guild.')
    out={'guild':' '.join(guild.split())}
    for key,low,high,default in (('milestone',1,1000,1),('hourlyCap',0,1000,0),('perMinute',1,120,DEFAULT_PER_MINUTE)):
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

    def run(self,seconds=45,every=20):
        """Varreduras a cada `every` s durante `seconds` s: o timer do sistema chama uma vez por minuto, então cabem 3 varreduras por chamada."""
        start=time.monotonic()
        while True:
            began=time.monotonic();self.tick()
            following=began+every
            if following-start>seconds: break
            time.sleep(max(0,following-time.monotonic()))

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

    def roster(self,data,stamp,meta,known):
        """Quem é da guild e em que mundo. A lista da guild na TibiaData traz o level atrasado, então só serve para a pertença (renovada a cada 15 min)."""
        if meta and meta['world'] and known and stamp-meta['roster_at']<ROSTER_TTL: return meta['world'],None
        guild=(self.fetch('/guild/'+quote(data['guild'])) or {}).get('guild') or {}
        members=[(m['name'],m.get('vocation')) for m in guild.get('members') or [] if isinstance(m,dict) and isinstance(m.get('name'),str) and m['name']]
        world=guild.get('world')
        if not members or not isinstance(world,str) or not world: raise Invalid('Guild sem membros.')  # falha fechada: lista vazia nunca vira "todos saíram"
        return world,members

    def scan(self,key,owner,data,stamp):
        with self.store.tx() as db:
            meta=db.execute('SELECT * FROM watch_meta WHERE watch=?',(key,)).fetchone()
            if meta and stamp-meta['last_run']<MIN_INTERVAL: return
            db.execute('INSERT INTO watch_meta(watch,last_run,since,primed) VALUES(?,?,?,0) ON CONFLICT(watch) DO UPDATE SET last_run=excluded.last_run',(key,stamp,stamp))
            known={r['name']:dict(r) for r in db.execute('SELECT * FROM watch_members WHERE watch=?',(key,))}
        primed=bool(meta and meta['primed']);since=meta['since'] if meta else stamp
        world,roster=self.roster(data,stamp,meta,known)
        # Level up vem da lista online do mundo, que é atual (a mesma fonte do UP Level do app); quem não está online não muda de level.
        listed=(self.fetch('/world/'+quote(world)) or {}).get('world',{}).get('online_players')
        if not isinstance(listed,list) or not listed: raise Invalid('Lista online indisponível.')
        online={p['name']:p for p in listed if isinstance(p,dict) and isinstance(p.get('name'),str) and type(p.get('level')) is int and p['level']>0}
        names={n for n,_ in roster} if roster is not None else set(known)
        vocations=dict(roster or ())
        def vocation(name): return (online.get(name) or {}).get('vocation') or vocations.get(name) or (known.get(name) or {}).get('vocation')
        events=[];ms=data['milestone'];levels={}
        for name in sorted(names&set(online)):
            level=online[name]['level'];prev=(known.get(name) or {}).get('level',0)
            if primed and prev>0 and data['ups'] and level//ms>prev//ms:
                events.append((f"up:{name}:{level//ms*ms}",up_text({'name':name,'level':level,'vocation':vocation(name)})))
            levels[name]=level
        checked=[]
        if data['deaths'] and primed:
            # a morte aparece na ficha quando o personagem ainda está online ou acabou de sair; rodízio pelos que esperam há mais tempo
            candidates=sorted((n for n in names if n in online or (known.get(n) or {}).get('online')),key=lambda n:((known.get(n) or {}).get('checked',0),n))
            checked=candidates[:MAX_FETCH]
            def sheet(name):
                try: return name,(self.fetch('/character/'+quote(name)) or {}).get('character',{}).get('deaths')
                except Exception: return name,None
            with ThreadPoolExecutor(max_workers=6) as pool: results=list(pool.map(sheet,checked))
            for name,deaths in results:
                for death in deaths if isinstance(deaths,list) else []:
                    try:
                        at=datetime.fromisoformat(str(death['time']).replace('Z','+00:00')).timestamp()
                        if type(death.get('level')) is not int or at<since or stamp-at>EVENT_TTL: continue
                        events.append((f"death:{name}:{death['time']}",death_text({'name':name,'vocation':vocation(name)},death)))
                    except (KeyError,ValueError,TypeError): continue
        with self.store.tx() as db:
            if roster is not None:
                for gone in set(known)-names: db.execute('DELETE FROM watch_members WHERE watch=? AND name=?',(key,gone))
                for name,voc in roster: db.execute('INSERT INTO watch_members(watch,name,level,online,vocation) VALUES(?,?,0,0,?) ON CONFLICT(watch,name) DO UPDATE SET vocation=excluded.vocation',(key,name,voc))
                db.execute('UPDATE watch_meta SET world=?,roster_at=? WHERE watch=?',(world,stamp,key))
            for name in names:
                if name in levels: db.execute('UPDATE watch_members SET level=?,online=1,vocation=COALESCE(?,vocation) WHERE watch=? AND name=?',(levels[name],online[name].get('vocation'),key,name))
                else: db.execute('UPDATE watch_members SET online=0 WHERE watch=? AND name=?',(key,name))
            for name in checked: db.execute('UPDATE watch_members SET checked=? WHERE watch=? AND name=?',(stamp,key,name))
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
            last_minute=db.execute("SELECT count(*) FROM watch_events WHERE watch=? AND sent_at>?",(key,stamp-60)).fetchone()[0]
            per_minute=data.get('perMinute',DEFAULT_PER_MINUTE)  # alertas criados antes do campo existir seguem no ritmo padrão
            room=per_minute-last_minute  # o ritmo vale por janela de 60 s, mesmo com várias varreduras por minuto
            if data['hourlyCap']: room=min(room,data['hourlyCap']-used)  # hourlyCap 0 = sem teto por hora
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
