"""CLI: demo sintética, worker, backup e restauração explicitamente offline."""
import argparse
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime,timedelta
from cryptography.fernet import Fernet
from .domain import UTC,validate,reference_day
from .store import Store
from .transport import FakeTransport
from .worker import Worker
from .watch import Watcher
from .commands import Commander
from .runtime import components

def demo():
    with tempfile.TemporaryDirectory() as folder:
        store=Store(Path(folder)/'demo.sqlite',Fernet.generate_key(),open_access=True);transport=FakeTransport()
        now=datetime(2026,10,21,12,tzinfo=UTC)
        config=validate({'personagem':'Pirata Teste','mundo':'Antica','blocks':{'mundo':True,'rashid':True},'generateAt':'12:00','sendAt':'12:10','timezone':'UTC'},True)
        connection=store.create('synthetic-owner','connection',{'riskAccepted':True},'active');transport.pair(connection)
        destination=store.create('synthetic-owner','destination',{'connection':connection,'group':'fake-group'},'active')
        store.create('synthetic-owner','subscription',{'config':config,'connection':connection,'destination':destination},'active')
        worker=Worker(store,transport);worker.tick(now)
        with store.tx() as db: prepared=db.execute("SELECT state FROM runs WHERE state='ready'").fetchone()
        if not prepared: raise RuntimeError('Demo não gerou snapshot.')
        worker.tick(now+timedelta(minutes=10))
        with store.tx() as db: sent=db.execute("SELECT state FROM runs WHERE state='simulated'").fetchone()
        if not sent or len(transport.sent)!=1: raise RuntimeError('Demo não completou simulação.')
        print(json.dumps({'mode':'simulation','generation':'ready','send':'simulated','attempts':len(transport.sent),'network':False}))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['demo','tick','backup','restore-offline','owners','grant','ungrant','claim-code']);parser.add_argument('--file');parser.add_argument('--owner');parser.add_argument('--note',default='');parser.add_argument('--uses',type=int);parser.add_argument('--services-stopped',action='store_true');args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
    if args.command=='demo': return demo()
    store,transport=components()
    if args.command=='tick':
        # Rotinas diárias primeiro; o vigia da guild roda no mesmo minuto e nunca derruba a rotina se falhar.
        Worker(store,transport).tick()
        commander=Commander(store,transport)
        return Watcher(store,transport).run(also=(commander.maintain,),fast=(commander.tick,))
    if args.command=='owners':
        for item in store.owners(): print(json.dumps(item))
        return
    if args.command=='claim-code':
        # O código aparece só agora e nunca mais: o servidor guarda apenas o hash. --uses limita quantas contas ele libera (vazio = sem limite).
        print(json.dumps({'code':store.create_claim(args.note or 'dono',args.uses),'note':args.note or 'dono','uses':args.uses}));return
    if args.command in ('grant','ungrant'):
        if not args.owner: parser.error('--owner obrigatório')
        if args.command=='grant': store.grant(args.owner,args.note)
        else: store.ungrant(args.owner)
        print(json.dumps({'owner':args.owner,'liberada':store.entitled(args.owner)}));return
    if not args.file: parser.error('--file obrigatório')
    if args.command=='backup': store.backup(args.file)
    else:
        if not args.services_stopped or transport.real: parser.error('Restauração exige serviços parados e transporte fake.')
        store.restore_offline(args.file)

if __name__=='__main__':main()
