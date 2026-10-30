"""Roteamento do chat e identidade de consultas, sem rede ou credencial real."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from datetime import datetime,timezone
import assistente_consultas as query
import assistente_tibiano
import chat
import mensagem_automatica_access as access

class QueryClientTests(unittest.TestCase):
 def test_aliases_keep_arguments_and_normalize_only_command(self):
  for text,expected in [('!party Alpha Knight',('pt','Alpha Knight')),('evolução Zandao',('evolucao','Zandao')),('!personagem Oi tenta',('char','Oi tenta')),('tc Antica',('precocoin','Antica')),('!comandos',('help',''))]:self.assertEqual(query.parse_command(text),expected)
 def test_domain_phrases_and_legacy_paths_are_not_stolen(self):
  with patch('mensagem_automatica_access.assistant_command') as send:
   for text in ('party 100 200','party level 100','TC tá 36.5k','tc 250 por 49 reais','timer de 30 segundos','shared 300','char Zandao','online Antica','não evolucao Zandao','ajuda com meu timer'):
    self.assertIsNone(query.responder(text,{}),text)
   send.assert_not_called()
 def test_group_mutations_never_reach_service_and_no_automatic_send(self):
  with patch('mensagem_automatica_access.assistant_command') as send:
   for text in ('!set world Antica','!alerta on','!bomdia teste'):self.assertIn('Mensagens',query.responder(text,{}))
   send.assert_not_called()
 def test_context_sends_only_public_fields_and_error_does_not_escape(self):
  context={'character_id':'Alpha Knight','world_id':'Antica','private_timer':'secret','token':'secret'}
  with patch('mensagem_automatica_access.assistant_command',return_value={'text':'XP correto'}) as send:
   self.assertEqual(query.responder('!evo',context),'XP correto');send.assert_called_once_with('!evolucao Alpha Knight','Antica','Alpha Knight')
  with patch('mensagem_automatica_access.assistant_command',side_effect=ValueError('secret')):
   self.assertNotIn('secret',query.responder('!xptop Alpha Knight',context))
 def test_access_uses_protected_identity_and_validates_response(self):
  with patch.object(access,'CredentialFile',return_value=object()) as credentials,patch.object(access,'InstallationClient') as client:
   client.return_value.request.return_value={'command':'pt','text':'Party pública'}
   self.assertEqual(access.assistant_command('!pt Alpha Knight','Antica','Alpha Knight'),{'command':'pt','text':'Party pública'})
   args=client.return_value.request.call_args;self.assertEqual(args.args[0:2],('/v1/assistant/command','POST'));self.assertEqual(set(args.args[2]),{'text','mundo','personagem'});credentials.assert_called_once()
   client.return_value.request.return_value={'command':'set','text':'danger'}
   with self.assertRaises(access.AccessError):access.assistant_command('!help')
  self.assertTrue(access.ALLOWED['POST'].fullmatch('/v1/assistant/command'))
 def test_both_chat_channels_resolve_queries_before_ai_without_domain_execution(self):
  with tempfile.TemporaryDirectory() as folder:
   store=assistente_tibiano.Store(folder);c=chat.Chat(store,folder)
   with patch('chat.assistente_consultas.responder',return_value='XP correto'),patch('chat.RemoteAIClient') as ai,patch.object(store,'execute') as mutate:
    for enabled in (False,True):
     reply=c.responder('!evolucao Alpha Knight',permitir_ia=enabled);self.assertEqual(reply['resposta'],'XP correto');self.assertEqual(reply['origem'],'local')
    ai.assert_not_called();mutate.assert_not_called()
 def test_query_failure_is_handled_and_never_falls_back_to_ai(self):
  with tempfile.TemporaryDirectory() as folder:
   c=chat.Chat(assistente_tibiano.Store(folder),folder)
   with patch('mensagem_automatica_access.assistant_command',side_effect=OSError('offline')),patch('chat.RemoteAIClient') as ai:
    result=c.responder('!duelo Alpha Knight x Beta Druid');self.assertIn('Não consegui consultar',result['resposta']);ai.assert_not_called()


if __name__=='__main__':unittest.main()
