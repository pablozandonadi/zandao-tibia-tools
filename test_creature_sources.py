import unittest
from unittest.mock import patch
import creature_sources as sources
import planejador

DWORC_EN='{{Infobox Creature|name=Dworc Shadowstalker|hp=8900|abilities={{Ability List|{{Ability|Invisibility|5~ seconds|element=invisible}}|{{Ability|Life Drain|0-625|element=life drain}}}}|maxdmg={{Max Damage|physical=250|lifedrain=625|death=100}}|physicalDmgMod=95%|hpDrainDmgMod=100%?}}'
class DualWikiTests(unittest.TestCase):
 def test_dworc_gap_filled_without_inventing_ranges(self):
  br=planejador.parse_wiki('{{Infobox_Criatura|name=Dworc Shadowstalker|hab_physical=()|hab_death=()|physicalDmgMod=95%}}','Dworc Shadowstalker')
  en=sources.parse_en(DWORC_EN,'Dworc Shadowstalker');r=sources.merge('Dworc Shadowstalker',br,en)
  self.assertEqual([(a['elemento'],a['min'],a['max']) for a in r['ataques']],[('lifedrain',0,625)])
  self.assertEqual(r['maximos_elemento']['physical'],250)
  self.assertEqual(r['maximos_elemento']['death'],100)
  self.assertNotIn('lifedrain',r['resist'])
  self.assertEqual(r['ataques'][0]['origem'],'en')
 def test_translated_melee_not_counted_twice(self):
  br={'ataques':[dict(nome='Corpo a corpo',elemento='physical',min=0,max=300)],'resist':{}}
  en={'ataques':[dict(nome='Melee',elemento='physical',min=0,max=300)],'resist':{}}
  r=sources.merge('X',br,en);self.assertEqual(len(r['ataques']),1);self.assertEqual(r['ataques'][0]['fontes'],['en','br'])
 def test_conflict_visible_and_en_preferred(self):
  br={'ataques':[dict(nome='Corpo a corpo',elemento='physical',min=0,max=300)],'resist':{'ice':80}}
  en={'ataques':[dict(nome='Melee',elemento='physical',min=0,max=500)],'resist':{'ice':90}}
  r=sources.merge('X',br,en);self.assertEqual(r['ataques'][0]['max'],500);self.assertEqual(r['resist']['ice'],90);self.assertEqual(len(r['divergencias']),2)
 def test_br_fills_en_missing_element(self):
  br={'ataques':[dict(nome='Ice Wave',elemento='ice',min=100,max=200)],'resist':{'ice':80}}
  en={'ataques':[],'resist':{'fire':110}}
  r=sources.merge('X',br,en);self.assertEqual(r['ataques'][0]['origem'],'br');self.assertEqual(r['resist'],{'ice':80,'fire':110})
 def test_same_source_distinct_spells_with_identical_ranges_preserved(self):
  attacks=[dict(nome='Fire Wave',elemento='fire',min=100,max=200),dict(nome='Fire Beam',elemento='fire',min=100,max=200)]
  r=sources.merge('X',{'ataques':attacks},{'ataques':attacks});self.assertEqual(len(r['ataques']),2)
 def test_element_conflict_does_not_duplicate_spell(self):
  a=dict(nome='Terra Strike',elemento='earth',min=100,max=250);b=dict(nome='Terra Strike',elemento='lifedrain',min=100,max=250)
  r=sources.merge('X',{'ataques':[a]},{'ataques':[b]});self.assertEqual(len(r['ataques']),1);self.assertEqual(r['ataques'][0]['elemento'],'lifedrain');self.assertTrue(r['divergencias'])
 def test_max_summary_never_used_as_individual_attack(self):
  en=sources.parse_en(DWORC_EN,'Dworc Shadowstalker');f=sources.merge('Dworc Shadowstalker',None,en)
  r=planejador.calcular([{'peso':1,'ficha':f}]);self.assertEqual([a['elemento'] for a in r['picos']],['lifedrain'])

if __name__=='__main__':unittest.main()
