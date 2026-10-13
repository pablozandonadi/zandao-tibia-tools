import copy
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import hunt_catalog as runtime
from hunt_catalog_core import aggregate,correlate,eligible_damage,profile,sanitize_records,title_candidates,validate_snapshot,local_composition,local_kills
from hunt_catalog_collect import parse_public_session,parse_wiki_place,normalize_places
from hunt_catalog_publish import prepare


def place(id='cave',name='Dragon Cave',roster=None,parent=None):
    return {'id':id,'name':name,'aliases':[name],'creatures':roster or ['Dragon','Dragon Lord'],'conditional':[], 'sources':{},'region':'','parent_id':parent}
def record(id='1',types=None,hints=None):
    return {'id':id,'date':'2026-10-12','members':1,'kills':{'Dragon':90,'Dragon Lord':10},'title_candidates':hints or [],'public_url':'https://www.hunt-analyser.com/hunt_sessions/'+id,'inputs':[{'origin':id+':0','types':types or {'physical':60,'fire':40},'sources':{'Dragon':100}}]}
def snapshot():
    return aggregate({'cave':place()},{'1':record(hints=['cave'])},{'collected_timestamp':1})

class CorrelationTests(unittest.TestCase):
    def test_title_and_kills_confirm(self):
        self.assertEqual(correlate(record(hints=['cave']),{'cave':place()})['status'],'confirmed')
    def test_shared_monsters_are_ambiguous(self):
        self.assertEqual(correlate(record(),{'cave':place(),'other':place('other')})['status'],'review')
    def test_wrong_title_not_overridden(self):
        self.assertEqual(correlate(record(hints=['other']),{'cave':place(),'other':place('other',roster=['Rat'])})['status'],'review')
    def test_floor_not_inferred_from_mobs(self):
        p={'cave':place(),'floor':place('floor',parent='cave')}
        self.assertEqual(correlate(record(),p)['place_id'],'cave')
    def test_alias_boundaries(self):
        self.assertEqual(title_candidates('Dragon Cave solo',{'cave':place()}),['cave'])
        self.assertEqual(title_candidates('Dragon Caverns',{'cave':place()}),[])
    def test_input_mean_not_long_session_weight(self):
        r=[record('1',{'physical':9000,'fire':1000}),record('2',{'physical':10,'fire':90})]
        p=profile(r);self.assertEqual(p['inputs'],2)
        self.assertEqual(next(x['mean_pct'] for x in p['elements'] if x['element']=='physical'),50)
    def test_missing_input_not_zero_and_duplicate_ignored(self):
        r=record();self.assertEqual(profile([r,copy.deepcopy(r),dict(record('2'),inputs=[])])['inputs'],1)
    def test_foreign_damage_excluded(self):
        r=record();r['inputs'][0]['sources']={'Rat':100}
        self.assertEqual(profile(eligible_damage(place(),[r]))['inputs'],0)
    def test_local_composition_excludes_trip_and_renormalizes_per_session(self):
        a=record();a['kills']={'Dragon':90,'Dragon Lord':10,'Rat':25}
        b=record('2');b['kills']={'Dragon':10,'Dragon Lord':90,'Rat':1}
        original=copy.deepcopy([a,b]);local=local_composition(place(),[a,b])
        self.assertEqual(local['composition'],{'Dragon':50,'Dragon Lord':50})
        self.assertEqual(local['excluded_kills'],26);self.assertEqual(local['excluded_species'],1)
        self.assertEqual(local['kills'],{'Dragon':100,'Dragon Lord':100});self.assertEqual([a,b],original)
    def test_floor_roster_never_uses_parent_or_conditional_mobs(self):
        p=place(roster=['Dragon','Boss Dragon']);p['conditional']=['Boss Dragon'];p['parent_id']='parent'
        self.assertEqual(local_kills(p,{'Dragon':3,'Rat':2,'Boss Dragon':1}),{'Dragon':3})
    def test_case_and_plural_match_wiki_roster(self):
        self.assertEqual(local_kills(place(),{'dragons':4,'DRAGON LORD':2}),{'Dragon':4,'Dragon Lord':2})
    def test_even_small_trip_damage_not_subtracted_or_attributed(self):
        r=record();r['inputs'][0]['sources']={'Dragon':999,'Rat':1};original=copy.deepcopy(r)
        self.assertEqual(profile(eligible_damage(place(),[r]))['inputs'],0);self.assertEqual(r,original)
    def test_unknown_damage_sources_cannot_prove_local_scope(self):
        r=record();r['inputs'][0]['sources']={}
        self.assertEqual(profile(eligible_damage(place(),[r]))['inputs'],0)
    def test_free_text_is_not_published(self):
        r=record();r['kills']['Someone Name']=3;r['inputs'][0]['sources']['Someone Name']=42
        sanitize_records({'1':r},{'dragon':'Dragon','dragon lord':'Dragon Lord'})
        self.assertNotIn('Someone',json.dumps(r));self.assertEqual(sum(r['kills'].values()),103)

