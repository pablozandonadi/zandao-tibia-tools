import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import assistente_tibiano as a

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
CTX = {'character_id': 'Teste', 'world_id': 'Antica', 'level': 438}

class StoreCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        (self.path/'meus_personagens.json').write_text(json.dumps({'atual':'Teste','lista':[{'nome':'Teste','mundo':'Antica','level':438},{'nome':'Outro','mundo':'Secura','level':200}]}))
        self.store = a.Store(self.path, clock=lambda: NOW)
    def call(self, intent, arguments=None, request_id=None, context=None):
        return self.store.execute(intent, arguments or {}, context or CTX, request_id)

class StoreTests(StoreCase):
    def test_stamina_alarm_phrases_are_local_and_queries_stay_read_only(self):
        for text in ('criar alarme quando minha stamina estiver cheia','crie um timer quando minha stamina estiver full','me avisa quando minha stamina chegar a 42 horas','avise quando a stamina estiver cheia'):
            self.assertEqual(('stamina.alert',{'target_stamina_minutes':2520}),a.parse(text,NOW))
        with self.assertRaises(ValueError):a.parse('criar alarme quando minha stamina estiver cheia ou calcula 39h',NOW)
        self.assertEqual(('alert.cancel',{}),a.parse('cancelar alarme da stamina',NOW))
        self.assertEqual('stamina.time_to',a.parse('quando minha stamina estará cheia',NOW)[0])

    def test_stamina_alarm_derived_deduplicated_scoped_and_persisted(self):
        with self.assertRaisesRegex(ValueError,'Registre stamina'):self.call('stamina.alert',{'target_stamina_minutes':2520})
        self.call('stamina.logout',{'stamina_minutes':2290})
        result=self.call(*a.parse('criar alarme quando minha stamina estiver cheia',NOW))
        alert=result['alert'];self.assertEqual(2290,alert['reference']['stamina_minutes'])
        self.assertIn('38h10',a.reply(result));self.assertIn('faltam',a.reply(result))
        self.assertEqual(alert['id'],self.call('stamina.alert',{'target_stamina_minutes':2520})['alert']['id'])
        self.assertEqual(1,len(self.call('timer.list')['stamina_alerts']))
        with self.assertRaises(ValueError):self.call('alert.cancel',{'alert_id':alert['id']},context={'character_id':'Outro','world_id':'Secura'})
        future=a.Store(self.path,clock=lambda:a.instant(alert['at'])+timedelta(seconds=1))
        self.assertEqual(1,len(future.poll()));self.assertEqual([],a.Store(self.path,clock=future.clock).poll())
        self.assertEqual([],future.execute('timer.list',{},CTX)['stamina_alerts'])

    def test_reopened_silent_service_reconciles_due_stamina_and_timer_once(self):
        from voz import Servico
        self.call('stamina.logout',{'stamina_minutes':2290})
        alert=self.call('stamina.alert',{'target_stamina_minutes':2520})['alert']
        self.call('timer.create',{'duration_seconds':30})
        restored=a.Store(self.path,clock=lambda:a.instant(alert['at'])+timedelta(seconds=1))
        notifications=[]
        with patch('voz.threading.Thread'):
            service=Servico(self.path,store=restored,silencioso=True,notificador=notifications.append)
        with patch.object(service._stop,'wait',side_effect=[False,False,False,False,True]):service._watch()
        self.assertEqual(2,len(notifications));self.assertEqual([],restored.poll())
        self.assertIsNone(service._mic)
        service.close()

    def test_stamina_reference_changes_cancel_and_full_does_not_schedule(self):
        for action in ('stamina.correct','stamina.logout','stamina.login'):
            self.call('stamina.logout',{'stamina_minutes':2290})
            self.call('stamina.alert',{'target_stamina_minutes':2520})
            self.call(action,{} if action=='stamina.login' else {'stamina_minutes':2280})
            self.assertEqual([],self.call('timer.list')['stamina_alerts'])
        with self.assertRaisesRegex(ValueError,'online'):self.call('stamina.alert',{'target_stamina_minutes':2520})
        self.call('stamina.logout',{'stamina_minutes':2520})
        self.assertTrue(self.call('stamina.alert',{'target_stamina_minutes':2520})['already_reached'])
        self.assertEqual([],self.store.poll())
        self.call('stamina.correct',{'stamina_minutes':2290})
        alert=self.call('stamina.alert',{'target_stamina_minutes':2520})['alert']
        self.call('alert.cancel',{'alert_id':alert['id']})
        self.assertEqual([],self.call('timer.list')['stamina_alerts'])
        self.assertEqual('alert.cancel',self.call('history')['events'][-1]['intent'])

    def test_market_pair_validates_both_prices_before_any_mutation(self):
        self.call('market.price.add',{'item':'TC','price':'46k'})
        original=(self.path/'assistente-tibiano.json').read_bytes()
        for invalid in ('0','inválido','-10'):
            with self.assertRaises(ValueError):self.call('market.price.add_pair',{'item':'TC','buy_price':'45k','sell_price':invalid})
            self.assertEqual(original,(self.path/'assistente-tibiano.json').read_bytes())
        with self.assertRaises(ValueError):self.call('market.price.add_pair',{'item':'TC','buy_price':'45k','sell_price':'46k','observed_at':(NOW+timedelta(minutes=1)).isoformat()})
        self.assertEqual(original,(self.path/'assistente-tibiano.json').read_bytes())

    def test_market_pair_atomic_replay_audit_and_world_isolation(self):
        args={'item':'TC','buy_price':'47k','sell_price':'46k'}
        result=self.call('market.price.add_pair',args,'pair-one')
        self.assertEqual(result,self.call('market.price.add_pair',args,'pair-one'))
        self.assertEqual(['buy','sell'],[r['offer_type'] for r in result['observations']])
        self.assertEqual([47000,46000],[r['price_gp'] for r in result['observations']])
        self.assertEqual(1,len({r['at'] for r in result['observations']}))
        self.assertEqual(2,self.store.market_prices('Antica')['total'])
        self.assertEqual(0,self.store.market_prices('Secura')['total'])
        event=self.call('history')['events'][-1]
        self.assertEqual([r['id'] for r in result['observations']],event['observation_ids'])
        self.assertTrue(all(r['event_id']==event['id'] and r['source']=='manual' for r in result['observations']))
        with self.assertRaises(ValueError):self.call('market.price.add_pair',{**args,'sell_price':'48k'},'pair-one')
        self.call('market.price.correct',{'observation_id':result['observations'][0]['id'],'price':'48k','reason':'Digitado errado'})
        self.assertEqual(48000,next(r for r in self.store.market_prices('Antica')['observations'] if r['offer_type']=='buy')['price_gp'])

    def test_market_pair_matches_alerts_for_both_sides(self):
        self.call('market.alert.create',{'item':'TC','offer_type':'buy','direction':'below','price':'46k'})
        self.call('market.alert.create',{'item':'TC','offer_type':'sell','direction':'above','price':'46k'})
        self.call('market.alert.create',{'item':'TC','offer_type':'buy','direction':'below','price':'46k'},context={'character_id':'Outro','world_id':'Secura'})
        self.call('market.price.add_pair',{'item':'TC','buy_price':'45k','sell_price':'47k'})
        self.assertEqual(2,len(self.store.poll()));self.assertEqual([],self.store.poll())
        alerts=self.call('market.alert.list',context={'character_id':'Outro','world_id':'Secura'})['alerts']
        self.assertIsNone(alerts[0]['matched_at'])

    def test_market_list_is_local_read_only_world_scoped_and_includes_other_characters(self):
        first = self.call('market.price.add', {'item':'TC','price':'46k'})['observation']
        self.call('market.price.add', {'item':'TC','price':'47k'}, context={'character_id':'Outro','world_id':'Secura'})
        second = self.call('market.price.add', {'item':'Gold Token','price':'40k'})['observation']
        before = (self.path/'assistente-tibiano.json').read_bytes()
        rows = self.store.market_prices('Antica')
        self.assertEqual([second['id'], first['id']], [row['id'] for row in rows['observations']])
        self.assertEqual(before, (self.path/'assistente-tibiano.json').read_bytes())
        self.assertEqual('Secura', self.store.market_prices('Secura')['observations'][0]['world_id'])
        self.assertEqual(0, self.store.market_prices('Premia')['total'])
        self.call('market.price.correct', {'observation_id':first['id'],'price':'48k','reason':'Correção'})
        self.assertEqual(48000, self.store.market_prices('Antica')['observations'][1]['price_gp'])
        self.call('market.price.delete', {'observation_id':second['id'],'reason':'Duplicado'})
        self.assertEqual(1, self.store.market_prices('Antica')['total'])

    def test_market_cards_include_watched_and_saved_items_full_scoped_history(self):
        self.call('market.price.add',{'item':'Rope Belt','price':'10k','offer_type':'buy'})
        self.call('market.price.add',{'item':'Rope Belt','price':'11k','offer_type':'sell'})
        self.call('market.item.watch',{'item':'Dragon Ham'})
        result=self.store.market_prices('Antica')
        items={row['item']:row for row in result['items']}
        self.assertIn('Dragon Ham',items);self.assertEqual(0,items['Dragon Ham']['total'])
        self.assertEqual(10000,items['Rope Belt']['latest']['buy']['price_gp'])
        self.assertEqual(11000,items['Rope Belt']['latest']['sell']['price_gp'])
        self.assertNotIn('Rope Belt',[row['item'] for row in self.store.market_prices('Secura')['items']])

    def test_market_list_reports_limit_and_sorts_observation_time(self):
        for index in range(102):
            self.call('market.price.add', {'item':f'Item {index}','price':100,'observed_at':(NOW-timedelta(minutes=102-index)).isoformat()})
        result = self.store.market_prices('Antica')
        self.assertEqual((102, 100), (result['total'], len(result['observations'])))
        self.assertEqual('Item 101', result['observations'][0]['item'])
        self.assertEqual('Item 2', result['observations'][-1]['item'])

    def test_timer_restart_idempotence_and_one_alert(self):
        x = self.call('timer.create', {'duration_seconds':30,'label':'boost'}, 'r1')
        self.assertEqual(x, self.call('timer.create', {'duration_seconds':30,'label':'boost'}, 'r1'))
        with self.assertRaises(ValueError): self.call('timer.create', {'duration_seconds':40}, 'r1')
        later = a.Store(self.path, clock=lambda: NOW+timedelta(seconds=31))
        self.assertEqual(1, len(later.poll()))
        self.assertEqual([], a.Store(self.path, clock=lambda: NOW+timedelta(seconds=32)).poll())
        self.assertEqual('completed', later.execute('timer.list',{},CTX)['timers'][0]['status'])
    def test_ambiguous_timer_does_not_cancel_and_repeat_new_id(self):
        first = self.call('timer.create', {'duration_seconds':90})['timer']
        self.call('timer.create', {'duration_seconds':90})
        with self.assertRaises(ValueError): self.call('timer.cancel', {'duration_seconds':90})
        self.call('timer.extend', {'timer_id':first['id'],'delta_seconds':60})
        self.assertNotEqual(first['id'], self.call('timer.repeat',{'timer_id':first['id']})['timer']['id'])
    def test_failed_io_does_not_change_memory(self):
        self.call('timer.create', {'duration_seconds':30})
        with patch('assistente_tibiano.os.replace', side_effect=OSError('disk')):
            with self.assertRaises(OSError): self.call('timer.create', {'duration_seconds':40})
        self.assertEqual(1, len(self.call('timer.list')['timers']))
    def test_corrupt_file_is_preserved(self):
        p=self.path/'assistente-tibiano.json';p.write_text('{bad')
        with self.assertRaises(ValueError): a.Store(self.path)
        self.assertEqual('{bad',p.read_text())
    def test_shared_party_and_hypothesis_do_not_write(self):
        self.assertEqual([292,657],self.call('shared.range')['range'])
        self.assertTrue(self.call('shared.check',{'party_levels':[200,300]})['compatible'])
        self.assertFalse(self.call('shared.check',{'party_levels':[199,300]})['compatible'])
        self.assertEqual([67,150],self.call('shared.range',{'reference_level':100})['range'])
        self.assertFalse((self.path/'assistente-tibiano.json').exists())
    def test_boss_atomic_boost_undo_and_profile_isolation(self):
        k=self.call('boss.kill',{'boss_id':'oberon','boosted':True},'kill1')['boss']
        self.assertEqual((1,3,(NOW+timedelta(hours=20)).isoformat()),(k['real_kills'],k['progress'],k['available_at']))
        self.assertEqual(0,self.call('bosstiary.get',{'boss_id':'oberon'},context={'character_id':'Outro','world_id':'Secura'})['boss']['real_kills'])
        self.call('bosstiary.set_total',{'boss_id':'oberon','total_kills':87})
        self.call('boss.kill.undo',{'boss_id':'oberon'})
        self.assertEqual(0,self.call('bosstiary.get',{'boss_id':'oberon'})['boss']['real_kills'])
        self.assertEqual(84,self.call('bosstiary.get',{'boss_id':'oberon'})['boss']['progress'])
    def test_boss_correction_does_not_add_kill(self):
        self.call('boss.kill',{'boss_id':'drume'})
        self.call('boss.kill.correct_time',{'boss_id':'drume','corrected_at':'2026-10-16T10:00:00+00:00'})
        x=self.call('bosstiary.get',{'boss_id':'drume'})['boss']
        self.assertEqual(1,x['real_kills']);self.assertEqual('2026-10-16T10:00:00+00:00',x['last_killed_at'])
    def test_deleted_profile_rejected(self):
        with self.assertRaises(ValueError): self.call('boss.kill',{'boss_id':'drume'},context={'character_id':'Deleted','world_id':'Antica'})
    def test_stamina_thresholds_projection_reverse_login(self):
        self.call('stamina.logout',{'stamina_minutes':2280,'logged_out_at':NOW.isoformat()})
        self.assertEqual('2026-10-16T15:10:00+00:00',self.call('stamina.time_to',{'target_stamina_minutes':2340})['at'])
        self.assertEqual('2026-10-17T09:10:00+00:00',self.call('stamina.time_to',{'target_stamina_minutes':2520})['at'])
        self.assertEqual(2340,self.call('stamina.project',{'target_datetime':'2026-10-16T15:10:00+00:00'})['stamina_minutes'])
        self.call('stamina.login',{'logged_in_at':'2026-10-16T12:00:00+00:00'})
        with self.assertRaises(ValueError): self.call('stamina.project',{'target_datetime':'2026-10-17T12:00:00+00:00'})
    def test_market_price_world_offer_correction_and_readonly(self):
        for raw,want in [('35k',35000),('36,5k',36500),('1.5kk',1500000),('2,75kk',2750000)]: self.assertEqual(want,a.price_gp(raw))
        for bad in ['1.500','0','-5','nan','1 k kk']:
            with self.assertRaises(ValueError): a.price_gp(bad)
        x=self.call('market.price.add',{'item':'TC','price':'35k','offer_type':'buy'})['observation']
        self.call('market.price.add',{'item':'TC','price':'90k','offer_type':'sell'})
        before=(self.path/'assistente-tibiano.json').read_bytes()
        stats=self.call('market.stats',{'item':'TC','offer_type':'buy','days':30})
        self.assertEqual((1,35000,True),(stats['count'],stats['median'],stats['insufficient']))
        self.assertEqual(before,(self.path/'assistente-tibiano.json').read_bytes())
        self.assertEqual(0,self.call('market.stats',{'item':'TC','offer_type':'buy'},context={'character_id':'Outro','world_id':'Secura'})['count'])
        self.call('market.price.correct',{'observation_id':x['id'],'price':'38k','reason':'digitação'})
        self.assertEqual(38000,self.call('market.stats',{'item':'TC','offer_type':'buy'})['median'])
        self.assertGreater(len(self.call('history')['events']),0)

