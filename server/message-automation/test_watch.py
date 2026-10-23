"""Alertas da guild: baseline sem enviar, marcos de level, mortes, limite por hora, revogação e falhas de envio."""
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
from automation.domain import UTC, Invalid
from automation.store import Store
from automation.transport import FakeTransport, NotDispatched
from automation.watch import Watcher, validate_watch

T0=datetime(2026,10,23,12,tzinfo=UTC)

def member(name,level,status='online',vocation='Elite Knight'): return {'name':name,'level':level,'status':status,'vocation':vocation}

class Feed:
    """TibiaData sintética: a lista da guild pode trazer level atrasado (guild_levels); a lista online do mundo é a atual."""
    def __init__(self): self.members=[];self.deaths={};self.calls=[];self.guild_levels={}
    def __call__(self,path):
        self.calls.append(path)
        if path.startswith('/guild/'): return {'guild':{'world':'Rasteibra','members':[{**m,'level':self.guild_levels.get(m['name'],m['level'])} for m in self.members]}}
        if path.startswith('/world/'): return {'world':{'online_players':[{'name':'Jogador de Fora','level':50,'vocation':'Druid'}]+[{'name':m['name'],'level':m['level'],'vocation':m['vocation']} for m in self.members if m['status']=='online']}}
        if path.startswith('/character/'):
            name=path.split('/')[-1].replace('%20',' ')
            return {'character':{'deaths':self.deaths.get(name,[])}}
        raise OSError(path)

def death(at,level=500,killers=('a Hydra',),player=False):
    return {'time':at.strftime('%Y-%m-%dT%H:%M:%SZ'),'level':level,'killers':[{'name':k,'player':player} for k in killers]}

class WatchTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/'s.sqlite',Fernet.generate_key());self.transport=FakeTransport();self.feed=Feed()
        self.conn=self.store.create('o','connection',{'riskAccepted':True},'active');self.transport.pair(self.conn)
        self.dest=self.store.create('o','destination',{'connection':self.conn,'group':'fake-group'},'active')
        self.watcher=Watcher(self.store,self.transport,self.feed)
    def watch(self,**extra):
        data={**validate_watch({'guild':'Piratas do Rocks',**extra}),'connection':self.conn,'destination':self.dest}
        return self.store.create('o','watch',data,'active')
    def texts(self): return [x['text'] for x in self.transport.sent]
    def tick(self,minutes): self.watcher.tick(T0+timedelta(minutes=minutes))

    def test_validacao_do_contrato(self):
        self.assertEqual(validate_watch({'guild':'  Piratas   do Rocks '}),{'guild':'Piratas do Rocks','milestone':1,'hourlyCap':0,'perMinute':3,'deaths':True,'ups':True})
        for bad in ({},{'guild':'x'},{'guild':'ok guild','milestone':0},{'guild':'ok guild','milestone':1001},{'guild':'ok guild','hourlyCap':1001},{'guild':'ok guild','hourlyCap':-1},{'guild':'ok guild','perMinute':0},{'guild':'ok guild','perMinute':121},{'guild':'ok guild','deaths':'sim'},
                    {'guild':'ok guild','deaths':False,'ups':False},{'guild':'<b>x</b>'}):
            with self.subTest(bad=bad),self.assertRaises(Invalid): validate_watch(bad)

    def test_primeira_varredura_so_memoriza_e_nao_envia(self):
        self.feed.members=[member('Ana',499,'online')];self.feed.deaths={'Ana':[death(T0-timedelta(minutes=5))]}
        self.watch();self.tick(0);self.tick(3)
        self.assertEqual(self.transport.sent,[])

    def test_level_up_so_nos_marcos_e_uma_vez(self):
        self.feed.members=[member('Ana',499)];self.watch(milestone=50);self.tick(0)
        self.feed.members=[member('Ana',500)];self.tick(3)
        self.assertEqual(len(self.texts()),1);self.assertIn('*Ana*',self.texts()[0]);self.assertIn('level *500*',self.texts()[0])
        self.feed.members=[member('Ana',510)];self.tick(6);self.feed.members=[member('Ana',480)];self.tick(9)
        self.feed.members=[member('Ana',501)];self.tick(12)
        self.assertEqual(len(self.texts()),1,'sem marco novo, sem aviso; voltar ao mesmo marco não repete')
        self.feed.members=[member('Ana',1001)];self.tick(15)
        self.assertEqual(len(self.texts()),2);self.assertIn('1.001',self.texts()[1])

    def test_padrao_avisa_todo_level_sem_repetir(self):
        self.feed.members=[member('Ana',100)];self.watch();self.tick(0)
        self.feed.members=[member('Ana',101)];self.tick(3);self.feed.members=[member('Ana',103)];self.tick(6)
        self.assertEqual(len(self.texts()),2);self.assertIn('level *101*',self.texts()[0]);self.assertIn('level *103*',self.texts()[1])
        self.feed.members=[member('Ana',102)];self.tick(9);self.feed.members=[member('Ana',103)];self.tick(12)
        self.assertEqual(len(self.texts()),2,'perder level e voltar ao mesmo não avisa de novo')

    def test_level_up_vem_da_lista_online_mesmo_com_a_guild_atrasada(self):
        # A lista da guild na TibiaData demora a refletir o level; o aviso não pode esperar por ela.
        self.feed.members=[member('Ana',499)];self.feed.guild_levels={'Ana':498};self.watch();self.tick(0)
        self.assertEqual(self.transport.sent,[],'level diferente entre as fontes não vira aviso falso na primeira varredura')
        self.feed.members=[member('Ana',500)];self.tick(1)
        self.assertEqual(len(self.texts()),1);self.assertIn('level *500*',self.texts()[0])
        self.tick(2);self.assertEqual(len(self.texts()),1)

    def test_quem_esta_offline_nao_gera_level_up(self):
        self.feed.members=[member('Ana',499)];self.watch();self.tick(0)
        self.feed.members=[member('Ana',520,'offline')];self.feed.guild_levels={'Ana':520};self.tick(2)
        self.assertEqual(self.transport.sent,[],'a lista da guild sozinha, com a pessoa offline, não gera aviso')
        self.feed.members=[member('Ana',520)];self.tick(4)
        self.assertEqual(len(self.texts()),1,'ao voltar online com level maior que o último visto, avisa uma vez')
        self.tick(6);self.assertEqual(len(self.texts()),1)

    def test_varredura_a_cada_minuto_sem_reconsultar_a_guild(self):
        self.feed.members=[member('Ana',499)];self.watch();self.tick(0);self.tick(1);self.tick(2)
        self.assertEqual(sum(c.startswith('/guild/') for c in self.feed.calls),1,'a pertença só renova a cada 15 min')
        self.assertEqual(sum(c.startswith('/world/') for c in self.feed.calls),3)
        self.tick(16);self.assertEqual(sum(c.startswith('/guild/') for c in self.feed.calls),2)

    def test_novo_membro_entra_na_lista_depois_da_renovacao(self):
        self.feed.members=[member('Ana',100)];self.watch();self.tick(0)
        self.feed.members=[member('Ana',100),member('Bia',300)];self.tick(16);self.tick(17)
        self.assertEqual(self.transport.sent,[],'novo membro só memoriza o level')
        self.feed.members=[member('Ana',100),member('Bia',301)];self.tick(18)
        self.assertEqual(len(self.texts()),1);self.assertIn('*Bia*',self.texts()[0])

    def test_rodizio_confere_a_ficha_de_todos_os_online(self):
        self.feed.members=[member(f'P{i:02d}',100) for i in range(45)];self.watch();self.tick(0)
        self.tick(1);self.tick(2)
        fichas={c for c in self.feed.calls if c.startswith('/character/')}
        self.assertEqual(len(fichas),45,'com mais online que o limite por varredura, ninguém fica sem conferência')

    def test_intervalo_minimo_entre_varreduras(self):
        self.feed.members=[member('Ana',499)];self.watch();self.tick(0);antes=len(self.feed.calls);self.watcher.tick(T0+timedelta(seconds=10))
        self.assertEqual(len(self.feed.calls),antes,'varredura mais seguida que 15 s é ignorada')
        self.watcher.tick(T0+timedelta(seconds=20));self.assertGreater(len(self.feed.calls),antes)

    def test_varredura_de_20_segundos_pega_level_e_morte_sem_estourar_o_ritmo_por_minuto(self):
        at=lambda seconds:self.watcher.tick(T0+timedelta(seconds=seconds))
        self.feed.members=[member(f'P{i}',100) for i in range(8)];self.watch(perMinute=3);at(0)
        self.feed.members=[member(f'P{i}',101) for i in range(8)];self.feed.deaths={'P7':[death(T0+timedelta(seconds=5))]}
        at(20);self.assertEqual(len(self.texts()),3,'3 por minuto, mesmo com a fila grande')
        at(40);at(60);self.assertEqual(len(self.texts()),3,'a janela de 60 s ainda está cheia')
        at(80);self.assertEqual(len(self.texts()),6)
        at(140);at(200);self.assertEqual(len(self.texts()),9)
        self.assertTrue(any('morreu' in t for t in self.texts()))

    def test_run_faz_tres_varreduras_por_minuto(self):
        ticks=[];self.watcher.tick=lambda now=None:ticks.append(1);clock=[0.0]
        with patch('automation.watch.time.monotonic',lambda:clock[0]),patch('automation.watch.time.sleep',lambda s:clock.__setitem__(0,clock[0]+s)):
            self.watcher.run()
        self.assertEqual(len(ticks),3);self.assertLess(clock[0],45)

    def test_morte_depois_da_criacao_avisa_uma_vez_e_ignora_antiga(self):
        self.feed.members=[member('Bia',800,'online',vocation='Royal Paladin')];self.watch();self.tick(0)
        self.feed.deaths={'Bia':[death(T0+timedelta(minutes=1),799,('a Hydra','Fulano'),False),death(T0-timedelta(hours=1))]}
        self.tick(3);self.tick(6)
        self.assertEqual(len(self.texts()),1)
        self.assertIn('💀 🏹 *Bia* morreu no level 799 — a Hydra, Fulano',self.texts()[0])

    def test_nome_com_marcadores_nao_formata_a_mensagem(self):
        self.feed.members=[member('Bia',800,'online')];self.watch();self.tick(0)
        self.feed.deaths={'Bia':[death(T0+timedelta(minutes=1),799,('*ENVIE_DINHEIRO*\nagora',),True)]};self.tick(3)
        self.assertEqual(self.texts()[0].count('*'),2);self.assertNotIn('\n',self.texts()[0]);self.assertIn('(jogador)',self.texts()[0])

    def test_morte_apos_logout_ainda_e_vista(self):
        self.feed.members=[member('Bia',800,'online')];self.watch();self.tick(0)
        self.feed.members=[member('Bia',800,'offline')];self.feed.deaths={'Bia':[death(T0+timedelta(minutes=2))]};self.tick(3)
        self.assertEqual(len(self.texts()),1)

    def test_so_mortes_ou_so_ups(self):
        self.feed.members=[member('Ana',499,'online')];self.watch(ups=False);self.tick(0)
        self.feed.members=[member('Ana',500,'online')];self.feed.deaths={'Ana':[death(T0+timedelta(minutes=1))]};self.tick(3)
        self.assertEqual(len(self.texts()),1);self.assertIn('morreu',self.texts()[0])

    def test_limite_por_hora_e_ritmo_por_minuto(self):
        self.feed.members=[member(f'P{i}',100,'online') for i in range(6)];self.watch(hourlyCap=4);self.tick(0)
        self.feed.deaths={f'P{i}':[death(T0+timedelta(minutes=1))] for i in range(6)}
        self.tick(3);self.assertEqual(len(self.texts()),3,'no máximo 3 por minuto')
        self.tick(6);self.assertEqual(len(self.texts()),4,'depois o teto de 4 por hora')
        self.tick(9);self.assertEqual(len(self.texts()),4)
        self.tick(65);self.assertEqual(len(self.texts()),6,'passada a hora, o restante ainda válido segue')

    def test_sem_limite_por_hora_so_com_ritmo_por_minuto(self):
        self.feed.members=[member(f'P{i}',100,'online') for i in range(8)];self.watch();self.tick(0)
        self.feed.deaths={f'P{i}':[death(T0+timedelta(minutes=1))] for i in range(8)}
        self.tick(3);self.assertEqual(len(self.texts()),3,'ritmo de 3 por minuto mesmo sem teto')
        self.tick(6);self.tick(9);self.assertEqual(len(self.texts()),8,'sem teto, a fila inteira sai nas varreduras seguintes')

    def test_ritmo_por_minuto_e_escolhido_pelo_dono(self):
        self.feed.members=[member(f'P{i}',100,'online') for i in range(8)];self.watch(perMinute=5);self.tick(0)
        self.feed.deaths={f'P{i}':[death(T0+timedelta(minutes=1))] for i in range(8)}
        self.tick(3);self.assertEqual(len(self.texts()),5,'5 por minuto, como configurado')
        self.tick(6);self.assertEqual(len(self.texts()),8)

    def test_aviso_velho_demais_expira_em_vez_de_chegar_atrasado(self):
        self.feed.members=[member('Ana',100,'online'),member('Bia',100,'online')];self.watch(hourlyCap=1);self.tick(0)
        self.feed.deaths={'Ana':[death(T0+timedelta(minutes=1))],'Bia':[death(T0+timedelta(minutes=2))]};self.tick(3);self.tick(6)
        self.assertEqual(len(self.texts()),1)
        self.tick(200);self.assertEqual(len(self.texts()),1)

    def test_conexao_revogada_cancela_o_que_estava_na_fila(self):
        self.feed.members=[member('Ana',100,'online'),member('Bia',100,'online')];self.watch(hourlyCap=1);self.tick(0)
        self.feed.deaths={'Ana':[death(T0+timedelta(minutes=1))],'Bia':[death(T0+timedelta(minutes=2))]};self.tick(3)
        self.store.revoke('o',self.conn);self.tick(70)
        self.assertEqual(len(self.texts()),1)
        with self.store.tx() as db: self.assertEqual(db.execute("SELECT count(*) FROM watch_events WHERE state='cancelled'").fetchone()[0],1)

    def test_falha_conhecida_vira_failed_e_incerta_nunca_repete(self):
        self.feed.members=[member('Ana',100,'online')];self.watch();self.tick(0)
        self.feed.deaths={'Ana':[death(T0+timedelta(minutes=1))]}
        def boom(*a): raise RuntimeError('rede')
        self.transport.send=boom;self.tick(3);self.tick(6)
        with self.store.tx() as db: self.assertEqual([r['state'] for r in db.execute('SELECT state FROM watch_events')],['uncertain'])
        self.assertEqual(self.transport.sent,[])
        def never(*a): raise NotDispatched('x')
        self.feed.deaths={'Ana':[death(T0+timedelta(minutes=7),300)]};self.transport.send=never;self.tick(9)
        with self.store.tx() as db: self.assertIn('failed',[r['state'] for r in db.execute('SELECT state FROM watch_events')])

    def test_guild_vazia_ou_falha_da_fonte_nao_gera_nada(self):
        self.feed.members=[member('Ana',499)];self.watch();self.tick(0)
        self.feed.members=[];self.tick(3)
        self.assertEqual(self.transport.sent,[])
        self.feed.members=[member('Ana',500)];self.tick(6)
        self.assertEqual(len(self.texts()),1,'a memória do baseline sobrevive à falha')

    def test_api_dono_isolamento_validacao_e_exclusao(self):
        from fastapi.testclient import TestClient
        from automation.api import create_app
        from automation.auth import Verifier
        verifier=Verifier(self.store);client=TestClient(create_app(self.store,self.transport,verifier,origins=('https://portal.test',)))
        a={'Authorization':'Bearer '+'a'*64};b={'Authorization':'Bearer '+'b'*64}
        verifier.register('a'*64,'c'*64);verifier.register('b'*64,'d'*64)
        conn=client.post('/v1/connections',json={'riskAccepted':True},headers=a).json()['id'];client.post(f'/v1/connections/{conn}/pair',headers=a)
        dest=client.post('/v1/destinations',json={'connection':conn,'group':'fake-group'},headers=a).json()['id']
        body={'guild':'Piratas do Rocks','milestone':50,'deaths':True,'ups':True,'hourlyCap':20,'perMinute':3,'connection':conn,'destination':dest,'active':True}
        self.assertEqual(client.post('/v1/watches',json=body).status_code,401)
        for bad in ({**body,'guild':''},{**body,'milestone':0},{**body,'extra':1},{**body,'deaths':False,'ups':False},{**body,'destination':'outro'}):
            self.assertEqual(client.post('/v1/watches',json=bad,headers=a).status_code,400,bad)
        self.assertEqual(client.post('/v1/watches',json=body,headers=b).status_code,400,'conexão de outro dono')
        made=client.post('/v1/watches',json=body,headers=a);self.assertEqual(made.status_code,200);key=made.json()['id']
        self.assertEqual(client.get('/v1/watches',headers=b).json(),[])
        listed=client.get('/v1/watches',headers=a).json()[0];self.assertEqual((listed['guild'],listed['state'],listed['destinationLabel']),('Piratas do Rocks','active','Grupo sintético (simulação)'))
        self.assertEqual(client.put(f'/v1/watches/{key}',json={**body,'active':False},headers=b).status_code,400)
        self.assertEqual(client.put(f'/v1/watches/{key}',json={**body,'active':False},headers=a).json()['state'],'inactive')
        for _ in range(2): self.assertEqual(client.post('/v1/watches',json=body,headers=a).status_code,200)
        self.assertEqual(client.post('/v1/watches',json=body,headers=a).status_code,400,'limite de 3 alertas')
        self.assertEqual(client.delete(f'/v1/watches/{key}',headers=b).status_code,400)
        self.assertEqual(client.delete(f'/v1/watches/{key}',headers=a).status_code,200)
        self.assertEqual(len(client.get('/v1/watches',headers=a).json()),2)
        self.assertEqual(client.put(f'/v1/watches/{key}',json=body,headers=a).status_code,400,'excluído não volta')

    def test_banco_antigo_ganha_as_colunas_novas_sem_perder_dados(self):
        import sqlite3
        from contextlib import closing
        old=Path(tempfile.mkdtemp())/'old.sqlite';self.addCleanup(lambda:old.unlink(missing_ok=True) if old.exists() else None)
        with closing(sqlite3.connect(old)) as db:
            db.executescript("CREATE TABLE watch_members(watch TEXT NOT NULL,name TEXT NOT NULL,level INTEGER NOT NULL,online INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(watch,name));"
                             "CREATE TABLE watch_meta(watch TEXT PRIMARY KEY,last_run REAL NOT NULL DEFAULT 0,since REAL NOT NULL DEFAULT 0,primed INTEGER NOT NULL DEFAULT 0);"
                             "INSERT INTO watch_members VALUES('w','Ana',500,1);INSERT INTO watch_meta VALUES('w',1,1,1);")
        Store(old,Fernet.generate_key())
        with closing(sqlite3.connect(old)) as db:
            self.assertTrue({'vocation','checked'}<={r[1] for r in db.execute('PRAGMA table_info(watch_members)')})
            self.assertTrue({'world','roster_at'}<={r[1] for r in db.execute('PRAGMA table_info(watch_meta)')})
            self.assertEqual(db.execute("SELECT name,level FROM watch_members").fetchall(),[('Ana',500)])

    def test_conteudo_cifrado_no_banco(self):
        self.feed.members=[member('Ana Secreta',499)];self.watch();self.tick(0)
        self.feed.members=[member('Ana Secreta',500)];self.tick(3)
        raw=self.store.path.read_bytes();self.assertNotIn(b'subiu para o level',raw)


if __name__=='__main__':unittest.main()
