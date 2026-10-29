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

    def test_duelo_blocos_e_quem_passa_quem(self):
        r=bot().handle('!duelo Papelaum Meliexp x Jorjao do Martelo','Tornabra',TODAY)
        self.assertIn('⚔️ *Papelaum Meliexp x Jorjao do Martelo*',r);self.assertNotIn('```',r)
        for esperado in ('🔥 *Papelaum Meliexp* · Lv *1.534*','🛡️ *Jorjao do Martelo* · Lv *1.541*','4,31kkk','4,22kkk','Último intervalo','7 dias','30 dias','153,97kk'): self.assertIn(esperado,r)
        self.assertIn('*Papelaum Meliexp* passa *Jorjao do Martelo*',r);self.assertNotIn('precisa de',r);self.assertNotIn('XP/dia',r)

    def test_duelo_quem_esta_na_frente_e_mais_rapido_nao_e_ultrapassado(self):
        r=Bot(ranking=lambda w,x:[('Aa',1000,3_000_000_000,'EK'),('Bb',900,1_000_000_000,'EK')],sheet=lambda n:{'name':n.capitalize(),'level':{'aa':1000,'bb':900}[n.casefold()],'vocation':'EK','world':'Tornabra'}).handle('!duelo aa x bb','',TODAY)
        self.assertIn('segue na frente',r);self.assertNotIn('passa',r)

    def test_duelo_erros(self):
        b=bot()
        self.assertIn('Use:',b.handle('!duelo so um','Tornabra',TODAY));self.assertIn('Use:',b.handle('!duelo <b>a</b> x c','Tornabra',TODAY))
        self.assertIn('Não encontrei o personagem *Fantasma*',b.handle('!duelo Fantasma x Papelaum Meliexp','Tornabra',TODAY))
        r=b.handle('!duelo Fora do Top x Papelaum Meliexp','Tornabra',TODAY)
        self.assertIn('Histórico incompleto',r);self.assertNotIn('passa',r);self.assertIn('—',r)

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

class MeasuredDuelTests(unittest.TestCase):
    def setUp(self):
        from copy import deepcopy
        self.infos=deepcopy(SHEETS)
        start=datetime(2026,9,23,7,tzinfo=UTC).timestamp();end=datetime(2026,10,23,7,tzinfo=UTC).timestamp()
        self.xps={}
        for name in ('papelaum meliexp','jorjao do martelo'):
            values={w:next(row[2] for row in RANK[('Tornabra',w)] if row[0].casefold()==name) for w in (0,7,30)}
            values.update(_rates={30:values[30]/30},_projection=True,_meta={w:{'source':'TibiaRise — variação entre registros','fresh':True,'start':start,'end':end} for w in (0,7,30)})
            self.xps[name]=values

    def render(self,custom=''):
        return Bot(sheet=lambda name:self.infos.get(name.casefold()),experience=lambda world,name:self.xps[name.casefold()],settings=lambda:{'duelo':{'text':custom}}).handle('!duelo Papelaum Meliexp x Jorjao do Martelo','Tornabra',TODAY)

    def test_stale_compact_values_emojis_and_only_one_short_warning(self):
        for xp in self.xps.values():
            xp['_projection']=False
            for meta in xp['_meta'].values():meta['fresh']=False
        self.xps['papelaum meliexp'][0]=0;self.xps['jorjao do martelo'][7]=-2_000_000
        text=self.render()
        for label in ('Último intervalo:','7 dias:','30 dias:'):self.assertEqual(text.count(label),2)
        self.assertIn('🔥 *Papelaum Meliexp*',text);self.assertIn('🛡️ *Jorjao do Martelo*',text)
        self.assertIn('Último intervalo: *0,00kk*',text);self.assertIn('7 dias: *-2,00kk*',text)
        self.assertEqual(text.count('⚠️ Dados antigos; sem projeção.'),1)
        for technical in ('TibiaRise','variação entre registros','UTC','registro antigo','```','XP/dia','intervalos diários','dados disponíveis'):
            self.assertNotIn(technical,text)

    def test_current_comparable_periods_keep_prediction_without_second_advice(self):
        text=self.render();self.assertIn('*Papelaum Meliexp* passa *Jorjao do Martelo*',text)
        self.assertNotIn('⚠️',text);self.assertNotIn('precisa de',text)

    def test_projection_guards_remain_for_missing_incomplete_sources_and_periods(self):
        from copy import deepcopy
        original=deepcopy(self.xps)
        for scenario in ('missing','incomplete','sources','periods'):
            self.xps=deepcopy(original);xp=self.xps['jorjao do martelo']
            if scenario=='missing':xp[30]=None;xp['_projection']=False
            if scenario=='incomplete':xp['_projection']=False
            if scenario=='sources':xp['_meta'][30]['source']='GuildStats'
            if scenario=='periods':xp['_meta'][30]['end']+=901
            with self.subTest(scenario=scenario):
                text=self.render();self.assertIn('sem projeção',text);self.assertNotIn('*Papelaum Meliexp* passa',text)
                self.assertIn('—' if scenario=='missing' else ('Histórico incompleto' if scenario=='incomplete' else 'Períodos ou fontes diferentes'),text)

    def test_same_level_and_all_vocations_have_compact_identity(self):
        self.infos['jorjao do martelo']['level']=1534
        for vocation,icon in (('Elite Knight','🛡️'),('Royal Paladin','🏹'),('Elder Druid','❄️'),('Master Sorcerer','🔥'),('Exalted Monk','👊'),('unknown','👤')):
            self.infos['papelaum meliexp']['vocation']=vocation
            with self.subTest(vocation=vocation):
                text=self.render();self.assertIn(icon+' *Papelaum Meliexp* · Lv *1.534*',text);self.assertIn('mesmo level',text)

    def test_custom_placeholders_and_default_response_still_render(self):
        text=self.render('Comparação: {nome1} / {nome2}\n{tabela}\n{resultado}')
        self.assertTrue(text.startswith('Comparação: Papelaum Meliexp / Jorjao do Martelo'))
        self.assertIn('🔥 *Papelaum Meliexp*',text);self.assertIn('30 dias:',text);self.assertNotIn('TibiaRise',text)
        self.assertEqual(self.render('{resposta}'),self.render())


