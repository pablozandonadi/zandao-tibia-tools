"""Comandos no grupo: respostas (!help, !precocoin, !duelo, !evolucao), roteador com limite por membro, histórico de XP, API e transporte."""
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
import httpx
from cryptography.fernet import Fernet
from automation.botcmds import Bot, HELP
from automation.commands import Commander, validate_botgroup
from automation.domain import UTC, Invalid
from automation.store import Store
from automation.transport import BridgeTransport, FakeTransport

TODAY=date(2026,10,23)
RANK={('Tornabra',30):[('Papelaum Meliexp',1534,4_310_000_000,'MS'),('Jorjao do Martelo',1541,4_220_000_000,'EK'),('Parado',900,-5_000_000,'ED'),('Marcado_Nome',100,1_000_000,'EK')],
      ('Tornabra',7):[('Papelaum Meliexp',1534,1_020_000_000,'MS'),('Jorjao do Martelo',1541,1_070_000_000,'EK'),('Marcado_Nome',100,1_000_000,'EK')],
      ('Tornabra',0):[('Papelaum Meliexp',1534,153_970_000,'MS'),('Jorjao do Martelo',1541,140_000_000,'EK'),('Marcado_Nome',100,1_000_000,'EK')]}
SHEETS={'papelaum meliexp':{'name':'Papelaum Meliexp','level':1534,'vocation':'Master Sorcerer','world':'Tornabra'},
        'jorjao do martelo':{'name':'Jorjao do Martelo','level':1541,'vocation':'Elite Knight','world':'Tornabra'},
        'fora do top':{'name':'Fora do Top','level':300,'vocation':'Druid','world':'Tornabra'},
        'marcado':{'name':'*Marcado_Nome*','level':100,'vocation':'Knight','world':'Tornabra'}}

def bot(**extra):
    return Bot(ranking=lambda world,window:RANK.get((world,window)),sheet=lambda name:SHEETS.get(name.casefold()),
               trade=lambda world:{'estado':'ok','gold_por_tc':48000,'data_base':'2026-10-22T10:00:00+00:00','motivo':''},**extra)

