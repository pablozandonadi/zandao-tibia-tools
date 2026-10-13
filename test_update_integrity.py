import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import atualizacoes as a
from assinatura import verificar_assinatura
PAYLOAD=b'MZ'+b'test executable bytes'*10
HASH=hashlib.sha256(PAYLOAD).hexdigest()
class Response(io.BytesIO):
    def __init__(self,payload=PAYLOAD,url=None,length=None):
        super().__init__(payload);self.url=url or URL
        self.headers={'Content-Length':str(len(payload) if length is None else length)}
    def geturl(self):return self.url
URL=f'https://github.com/{a.REPO_GITHUB}/releases/download/v1.0.22/{a.NOME_INSTALADOR}'
class IntegrityTests(unittest.TestCase):
    def download(self,root,payload=PAYLOAD,**kw):
        with patch.object(a.tempfile,'gettempdir',return_value=root),patch.object(a.urllib.request,'urlopen',return_value=Response(payload,**kw)),patch.object(a,'verificar_assinatura',return_value={'status':'NotSigned'}):
            return a.baixar_instalador(URL,sha256=HASH,tamanho=len(PAYLOAD))
    def test_unique_verified_files_and_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            one=self.download(directory);two=self.download(directory)
            self.assertNotEqual(one,two)
            self.assertEqual(Path(one).read_bytes(),PAYLOAD)
            self.assertFalse(list(Path(directory).rglob('*.part')))
    def test_changed_bytes_are_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):self.download(directory,b'MZ'+b'X'*(len(PAYLOAD)-2))
            self.assertEqual(list(Path(directory).iterdir()),[])
    def test_truncated_and_excess_downloads(self):
        for payload in (PAYLOAD[:-1],PAYLOAD+b'X'):
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):self.download(directory,payload,length=len(PAYLOAD))
                self.assertFalse(list(Path(directory).iterdir()))
    def test_html_instead_of_exe_rejected_even_matching_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'x';file.write_bytes(b'HTML')
            with self.assertRaises(ValueError):a.validar_instalador(file,hashlib.sha256(b'HTML').hexdigest(),4)
    def test_untrusted_url_and_missing_metadata_never_request(self):
        with patch.object(a.urllib.request,'urlopen') as request:
            for url,sha,size in [('https://evil.test/x',HASH,len(PAYLOAD)),(URL,None,len(PAYLOAD)),(URL,HASH,None)]:
                with self.assertRaises(ValueError):a.baixar_instalador(url,sha256=sha,tamanho=size)
            request.assert_not_called()
    def test_redirect_away_from_github_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):self.download(directory,url='https://evil.test/payload')
    def test_offline_does_not_leave_partial_and_can_retry(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(a.tempfile,'gettempdir',return_value=directory),patch.object(a.urllib.request,'urlopen',side_effect=OSError('offline')):
            with self.assertRaises(OSError):a.baixar_instalador(URL,sha256=HASH,tamanho=len(PAYLOAD))
            self.assertFalse(list(Path(directory).iterdir()))
        with tempfile.TemporaryDirectory() as directory:self.download(directory)
    def test_signature_required_and_wrong_publisher(self):
        from types import SimpleNamespace
        cases=[({'required':True,'thumbprints':['A'*40]},{'status':'NotSigned'}),({'required':True,'thumbprints':['A'*40]},{'status':'Valid','thumbprint':'B'*40}),({'required':False,'thumbprints':[]},{'status':'HashMismatch'})]
        for policy,result in cases:
            with patch('assinatura.sys.platform','win32'),patch('assinatura.politica',return_value=policy),patch('assinatura.native_signature',return_value=result):
                with self.assertRaises(ValueError):verificar_assinatura('test.exe')
    def test_matching_signed_publisher(self):
        from types import SimpleNamespace
        with patch('assinatura.sys.platform','win32'),patch('assinatura.politica',return_value={'required':True,'thumbprints':['A'*40]}),patch('assinatura.native_signature',return_value={'status':'Valid','thumbprint':'A'*40}):
            self.assertEqual(verificar_assinatura('test.exe')['status'],'Valid')
    def test_bad_download_never_executes_installer(self):
        import web_api
        api=web_api.API();api._atualizacao_info={'url_instalador':URL,'sha256':HASH,'tamanho':len(PAYLOAD),'url_release':'official'}
        with patch('web_api.atualizacoes.baixar_instalador',side_effect=ValueError('hash mismatch')),patch.object(api,'_emit') as emit,patch('web_api.subprocess.Popen') as execute,patch('web_api.os._exit') as exit:
            api._trabalho_instalar_atualizacao()
            execute.assert_not_called();exit.assert_not_called()
            self.assertEqual(emit.call_args.args[0],'onFalhaAtualizacao')

    def test_temp_directory_failure_releases_download_lock(self):
        with patch.object(a.tempfile,'mkdtemp',side_effect=OSError('no space')):
            with self.assertRaises(OSError):a.baixar_instalador(URL,sha256=HASH,tamanho=len(PAYLOAD))
        self.assertFalse(a._DOWNLOAD_LOCK.locked())
