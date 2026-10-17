import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch

class RemoteClientTests(unittest.TestCase):
    def test_pcm_resample_and_fixed_authenticated_request(self):
        from voice.remote_ai_client import RemoteAIClient, pcm_wav
        import wave
        raw = struct.pack('<h',1000)*48000
        wav = pcm_wav(raw,48000)
        with wave.open(io.BytesIO(wav),'rb') as audio:
            self.assertEqual((audio.getframerate(),audio.getnframes(),audio.getnchannels()),(16000,16000,1))
        response=io.BytesIO(json.dumps({'request_id':'b92e3ae7-3591-4cd9-9188-1e5422fa1121','text':'crie um timer de trinta segundos'}).encode())
        response.status=200
        client=RemoteAIClient('a'*43);client._opener=Mock();client._opener.open.return_value=response
        self.assertEqual(client.transcribe(wav,'b92e3ae7-3591-4cd9-9188-1e5422fa1121'),'crie um timer de trinta segundos')
        request=client._opener.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://tibia-tudo-voz.pablo-0af.workers.dev/transcribe')
        self.assertEqual(request.get_header('Authorization'),'Bearer '+'a'*43)
        self.assertEqual(request.get_header('User-agent'),'TibiaTudo/1.0')
        self.assertEqual(client._opener.open.call_args.kwargs['timeout'],15)

    def test_optional_vocabulary_header(self):
        import base64
        from voice.remote_ai_client import RemoteAIClient
        rid='b92e3ae7-3591-4cd9-9188-1e5422fa1121'
        for terms in ([], ['Drume', 'Ahau']):
            response=io.BytesIO(json.dumps({'request_id':rid, 'text':'Drume'}).encode());response.status=200
            client=RemoteAIClient('a'*43);client._opener=Mock();client._opener.open.return_value=response
            client.transcribe(b'fake',rid,terms)
            header=client._opener.open.call_args.args[0].get_header('X-vocabulary')
            if terms:self.assertEqual(json.loads(base64.urlsafe_b64decode(header+'==')),terms)
            else:self.assertIsNone(header)

    def test_http_statuses_and_limit_details_are_sanitized_without_retry(self):
        from voice.remote_ai_client import RemoteAIClient, RemoteAIError
        from urllib.error import HTTPError, URLError
        cases=[(429,{},'Limite temporário ou diário'),(401,{},'não autorizado'),(403,{},'bloqueado'),(502,{},'Servidor'),
               (429,{'limit_reason':'user_daily_requests','retry_after_seconds':60},'Limite diário de comandos'),
               (429,{'limit_reason':'global_daily_budget','retry_after_seconds':70},'Limite diário de uso do serviço'),
               (429,{'limit_reason':['secret'],'retry_after_seconds':True},'Limite temporário ou diário'),
               (429,{'limit_reason':'secret','retry_after_seconds':86401},'Limite temporário ou diário')]
        for status,body,message in cases:
            with self.subTest(status=status,body=body):
                client=RemoteAIClient('a'*43);client._opener=Mock()
                client._opener.open.side_effect=HTTPError('https://fixed',status,'private-secret',{},io.BytesIO(json.dumps({**body,'raw':'private-secret'}).encode()))
                with self.assertRaisesRegex(RemoteAIError,message) as error:
                    client.transcribe(b'fake','b92e3ae7-3591-4cd9-9188-1e5422fa1121')
                self.assertNotIn('private-secret',str(error.exception))
                client._opener.open.assert_called_once()
        client._opener.open.reset_mock()
        client._opener.open.side_effect=URLError('private-secret')
        with self.assertRaisesRegex(RemoteAIError,'conexão'):
            client.transcribe(b'fake','b92e3ae7-3591-4cd9-9188-1e5422fa1121')
        client._opener.open.assert_called_once()

    def test_invalid_intents_are_rejected(self):
        from voice.remote_ai_client import valid_intent
        good={'action':'create_timer','parameters':{'seconds':30},'needs_clarification':False,'clarification':None}
        self.assertTrue(valid_intent(good))
        for params in ({'seconds':True},{'seconds':30.0},{'seconds':-1},{'seconds':10801},{'seconds':30,'shell':'oops'}):
            self.assertFalse(valid_intent({**good,'parameters':params}))
        self.assertFalse(valid_intent({**good,'action':'shell'}))
        self.assertFalse(valid_intent({**good,'extra':1}))

    def test_private_settings_are_dpapi_only_and_off_without_token(self):
        from voice.remote_ai_client import load_settings, save_settings
        with tempfile.TemporaryDirectory() as folder, patch('voz_credenciais._proteger',return_value=b'encrypted') as protect, patch('voz_credenciais._desproteger',return_value='a'*43):
            self.assertEqual(load_settings(folder),(False,None))
            save_settings(folder,'a'*43,True)
            protect.assert_called_once_with('a'*43)
            self.assertEqual(load_settings(folder),(True,'a'*43))
            self.assertNotIn(b'a'*43,(Path(folder)/'voice-online.dpapi').read_bytes())
            with patch('voz_credenciais._desproteger',side_effect=ValueError('wrong user')):
                self.assertEqual(load_settings(folder),(False,None))

    def test_redirect_and_oversize_do_not_expose_provider_body(self):
        from voice.remote_ai_client import RemoteAIClient, RemoteAIError, NoRedirect
        from urllib.error import HTTPError
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'redirect',{},'https://evil.example'))
        client=RemoteAIClient('a'*43);client._opener=Mock()
        client._opener.open.side_effect=HTTPError('https://fixed',401,'secret',{},io.BytesIO(b'secret'))
        with self.assertRaisesRegex(RemoteAIError,'não autorizado') as error:
            client.transcribe(b'fake','b92e3ae7-3591-4cd9-9188-1e5422fa1121')
        self.assertNotIn('secret',str(error.exception))
        client._opener.open.side_effect=None
        response=io.BytesIO(b'x'*8193);response.status=200;client._opener.open.return_value=response
        with self.assertRaises(RemoteAIError):client.transcribe(b'fake','b92e3ae7-3591-4cd9-9188-1e5422fa1121')
    def _chat_client(self, payload):
        from voice.remote_ai_client import RemoteAIClient
        client=RemoteAIClient('a'*43);client._opener=Mock()
        response=io.BytesIO(json.dumps(payload).encode());response.status=200;client._opener.open.return_value=response
        return client

    def test_chat_posts_the_exact_body_and_returns_reply(self):
        rid='b92e3ae7-3591-4cd9-9188-1e5422fa1121'
        messages=[{'role':'user','text':'oi'},{'role':'assistant','text':'Olá!'},{'role':'user','text':'qual a stamina cheia? ã'}]
        client=self._chat_client({'request_id':rid,'kind':'reply','text':'42h','intent':None})
        self.assertEqual(client.chat(messages,rid),{'kind':'reply','text':'42h','intent':None})
        request=client._opener.open.call_args.args[0]
        self.assertEqual(request.full_url,'https://tibia-tudo-voz.pablo-0af.workers.dev/chat')
        self.assertEqual(request.get_header('Content-type'),'application/json')
        self.assertEqual(request.get_header('X-request-id'),rid)
        self.assertEqual(json.loads(request.data.decode('utf-8')),{'request_id':rid,'messages':messages})
        self.assertIn('ã'.encode(),request.data)

    def test_chat_rejects_invalid_messages_without_network(self):
        from voice.remote_ai_client import RemoteAIClient, RemoteAIError
        rid='b92e3ae7-3591-4cd9-9188-1e5422fa1121'
        ok={'role':'user','text':'oi'}
        seven=[{'role':'user' if (7-i)%2 else 'assistant','text':'oi'} for i in range(7)]
        cases=[None,'oi',{},[],seven,[{**ok,'text':''}],[{**ok,'text':'  '}],[{**ok,'text':'x'*501}],[{**ok,'text':7}],[{**ok,'role':'system'}],[{**ok,'role':'assistant'}],
               [{**ok,'extra':1}],[{'role':'user'}],[None],['oi'],[ok,{'role':'assistant','text':'olá'}]]
        for messages in cases:
            with self.subTest(messages=messages):
                client=RemoteAIClient('a'*43);client._opener=Mock()
                with self.assertRaises(RemoteAIError):client.chat(messages,rid)
                client._opener.open.assert_not_called()
        six=[{'role':'user' if (6-i)%2 else 'assistant','text':'x'*500} for i in range(6)]
        self.assertEqual(self._chat_client({'request_id':rid,'kind':'out_of_scope','text':None,'intent':None}).chat(six,rid)['kind'],'out_of_scope')

    def test_chat_accepts_action_and_out_of_scope_and_guards_dates(self):
        rid='b92e3ae7-3591-4cd9-9188-1e5422fa1121'
        timer={'action':'create_timer','parameters':{'seconds':30},'needs_clarification':False,'clarification':None}
        kill={'action':'boss.kill','parameters':{'boss_id':'drume','killed_at':None,'boosted':False},'needs_clarification':False,'clarification':None}
        unknown={'action':'unknown','parameters':{},'needs_clarification':True,'clarification':'Confirme a data pelo formulário. Datas do fallback online não são presumidas; use o comando local com horário explícito.'}
        for text,reply,want in [('crie um timer de 30 segundos',{'kind':'action','text':None,'intent':timer},timer),
                                ('crie um timer de 30 segundos',{'kind':'action','text':'Ok.','intent':timer},timer),
                                ('matei o Drume ontem',{'kind':'action','text':'Anotado.','intent':kill},unknown),
                                ('matei o Drume',{'kind':'action','text':None,'intent':kill},kill),
                                ('quem ganhou o jogo?',{'kind':'out_of_scope','text':None,'intent':None},None)]:
            with self.subTest(text=text,kind=reply['kind']):
                client=self._chat_client({'request_id':rid,**reply})
                result=client.chat([{'role':'user','text':'oi'},{'role':'assistant','text':'Olá!'},{'role':'user','text':text}],rid)
                self.assertEqual(result,{'kind':reply['kind'],'text':reply['text'],'intent':want})
        for turns,want in [([{'role':'user','text':'ontem foi legal'},{'role':'assistant','text':'Que bom!'},{'role':'user','text':'matei o Drume'}],unknown),
                           ([{'role':'user','text':'matei o Drume ontem'},{'role':'assistant','text':'Confirma o abate do Drume?'},{'role':'user','text':'sim'}],unknown),
                           ([{'role':'user','text':'matei o Drume'},{'role':'assistant','text':'Confirma o abate do Drume?'},{'role':'user','text':'sim'}],kill)]:
            with self.subTest(turns=turns):
                client=self._chat_client({'request_id':rid,'kind':'action','text':None,'intent':kill})
                self.assertEqual(client.chat(turns,rid)['intent'],want)

    def test_chat_rejects_invalid_responses(self):
        from voice.remote_ai_client import RemoteAIError
        rid='b92e3ae7-3591-4cd9-9188-1e5422fa1121'
        timer={'action':'create_timer','parameters':{'seconds':30},'needs_clarification':False,'clarification':None}
        base={'request_id':rid,'kind':'reply','text':'ok','intent':None}
        bad=[{**base,'extra':1},{k:v for k,v in base.items() if k!='text'},{k:v for k,v in base.items() if k!='kind'},{**base,'kind':'banana'},{**base,'kind':['reply']},{**base,'kind':None},
             {**base,'text':None},{**base,'text':''},{**base,'text':'  '},{**base,'text':7},{**base,'text':'x'*601},{**base,'intent':timer},
             {**base,'kind':'action','intent':None},{**base,'kind':'action','intent':{**timer,'action':'shell'}},{**base,'kind':'action','intent':{**timer,'parameters':{'seconds':-1}}},{**base,'kind':'action','text':7,'intent':timer},{**base,'kind':'action','text':'x'*601,'intent':timer},
             {**base,'kind':'out_of_scope','text':'Não falo disso.'},{**base,'kind':'out_of_scope','text':None,'intent':timer}]
        for payload in bad:
            with self.subTest(payload=payload):
                client=self._chat_client(payload)
                with self.assertRaisesRegex(RemoteAIError,'Resposta online inválida'):client.chat([{'role':'user','text':'oi'}],rid)
        client=self._chat_client({**base,'request_id':'11111111-1111-4111-8111-111111111111'})
        with self.assertRaises(RemoteAIError):client.chat([{'role':'user','text':'oi'}],rid)

if __name__=='__main__':unittest.main()
