"""Comandos no grupo (!help, !duelo, !evolucao, !precocoin).

Só linhas que começam com "!" chegam aqui (a ponte descarta o resto). Cada comando é respondido uma vez, com limite por membro; o texto
recebido nunca é gravado: guardamos só o id da mensagem (para não responder duas vezes) e quando cada membro usou o bot por último.
"""
import logging
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from .botcmds import Bot, WORLD, WARM_EVERY
from .domain import UTC, Invalid, reference_day
from .store import ident

log=logging.getLogger('automation')
MAX_PER_TICK=5          # comandos tratados por varredura; o excesso (enxurrada) é ignorado
HISTORY_DAYS=60
SEEN_TTL=3600

def validate_botgroup(data):
    """Normaliza a configuração do grupo; valor fora do contrato é recusado."""
    world=data.get('world')
    if not isinstance(world,str) or not WORLD.fullmatch(world.strip()): raise Invalid('Informe o mundo padrão do grupo.')
    cooldown=data.get('cooldown',30)
    if type(cooldown) is not int or not 5<=cooldown<=600: raise Invalid('Intervalo por membro de 5 a 600 segundos.')
    return {'world':world.strip().capitalize(),'cooldown':cooldown}

class Commander:
    def __init__(self,store,transport,bot=None,clock=None):
        self.store=store;self.transport=transport;self.clock=clock or (lambda:datetime.now(UTC))
        self.bot=bot or Bot(history=self.history,track=self.track,daily=self.daily);self.warmed={}

    # ---- histórico diário de XP (instantâneo do ranking de "ontem" do mundo) ----
    def track(self,world):
        with self.store.tx() as db: db.execute("INSERT OR IGNORE INTO rank_meta(world,last_day) VALUES(?,'')",(world.capitalize(),))

    def history(self,world,name):
        with self.store.tx() as db:
            return [(r['day'],r['xp']) for r in db.execute('SELECT day,xp FROM rank_history WHERE world=? AND name=? COLLATE NOCASE ORDER BY day',(world.capitalize(),name))]

    def daily(self,world,name):
        """[(dia, level, xp)] gravados pelo próprio servidor para o personagem."""
        with self.store.tx() as db:
            return [(r['day'],r['level'],r['xp']) for r in db.execute('SELECT day,level,xp FROM rank_history WHERE world=? AND name=? COLLATE NOCASE ORDER BY day DESC',(world.capitalize(),name))]

    def snapshot(self,now):
        local=now.astimezone(ZoneInfo('Europe/Berlin'))
        if local.hour<12: return  # o ranking de "ontem" do GuildStats só vira depois do server save; espera para não gravar o dia errado
        today=reference_day(now);yesterday=(date.fromisoformat(today)-timedelta(days=1)).isoformat()
        with self.store.tx() as db: worlds=[r['world'] for r in db.execute("SELECT world FROM rank_meta WHERE last_day!=?",(today,))]
        for world in worlds:
            rows=self.bot.ranking(world,0)
            if not rows: continue
            with self.store.tx() as db:
                db.executemany('INSERT OR REPLACE INTO rank_history(world,day,name,level,xp) VALUES(?,?,?,?,?)',[(world,yesterday,name,level,xp) for name,level,xp,_ in rows])
                db.execute('UPDATE rank_meta SET last_day=? WHERE world=?',(today,world))
                db.execute('DELETE FROM rank_history WHERE day<?',((date.fromisoformat(today)-timedelta(days=HISTORY_DAYS)).isoformat(),))

    # ---- leitura e resposta ----
    def groups(self):
        with self.store.tx() as db:
            rows=db.execute("SELECT id,owner,body FROM objects WHERE kind='botgroup' AND state='active' ORDER BY id").fetchall()
            return [(r['id'],r['owner'],self.store.unpack(r['owner'],r['id'],r['body'])) for r in rows]

    def maintain(self,now=None):
        """Tarefas de fundo, no ritmo das varreduras: registrar mundos, manter o ranking quente, gravar o histórico do dia e limpar ids antigos."""
        now=now or self.clock()
        with self.store.tx() as db: db.execute('DELETE FROM command_seen WHERE at<?',(now.timestamp()-SEEN_TTL,))
        for key,owner,data in self.groups():
            self.track(data['world'])
            last=self.warmed.get(data['world'])
            if last is None or time.monotonic()-last>=WARM_EVERY:
                self.warmed[data['world']]=time.monotonic()
                try: self.bot.warm(data['world'])
                except Exception as error: log.warning('warm_failed=%s',type(error).__name__)
        try: self.snapshot(now)
        except Exception as error: log.warning('snapshot_failed=%s',type(error).__name__)

    def tick(self,now=None):
        """Lê e responde os comandos recebidos (chamado a cada poucos segundos)."""
        now=now or self.clock();stamp=now.timestamp()
        groups=self.groups()
        for connection in sorted({data['connection'] for _,_,data in groups}):
            try: items=self.transport.inbox(connection) or []
            except Exception as error:
                log.warning('inbox failed=%s',type(error).__name__);continue
            handled=0
            for item in items:
                if handled>=MAX_PER_TICK: break
                for key,owner,data in groups:
                    if data['connection']!=connection: continue
                    try:
                        if self.process(key,owner,data,item,stamp,now): handled+=1
                    except Exception as error: log.warning('botgroup=%s command_failed=%s',key,type(error).__name__)

    def process(self,key,owner,data,item,stamp,now):
        if not isinstance(item,dict) or any(not isinstance(item.get(k),str) or not item[k] for k in ('id','group','sender','text')): return False
        with self.store.tx() as db:
            conn=self.store.read(db,owner,data['connection'],'connection');dest=self.store.read(db,owner,data['destination'],'destination')
            if conn['state']!='active' or dest['state']!='active' or dest['data']['connection']!=conn['id'] or dest['data']['group']!=item['group']: return False
            if self.transport.real and not conn['data'].get('riskAccepted'): return False
            if db.execute('INSERT OR IGNORE INTO command_seen(botgroup,msg,at) VALUES(?,?,?)',(key,item['id'],stamp)).rowcount==0: return False
            last=db.execute('SELECT last FROM command_use WHERE botgroup=? AND sender=?',(key,item['sender'])).fetchone()
            if last and stamp-last['last']<data.get('cooldown',30): return False  # dentro do intervalo: silêncio, sem responder "espere"
        if not self.bot.known(item['text']): return False
        try: self.transport.typing(conn['id'],dest['data']['group'],'composing')  # "digitando…" enquanto busca os dados
        except Exception: pass
        reply=self.bot.handle(item['text'],data['world'],now.astimezone(ZoneInfo('America/Sao_Paulo')).date())
        if reply is None: return False
        with self.store.tx() as db: db.execute('INSERT INTO command_use(botgroup,sender,last) VALUES(?,?,?) ON CONFLICT(botgroup,sender) DO UPDATE SET last=excluded.last',(key,item['sender'],stamp))
        try: self.transport.send(conn['id'],dest['data']['group'],reply[:3500],ident())
        except Exception as error: log.warning('botgroup=%s reply_failed=%s',key,type(error).__name__)
        return True
