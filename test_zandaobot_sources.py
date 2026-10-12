import ast
import copy
import json
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import zandaobot_sources as s


def event(title='Full Moon', start='2026-10-12', end='2026-10-15', **kwargs):
    return {'id': title, 'title': title, 'startDate': start, 'endDate': end, 'type': 'scheduled',
            'calendarId': 'scheduled_events', 'serverSaveEvent': True, 'worldId': None, 'worldScopeLabel': None, **kwargs}


def wiki_fixture():
    formula = '{{#if:{{{1}}}|{{#switch:{{#expr:ceil(({{#time: U |now + {{#expr:3600*{{Rashid Location/DST}}}} seconds - 10 hours }} / 60 / 60 / 24) + {{{1|}}}) mod 5 }}|0=Maxxenius|1=Alptramun|2=Izcandar the Banished|3=Plagueroot|4=Malofur Mangrinder|}}|Unknown}}'
    offsets = '{{#expr:4+{{#switch:{{{1}}}\n|Antica=1\n|Rasteibra=4\n|Uncertainia=0 <!-- Uncertain -->\n|0\n}}}}'
    return {'query': {'pages': {str(i): {'title': title, 'revisions': [{'timestamp': '2026-09-11T15:05:02Z', 'slots': {'main': {'*': text}}}]} for i,(title,text) in enumerate([('Template:Dream Scar Boss', formula), ('Template:Dream Scar Boss/Offsets', offsets)])}}}


