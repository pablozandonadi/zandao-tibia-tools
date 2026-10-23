"""Execuções diárias persistentes, com claims e tentativas ambíguas sem repetição."""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from mensagem_automatica_report import generate
from .domain import UTC, Invalid, SourceUnavailable, MAX_AGE, local_instant, reference_day, fresh
from .store import ident
from .transport import NotDispatched

log=logging.getLogger('automation')

class Worker:
    def __init__(self,store,transport,generator=generate,clock=None):
        self.store=store;self.transport=transport;self.generate=generator;self.clock=clock or (lambda:datetime.now(UTC))

    def tick(self,now=None):
        moment=(lambda:now) if now is not None else self.clock
        now=moment();stamp=now.timestamp();store=self.store
        with store.tx() as db:
            db.execute("UPDATE runs SET state='uncertain',error='dispatch_interrupted' WHERE state='sending' AND lease<=?",(stamp,))
            db.execute("UPDATE runs SET state='pending',lease=NULL WHERE state='preparing' AND lease<=?",(stamp,))
            subs=[s for s in db.execute("SELECT * FROM objects WHERE kind='subscription' AND state='active' ORDER BY id").fetchall() if store.entitled_in(db,s['owner'])]
            for row in subs:
                owner=row['owner'];data=store.unpack(owner,row['id'],row['body']);c=data['config']
                for offset in (1,0):
                    day=(now.astimezone(ZoneInfo(c['timezone'])).date()-timedelta(days=offset)).isoformat()
                    generation=local_instant(day,c['generateAt'],c['timezone']);send=local_instant(day,c['sendAt'],c['timezone'])
                    # Nonexistent DST occurrence is audited under its nominal fold=0 date,
                    # never under noon, which could reserve tomorrow's valid delivery key.
                    nominal=datetime.fromisoformat(day+'T'+c['generateAt']).replace(tzinfo=ZoneInfo(c['timezone']),fold=0).astimezone(UTC)
                    ref=reference_day(generation or nominal)
                    if generation and generation>now: continue
                    state='pending' if generation and send else 'expired';error=None if state=='pending' else 'dst_nonexistent'
                    if generation and stamp-generation.timestamp()>MAX_AGE: state='expired';error='generation_late'
                    # Rotina editada: execução de versão antiga que nunca despachou cede a vaga do dia; enviada ou incerta nunca.
                    db.execute("DELETE FROM runs WHERE owner=? AND subscription=? AND destination=? AND reference=? AND version<? AND state IN ('failed','expired','cancelled')",(owner,row['id'],data['destination'],ref,row['version']))
                    db.execute('INSERT OR IGNORE INTO runs(id,owner,subscription,destination,reference,generation,send,state,error,version) VALUES(?,?,?,?,?,?,?,?,?,?)',
                               (ident(),owner,row['id'],data['destination'],ref,generation.timestamp() if generation else None,send.timestamp() if send else None,state,error,row['version']))
            # Per-owner round robin prevents a tenant's queue from occupying all 50 slots.
            todo=db.execute("SELECT id FROM (SELECT id,generation,row_number() OVER(PARTITION BY owner ORDER BY generation,id) AS n FROM runs WHERE state='pending' AND generation<=? AND retry_after<=?) ORDER BY n,generation LIMIT 50",(stamp,stamp)).fetchall()
        for row in todo: self.prepare(row['id'],moment(),moment)
        with store.tx() as db:
            ready=db.execute("SELECT id FROM runs WHERE state='ready' AND send<=? ORDER BY send LIMIT 50",(moment().timestamp(),)).fetchall()
        for row in ready: self.dispatch(row['id'],moment())

    def context(self,db,run):
        sub=self.store.read(db,run['owner'],run['subscription'],'subscription')
        if sub['state']!='active' or sub['version']!=run['version']: raise Invalid('Configuração alterada.')
        data=sub['data'];dest=self.store.read(db,run['owner'],run['destination'],'destination')
        conn=self.store.read(db,run['owner'],data['connection'],'connection')
        if conn['state']!='active' or dest['state']!='active' or dest['data']['connection']!=conn['id']: raise Invalid('Conexão indisponível.')
        if self.transport.real and not conn['data'].get('riskAccepted'): raise Invalid('Risco não aceito.')
        return data['config'],conn,dest

    def prepare(self,key,now,clock=None):
        store=self.store
        with store.tx() as db:
            run=db.execute("SELECT * FROM runs WHERE id=? AND state='pending'",(key,)).fetchone()
            if not run: return
            if run['retry_after']>now.timestamp(): return
            try:
                c,_,_=self.context(db,run)
                if now.timestamp()-run['generation']>MAX_AGE: raise Invalid('Geração expirada.')
                if reference_day(now)!=run['reference']: raise Invalid('Server save alterou a referência.')
                if run['generation_attempts']>=3: raise Invalid('Limite de tentativas atingido.')
            except Invalid:
                db.execute("UPDATE runs SET state='expired',error='generation_invalid' WHERE id=?",(key,));return
            claim=ident()
            db.execute("UPDATE runs SET state='preparing',attempt=?,lease=?,generation_attempts=generation_attempts+1 WHERE id=?",(claim,now.timestamp()+300,key))
        try: snapshot=self.generate(c,now)
        except Exception as error:
            failed_at=clock() if clock else now
            with store.tx() as db:
                current=db.execute('SELECT * FROM runs WHERE id=?',(key,)).fetchone()
                retry=failed_at.timestamp()+60*current['generation_attempts']
                transient=isinstance(error,(SourceUnavailable,OSError,TimeoutError,ConnectionError))
                can_retry=transient and current['generation_attempts']<3 and retry<=current['generation']+MAX_AGE and reference_day(failed_at)==current['reference']
                db.execute("UPDATE runs SET state=?,error=?,retry_after=?,lease=NULL WHERE id=? AND attempt=? AND state='preparing'",('pending' if can_retry else 'failed','source_retry' if can_retry else 'generation_failed',retry,key,claim))
            return
        with store.tx() as db:
            current=db.execute('SELECT * FROM runs WHERE id=?',(key,)).fetchone()
            if current['state']!='preparing' or current['attempt']!=claim: return
            try:
                self.context(db,current)
                completed=clock() if clock else now
                if reference_day(completed)!=current['reference'] or completed.timestamp()-current['generation']>MAX_AGE: raise Invalid('Referência expirada.')
                fresh(snapshot,completed,current['reference'])
            except Invalid:
                db.execute("UPDATE runs SET state='expired',error='generation_reference_or_config_changed' WHERE id=?",(key,));return
            db.execute("UPDATE runs SET state='ready',snapshot=?,lease=NULL WHERE id=?",(store.pack(current['owner'],key,snapshot),key))

    def dispatch(self,key,now):
        store=self.store
        with store.tx() as db:
            run=db.execute("SELECT * FROM runs WHERE id=? AND state='ready'",(key,)).fetchone()
            if not run: return
            try:
                self.context(db,run)
                if now.timestamp()-run['send']>MAX_AGE: raise Invalid('Envio atrasado.')
                if reference_day(now)!=run['reference']: raise Invalid('Server save alterou a referência.')
                snapshot=store.unpack(run['owner'],key,run['snapshot']);fresh(snapshot,now,run['reference'])
            except Invalid:
                db.execute("UPDATE runs SET state='expired',error='send_invalid' WHERE id=?",(key,));return
            attempt=ident()
            db.execute("UPDATE runs SET state='sending',attempt=?,lease=? WHERE id=?",(attempt,now.timestamp()+60,key))
        # Sending is committed first. A crash during the call can only become uncertain.
        with store.tx() as db:
            run=db.execute('SELECT * FROM runs WHERE id=?',(key,)).fetchone()
            if run['state']!='sending' or run['attempt']!=attempt:return
            try: _,conn,dest=self.context(db,run)
            except Invalid:
                db.execute("UPDATE runs SET state='cancelled',error='revoked_before_dispatch' WHERE id=?",(key,));return
        # No database lock during network I/O. The bridge serializes session revoke/send.
        # A revocation racing an already claimed send is uncertain, not a promised recall.
        receipt=None
        try:
            receipt=self.transport.send(conn['id'],dest['data']['group'],snapshot['text'],attempt)
            state='accepted' if self.transport.real else 'simulated';error=None
        except NotDispatched: state='failed';error='transport_not_started'
        except Exception: state='uncertain';error='transport_uncertain'
        with store.tx() as db:
            db.execute("UPDATE runs SET state=?,error=?,lease=NULL,receipt=? WHERE id=? AND state='sending' AND attempt=?",(state,error,store.pack(run['owner'],key,receipt) if receipt else None,key,attempt))
        log.info('run=%s state=%s',key,state)
