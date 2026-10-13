import unittest
from unittest.mock import patch
import planejador as p

class TestPlanejador(unittest.TestCase):
 def test_explicit_element_over_spell_name(self):
  f=p.parse_wiki('{{Infobox_Criatura|name=Medusa|hab_lifedrain=[[Terra Strike]] (100-250)|hab_physical=Melee (0-300), causando Poisoned em 40 hp/turno}}','Medusa')
  self.assertEqual(f['ataques'][1]['elemento'],'lifedrain')
  self.assertEqual(len(f['ataques']),2)
  self.assertTrue(f['avisos'])
 def test_rare_peak_is_not_diluted(self):
  rows=[{'peso':99,'ficha':{'nome':'Common','ataques':[dict(nome='Hit',elemento='physical',min=100,max=200)]}}, {'peso':1,'ficha':{'nome':'Rare','ataques':[dict(nome='Drain',elemento='lifedrain',min=0,max=2000)]}}]
  r=p.calcular(rows)
  self.assertEqual(r['picos'][0]['max'],2000)
  self.assertEqual(r['picos'][0]['participacao'],1)
  self.assertEqual(next(e['media'] for e in r['elementos'] if e['elemento']=='physical'),148.5)
 def test_mana_not_in_hp_percent(self):
  r=p.calcular([{'peso':1,'ficha':{'nome':'X','ataques':[dict(nome='Hit',elemento='physical',min=100,max=100),dict(nome='Mana',elemento='manadrain',min=900,max=900)]}}])
  self.assertEqual(next(e['pct'] for e in r['elementos'] if e['elemento']=='physical'),100)
  self.assertIsNone(next(e['pct'] for e in r['elementos'] if e['elemento']=='manadrain'))
 def test_missing_is_visible(self):
  f=p.parse_wiki('{{Infobox_Criatura|hab_death=Death Beam (?)}}','X'); self.assertFalse(f['ataques']); self.assertTrue(f['avisos'])
 def test_invalid_input(self):
  for w in [0,-1,float('nan'),float('inf')]: self.assertIn('erro',p.analisar([{'nome':'X','peso':w}]))
  self.assertIn('erro',p.analisar([{'nome':'X','peso':1}]*2))
 def test_weight_scale_invariant(self):
  f={'nome':'X','ataques':[dict(nome='Hit',elemento='physical',min=0,max=100)]}
  self.assertEqual(p.calcular([dict(peso=1,ficha=f)])['elementos'],p.calcular([dict(peso=100,ficha=f)])['elementos'])

class TestImportacao(unittest.TestCase):
 def test_mesma_hunt_completa_e_dano_colado_junto(self):
  names=['Draken Warmaster','Lizard High Guard','Draken Spellweaver','Lizard Legionnaire','Lizard Dragon Priest','Lizard Zaogun']
  text='XP Gain: 123\nKilled Monsters:\n  126x draken warmasters\n  104x lizard high guards\n  86x draken spellweavers\n  47x lizard legionnaires\n  31x lizard dragon priests\n  14x lizard zaoguns\n  5x lizard magistratus\n  2x lizard noble\nLooted Items:\n  100x gold coins\nReceived Damage\nTotal: 50,178\nMax-DPS: 2,043\nDamage Types:\nPhysical 28,752 (57.3%)\nFire 8,781 (17.5%)\nEarth 7,175 (14.3%)\nEnergy 3,864 (7.7%)\nLife Drain 1,606 (3.2%)'
  with patch.object(p,'catalogo_visual',return_value={'lista':[{'name':n} for n in names]}):
   r=p.importar_texto(text)
  self.assertEqual((r['total'],r['total_log']),(408,415))
  self.assertEqual([c['peso'] for c in r['selecao']],[126,104,86,47,31,14])
  self.assertTrue(r['real'])
  self.assertTrue(r['dano_texto'].startswith('Received Damage'))
  self.assertIn('lizard magistratus',r['avisos'][0])
 def test_abates_pesam_e_loot_nao_entra(self):
  text="XP Gain: 123\nKilled Monsters:\n  200x flimsy lost souls\n  50x freakish lost souls\n  10x flimsy lost soul\nLooted Items:\n  999x gold coins"
  with patch.object(p,'catalogo_visual',return_value={'lista':[{'name':'Flimsy Lost Soul'},{'name':'Freakish Lost Soul'}]}):
   r=p.importar_texto(text)
  self.assertEqual(r['total'],260)
  self.assertEqual(r['selecao'],[{'nome':'Flimsy Lost Soul','peso':210},{'nome':'Freakish Lost Soul','peso':50}])
 def test_invalid_and_party_logs(self):
  for text in ['', 'Loot: 100\nLooted Items:\n  1x gold coin', 'Party Hunt Analyser']:
   self.assertIn('erro',p.importar_texto(text))
 def test_no_gif_names_are_omitted_with_notice(self):
  with patch.object(p,'catalogo_visual',return_value={'lista':[{'name':'Flimsy Lost Soul'}]}):
   r=p.importar_texto('XP Gain: 0\nKilled Monsters:\n  5x strange monster\n  20x flimsy lost soul')
  self.assertEqual(r['selecao'],[{'nome':'Flimsy Lost Soul','peso':20}])
  self.assertTrue(r['avisos'])
 def test_resistance_from_explicit_source(self):
  f=p.parse_wiki('{{Infobox_Criatura|fireDmgMod=110%|earthDmgMod=0%|iceDmgMod=80%?}}','X')
  self.assertEqual(f['resist'],{'fire':110,'earth':0})