if __name__ == '__main__': unittest.main()

class ParserTests(StoreCase):
    def test_voice_domains_and_negations(self):
        cases=[('inicia um timer chamado boost de 45 minutos','timer.create',{'duration_seconds':2700,'label':'boost'}),
               ('matei o Drume há meia hora','boss.kill',{'boss_id':'Drume','killed_at':'2026-10-16T11:30:00+00:00'}),
               ('atualiza meu Oberon para 87 kills','bosstiary.set_total',{'boss_id':'Oberon','total_kills':87}),
               ('Gold Token a 40k tá caro?','market.stats',{'item':'Gold Token','price':'40k','offer_type':'sell'}),
               ('TC tá 1.5kk','market.price.add',{'item':'TC','price':'1.5kk','offer_type':'sell'}),
               ('estou deslogando agora minha stamina está em 38 horas','stamina.logout',{'stamina_minutes':2280,'logged_out_at':NOW.isoformat()})]
        for text,action,args in cases:
            self.assertEqual((action,args),a.parse(text,NOW),text)
        for text in ['não matei Oberon','sem registrar TC tá 35k','jamais cancela timer']:
            with self.assertRaises(ValueError):a.parse(text,NOW)
        self.assertEqual('2026-10-17T17:00:00+00:00',a.local_datetime('amanhã às 13',NOW))
    def test_asr_time_requires_a_duration(self):
        self.assertEqual(('timer.create', {'duration_seconds':1800}), a.parse('time trinta minutos', NOW))
        self.assertIsNone(a.parse('time', NOW))
        with self.assertRaises(ValueError): a.parse('time de futebol', NOW)

    def test_descriptions_cover_actions_and_human_units(self):
        self.assertEqual(set(a.LABELS),set(a.FIELDS))
        self.assertEqual(a.describe('stamina.time_to',{'target_stamina_minutes':2520}),'Quando a stamina chega a · 42h00')
        self.assertEqual(a.describe('timer.create',{'duration_seconds':300}),'Criar timer · 5 min')
        self.assertIn('Registrar abate',a.describe('boss.kill',{'boss_id':'drume'}))

    def test_chat_ranges_are_not_prices_and_short_durations_are_exact(self):
        self.assertIsNone(a.parse('qual hunt é boa do level 300 a 400',NOW))
        for phrase,seconds in [('timer de 5 min',300),('timer 30s',30),('timer 1h30',5400),('alarme 45 min',2700),('timer 5m',300),('timer 30seg',30)]:
            self.assertEqual(a.parse(phrase,NOW),('timer.create',{'duration_seconds':seconds}))
        for phrase in ('timer -5min','timer −5min','timer 1h60'):
            with self.assertRaises(ValueError):a.parse(phrase,NOW)

    def test_unknown_actions_and_extra_fields_cannot_write(self):
        with self.assertRaises(ValueError):self.call('timer.create',{'duration_seconds':30,'arbitrary':True})
        self.assertFalse((self.path/'assistente-tibiano.json').exists())