class ParserTests(unittest.TestCase):
    def test_header_tables_and_footer_not_counted(self):
        html='''<div id="hunt_session_1"><table><tr><th>#</th><th>Type</th><th>Damage</th></tr><tr><td>1</td><td>Physical</td><td>1,234 (80%)</td></tr><tr><td>2</td><td>Life Drain</td><td>300 (20%)</td></tr></table><table><tr><th>#</th><th>Monster</th><th>Damage</th></tr><tr><td>1</td><td>Dragon</td><td>1,534 (100%)</td></tr></table><table><tr><th>#</th><th>Monster</th><th>Killed</th></tr><tr><td>1</td><td>Dragons</td><td>120</td></tr></table></div><table><tr><th>#</th><th>Monster</th><th>Killed</th></tr><tr><td>1</td><td>Rat</td><td>999</td></tr></table>'''
        r=parse_public_session(html,{'id':'1','members':4},{'dragon':'Dragon'})
        self.assertEqual(r['kills'],{'Dragon':120});self.assertTrue(r['input_partial'])
        self.assertEqual(r['inputs'][0]['types'],{'physical':1234,'lifedrain':300})
    def test_br_respawns_and_conditional_boss(self):
        text="{{Infobox_Hunts\n| city=Thais\n| infoLocal=\n* '''Respawns:'''\n** '''Andar -1:''' Dragon, Dragon Lord.\n** '''Bosses:''' Boss Dragon.\n| rotaLocal=Rat\n}}"
        r=parse_wiki_place(text,'Cave','br',{})
        self.assertEqual(r['creatures'],['Dragon','Dragon Lord']);self.assertEqual(r['conditional'],['Boss Dragon']);self.assertEqual(r['sections'][0]['floor'],1)
    def test_en_roster_not_story(self):
        r=parse_wiki_place('{{Infobox Hunt|city=Thais}}\nStory [[Rat]]\n{{CreatureList|type=List|caption=Ice Section|Dragon|Dragon Lord}}','Library','en',{})
        self.assertEqual(r['creatures'],['Dragon','Dragon Lord']);self.assertEqual(len(r['sections']),1)
    def test_merge_equivalent_sections(self):
        p={'secret-library-ice-section':place('secret-library-ice-section','Secret Library Ice Section'), 'secret-library--ice':place('secret-library--ice','Secret Library · Ice Section',parent='secret-library')}
        normalize_places(p);self.assertEqual(len(p),1);self.assertIn('livraria gelo',next(iter(p.values()))['aliases'])

class RuntimeTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
    def test_bundled_snapshot_complete_and_no_personal_fields(self):
        root=Path(__file__).parent;d=validate_snapshot(json.loads((root/'data/hunt_catalog.json').read_text(encoding='utf-8')))
        self.assertGreater(d['metadata']['index_reported'],4000)
        self.assertGreater(d['metadata']['sessions_collected'],4000)
        self.assertGreater(d['metadata']['places_with_creatures'],800)
        self.assertEqual(d['metadata']['sessions_collected'],len(d['records']))
        self.assertEqual(d['metadata']['sessions_confirmed'],sum(r['assignment']['status']=='confirmed' for r in d['records'].values()))
    def test_invalid_url_and_personal_fields_rejected(self):
        for change in ('url','personal'):
            d=snapshot()
            if change=='url':d['records']['1']['public_url']='javascript:alert(1)'
            else:d['records']['1']['player']='Example'
            with self.assertRaises(ValueError):validate_snapshot(d)
    def test_exact_party_size_and_all_history(self):
        d=snapshot();old=copy.deepcopy(d['records']['1']);old['id']='2';old['date']='2020-01-01';old['members']=2;old['public_url']='https://www.hunt-analyser.com/hunt_sessions/2'
        d['records']['2']=old;d['places']['cave']['observed']['sample_ids'].append('2')
        for members in (3,4,5,6):
            r=copy.deepcopy(old);r['id']=str(members);r['members']=members;d['records'][str(members)]=r;d['places']['cave']['observed']['sample_ids'].append(str(members))
        with patch.object(runtime,'data',return_value=d):
            self.assertEqual(runtime.detalhes('cave','size_2',0)['sessoes'],1)
            self.assertEqual(runtime.detalhes('cave','size_4',0)['amostras'][0]['membros'],4)
            self.assertEqual(runtime.detalhes('cave','size_5plus',0)['sessoes'],2)
            self.assertEqual(runtime.detalhes('cave','all',0)['sessoes'],6)
    def test_context_and_empty_period(self):
        with patch.object(runtime,'data',return_value=snapshot()):
            d=runtime.detalhes('cave','party',0);self.assertEqual(d['sessoes'],0);self.assertEqual(d['perfil']['inputs'],0)
    def test_exact_session_and_no_old_input_for_wiki(self):
        with patch.object(runtime,'data',return_value=snapshot()),patch('planejador.catalogo_visual',return_value={'lista':[{'name':'Dragon'},{'name':'Dragon Lord'}]}):
            r=runtime.preset('cave','session','1',dias=0);self.assertTrue(r['real']);self.assertEqual(r['selecao'][0]['peso'],90);self.assertIn('Physical 60',r['dano_texto'])
            self.assertFalse(runtime.preset('cave','wiki',dias=0)['real'])
    def test_missing_gif_preserves_original_count_warning(self):
        with patch.object(runtime,'data',return_value=snapshot()),patch('planejador.catalogo_visual',return_value={'lista':[{'name':'Dragon'}]}):
            r=runtime.preset('cave','session','1',dias=0);self.assertEqual(r['total_log'],100);self.assertEqual(r['total'],90);self.assertTrue(r['avisos'])
    def test_large_roster_not_silently_truncated(self):
        d=snapshot();d['places']['cave']['creatures']=['Creature '+str(i) for i in range(31)]
        with patch.object(runtime,'data',return_value=d),patch('planejador.catalogo_visual',return_value={'lista':[{'name':n} for n in d['places']['cave']['creatures']]}):
            self.assertIn('31',runtime.preset('cave','wiki',dias=0)['erro'])
    def test_session_preset_filters_kills_and_rejects_mixed_input(self):
        d=snapshot();r=d['records']['1'];r['kills']['Rat']=7;r['inputs'][0]['sources']['Rat']=1
        with patch.object(runtime,'data',return_value=d),patch('planejador.catalogo_visual',return_value={'lista':[{'name':'Dragon'},{'name':'Dragon Lord'},{'name':'Rat'}]}):
            detail=runtime.detalhes('cave',dias=0);self.assertEqual(set(detail['composicao']),{'Dragon','Dragon Lord'})
            self.assertEqual(detail['abates_excluidos'],7);self.assertEqual(detail['inputs_excluidos'],1)
            p=runtime.preset('cave','session','1',dias=0);self.assertEqual(p['total_log'],107);self.assertEqual(p['total_local'],100)
            self.assertFalse(p['real']);self.assertEqual(p['dano_texto'],'');self.assertTrue(p['avisos'])
            self.assertNotIn('Rat',{c['nome'] for c in p['selecao']})
    def test_legacy_cached_observed_union_does_not_leak_trip_mobs(self):
        d=snapshot();d['places']['cave']['observed']['composition']['Rat']=90;d['records']['1']['kills']['Rat']=7
        with patch.object(runtime,'data',return_value=d),patch('planejador.catalogo_visual',return_value={'lista':[{'name':'Dragon'},{'name':'Dragon Lord'},{'name':'Rat'}]}):
            p=runtime.preset('cave','observed',dias=0);self.assertEqual(len(p['selecao']),2);self.assertAlmostEqual(p['total_local'],100)
    def test_both_libraries_load_with_only_their_documented_rosters(self):
        d=json.loads((Path(__file__).parent/'data/hunt_catalog.json').read_text(encoding='utf-8'))
        for name in ('Secret Library Fire Section','Secret Library Ice Section'):
            p=next(p for p in d['places'].values() if p['name']==name)
            with self.subTest(name=name),patch.object(runtime,'data',return_value=d),patch('planejador.catalogo_visual',return_value={'lista':[{'name':n} for n in p['creatures']]+[{'name':'Rat'},{'name':'Falcon Knight'}]}):
                detail=runtime.detalhes(p['id'],dias=0);self.assertTrue(set(detail['composicao']).issubset(p['creatures']))
                self.assertGreater(detail['abates_excluidos'],0)
                preset=runtime.preset(p['id'],'observed',dias=0);self.assertNotIn('erro',preset)
                self.assertLessEqual(len(preset['selecao']),6);self.assertAlmostEqual(sum(detail['composicao'].values()),100,places=3)
    def test_refresh_daily_ttl_does_not_request(self):
        root=Path(self.tmp.name);(root/'check.json').write_text(json.dumps({'at':time.time()}))
        with patch.object(runtime,'CHECK',str(root/'check.json')),patch('urllib.request.urlopen') as request:
            self.assertEqual(runtime.refresh()['status'],'atualizado');request.assert_not_called()
    def test_valid_remote_refresh_is_atomic(self):
        class Response:
            def __init__(self,raw):self.raw=raw
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return self.raw[:n]
        root=Path(self.tmp.name);new=snapshot();new['metadata']['collected_timestamp']=2;raw=json.dumps(new).encode()
        with patch.object(runtime,'CACHE',str(root/'cache.json')),patch.object(runtime,'CHECK',str(root/'check.json')),patch.object(runtime,'_data',snapshot()),patch('urllib.request.urlopen',side_effect=[Response(hashlib.sha256(raw).hexdigest().encode()),Response(raw)]):
            self.assertEqual(runtime.refresh(True)['status'],'atualizado');self.assertEqual(runtime.data()['metadata']['collected_timestamp'],2)
            self.assertFalse((root/'cache.json.tmp').exists())
    def test_corrupt_remote_keeps_previous_data(self):
        class Response:
            def __init__(self,raw):self.raw=raw
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,n):return self.raw[:n]
        old=snapshot()
        with patch.object(runtime,'CACHE',str(Path(self.tmp.name)/'cache.json')),patch.object(runtime,'CHECK',str(Path(self.tmp.name)/'check.json')),patch.object(runtime,'_data',old),patch('urllib.request.urlopen',side_effect=[Response(b'0'*64),Response(b'corrupt')]):
            self.assertEqual(runtime.refresh(True)['status'],'cache');self.assertIs(runtime.data(),old)
    def test_publisher_uses_validated_records_not_raw_checkpoint(self):
        root=Path(self.tmp.name);(root/'s.json').write_text(json.dumps(snapshot()),encoding='utf-8');(root/'records.json').write_text('{"player":"private"}')
        prepare(root/'s.json',root,root/'out')
        raw=(root/'out/catalog.json').read_bytes();self.assertEqual((root/'out/catalog.json.sha256').read_text(),hashlib.sha256(raw).hexdigest())
        self.assertNotIn('private',(root/'out/state/records.json').read_text())

if __name__=='__main__':unittest.main()
