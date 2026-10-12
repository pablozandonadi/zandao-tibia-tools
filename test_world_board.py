import unittest, tempfile, os, json
from datetime import date
from unittest.mock import patch
import world_board as w
import zandaobot_report as report
class BoardTests(unittest.TestCase):
 def test_partial_and_full(self):
  text='17:50:59 Nomads travel the eternal sands of Ankrahmun\'s desert. There must be a camp somewhere.'
  self.assertEqual(w.analisar(text)['yasir'],'nao_confirmado')
  self.assertEqual(w.analisar(text,True)['yasir'],'ausente')
  self.assertEqual(w.analisar(text+'\nUnrecognized message',True)['yasir'],'nao_confirmado')
  self.assertEqual(len(w.analisar(text+'\n'+text)['eventos']),1)
 def test_look_not_events(self):
  self.assertIn('erro',w.analisar('You see the world board.\nYou read: Maintained by Charos (Do not touch the leaflets!)'))
 def test_yasir_present(self):
  self.assertEqual(w.analisar('Oriental ships sighted! A trader offers creature products.')['yasir'],'presente')
 def test_persistence_profile_expiry(self):
  with tempfile.TemporaryDirectory() as tmp, patch.object(w.tibia_info,'dia_tibia',return_value=date(2026,10,12)):
   path=os.path.join(tmp,'board.json');text='Nomads travel the eternal sands of Ankrahmun desert. There must be a camp somewhere.'
   self.assertTrue(w.salvar(text+'\nPrivate unknown text','Char','Antica','2026-10-12',True,path)['ok'])
   self.assertNotIn('Private unknown',open(path,encoding='utf8').read())
   self.assertIsNone(w.ultimo('Other','Antica',path));self.assertIsNone(w.ultimo('Char','Lobera',path))
   self.assertIn('erro',w.preparar(text,'Char','Antica','2026-10-13'))
   w.remover('Char','Antica','2026-10-12',path);self.assertIsNone(w.ultimo('Char','Antica',path))
 def test_invalid_storage(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=os.path.join(tmp,'board.json');open(path,'w').write('{"registros":null}')
   self.assertIsNone(w.ultimo('Char','Antica',path))
 def test_report_unknown_not_inactive(self):
  r={'dia':'2026-10-12','mundo':'Antica','personagem':'Char','boostados':{'velho':True},'yasir':{'estado':'indisponivel'}}
  s=report.gerar(r,{'comunidade':'Piratas','coin_compra':'43.552'})
  self.assertIn('Bom dia, Piratas!',s);self.assertIn('*Fury Gate:* ❓',s);self.assertIn('comprar 43.552 gp',s);self.assertNotIn('None',s)
 def test_report_manual_presence(self):
  r={'dia':'2026-10-12','world_board':{'valido':True,'completo':True,'consulta':1,'eventos':[{'id':'warpath','nome':'Warpath'}]}}
  s=report.gerar(r);self.assertIn("*Bibby's Bloodbath:* 🟢 Ativo",s);self.assertIn('*Fury Gate:* 🔴 Inativo',s)
if __name__=='__main__':unittest.main()