class IntegrationTests(StoreCase):
    def test_voice_and_manual_use_same_store_without_duplicate_lists(self):
        import voz
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        self.assertIn('iniciado',service.comando('timer de 30 segundos'))
        self.assertEqual(1,len(service.estado()['timers']))
        self.assertEqual(1,len(self.call('timer.list')['timers']))
        self.assertIn('cancelado',service.comando('cancela o ultimo timer'))
        self.assertEqual([],service.estado()['timers'])
    def test_asr_time_from_wake_reaches_shared_store(self):
        import voz
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'),patch('voz.play_wake_sound') as ding:
            service=voz.Servico(self.path,store=self.store)
            self.addCleanup(service.close)
            service.receber_texto('hei tíbia tudo time trinta minutos')
            ding.assert_called_once()
        timers=self.call('timer.list')['timers']
        self.assertEqual(1,len(timers))
        self.assertEqual(1800,timers[0]['duration_seconds'])
        self.assertEqual(1,len(service.estado()['timers']))

    def test_direct_mode_captures_each_command_context(self):
        import voz
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        service._ready.set()
        service.escutar()
        service.receber_texto('matei o Drume agora')
        path=self.path/'meus_personagens.json'
        data=json.loads(path.read_text());data['atual']='Outro';path.write_text(json.dumps(data))
        service.receber_texto('matei o Drume agora')
        self.assertEqual(1,self.call('bosstiary.get',{'boss_id':'drume'})['boss']['real_kills'])
        self.assertEqual(1,self.call('bosstiary.get',{'boss_id':'drume'},context={'character_id':'Outro','world_id':'Secura'})['boss']['real_kills'])

    def test_vocabulary_tracks_ui_voice_expiry_and_profile_without_double_execution(self):
        import voz
        import web_api
        from unittest.mock import Mock
        from voice.remote_ai_client import RemoteAIClient
        import struct
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        api=object.__new__(web_api.API)
        api._voz_obter=lambda:service
        with patch('voz.time.monotonic',return_value=100):
            service.comando('matei o Drume agora')
            self.assertEqual(service._recentes, {'Drume':100})
            with patch.object(self.store,'execute',wraps=self.store.execute) as execute:
                result=api.assistente_executar('boss.kill',{'boss_id':'oberon'},CTX)
                execute.assert_called_once()
            self.assertEqual(result['boss']['real_kills'],1)
            self.assertIn('Drume',service.estado()['entendi'])
            self.assertEqual(service._vocabulario(CTX)[:2],['Drume','Grand Master Oberon'])
        with patch('voz.time.monotonic',return_value=3701):
            service._vocabulario(CTX)
            self.assertEqual(service._recentes,{})
        other={'character_id':'Outro','world_id':'Secura'}
        with patch('voz.time.monotonic',return_value=4000):
            service.registrar_resultado('bosstiary.get',{'boss_id':'oberon'},result,CTX)
            self.assertNotIn('Grand Master Oberon',service._vocabulario(other))
            self.assertEqual(service._recentes,{})
        client=Mock(spec=RemoteAIClient)
        client.transcribe.return_value='quantas kills tenho no Drume'
        service._online_client=client;service._online_enabled=True
        service._ready.set();service.escutar()
        def transcribe(wav,rid,terms):
            self.assertIn('Drume',terms)
            path=self.path/'meus_personagens.json'
            data=json.loads(path.read_text());data['atual']='Outro';path.write_text(json.dumps(data))
            return 'quantas kills tenho no Drume'
        client.transcribe.side_effect=transcribe
        service.receber_audio('unk',struct.pack('<h',1000)*16000,16000)
        client.transcribe.assert_called_once()
        self.assertIn('Drume',service.estado()['entendi'])
        self.assertIn('1 abates reais',service.estado()['resposta'])
        self.assertNotIn('Drume',service._vocabulario(other))

    def test_manual_action_updates_vocabulary_without_mixing_voice_feedback(self):
        import voz
        import web_api
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        with patch('voz.play_wake_sound'):
            service.receber_texto('hey tibia tudo matei o Drume agora')
        fields=('ouvi','entendi','resposta')
        before={key:service.estado()[key] for key in fields}
        self.assertIn('Drume',before['ouvi'])
        self.assertTrue(before['entendi'].startswith('Registrar abate · Drume'))
        self.assertIn('Drume',before['resposta'])
        api=object.__new__(web_api.API)
        api._voz_obter=lambda:service
        result=api.assistente_executar('boss.kill',{'boss_id':'oberon'},CTX)
        self.assertEqual(result['boss']['real_kills'],1)
        self.assertIn('Grand Master Oberon',service._recentes)
        self.assertEqual(before,{key:service.estado()[key] for key in fields})

    def test_entendi_and_recent_boss_on_domain_nlu(self):
        import voz
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        reply=service._intent_reply({'action':'boss.kill','parameters':{'boss_id':'drumi','boosted':False,'killed_at':None},'needs_clarification':False,'clarification':None})
        self.assertIn('Drume',reply)
        self.assertEqual(service.estado()['entendi'],'Registrar abate · Drume')
        self.assertIn('Drume',service._recentes)

    def test_intent_reply_with_store_keeps_voice_source_and_legacy_actions(self):
        import voz
        from voice.spike_assistente import UNKNOWN_REPLY
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        intent=lambda action,parameters:{'action':action,'parameters':parameters,'needs_clarification':False,'clarification':None}
        service._intent_reply(intent('market.price.add',{'item':'TC','price':'35k','offer_type':'sell','observed_at':None}))
        self.assertEqual('voice',self.call('history')['events'][-1]['source'])
        self.assertEqual('Timer de 30 segundos iniciado.',service._intent_reply(intent('create_timer',{'seconds':30})))
        self.assertEqual('Criar timer · 30 s',service.estado()['entendi'])
        self.assertIn('Seu shared vai do level 67',service._intent_reply(intent('shared',{'level':100})))
        self.assertEqual('Consultar shared · level 100',service.estado()['entendi'])
        self.assertEqual('Timer de 30 segundos cancelado.',service._intent_reply(intent('cancel_last_timer',{})))
        self.assertEqual(UNKNOWN_REPLY,service._intent_reply(intent('unknown',{})))
        self.assertEqual('',service.estado()['entendi'])
        self.assertIn('nenhum abate foi registrado',service._intent_reply(intent('boss.kill',{'boss_id':'drume','killed_at':None,'boosted':True})))

    def test_user_spoken_phrases_execute_locally_in_temporary_profile(self):
        import voz
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        cases=[('matei drume','boss.kill',{'boss_id':'drume','killed_at':NOW.isoformat()},'Drume'),
               ('matei oberom','boss.kill',{'boss_id':'oberom','killed_at':NOW.isoformat()},'Grand Master Oberon'),
               ('minha stamina esta 39 horas','stamina.correct',{'stamina_minutes':2340,'reference_at':NOW.isoformat()},None)]
        for phrase,intent,args,boss in cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(a.parse(phrase,NOW),(intent,args))
                reply=service.comando(phrase)
                if boss:
                    self.assertIn(boss,reply)
                    self.assertEqual(self.call('bosstiary.get',{'boss_id':boss})['boss']['real_kills'],1)
                else:
                    self.assertIn('registrada',reply)
                    stamina=self.call('stamina.get')['stamina']
                    self.assertEqual(stamina['stamina_minutes'],2340)
                    self.assertEqual(stamina['reference_at'],NOW.isoformat())
        for boss in ('drume','oberon'):
            self.assertEqual(self.call('bosstiary.get',{'boss_id':boss},context={'character_id':'Outro','world_id':'Secura'})['boss']['real_kills'],0)

    def test_captured_context_survives_profile_change(self):
        import voz
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        service._command_context=CTX.copy()
        path=self.path/'meus_personagens.json';data=json.loads(path.read_text());data['atual']='Outro';path.write_text(json.dumps(data))
        service.comando('matei o Drume agora')
        self.assertEqual(1,self.call('bosstiary.get',{'boss_id':'drume'})['boss']['real_kills'])
        self.assertEqual(0,self.call('bosstiary.get',{'boss_id':'drume'},context={'character_id':'Outro','world_id':'Secura'})['boss']['real_kills'])

