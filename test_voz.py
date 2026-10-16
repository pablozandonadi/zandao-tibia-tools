import hashlib
import io
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from voz import Servico


class VozTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        threads = patch('voz.threading.Thread')
        threads.start()
        self.addCleanup(threads.stop)
        self.service = Servico(self.tmp.name)
        self.addCleanup(self.service.close)

    def test_manual_and_voice_share_timers_and_stable_ids(self):
        with patch('voz.time.monotonic', return_value=100):
            first = self.service.criar(30, 'segundo')['timers'][0]
            self.service.comando('novo timer de dois minutos')
            snapshot = self.service.estado()
            self.assertEqual(len(snapshot['timers']), 2)
            self.assertEqual(snapshot['timers'][0]['id'], first['id'])
            self.assertEqual(snapshot['timers'][1]['restante'], 120)
            self.service.cancelar(first['id'])
            self.assertEqual(self.service.estado()['timers'][0]['label'], '2 minutos')
            self.service.comando('cancelar timer')
            self.assertEqual(self.service.estado()['timers'], [])
            self.assertIn('erro', self.service.cancelar(first['id']))

    def test_manual_validation_does_not_mutate(self):
        for value, unit in ((True, 'minuto'), ('30', 'segundo'), (1.5, 'minuto'), (0, 'segundo'), (181, 'minuto'), (3, 'hora')):
            self.assertIn('erro', self.service.criar(value, unit))
        self.assertEqual(self.service.estado()['timers'], [])

    def test_manual_exact_duplicate_and_voice_followup(self):
        state = {}
        with patch('voz.time.monotonic', return_value=100):
            self.service.criar(30, 'segundo')
            second = self.service.criar(30, 'segundo')['timers'][1]
            self.service.criar(2, 'minuto')
            self.service.cancelar(second['id'])
            self.assertEqual([t['label'] for t in self.service.estado()['timers']], ['30 segundos', '2 minutos'])
            self.assertIn('2 timers ativos', self.service.comando('cancelar timer', state))
            self.service.comando('dois minutos', state)
            self.assertEqual([t['label'] for t in self.service.estado()['timers']], ['30 segundos'])

    def test_expiration_enqueues_once_without_waiting_for_speech(self):
        with patch('voz.time.monotonic', return_value=100):
            self.service.criar(1, 'segundo')
        self.service._falas.get_nowait()  # Creation acknowledgement.
        with patch('voz.time.monotonic', return_value=102), patch.object(self.service._stop, 'wait', side_effect=[False, True]):
            self.service._watch()
        self.assertEqual(self.service.estado()['timers'], [])
        text, done = self.service._falas.get_nowait()
        self.assertEqual(text, 'Timer de 1 segundo terminou, tibiano.')
        self.assertFalse(done.is_set())
        self.assertTrue(self.service._falas.empty())

    def test_shared_reads_actual_data_directory(self):
        (Path(self.tmp.name) / 'meus_personagens.json').write_text('{"lista":[{"nome":"A","level":300}]}', encoding='utf-8')
        self.assertIn('200 até 450', self.service.comando('qual meu share'))

    def test_start_idempotent_stop_preserves_timers(self):
        self.service._mic = Mock()
        self.service._mic.is_alive.return_value = True
        with patch('voz.threading.Thread') as constructor:
            self.service.iniciar()
            constructor.assert_not_called()
        self.service.criar(20, 'segundo')
        self.assertEqual(self.service.parar()['estado'], 'pausado')
        self.assertEqual(len(self.service.estado()['timers']), 1)
        self.assertTrue(self.service._mic_stop.is_set())
        self.service._status('preparando', 'Download em andamento')
        self.assertEqual(self.service.estado()['estado'], 'pausado')

    def test_download_hash_atomic_and_rejects_corruption(self):
        payload = b'fake voice model'
        digest = hashlib.sha256(payload).hexdigest()
        target = Path(self.tmp.name) / 'models' / 'voice.onnx'
        def response(data):
            result = io.BytesIO(data)
            result.headers = {'Content-Length': str(len(data))}
            return result
        with patch('voz.urllib.request.urlopen', return_value=response(payload)):
            self.service._download('https://example.invalid/model', target, 'voz', len(payload), digest)
        self.assertEqual(target.read_bytes(), payload)
        with patch('voz.urllib.request.urlopen') as request:
            self.service._download('https://example.invalid/model', target, 'voz', len(payload), digest)
            request.assert_not_called()
        target.unlink()
        with patch('voz.urllib.request.urlopen', return_value=response(b'wrong')):
            with self.assertRaises(OSError):
                self.service._download('https://example.invalid/model', target, 'voz', len(payload), digest)
        self.assertFalse(target.exists())
        self.assertFalse(target.with_name(target.name + '.download').exists())

    def test_extract_rejects_traversal(self):
        root = Path(self.tmp.name) / 'voice_models'
        root.mkdir()
        archive = root / 'vosk.zip'
        with zipfile.ZipFile(archive, 'w') as zipped:
            zipped.writestr('../escape', 'invalid')
        with patch.object(self.service, '_download'):
            with self.assertRaises(ValueError):
                self.service._models()
        self.assertFalse((root.parent / 'escape').exists())

    def test_speech_failure_completes_waiter(self):
        self.service._speech = Mock(side_effect=OSError('no speakers'))
        self.service._reply('Resposta de teste.')
        _, done = self.service._falas.queue[0]
        with patch.object(self.service._stop, 'is_set', side_effect=[False, True]):
            self.service._say_loop()
        self.assertTrue(done.is_set())
        self.assertFalse(self.service._speaking.is_set())
        self.assertIn('saída de voz falhou', self.service.estado()['detalhe'])


if __name__ == '__main__':
    unittest.main()