ZANDAO={'character':{'character':{'name':'Zandao','vocation':'Master Sorcerer','level':524,'world':'Rasteibra','residence':'Roshamuul','achievement_points':357,'account_status':'Premium Account',
        'guild':{'name':'Xandebro','rank':'Member'},'last_login':'2026-10-23T13:30:38Z',
        'houses':[{'name':'Theater Avenue 8a','town':'Carlin'},{'name':'Wood Avenue 4b','town':'Edron'}]},
        'deaths':[{'time':'2026-10-23T01:46:01Z','level':524,'reason':'Died at Level 524 by crazed summer rearguard.'},{'time':'2026-10-22T18:32:13Z','level':524,'reason':'Killed at Level 524 by *Zandao* and burning book.'}]}}
ONLINE=[{'name':'Zandao','level':524,'vocation':'Master Sorcerer'},{'name':'Bolotiss','level':378,'vocation':'Elite Knight'},{'name':'Artututs','level':551,'vocation':'Elite Knight'},
        {'name':'Guardia Nevery','level':652,'vocation':'Elite Knight'},{'name':'Longe','level':900,'vocation':'Elite Knight'},{'name':'Pequeno','level':100,'vocation':'Royal Paladin'},
        {'name':'Perto Rp','level':600,'vocation':'Royal Paladin'},{'name':'Perto Ed','level':500,'vocation':'Elder Druid'}]
GUILDS={'artututs':None,'bolotiss':None,'guardia nevery':'Xandebro'}

def party_bot(**extra):
    sheets={**{k:v for k,v in SHEETS.items()},'zandao':{'name':'Zandao','level':524,'vocation':'Master Sorcerer','world':'Rasteibra','guild':'Xandebro'}}
    base=dict(sheet=lambda n:sheets.get(n.casefold()) or ({'name':n,'level':1,'vocation':'x','world':'Rasteibra','guild':GUILDS.get(n.casefold())} if n.casefold() in GUILDS else None),
               online=lambda world:ONLINE if world=='Rasteibra' else None,character=lambda n:ZANDAO if n.casefold()=='zandao' else None,
               world=lambda n:{'name':'Rasteibra','status':'online','players_online':206,'location':'South America','pvp_type':'Open PvP'} if n.casefold()=='rasteibra' else None,
               guild=lambda n:{'name':'Xandebro','members':[{'name':'Ana','level':900,'vocation':'Elite Knight','status':'online'},{'name':'Bia','level':1000,'vocation':'Master Sorcerer','status':'online'},{'name':'Cid','level':50,'vocation':'Knight','status':'offline'}]} if n.casefold()=='xandebro' else None,
               ranking=lambda world,window:RANK.get((world,window)) if world=='Tornabra' else [('Zandao',524,{0:30_000_000,7:200_000_000,30:800_000_000}[window],'MS')])
    base.update(extra)
    return Bot(**base)