class IntegrityTests(StoreCase):
    def test_size_limit_rejects_write_without_breaking_previous_state(self):
        self.call('timer.create',{'duration_seconds':30},'first')
        before=(self.path/'assistente-tibiano.json').read_bytes()
        with patch('assistente_tibiano.MAX_STORE_BYTES',len(before)+50):
            with self.assertRaises(ValueError):self.call('timer.create',{'duration_seconds':40},'second')
        self.assertEqual(before,(self.path/'assistente-tibiano.json').read_bytes())
        self.assertEqual(1,len(a.Store(self.path).execute('timer.list',{},CTX)['timers']))
    def test_market_correction_and_delete_audit_keeps_before_and_after(self):
        obs=self.call('market.price.add',{'item':'TC','price':'35k'})['observation']
        self.call('market.price.correct',{'observation_id':obs['id'],'price':'38k','reason':'digitação'})
        event=self.call('history')['events'][-1]
        self.assertEqual(35000,event['before']['price_gp']);self.assertEqual(38000,event['after']['price_gp'])
        self.call('market.price.delete',{'observation_id':obs['id'],'reason':'duplicado'})
        event=self.call('history')['events'][-1]
        self.assertFalse(event['before']['deleted']);self.assertTrue(event['after']['deleted'])
    def test_login_invalidates_estimated_stamina_alert(self):
        self.call('stamina.logout',{'stamina_minutes':2280})
        self.call('stamina.alert',{'target_stamina_minutes':2340})
        self.call('stamina.login')
        self.assertEqual([],a.Store(self.path,clock=lambda:NOW+timedelta(days=2)).poll())