class BotTests(unittest.TestCase):
    def test_help_e_apelidos(self):
        b=bot()
        for text in ('!help','!ajuda','!comandos','! help'): self.assertEqual(b.handle(text,'Tornabra',TODAY),HELP)
        for command in ('!duelo','!evolucao','!precocoin'): self.assertIn(command,HELP)

    def test_so_responde_a_comando_conhecido(self):
        b=bot()
        for text in ('oi','!','!naoexiste','!!!','hello !help','','!rank'): self.assertIsNone(b.handle(text,'Tornabra',TODAY),text)

    def test_precocoin_no_padrao_do_app(self):
        r=bot().handle('!precocoin Rasteibra','Tornabra',TODAY)
        self.assertIn('🪙 *Tibia Coin — Rasteibra*',r);self.assertIn('*48.000* gold',r);self.assertIn('22/10',r)
        self.assertIn('20,83 TC',r);self.assertIn('R$ 4,08 a R$ 4,33',r);self.assertIn('R$ 49,00 a R$ 52,00',r)
        self.assertIn('Tornabra',bot().handle('!precocoin','Tornabra',TODAY));self.assertIn('Use:',bot().handle('!precocoin 123','',TODAY))

    def test_precocoin_indisponivel_e_antiga(self):
        down=Bot(trade=lambda w:{'estado':'indisponivel','motivo':'Cotação indisponível. Valor manual em uso.'})
        self.assertIn('indisponível agora',down.handle('!tc Antica','',TODAY))
        old=Bot(trade=lambda w:{'estado':'antiga','gold_por_tc':50000,'data_base':'2026-10-01T00:00:00+00:00','motivo':''})
        self.assertIn('Cotação antiga',old.handle('!tc Antica','',TODAY))

    def test_duelo_tabela_e_quem_passa_quem(self):
        r=bot().handle('!duelo Papelaum Meliexp x Jorjao do Martelo','Tornabra',TODAY)
        self.assertIn('⚔️ *Papelaum Meliexp x Jorjao do Martelo* — últimos 30 dias',r);self.assertIn('```',r)
        for esperado in ('Level','1.534','1.541','4,31kkk','4,22kkk','143,67kk','140,67kk','XP ontem','153,97kk'): self.assertIn(esperado,r)
        self.assertIn('*Papelaum Meliexp* passa *Jorjao do Martelo*',r);self.assertIn('Jorjao do Martelo precisa de 143,67kk/dia pra não ser passado',r)

    def test_duelo_quem_esta_na_frente_e_mais_rapido_nao_e_ultrapassado(self):
        r=Bot(ranking=lambda w,x:[('Aa',1000,3_000_000_000,'EK'),('Bb',900,1_000_000_000,'EK')],sheet=lambda n:{'name':n.capitalize(),'level':{'aa':1000,'bb':900}[n.casefold()],'vocation':'EK','world':'Tornabra'}).handle('!duelo aa x bb','',TODAY)
        self.assertIn('segue na frente',r);self.assertNotIn('passa',r)

    def test_duelo_erros(self):
        b=bot()
        self.assertIn('Use:',b.handle('!duelo so um','Tornabra',TODAY));self.assertIn('Use:',b.handle('!duelo <b>a</b> x c','Tornabra',TODAY))
        self.assertIn('Não encontrei o personagem *Fantasma*',b.handle('!duelo Fantasma x Papelaum Meliexp','Tornabra',TODAY))
        r=b.handle('!duelo Fora do Top x Papelaum Meliexp','Tornabra',TODAY)
        self.assertIn('fora do top 500',r);self.assertNotIn('passa',r);self.assertIn('—',r)

    def test_nomes_com_marcadores_nao_formatam_a_resposta(self):
        r=bot().handle('!evolucao Marcado','Tornabra',TODAY);self.assertNotIn('*Marcado_Nome*',r);self.assertIn('*Evolução — MarcadoNome*',r)

    def test_evolucao_com_projecao_e_sem_historico(self):
        r=bot().handle('!evolucao Papelaum Meliexp','Tornabra',TODAY)
        for esperado in ('📈 *Evolução — Papelaum Meliexp*','Lv *1.534*','Tornabra','Ontem: *153,97kk*','7 dias: *1,02kkk*','30 dias: *4,31kkk*','Projeção','Lv 1.535','começa a ser gravada'): self.assertIn(esperado,r)
        self.assertNotIn('```',r)

    def test_evolucao_com_curva_diaria_e_dia_no_vermelho(self):
        days=[('2026-10-19',2_000_000_000),('2026-10-20',1_000_000_000),('2026-10-21',-50_000_000),('2026-10-22',1_500_000_000)]
        tracked=[];r=bot(history=lambda world,name:days,track=tracked.append).handle('!evolucao Papelaum Meliexp','Tornabra',TODAY)
        self.assertIn('XP por dia (últimos 4 dias)',r);self.assertIn('21/10',r);self.assertIn('💀',r);self.assertIn('██████████ 2,00kkk',r)
        self.assertIn('Tornabra',tracked)

    def test_evolucao_fora_do_top_500_e_erros(self):
        self.assertIn('fora do top 500',bot().handle('!evolucao Fora do Top','Tornabra',TODAY))
        self.assertIn('Não encontrei',bot().handle('!evolucao Fantasma','Tornabra',TODAY));self.assertIn('Use:',bot().handle('!evolucao 12','Tornabra',TODAY))

    def test_falha_de_fonte_vira_aviso_curto(self):
        def boom(name): raise OSError('rede')
        self.assertIn('Não consegui consultar',Bot(sheet=boom).handle('!evolucao Alguem','Tornabra',TODAY))

NOW=datetime(2026,10,23,15,tzinfo=UTC)  # 17h em Berlim: depois do server save e do meio-dia
def item(text,id_='m1',sender='s1',group='fake-group'): return {'id':id_,'group':group,'sender':sender,'text':text}

class CommanderTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/'s.sqlite',Fernet.generate_key());self.transport=FakeTransport()
        self.conn=self.store.create('o','connection',{'riskAccepted':True},'active');self.transport.pair(self.conn)
        self.dest=self.store.create('o','destination',{'connection':self.conn,'group':'fake-group'},'active')
        self.fetches=[];self.bot=bot();original=self.bot.ranking
        self.bot.ranking=lambda world,window:(self.fetches.append((world,window)),original(world,window))[1]
        self.commander=Commander(self.store,self.transport,self.bot)
    def group(self,**extra):
        return self.store.create('o','botgroup',{'world':'Tornabra','cooldown':30,'connection':self.conn,'destination':self.dest,**extra},'active')
    def receive(self,*items,at=0): self.transport.inbound[self.conn]=list(items);self.commander.tick(NOW+timedelta(seconds=at))
    def texts(self): return [m['text'] for m in self.transport.sent]

    def test_responde_ao_comando_no_grupo_autorizado(self):
        self.group();self.receive(item('!help'));self.assertEqual(self.texts(),[HELP])

    def test_ignora_grupo_nao_autorizado_e_texto_comum(self):
        self.group();self.receive(item('!help',group='outro-grupo'),item('bom dia',id_='m2'),item('!naoexiste',id_='m3'));self.assertEqual(self.texts(),[])

    def test_nao_responde_duas_vezes_a_mesma_mensagem(self):
        self.group();self.receive(item('!help'));self.receive(item('!help'),at=100);self.assertEqual(len(self.texts()),1)

    def test_limite_por_membro_e_outro_membro_livre(self):
        self.group(cooldown=30);self.receive(item('!help'))
        self.receive(item('!help',id_='m2'),at=10);self.assertEqual(len(self.texts()),1,'mesmo membro dentro dos 30 s: silêncio')
        self.receive(item('!help',id_='m3',sender='s2'),at=11);self.assertEqual(len(self.texts()),2,'outro membro responde na hora')
        self.receive(item('!help',id_='m4'),at=31);self.assertEqual(len(self.texts()),3,'passados os 30 s, volta a responder')

    def test_comando_desconhecido_nao_gasta_o_intervalo(self):
        self.group();self.receive(item('!naoexiste'));self.receive(item('!help',id_='m2'),at=1);self.assertEqual(len(self.texts()),1)

    def test_enxurrada_e_limitada_por_varredura(self):
        self.group(cooldown=5);self.receive(*[item('!help',id_=f'm{i}',sender=f's{i}') for i in range(12)]);self.assertEqual(len(self.texts()),5)

    def test_conexao_revogada_para_de_responder(self):
        self.group();self.store.revoke('o',self.conn);self.receive(item('!help'));self.assertEqual(self.texts(),[])

    def test_falha_ao_ler_ou_responder_nao_derruba(self):
        self.group()
        def boom(*a): raise RuntimeError('ponte fora')
        self.transport.inbox=boom;self.commander.tick(NOW)
        del self.transport.inbox;self.transport.send=boom;self.receive(item('!help'))

    def test_texto_recebido_nunca_fica_gravado(self):
        self.group();self.receive(item('!duelo SegredoUnico x OutroSegredo'))
        raw=self.store.path.read_bytes();self.assertNotIn(b'SegredoUnico',raw);self.assertNotIn(b'OutroSegredo',raw)

    def test_snapshot_diario_so_depois_do_meio_dia_de_berlim_e_uma_vez(self):
        self.group();self.commander.tick(datetime(2026,10,23,9,tzinfo=UTC))
        self.assertEqual(self.fetches,[],'antes do meio-dia em Berlim não grava')
        self.commander.tick(NOW)
        with self.store.tx() as db: rows=db.execute('SELECT day,name,xp FROM rank_history ORDER BY name').fetchall()
        self.assertEqual({r['day'] for r in rows},{'2026-10-22'});self.assertEqual(len(rows),3)
        antes=len(self.fetches);self.commander.tick(NOW+timedelta(minutes=5));self.assertEqual(len(self.fetches),antes,'já gravou hoje')
        self.assertEqual(self.commander.history('Tornabra','papelaum meliexp'),[('2026-10-22',153_970_000)])

    def test_mundo_consultado_passa_a_ter_historico(self):
        self.group();self.commander.track('Antica')
        with self.store.tx() as db: self.assertIn('Antica',[r['world'] for r in db.execute('SELECT world FROM rank_meta')])