class TestSources(unittest.TestCase):
    def setUp(self):
        s._cache.clear()
        network = patch.object(s, 'get_json', side_effect=OSError('rede não usada nos testes'))
        network.start()
        self.addCleanup(network.stop)

    def test_sem_mundo_pede_selecao_e_ainda_lista_yasir(self):
        with patch.object(s,'_yasir_worlds',return_value=['Lobera']), patch.object(s,'dream_rules') as rules:
            r=s.mini_changes('')
            dream=s.dream_court('')
        self.assertEqual(r['estado'],'selecionar_mundo')
        self.assertEqual(r['mundos_com_yasir'],['Lobera'])
        self.assertEqual(dream['estado'],'selecionar_mundo')
        rules.assert_not_called()

    def test_yasir_presente_e_ausente_por_mundo(self):
        def api(method, args=None):
            if method == 'world.list':
                return {'worlds': [{'name': 'Antica', 'id': 3}, {'name': 'Lobera', 'id': 40}]}
            return {'active_mini_world_changes': [{'mini_world_change_name': 'Oriental Trader'}] if args['world_id']==40 else []}
        with patch.object(s, 'trade', side_effect=api):
            self.assertEqual(s.mini_changes('lobera')['estado'], 'presente')
            self.assertEqual(s.mini_changes('Antica')['estado'], 'ausente')
            self.assertIsNone(s.mini_changes('Lobera')['cidade'])

    def test_yasir_schema_incompleto_nao_significa_ausente(self):
        with patch.object(s, 'trade', side_effect=[{'worlds': [{'name':'Antica','id':3}]}, {}]):
            self.assertEqual(s.mini_changes('Antica')['estado'], 'indisponivel')

    def test_yasir_cache_antigo_nao_confirma_hoje(self):
        s._cache['trade-worlds'] = {'dados': {'antica':3}, 'consulta': __import__('time').time(), 'dia':'2026-10-11'}
        s._cache['changes:antica'] = {'dados':['Oriental Trader'], 'consulta':1, 'dia':'2026-10-11'}
        with patch.object(s, 'trade', side_effect=OSError()):
            r=s.mini_changes('Antica')
        self.assertEqual(r['estado'],'desatualizado')
        self.assertEqual(r['dia'],'2026-10-11')
        self.assertEqual(r['consulta'],1)

    def test_yasir_confere_duas_consultas_e_lista_mundos(self):
        def api(method, args=None):
            if method=='world.list': return {'worlds':[{'name':'Lobera','id':40}]}
            if method=='miniWorldChange.list': return {'mini_world_changes':[{'id':20,'name':'Oriental Trader'}]}
            if method=='miniWorldChange.listActive': return {'active_mini_world_changes':[{'mini_world_change_name':'Oriental Trader'}]}
            if method=='miniWorldChange.listActiveWorlds': return {'active_worlds':[{'world_name':'Lobera'}]}
            raise AssertionError(method)
        with patch.object(s,'trade',side_effect=api):
            r=s.mini_changes('Lobera')
        self.assertTrue(r['conferido'])
        self.assertEqual(r['estado'],'presente')
        self.assertEqual(r['mundos_com_yasir'],['Lobera'])

    def test_yasir_divergencia_nao_confirma_ausencia(self):
        def api(method, args=None):
            if method=='world.list': return {'worlds':[{'name':'Lobera','id':40}]}
            if method=='miniWorldChange.list': return {'mini_world_changes':[{'id':20,'name':'Oriental Trader'}]}
            if method=='miniWorldChange.listActive': return {'active_mini_world_changes':[]}
            if method=='miniWorldChange.listActiveWorlds': return {'active_worlds':[{'world_name':'Lobera'}]}
            raise AssertionError(method)
        with patch.object(s,'trade',side_effect=api):
            self.assertEqual(s.mini_changes('Lobera')['estado'],'inconsistente')

    def test_yasir_fallback_lista_completa_quando_consulta_mundo_falha(self):
        def api(method, args=None):
            if method=='world.list': return {'worlds':[{'name':'Lobera','id':40}]}
            if method=='miniWorldChange.list': return {'mini_world_changes':[{'id':20,'name':'Oriental Trader'}]}
            if method=='miniWorldChange.listActive': raise OSError()
            if method=='miniWorldChange.listActiveWorlds': return {'active_worlds':[{'world_name':'Lobera'}]}
            raise AssertionError(method)
        with patch.object(s,'trade',side_effect=api):
            r=s.mini_changes('Lobera')
        self.assertEqual(r['estado'],'presente')
        self.assertFalse(r['velho'])

    def test_dream_conferido_na_resposta_da_wiki(self):
        rules=s.parse_dream_rules(wiki_fixture())
        with patch.object(s,'dream_rules',return_value=rules), patch.object(s,'expand_dream',return_value='Izcandar the Banished'), patch.object(s.tibia_info,'dia_tibia',return_value=date(2026,10,12)):
            r=s.dream_court('Rasteibra')
        self.assertTrue(r['conferido'])
        self.assertEqual(r['nome'],'Izcandar the Banished')

    def test_dream_respostas_divergentes_nao_afirmam_boss(self):
        rules=s.parse_dream_rules(wiki_fixture())
        with patch.object(s,'dream_rules',return_value=rules), patch.object(s,'expand_dream',return_value='Plagueroot'), patch.object(s.tibia_info,'dia_tibia',return_value=date(2026,10,12)):
            r=s.dream_court('Rasteibra')
        self.assertEqual(r['estado'],'inconsistente')
        self.assertNotIn('nome',r)

    def test_dream_world_offsets_e_server_save(self):
        rules=s.parse_dream_rules(wiki_fixture())
        with patch.object(s,'dream_rules',return_value=rules), patch.object(s.tibia_info,'dia_tibia',return_value=date(2026,10,12)):
            self.assertEqual(s.dream_court('Antica')['nome'],'Malofur Mangrinder')
            self.assertEqual(s.dream_court('Rasteibra')['nome'],'Izcandar the Banished')
            self.assertTrue(s.dream_court('Uncertainia')['incerto'])
            self.assertEqual(s.dream_court('MundoNovo')['estado'],'indisponivel')
        with patch.object(s,'dream_rules',return_value=rules), patch.object(s.tibia_info,'dia_tibia',return_value=date(2026,10,13)):
            self.assertEqual(s.dream_court('Antica')['nome'],'Maxxenius')

    def test_dream_formula_nova_falha(self):
        data=wiki_fixture()
        data['query']['pages']['0']['revisions'][0]['slots']['main']['*']='nova regra'
        with self.assertRaises(ValueError): s.parse_dream_rules(data)

    def test_dream_pequena_mudanca_na_formula_nao_e_ignorada(self):
        data=wiki_fixture()
        revision=data['query']['pages']['0']['revisions'][0]['slots']['main']
        revision['*']=revision['*'].replace('mod 5', '+ 1 mod 5')
        with self.assertRaises(ValueError): s.parse_dream_rules(data)

    def test_calendario_end_exclusivo_e_noticias_nao_sao_eventos(self):
        events=[event(),event('Orcsoberfest','2026-10-09','2026-10-16'),event('News',type='news'),event('Tomorrow','2026-10-16','2026-10-20')]
        before=s.parse_calendar({'events':events},today=date(2026,10,14))
        after=s.parse_calendar({'events':events},today=date(2026,10,15))
        self.assertEqual(next(e for e in before if e['titulo']=='Full Moon')['estado'],'ativo')
        self.assertNotIn('Full Moon',[e['titulo'] for e in after])
        self.assertNotIn('News',[e['titulo'] for e in after])
        self.assertEqual(next(e for e in after if e['titulo']=='Tomorrow')['estado'],'proximo')

    def test_eventos_especificos_nao_vazam_para_outro_mundo(self):
        data={'events':[event('Ferobra',worldId='Ferobra'),event('Global')]}
        self.assertEqual([e['titulo'] for e in s.parse_calendar(data,'Antica',date(2026,10,12))],['Global'])
        self.assertEqual(len(s.parse_calendar(data,'Ferobra',date(2026,10,12))),2)

    def test_calendario_datas_iso_e_horizonte(self):
        data={'events':[event(start='2026-10-12T00:00:00.000Z',end='2026-10-15T00:00:00.000Z'),event('Distant','2027-01-01','2027-01-02')]}
        events=s.parse_calendar(data,today=date(2026,10,12))
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]['inicio'],'2026-10-12')

    def test_delta_substitui_snapshot_e_adiciona_evento(self):
        meta={'hotUrl':'https://cdn.tibiacalendar.com/events-bundle-hot_test.json','maxUpdatedAt':123,'maxStartDate':'2027-08-01'}
        base={'events':[event()], 'generatedAt':1}
        delta={'result':{'data':{'json':[event(end='2026-10-16'),event('New')]}}}
        with patch.object(s,'get_text',return_value='window.__BUNDLE_META__='+json.dumps(meta)+';'), patch.object(s,'get_json',side_effect=[base,delta]) as get:
            r=s.calendar_bundle()
        self.assertEqual(len(r['events']),2)
        self.assertEqual(r['events'][0]['endDate'],'2026-10-16')
        self.assertIn('events.listDelta',get.call_args.args[0])

    def test_falha_delta_nao_publica_snapshot_como_atual(self):
        meta={'hotUrl':'https://cdn.tibiacalendar.com/events-bundle-hot_test.json','maxUpdatedAt':123,'maxStartDate':'2027-08-01'}
        with patch.object(s,'get_text',return_value='window.__BUNDLE_META__='+json.dumps(meta)+';'), patch.object(s,'get_json',side_effect=[{'events':[], 'generatedAt':1}, OSError()]):
            self.assertEqual(s.calendar()['estado'],'indisponivel')

    def test_url_remota_do_bundle_e_restrita(self):
        with patch.object(s,'get_text',return_value='window.__BUNDLE_META__={"hotUrl":"https://evil.invalid/data.json"};'), patch.object(s,'get_json') as get:
            with self.assertRaises(ValueError): s.calendar_bundle()
            get.assert_not_called()

    def test_cache_nao_mistura_server_saves(self):
        days=[date(2026,10,12),date(2026,10,13)]
        with patch.object(s.tibia_info,'dia_tibia',side_effect=days):
            result=s.cached('daily', lambda:['Oriental Trader'])
        self.assertTrue(result['velho'])
        self.assertIsNone(result['dados'])


class TestApiDefaultWorld(unittest.TestCase):
    def test_personagem_ativo_e_consulta_independente(self):
        tree=ast.parse(Path(__file__).with_name('web_api.py').read_text(encoding='utf-8'))
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='zandaobot_buscar')
        module=ast.Module(body=[method],type_ignores=[])
        characters=Mock()
        characters.carregar.return_value={'atual':'Char B','lista':[{'nome':'Char A','mundo':'Antica'},{'nome':'Char B','mundo':'Lobera'}]}
        bot=Mock()
        namespace={'personagens':characters,'zandaobot':bot}
        exec(compile(module,'api-test','exec'),namespace)
        namespace['zandaobot_buscar'](None)
        bot.buscar.assert_called_with('Lobera',False)
        characters.carregar.reset_mock()
        namespace['zandaobot_buscar'](None,'Antica',True)
        bot.buscar.assert_called_with('Antica',True)
        characters.carregar.assert_not_called()


if __name__=='__main__': unittest.main()