class CorruptionTests(StoreCase):
    def test_all_collections_fail_closed_on_corruption(self):
        self.call('timer.create',{'duration_seconds':30})
        path=self.path/'assistente-tibiano.json';base=json.loads(path.read_text())
        broken=[('kills',[{'id':'broken'}]),('alerts',[{'kind':'market','fired':False}]),('stamina',{'Teste':{'offline':'yes'}}),('totals',{'Teste':{'drume':-1}}),('catalog',[{'boss_id':'bad'}]),('requests',{'r':{'hash':3}}),('events',[{'intent':'unknown'}])]
        for key,value in broken:
            d=dict(base);d[key]=value;path.write_text(json.dumps(d));before=path.read_bytes()
            with self.subTest(key=key):
                with self.assertRaises(ValueError):a.Store(self.path).execute('timer.create',{'duration_seconds':40},CTX)
                self.assertEqual(before,path.read_bytes())

class AlertCycleTests(unittest.TestCase):
    def test_boss_correction_and_undo_reconcile_existing_alert(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'meus_personagens.json').write_text(json.dumps({'atual':'Teste','lista':[{'nome':'Teste','mundo':'Antica'}]}))
            store=a.Store(folder,clock=lambda:NOW)
            boss={'boss_id':'known','name':'Known','aliases':[],'category':'archfoe','cooldown_type':'fixed','cooldown_minutes':120,'source':'https://example.org/verified','verified_at':'2026-10-16','status':'verified'}
            store.execute('boss.catalog.import',{'bosses':[boss]},CTX)
            store.execute('boss.kill',{'boss_id':'known'},CTX)
            store.execute('boss.alert',{'boss_id':'known'},CTX)
            store.execute('boss.alert',{'boss_id':'known'},CTX)
            store.execute('boss.kill.correct_time',{'boss_id':'known','corrected_at':'2026-10-16T09:00:00+00:00'},CTX)
            self.assertEqual(1,len(store.poll()))
            store.execute('boss.kill',{'boss_id':'known'},CTX)
            store.execute('boss.kill.undo',{'boss_id':'known'},CTX)
            self.assertEqual([],a.Store(folder,clock=lambda:NOW+timedelta(days=1)).poll())