class NovosComandosTests(unittest.TestCase):
    def test_char_ficha_completa_no_padrao(self):
        r=party_bot().handle('!char Zandao','',TODAY)
        for esperado in ('📜 *Zandao*','🔥 Master Sorcerer · 🏆 Level *524* · 🌍 Rasteibra','⚔️ *Guilda:* Xandebro (Member)','🏠 *Casa(s):* Theater Avenue 8a (Carlin), Wood Avenue 4b (Edron)',
                         '📍 *Residência:* Roshamuul','357 achievement points · Premium Account','⏰ *Último login:* 23/10/26 - 10:30','🔥 *Mortes (últimos 30 dias)*',
                         '· 22/10/2026 — Lv 524 — Died at Level 524 by crazed summer rearguard.'): self.assertIn(esperado,r)
        self.assertNotIn('*Zandao* and burning',r,'marcadores dentro do texto de morte são removidos')

    def test_char_erros_e_sem_mortes(self):
        b=party_bot();self.assertIn('Não encontrei',b.handle('!char Fantasma','',TODAY));self.assertIn('Use:',b.handle('!char','',TODAY));self.assertIn('Use:',b.handle('!personagem 12','',TODAY))
        sem={'character':{'character':{'name':'Novo','level':10,'vocation':'Knight','world':'Antica'},'deaths':[]}}
        self.assertIn('Sem mortes',Bot(character=lambda n:sem).handle('!char Novo','',TODAY))

    def test_pt_party_finder_na_faixa_de_shared(self):
        r=party_bot().handle('!pt Zandao ek','',TODAY)
        self.assertIn('🤝 *Party match — Zandao* — filtro EK',r);self.assertIn('[MS] · 🏆 Lv *524* · 🌍 Rasteibra',r);self.assertIn('🔗 Shared: 350–786 · jogadores online',r)
        self.assertIn('*Artututs* — Lv *551* (Sem Guild)',r);self.assertIn('*Guardia Nevery* — Lv *652* (Xandebro)',r);self.assertIn('*Bolotiss* — Lv *378*',r)
        for fora in ('Longe','Pequeno','Perto Rp','Perto Ed','*Zandao* —'): self.assertNotIn(fora,r)

    def test_pt_sem_filtro_agrupa_por_vocacao_em_ordem(self):
        r=party_bot().handle('!pt Zandao','',TODAY)
        self.assertLess(r.index('Elite Knight'),r.index('Royal Paladin'));self.assertLess(r.index('Royal Paladin'),r.index('Elder Druid'))
        self.assertLess(r.index('Artututs'),r.index('Guardia Nevery'),'ordem alfabética dentro da vocação');self.assertIn('Perto Rp',r);self.assertIn('Perto Ed',r)

    def test_pt_filtro_e_mensagens(self):
        b=party_bot()
        self.assertIn('Use:',b.handle('!pt','',TODAY));self.assertIn('Não encontrei',b.handle('!pt Fantasma','',TODAY))
        self.assertIn('Ninguém online na faixa',b.handle('!pt Zandao em','',TODAY));self.assertIn('filtro RP',b.handle('!pt Zandao rp','',TODAY))

    def test_pt_limita_por_vocacao(self):
        many=[{'name':f'Jogador{i:02d}','level':600,'vocation':'Elite Knight'} for i in range(12)]
        r=party_bot(online=lambda w:[{'name':'Zandao','level':524,'vocation':'Master Sorcerer'},*many]).handle('!pt Zandao ek','',TODAY)
        self.assertEqual(r.count('· 🟢'),8);self.assertIn('…e mais 4',r)

    def test_online_mundo_no_padrao(self):
        r=party_bot().handle('!online Rasteibra','',TODAY)
        self.assertEqual(r.split('\n'),['🟢 *Rasteibra* — Online','👥 *206* jogadores online agora','📍 South America · ⚔️ Open PvP'])
        self.assertIn('206',party_bot().handle('!online','Rasteibra',TODAY))

    def test_online_de_guild_e_erros(self):
        r=party_bot().handle('!online Xandebro','',TODAY)
        self.assertIn('🟢 *Xandebro* online (2 de 3)',r);self.assertLess(r.index('Bia'),r.index('Ana'));self.assertNotIn('Cid',r)
        self.assertIn('Não encontrei o mundo ou a guild',party_bot().handle('!online Inexistente','',TODAY));self.assertIn('Use:',party_bot().handle('!online 12','',TODAY))

    def test_xptop_sem_historico_e_com_historico(self):
        r=party_bot().handle('!xptop Zandao','',TODAY)
        self.assertIn('📈 *XP — últimos 30 dias*',r);self.assertIn('📅 até 22/10',r);self.assertIn('📜 *Zandao*',r);self.assertIn('Ainda sem dados diários',r)
        self.assertIn('30 dias: *800,00kk* (média 26,67kk/dia)',r)
        rows=[('2026-10-22',524,30_000_000),('2026-10-21',523,25_000_000),('2026-10-20',522,-5_000_000),('2026-10-18',520,9_000_000)]
        r=party_bot(daily=lambda w,n:rows).handle('!xptop Zandao','',TODAY)
        self.assertIn('22/10 — Lv *524* — 30,00kk 📈',r);self.assertIn('21/10 — Lv *523* — 25,00kk 📈',r);self.assertIn('20/10 — Lv *522* — -5,00kk 💀',r)
        self.assertIn('18/10 — Lv *520* — 9,00kk',r);self.assertNotIn('19/10',r);self.assertIn('Sem dados antes de 18/10',r)
        self.assertIn('Não encontrei',party_bot().handle('!xptop Fantasma','',TODAY))

    def test_help_lista_todos(self):
        for comando in ('!help','!duelo','!evolucao','!precocoin','!pt','!char','!online','!xptop','!set','!alerta','!set cooldown','!alerta guild','!bomdia on/off','!bomdia horario','https://tibia-tudo.web.app'): self.assertIn(comando,HELP)

