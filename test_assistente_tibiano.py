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
        self.assertEqual((1,3,None),(k['real_kills'],k['progress'],k['available_at']))
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
        for text in ['o boss a caminho','minha stamina ta 40 horas']:
            self.assertIsNone(a.parse(text,NOW),text)
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
    def test_bridge_parameter_is_not_js_arguments(self):
        import inspect,web_api
        self.assertNotIn('arguments',inspect.signature(web_api.API.assistente_executar).parameters)