class ReviewRegressionTests(StoreCase):
    def test_correcting_fired_boss_alert_to_future_rearms_once(self):
        clock=[NOW];store=a.Store(self.path,clock=lambda:clock[0])
        b={'boss_id':'known','name':'Known','aliases':[],'category':'archfoe','cooldown_type':'fixed','cooldown_minutes':120,'source':'https://example.org/verified','verified_at':'2026-10-16','status':'verified'}
        store.execute('boss.catalog.import',{'bosses':[b]},CTX)
        store.execute('boss.kill',{'boss_id':'known'},CTX);store.execute('boss.alert',{'boss_id':'known'},CTX)
        clock[0]=NOW+timedelta(hours=3);self.assertEqual(1,len(store.poll()))
        store.execute('boss.kill.correct_time',{'boss_id':'known','corrected_at':(NOW+timedelta(hours=2)).isoformat()},CTX)
        self.assertEqual([],store.poll());clock[0]=NOW+timedelta(hours=5)
        self.assertEqual(1,len(store.poll()));self.assertEqual([],store.poll())
    def test_price_origin_is_trusted_caller_metadata(self):
        result=self.store.execute('market.price.add',{'item':'TC','price':'35k'},CTX,'voice-one',source='voice')
        self.assertEqual('voice',result['observation']['source'])
        self.assertEqual('voice',self.call('history')['events'][-1]['source'])
        self.assertEqual('manual',self.call('market.price.add',{'item':'TC','price':'36k'})['observation']['source'])
        with self.assertRaises(ValueError):self.call('market.price.add',{'item':'TC','price':'36k','source':'voice'})
    def test_extend_and_edit_reply_describes_change(self):
        t=self.call('timer.create',{'duration_seconds':30})['timer']
        self.assertIn('estendido',a.reply(self.call('timer.extend',{'timer_id':t['id'],'delta_seconds':60})))
        self.assertIn('alterado',a.reply(self.call('timer.edit',{'timer_id':t['id'],'label':'mudou'})))

class OriginPersistenceTests(StoreCase):
    def test_voice_origin_survives_reload_and_appears_in_audit(self):
        obs=self.store.execute('market.price.add',{'item':'TC','price':'35k'},CTX,'voice-reload',source='voice')['observation']
        reopened=a.Store(self.path,clock=lambda:NOW)
        row=reopened.execute('market.stats',{'item':'TC'},CTX)['observations'][0]
        self.assertEqual('voice',row['source'])
        event=reopened.execute('history',{},CTX)['events'][-1]
        self.assertEqual('voice',event['source'])
        self.assertEqual(obs['id'],event['entity_id'])
        self.assertEqual(event['id'],row['event_id'])