NOW=datetime(2026,10,23,15,tzinfo=UTC)  # 17h em Berlim: depois do server save e do meio-dia
def item(text,id_='m1',sender='s1',group='fake-group'): return {'id':id_,'group':group,'sender':sender,'text':text}

class CommanderTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/'s.sqlite',Fernet.generate_key(),open_access=True);self.transport=FakeTransport()
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
        self.group();self.commander.maintain(datetime(2026,10,23,9,tzinfo=UTC))
        self.assertEqual([f for f in self.fetches if f[1]==0 and False],[]);antes_do_meio_dia=len(self.fetches)
        with self.store.tx() as db: self.assertEqual(db.execute('SELECT count(*) FROM rank_history').fetchone()[0],0,'antes do meio-dia em Berlim não grava')
        self.commander.maintain(NOW)
        with self.store.tx() as db: rows=db.execute('SELECT day,name,xp FROM rank_history ORDER BY name').fetchall()
        self.assertEqual({r['day'] for r in rows},{'2026-10-22'});self.assertEqual(len(rows),3)
        with self.store.tx() as db: gravado=db.execute('SELECT count(*) FROM rank_history').fetchone()[0]
        self.commander.maintain(NOW+timedelta(minutes=5))
        with self.store.tx() as db: self.assertEqual(db.execute('SELECT count(*) FROM rank_history').fetchone()[0],gravado,'já gravou hoje')
        self.assertEqual(self.commander.history('Tornabra','papelaum meliexp'),[('2026-10-22',153_970_000)])

    def test_mundo_consultado_passa_a_ter_historico(self):
        self.group();self.commander.track('Antica')
        with self.store.tx() as db: self.assertIn('Antica',[r['world'] for r in db.execute('SELECT world FROM rank_meta')])

class ConfigTests(unittest.TestCase):
    def test_validacao(self):
        self.assertEqual(validate_botgroup({'world':' rasteibra '}),{'world':'Rasteibra','cooldown':30,'groupConfig':True})
        self.assertEqual(validate_botgroup({'world':'Antica','cooldown':3,'groupConfig':False}),{'world':'Antica','cooldown':3,'groupConfig':False})
        self.assertEqual(validate_botgroup({'world':'Antica','cooldown':86400})['cooldown'],86400)
        for bad in ({},{'world':'1'},{'world':'Antica','cooldown':2},{'world':'Antica','cooldown':86401},{'world':'Antica','cooldown':'30'},{'world':'Antica','groupConfig':'sim'}):
            with self.assertRaises(Invalid): validate_botgroup(bad)

    def test_api_dono_isolamento_grupo_unico_e_exclusao(self):
        from fastapi.testclient import TestClient
        from automation.api import create_app
        from automation.auth import Verifier
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        store=Store(Path(tmp.name)/'s.sqlite',Fernet.generate_key(),open_access=True);transport=FakeTransport();verifier=Verifier(store)
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
        with p: self.assertEqual(t.inbox('a'*32),[{**good,'admin':False}])
        t,p=self.transport(lambda r:httpx.Response(200,json={'messages':[{**good,'admin':True},{**good,'id':'m2','admin':'sim'},{**good,'id':'m3','extra':1}],'simulated':False}))
        with p: self.assertEqual([(i['id'],i['admin']) for i in t.inbox('a'*32)],[('m1',True),('m2',False),('m3',False)],'só o booleano verdadeiro vale; campo estranho some')

    def test_simulado_desconectado_ou_com_erro_devolve_vazio(self):
        t,p=self.transport(lambda r:httpx.Response(200,json={'messages':[{'id':'m','group':'g','sender':'s','text':'!help'}],'simulated':True}))
        with p: self.assertEqual(t.inbox('a'*32),[])
        t,p=self.transport(lambda r:httpx.Response(200,json={'messages':[]}),resume_state='disconnected')
        with p: self.assertEqual(t.inbox('a'*32),[])
        t,p=self.transport(lambda r:httpx.Response(500,json={'error':'x'}))
        with p: self.assertEqual(t.inbox('a'*32),[])

if __name__=='__main__':unittest.main()