class ConfigTests(unittest.TestCase):
    def test_validacao(self):
        self.assertEqual(validate_botgroup({'world':' rasteibra '}),{'world':'Rasteibra','cooldown':30})
        for bad in ({},{'world':'1'},{'world':'Antica','cooldown':4},{'world':'Antica','cooldown':601},{'world':'Antica','cooldown':'30'}):
            with self.assertRaises(Invalid): validate_botgroup(bad)

    def test_api_dono_isolamento_grupo_unico_e_exclusao(self):
        from fastapi.testclient import TestClient
        from automation.api import create_app
        from automation.auth import Verifier
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        store=Store(Path(tmp.name)/'s.sqlite',Fernet.generate_key());transport=FakeTransport();verifier=Verifier(store)
        client=TestClient(create_app(store,transport,verifier,origins=('https://portal.test',)))
        a={'Authorization':'Bearer '+'a'*64};b={'Authorization':'Bearer '+'b'*64}
        verifier.register('a'*64,'c'*64);verifier.register('b'*64,'d'*64)
        conn=client.post('/v1/connections',json={'riskAccepted':True},headers=a).json()['id'];client.post(f'/v1/connections/{conn}/pair',headers=a)
        dest=client.post('/v1/destinations',json={'connection':conn,'group':'fake-group'},headers=a).json()['id']
        body={'world':'Rasteibra','cooldown':30,'connection':conn,'destination':dest,'active':True}
        self.assertEqual(client.post('/v1/botgroups',json=body).status_code,401)
        for bad in ({**body,'world':''},{**body,'cooldown':1},{**body,'extra':1},{**body,'destination':'outro'}): self.assertEqual(client.post('/v1/botgroups',json=bad,headers=a).status_code,400,bad)
        self.assertEqual(client.post('/v1/botgroups',json=body,headers=b).status_code,400,'conexão de outro dono')
        made=client.post('/v1/botgroups',json=body,headers=a);self.assertEqual(made.status_code,200);key=made.json()['id']
        self.assertEqual(client.post('/v1/botgroups',json=body,headers=a).status_code,400,'um grupo, um conjunto de comandos ativo')
        self.assertEqual(client.get('/v1/botgroups',headers=b).json(),[])
        listed=client.get('/v1/botgroups',headers=a).json()[0];self.assertEqual((listed['world'],listed['cooldown'],listed['state']),('Rasteibra',30,'active'))
        self.assertEqual(client.put(f'/v1/botgroups/{key}',json={**body,'cooldown':60},headers=a).json()['state'],'active','editar o próprio não conflita')
        self.assertEqual(client.put(f'/v1/botgroups/{key}',json={**body,'active':False},headers=b).status_code,400)
        self.assertEqual(client.delete(f'/v1/botgroups/{key}',headers=b).status_code,400)
        self.assertEqual(client.delete(f'/v1/botgroups/{key}',headers=a).status_code,200)
        self.assertEqual(client.get('/v1/botgroups',headers=a).json(),[])
        self.assertEqual(client.put(f'/v1/botgroups/{key}',json=body,headers=a).status_code,400,'excluído não volta')

class BridgeInboxTests(unittest.TestCase):
    def transport(self,inbox,resume_state='connected'):
        original=httpx.Client
        def handler(request):
            if request.url.path.endswith('/resume'): return httpx.Response(200,json={'state':resume_state,'simulated':False})
            return inbox(request)
        return BridgeTransport('http://127.0.0.1:8788','a'*48),patch('automation.transport.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler),**kw))

    def test_le_so_itens_validos(self):
        good={'id':'m1','group':'g','sender':'s','text':'!help'}
        t,p=self.transport(lambda r:httpx.Response(200,json={'messages':[good,{'id':'x'},'lixo',{**good,'text':''}],'simulated':False}))
        with p: self.assertEqual(t.inbox('a'*32),[good])

    def test_simulado_desconectado_ou_com_erro_devolve_vazio(self):
        t,p=self.transport(lambda r:httpx.Response(200,json={'messages':[{'id':'m','group':'g','sender':'s','text':'!help'}],'simulated':True}))
        with p: self.assertEqual(t.inbox('a'*32),[])
        t,p=self.transport(lambda r:httpx.Response(200,json={'messages':[]}),resume_state='disconnected')
        with p: self.assertEqual(t.inbox('a'*32),[])
        t,p=self.transport(lambda r:httpx.Response(500,json={'error':'x'}))
        with p: self.assertEqual(t.inbox('a'*32),[])

if __name__=='__main__':unittest.main()