class TestRevisaoDano(unittest.TestCase):
 def test_dano_medido_e_pesos_seguem_o_hunt_analyser(self):
  import damage_core
  rows=[{'peso':126,'ficha':{'nome':'Draken Warmaster','ataques':[dict(nome='Fire',elemento='fire',min=0,max=600)],'resist':{'ice':100}}},
        {'peso':86,'ficha':{'nome':'Draken Spellweaver','ataques':[dict(nome='Melee',elemento='physical',min=0,max=350)],'resist':{'ice':120}}}]
  dano=p.parse_damage_input('Received Damage\nTotal: 50,178\nDamage Types:\nPhysical 28,752 (57.3%)\nFire 8,781 (17.5%)\nEarth 7,175 (14.3%)\nEnergy 3,864 (7.7%)\nLife Drain 1,606 (3.2%)\nDamage Sources:\ndraken warmasters 10,000 (20%)\ndraken spellweavers 40,178 (80%)')
  expected=damage_core.analisar([{'nome':r['ficha']['nome'],'kills':r['peso'],'ficha':r['ficha']} for r in rows],dano,p.monstros.singularizar)
  result=p.calcular(rows,dano)
  for e in expected['elementos']:
   actual=next(v for v in result['elementos'] if v['elemento']==e['elemento'])
   self.assertAlmostEqual(actual['pct'],e['parte']*100)
  self.assertAlmostEqual(result['resistencias'][0]['modificador'],sum(r['ficha']['resist']['ice']*e['peso'] for r,e in zip(rows,expected['pesos'])))
  self.assertEqual(result['ponderacao_resistencias'],'abates + Damage Sources')
  self.assertAlmostEqual(result['criaturas'][0]['participacao'],126/212*100)
 def _rows(self):
  return [{'peso':1,'ficha':{'nome':'X','ataques':[dict(nome='Melee',elemento='physical',min=0,max=700),dict(nome='Death',elemento='death',min=400,max=600)],'resist':{'energy':115,'earth':75,'physical':100}}}]
 def test_real_damage_overrides_wiki_distribution_without_changing_peaks(self):
  log='Received Damage\nTotal: 112,472\nDamage Types:\nPhysical 66,471 (59.1%)\nLife Drain 23,619 (21.0%)\nDeath 15,746 (14.0%)\nEnergy 6,636 (5.9%)'
  r=p.calcular(self._rows(),p.parse_damage_input(log))
  self.assertTrue(r['real'])
  self.assertEqual([e['elemento'] for e in r['elementos'][:4]],['physical','lifedrain','death','energy'])
  self.assertAlmostEqual(r['elementos'][0]['pct'],59.1)
  self.assertEqual(r['picos'][0]['max'],700)
 def test_resistances_descending(self):
  r=p.calcular(self._rows())
  self.assertEqual([v['modificador'] for v in r['resistencias']],[115,100,75])
 def test_ice_profile_can_dominate_physical(self):
  r=p.calcular([{'peso':1,'ficha':{'nome':'Icecold Book','ataques':[dict(nome='Melee',elemento='physical',min=0,max=700),dict(nome='Ice Berserk',elemento='ice',min=700,max=900),dict(nome='Ice Strike',elemento='ice',min=700,max=850),dict(nome='Ice Beam',elemento='ice',min=800,max=1350)]}}])
  self.assertFalse(r['real'])
  self.assertGreater(next(v['pct'] for v in r['elementos'] if v['elemento']=='ice'),next(v['pct'] for v in r['elementos'] if v['elemento']=='physical'))
 def test_creatures_with_more_listed_attacks_do_not_gain_composition_weight(self):
  rows=[{'peso':1,'ficha':{'nome':'A','ataques':[dict(nome='Melee',elemento='physical',min=100,max=100)]}}, {'peso':1,'ficha':{'nome':'B','ataques':[dict(nome='Fire',elemento='fire',min=100,max=100)]*3}}]
  r=p.calcular(rows)
  self.assertEqual(next(v['pct'] for v in r['elementos'] if v['elemento']=='physical'),50)
 def test_catalog_only_shows_existing_gifs(self):
  with patch.object(p,'catalogo',return_value={'lista':[{'name':'Flimsy Lost Soul'},{'name':'Abyss Hammer'},{'name':'Abominable Spawn'}]}):
   r=p.catalogo_visual()
  self.assertEqual([c['name'] for c in r['lista']],['Flimsy Lost Soul'])

if __name__=='__main__': unittest.main()
