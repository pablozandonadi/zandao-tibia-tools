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

if __name__=='__main__':unittest.main()
