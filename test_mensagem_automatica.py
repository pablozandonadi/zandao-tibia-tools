"""Contrato/formatação públicos; usa somente fixtures, sem servidor ou perfis reais."""
import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
import comandos_tibia
import zandaobot
import zandaobot_sources
import mensagens_tibianas
from mensagem_automatica_core import UTC,FIELDS,Invalid,SourceUnavailable,reference_day,validate
from mensagem_automatica_report import generate,PublicProvider

NOW=datetime.now(UTC)
def config():return {'personagem':'Pirata Teste','mundo':'Antica','timezone':'UTC','blocks':{'mundo':True}}

class AutomaticMessageTests(unittest.TestCase):
 def test_all_nine_fields_and_no_manual_generator_state(self):
  with patch.object(mensagens_tibianas,'proxima',side_effect=AssertionError('manual state touched')):
   for key in FIELDS:
    c={**config(),'fields':{key:True},'values':{key:'Fixture'},'manualDate':reference_day(NOW)}
    self.assertIn('Fixture',generate(c,NOW)['text'])
 def test_all_thirteen_blocks_failclosed_without_world_board(self):
  class Provider:
   def summary(self,c,now):
    base={'consulta':now.timestamp(),'dia':reference_day(now)}
    return {'calendario':{**base,'estado':'disponivel','eventos':[]},'yasir':{**base,'estado':'presente','mudancas':['Fixture online']},'boostados':{**base,'boss':{'nome':'Boss fixture'},'criatura':{'nome':'Rat fixture'}},'dream_court':{**base,'estado':'previsto','nome':'Dream fixture'},'killstatistics':{**base,'estado':'disponivel','bosses':[{'nome':'Dream fixture','last_day_killed':0}]},'world_board':{'valido':True,'eventos':[{'nome':'PRIVATE MANUAL'}]}}
  from mensagem_automatica_core import BLOCKS
  for key in BLOCKS:
   out=generate({**config(),'blocks':{key:True}},NOW,Provider())
   self.assertTrue(out['text']);self.assertNotIn('PRIVATE MANUAL',out['text'])
  class Stale(Provider):
   def summary(self,c,now):
    result=super().summary(c,now);result['boostados']['dia']='2000-01-01';return result
  with self.assertRaises(Invalid):generate({**config(),'blocks':{'boss':True}},NOW,Stale())
 def test_all_seven_extras_reuse_bytecode_without_source_or_stale_cache(self):
  original=comandos_tibia._get
  def response(key,endpoint,*args,**kwargs):
   if endpoint.startswith('/character/'):
    data={'character':{'character':{'name':'Pirata Teste','world':'Antica','level':100,'vocation':'Knight','guild':{'name':'Guild Fixture'}},'deaths':[]}}
   elif endpoint.startswith('/guild/'):
    data={'guild':{'name':'Guild Fixture','world':'Antica','members':[{'name':'Pirata Teste','status':'online','level':100,'vocation':'Knight','joined':NOW.date().isoformat()}]}}
   else:data={'killstatistics':{'entries':[{'race':'Rat','last_day_killed':1}]}}
   return {'dados':data,'consulta':NOW.timestamp(),'velho':False}
  def html(url,*args):
   if 'world-transfer' in url:
    return '<table><tr>'+''.join('<th>'+v+'</th>' for v in ['Rank','Name','Level','Voc','Former','Actual','Change date'])+'</tr><tr>'+''.join('<td>'+v+'</td>' for v in ['1','Pirata Teste','100','Knight','Secura','Antica',NOW.date().isoformat()])+'</tr></table>'
   return '<table><tr>'+''.join('<th>'+str(i)+'</th>' for i in range(7))+'</tr><tr>'+''.join('<td>'+v+'</td>' for v in ['1','Pirata Teste','100','10000','x','Knight','x'])+'</tr></table>'
  with patch.object(zandaobot,'_consultar',side_effect=response),patch.object(zandaobot_sources,'get_text',side_effect=html),patch.object(comandos_tibia,'__file__','/frozen/unavailable.pyc'):
   for key in ['kill','exp_mundo','exp_guild','guild','online_guild','char','transfer']:
    output=generate({**config(),'extras':{key:True}},NOW,PublicProvider());self.assertTrue(output['text']);self.assertGreater(len(output['sources']),1)
  self.assertIs(original,comandos_tibia._get)
  with patch.object(zandaobot,'_consultar',return_value={'dados':{'anything':'stale'},'velho':True,'consulta':NOW.timestamp()}):
   with self.assertRaises(SourceUnavailable):generate({**config(),'extras':{'char':True}},NOW,PublicProvider())
 def test_desktop_methods_without_loading_app_or_server(self):
  tree=ast.parse(Path('web_api.py').read_text(encoding='utf-8'));methods=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name in ('mensagem_automatica_previa','mensagem_automatica_abrir_portal')]
  cls=ast.ClassDef(name='FixtureAPI',bases=[],keywords=[],body=methods,decorator_list=[]);module=ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[]));liberado=[True];namespace={'os':os,'_recurso_dono':lambda nome:liberado[0]};exec(compile(module,'<public-preview-test>','exec'),namespace);api=namespace['FixtureAPI']()
  self.assertIn('Mundo:* Antica',api.mensagem_automatica_previa(config())['text'])
  self.assertIn('erro',api.mensagem_automatica_previa({**config(),'blocks':{'mini':True}}))
  with patch('mensagem_automatica_access.open_management',return_value={'ok':True}) as opened:
   self.assertTrue(api.mensagem_automatica_abrir_portal(config())['ok']);opened.assert_called_once_with(config())
  from mensagem_automatica_access import AccessError
  with patch('mensagem_automatica_access.open_management',side_effect=AccessError('Unavailable')):
   self.assertIn('erro',api.mensagem_automatica_abrir_portal(config()))
  liberado[0]=False  # instalação sem a liberação do dono: a gestão nem abre
  with patch('mensagem_automatica_access.open_management',return_value={'ok':True}) as opened:
   self.assertIn('erro',api.mensagem_automatica_abrir_portal(config()));opened.assert_not_called()
 def test_windows_timezone_is_in_build_lock(self):
  self.assertIn('tzdata==2026.5',Path('requirements-build.lock').read_text())
  self.assertIn('--collect-all tzdata',Path('instalador/gerar_instalador.ps1').read_text())
 def test_legacy_commands_fail_controlled_only_when_extras_selected(self):
  with patch.object(comandos_tibia,'EXTRAS',None,create=True),patch.object(comandos_tibia,'extra',None,create=True):
   self.assertIn('Mundo:* Antica',generate(config(),NOW)['text'])
   with self.assertRaisesRegex(Invalid,'Atualize os módulos de consulta'):
    generate({**config(),'extras':{'char':True}},NOW)

if __name__=='__main__':unittest.main()