class FinishUpdateTests(StoreCase):
    def test_free_logout_speech_is_stamina_not_price(self):
        self.assertEqual(('stamina.logout',{'stamina_minutes':2460,'logged_out_at':NOW.isoformat()}),
                         a.parse('Vou fazer logout agora, minha estamina está em quarenta e uma horas.',NOW))
        self.assertEqual(2400,a.parse('deslogando, stamina 40h',NOW)[1]['stamina_minutes'])
        self.assertEqual(('stamina.correct',{'stamina_minutes':2400,'reference_at':NOW.isoformat()}),
                         a.parse('minha stamina ta 40 horas',NOW))
        self.assertIsNone(a.parse('o boss a caminho',NOW))
        with self.assertRaises(ValueError):a.parse('TC tá 1.500',NOW)
    def test_full_boss_catalog_with_spoken_alias(self):
        bosses=self.call('boss.catalog')['bosses']
        self.assertGreater(len(bosses),500)
        a.validate_state({**self.store._read(),'catalog':bosses})
        self.assertEqual('Drume',self.call('boss.kill',{'boss_id':'drumi'})['boss']['name'])
    def test_old_three_boss_file_keeps_kills_and_gains_catalog(self):
        self.call('boss.kill',{'boss_id':'drume'})
        path=self.path/'assistente-tibiano.json';d=json.loads(path.read_text())
        d['catalog']=[{**b,'aliases':['meu-apelido']} if b['boss_id']=='drume' else b for b in d['catalog'] if b['boss_id'] in ('drume','grand-master-oberon','scarlett-etzel')]
        path.write_text(json.dumps(d))
        store=a.Store(self.path,clock=lambda:NOW)
        self.assertEqual(1,store.execute('bosstiary.get',{'boss_id':'meu-apelido'},CTX)['boss']['real_kills'])
        self.assertEqual(1,store.execute('bosstiary.get',{'boss_id':'drumi'},CTX)['boss']['real_kills'])
        self.assertGreater(len(store.execute('boss.catalog',{},CTX)['bosses']),500)
    def test_cache_sees_writes_from_another_instance(self):
        self.call('timer.create',{'duration_seconds':30})
        a.Store(self.path,clock=lambda:NOW).execute('timer.create',{'duration_seconds':40},CTX)
        self.assertEqual(2,len(self.call('timer.list')['timers']))
    def online(self, transcript, intent=None):
        import struct,voz
        from unittest.mock import Mock
        from voice.remote_ai_client import RemoteAIClient
        with patch.object(voz.Servico,'_watch'),patch.object(voz.Servico,'_say_loop'):
            service=voz.Servico(self.path,store=self.store)
        self.addCleanup(service.close)
        client=Mock(spec=RemoteAIClient);client.transcribe.return_value=transcript;client.interpret.return_value=intent
        service._online_enabled=True;service._online_client=client;service._ready.set();service.escutar()
        service.receber_audio('',struct.pack('<h',1000)*16000,16000)
        return client,service
    def test_online_ai_understands_free_speech_first(self):
        intent={'action':'stamina.logout','parameters':{'stamina_minutes':2460,'logged_out_at':None},'needs_clarification':False,'clarification':None}
        client,_=self.online('vou sair do jogo, tô com 41 horas de stamina',intent)
        client.interpret.assert_called_once()
        self.assertEqual(2460,self.call('stamina.get')['stamina']['stamina_minutes'])
    def test_online_timer_stays_local_without_ai(self):
        client,_=self.online('timer de 30 segundos')
        client.interpret.assert_not_called()
        self.assertEqual(30,self.call('timer.list')['timers'][0]['duration_seconds'])
    def test_full_stamina_question_is_local(self):
        self.assertEqual(('stamina.time_to',{'target_stamina_minutes':2520}),a.parse('Quando minha estamina estará cheia?',NOW))
        self.assertEqual(2340,a.parse('quando a stamina fica verde',NOW)[1]['target_stamina_minutes'])
        client,_=self.online('Quando minha estamina estará cheia?')
        client.interpret.assert_not_called()
    def test_full_stamina_question_tolerates_typos(self):
        for text in ('a que horas minha stmina vai star full?','que horas minha estamina fica cheia','quando minha stamina estiver completa','Quando minha stmina vai ficar full'):
            with self.subTest(text=text):self.assertEqual(('stamina.time_to',{'target_stamina_minutes':2520}),a.parse(text,NOW))
    def test_market_item_drops_article_and_trailing_fillers(self):
        for text in ('a tc aqui ta 40k','o tc agora ta 40k','TC hoje tá 40k','a tc aqui no meu mundo ta 40k','registra a tc a 40k'):
            with self.subTest(text=text):
                intent,args=a.parse(text,NOW)
                self.assertEqual(('market.price.add','tc','40k'),(intent,args['item'].lower(),args['price']))
                self.assertEqual('Tibia Coin',self.call(intent,args)['observation']['item'])
        self.assertEqual('Gold Token',a.parse('um Gold Token ta 40k',NOW)[1]['item'])
    def test_online_ai_unsure_without_local_match_asks(self):
        intent={'action':'unknown','parameters':{},'needs_clarification':True,'clarification':'Qual boss?'}
        _,service=self.online('marca aquele boss la',intent)
        self.assertEqual('Qual boss?',service.estado()['resposta'])
    def test_every_phrase_in_instructions_is_understood(self):
        import html,re
        page=(Path(__file__).parent/'web'/'index.html').read_text(encoding='utf-8')
        section=page[page.index('id="assistente-instrucoes"'):]
        section=section[:section.index('</section>')]
        phrases=[html.unescape(p) for p in re.findall(r'<q>(.*?)</q>',section)]
        self.assertGreater(len(phrases),40)
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIsNotNone(a.parse(phrase,NOW))
    def test_wiki_cooldown_gives_release_time(self):
        boss=self.call('boss.kill',{'boss_id':'drume'})['boss']
        self.assertEqual((1200,'wiki'),(boss['cooldown_minutes'],boss['status']))
        self.assertEqual((NOW+timedelta(hours=20)).isoformat(),boss['available_at'])
        self.assertIn('Libera em 20h 0min',a.reply({'boss':boss}))
        self.assertIsNone(self.call('bosstiary.get',{'boss_id':'Ekatrix'})['boss']['cooldown_minutes'])
    def test_player_cooldown_by_voice_survives_reload(self):
        intent,args=a.parse('o cooldown do Black Knight é 2 horas',NOW)
        self.assertEqual(('boss.cooldown.set',120),(intent,args['cooldown_minutes']))
        self.call(intent,args)
        self.call('boss.kill',{'boss_id':'Black Knight'})
        boss=a.Store(self.path,clock=lambda:NOW).execute('bosstiary.get',{'boss_id':'black knight'},CTX)['boss']
        self.assertEqual((120,'player',(NOW+timedelta(hours=2)).isoformat()),(boss['cooldown_minutes'],boss['status'],boss['available_at']))
    def test_stamina_now_offline_and_online(self):
        self.call('stamina.logout',{'stamina_minutes':2280})
        later=a.Store(self.path,clock=lambda:NOW+timedelta(minutes=190))
        r=later.execute('stamina.get',{},CTX)
        self.assertEqual((2340,'2026-10-16T15:10:00+00:00','2026-10-17T09:10:00+00:00'),(r['estimate_minutes'],r['green_at'],r['full_at']))
        self.assertIn('Stamina estimada: 39h00',a.reply(r))
        later.execute('stamina.login',{},CTX)
        r=a.Store(self.path,clock=lambda:NOW+timedelta(minutes=250)).execute('stamina.get',{},CTX)
        self.assertEqual((2340,60),(r['stamina']['stamina_minutes'],r['online_minutes']))
        self.assertEqual(('stamina.get',{}),a.parse('Qual é minha stamina?',NOW))
    def test_span_matches_tibia_widget(self):
        self.assertEqual(['3h 12min','45min','2d 4h','1min'],[a.span(s) for s in (11520,2700,187200,5)])
    def test_instruction_phrases_tolerate_small_changes(self):
        import html,re
        page=(Path(__file__).parent/'web'/'index.html').read_text(encoding='utf-8')
        section=page[page.index('id="assistente-instrucoes"'):];section=section[:section.index('</section>')]
        for phrase in [html.unescape(p) for p in re.findall(r'<q>(.*?)</q>',section)]:
            first,_,rest=phrase.partition(' ')
            for variant in (f'{first}, {rest}',f'Eu {phrase}.',f'{phrase}, por favor',f'Ok, {phrase}!'):
                with self.subTest(variant=variant):
                    self.assertEqual(a.parse(phrase,NOW),a.parse(variant,NOW))
    def test_boss_names_are_forgiving_but_never_guess_between_two(self):
        name=lambda spoken:self.call('bosstiary.get',{'boss_id':spoken})['boss']['name']
        self.assertEqual('Scarlett Etzel',name('Scarlet Etzel'))
        self.assertEqual('Ferumbras Mortal Shell',name('mortal shell'))
        self.assertEqual('Grand Master Oberon',name('grand master oberon!'))
        with self.assertRaisesRegex(ValueError,'Você quis dizer'):name('Ferumbrass Shel')
        with self.assertRaisesRegex(ValueError,'Confira o nome'):name('xyzzy')
    def test_common_synonyms(self):
        self.assertEqual('boss.kill',a.parse('acabei de matar o Drume',NOW)[0])
        self.assertEqual('Drume',a.parse('fiz o Drume',NOW)[1]['boss_id'])
        self.assertEqual(('timer.create',{'duration_seconds':300}),a.parse('bota um timer de 5 minutos',NOW))
        self.assertEqual('stamina.login',a.parse('acabei de logar',NOW)[0])
        self.assertEqual(2400,a.parse('vou sair do jogo, minha stamina está em 40 horas',NOW)[1]['stamina_minutes'])
        self.assertEqual('36.5k',a.parse('TC tá 36.5k.',NOW)[1]['price'])
        self.assertEqual('market.price.add',a.parse('TC tá 36.5k',NOW)[0])
        self.assertEqual('market.stats',a.parse('Gold Token a 40k tá caro?',NOW)[0])
        for text in ('quanto tempo pra chegar a 300','como chegar a 400','compensa vender tc a 36k?','devo comprar tc a 40k','por quanto vendo tc a 35k?','o preço do tc ta 36k?','TC tá 36k?'):
            with self.subTest(text=text):self.assertIsNone(a.parse(text,NOW))
    def test_boss_view_has_bosstiary_goals(self):
        self.assertEqual([5,20,60],self.call('bosstiary.get',{'boss_id':'drume'})['boss']['goals'])
    def test_bridge_parameter_is_not_js_arguments(self):
        import inspect,web_api
        self.assertNotIn('arguments',inspect.signature(web_api.API.assistente_executar).parameters)
