import hashlib
import io
import json
import struct
from types import SimpleNamespace
from pathlib import Path
import queue
import tempfile
import threading
from threading import Thread as RealThread
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
        ding = patch('voz.play_wake_sound')
        self.ding = ding.start()
        self.addCleanup(ding.stop)
        self.service = Servico(self.tmp.name)
        self.addCleanup(self.service.close)

    def test_entendi_describes_local_timer_and_clears_unknown(self):
        self.assertEqual(self.service.estado()['entendi'], '')
        self.service.comando('timer de 30 segundos')
        self.assertEqual(self.service.estado()['entendi'], 'Criar timer · 30 s')
        self.service.comando('conversa qualquer')
        self.assertEqual(self.service.estado()['entendi'], '')

    def test_wake_session_click_and_tts_gate(self):
        with patch('voz.time.monotonic', return_value=100):
            self.service.receber_texto('tibia tudo timer de 30 segundos')
            self.assertEqual(self.service.estado()['timers'], [])
            self.service.receber_texto('hey tibia tudo')
            self.assertTrue(self.service._falas.empty(), 'Wake must not speak over the command')
            self.service.receber_texto('timer de um minuto e meio')
            self.assertEqual(len(self.service.estado()['timers']), 1)
            self.assertEqual(self.service.estado()['timers'][0]['duracao'], 90)
            self.service.receber_texto('timer de 20 segundos')
            self.assertEqual(len(self.service.estado()['timers']), 1)
            self.service._speaking.set()
            self.service.receber_texto('hey tibia tudo timer de 10 segundos')
            self.assertEqual(len(self.service.estado()['timers']), 1)
            self.service._speaking.clear()
            self.service._mic = Mock(is_alive=Mock(return_value=True))
            self.service._ready.set()
            self.service.escutar()
            self.service.receber_texto('timer de 20 segundos')
            self.assertEqual(len(self.service.estado()['timers']), 2)
        with patch('voz.time.monotonic', return_value=200):
            self.service.receber_texto('timer de 10 segundos')
            self.assertEqual(len(self.service._timers), 3)

    def test_direct_mode_continues_until_toggle_and_pause_resets_it(self):
        self.service._ready.set()
        self.service._mic = Mock(is_alive=Mock(return_value=True))
        self.assertFalse(self.service.estado()['direto'])
        self.assertTrue(self.service.escutar()['direto'])
        with patch('voz.time.monotonic', return_value=100):
            self.service.receber_texto('time trinta minutos')
        with patch('voz.time.monotonic', return_value=200):
            self.service.receber_texto('timer de 20 segundos')
            self.service._speaking.set()
            self.service.receber_texto('timer de 1 segundo')
            self.service._speaking.clear()
            self.assertEqual(len(self.service.estado()['timers']), 2)
            self.assertTrue(self.service.estado()['direto'])
            self.assertFalse(self.service.escutar()['direto'])
            self.service.receber_texto('timer de 1 segundo')
            self.assertEqual(len(self.service.estado()['timers']), 2)
            self.assertEqual(self.service.estado()['detalhe'], 'Aguardando comando: Hey Tibia')
            self.service.escutar()
            self.service.parar()
            self.assertFalse(self.service.estado()['direto'])
        self.ding.assert_not_called()

    def test_wake_ding_gate_ttl_and_combined_command(self):
        clock = [100]
        def ding():
            self.assertTrue(self.service._speaking.is_set())
            self.assertTrue(self.service._audio_reset.is_set())
            self.service.receber_texto('hey tibia tudo timer de 1 segundo')
            clock[0] = 105
        self.ding.side_effect = ding
        with patch('voz.time.monotonic', side_effect=lambda: clock[0]), patch.object(self.service._stop, 'wait'):
            self.service.receber_texto('timer de 30 segundos')
            self.ding.assert_not_called()
            self.service.receber_texto('hei tíbia tudo')
            self.ding.assert_called_once()
            self.assertEqual(self.service._armed_until, 113)
            self.assertFalse(self.service._speaking.is_set())
            self.assertTrue(self.service._falas.empty())
            self.service.receber_texto('hei tíbia tudo time trinta minutos')
            self.assertEqual(self.ding.call_count, 2)
            self.assertEqual(self.service.estado()['timers'][0]['duracao'], 1800)

    def test_ding_failure_does_not_block_combined_command(self):
        self.ding.side_effect = OSError('no speakers')
        self.service.receber_texto('hei tíbia tudo time trinta minutos')
        self.assertFalse(self.service._speaking.is_set())
        self.assertTrue(self.service._audio_reset.is_set())
        self.assertEqual(self.service.estado()['timers'][0]['duracao'], 1800)

    def test_clarification_expires_and_manual_pause_clears_session(self):
        with patch('voz.time.monotonic', return_value=100):
            self.service.criar(2, 'minuto')
            self.service.criar(2, 'minuto')
            self.service.receber_texto('hey tibia tudo cancela timer de dois minutos')
            self.assertEqual(len(self.service._timers), 2)
        with patch('voz.time.monotonic', return_value=109):
            self.service.receber_texto('o ultimo')
            self.assertEqual(len(self.service._timers), 2)
            self.service.receber_texto('hey tibia tudo')
            self.service.parar()
            self.service.receber_texto('timer de 30 segundos')
            self.assertEqual(len(self.service._timers), 2)

    def test_click_during_preparation_does_not_open_expiring_session(self):
        self.assertIn('erro', self.service.escutar())
        self.assertEqual(self.service._armed_until, 0)

    def test_clarification_only_accepts_the_pending_selection(self):
        with patch('voz.time.monotonic', return_value=100):
            self.service.criar(2, 'minuto')
            self.service.criar(2, 'minuto')
            self.service.receber_texto('hey tibia tudo cancela timer de dois minutos')
            self.service.receber_texto('timer de 30 segundos')
            self.assertEqual(len(self.service._timers), 2)
            self.service.receber_texto('o ultimo')
            self.assertEqual(len(self.service._timers), 1)

    def _mock_microphone(self, phrase, overflow=False, speaking=False):
        quiet = b'\0\0' * 100
        speech = struct.pack('<h', 2000) * 100
        blocks = [quiet] * 5 + [speech] * 3 + [quiet] * 5 + [speech] * 3 + [quiet] * 8
        real_queue = queue.Queue
        class AudioQueue(real_queue):
            def get(self, block=True, timeout=None):
                if timeout is not None and self.empty():
                    raise InterruptedError()
                return super().get(block, timeout)
        def stream(**kwargs):
            def enter():
                for audio in blocks:
                    kwargs['callback'](audio, 100, None, overflow)
            return Mock(__enter__=Mock(side_effect=enter), __exit__=Mock(return_value=False))
        recognizer = Mock()
        recognizer.FinalResult.return_value = json.dumps({'text': phrase})
        sd = SimpleNamespace(query_devices=lambda **kw: {'default_samplerate': 1000}, RawInputStream=stream)
        vosk = SimpleNamespace(SetLogLevel=Mock(), Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer))
        if speaking:
            self.service._speaking.set()
        with patch.object(self.service, '_models', return_value=('.', '.')), patch('voz.PiperSpeech'), patch('voz.queue.Queue', AudioQueue), patch.dict('sys.modules', {'sounddevice': sd, 'vosk': vosk}), patch('voz.time.monotonic', return_value=100):
            self.service._listen()
        self.service._speaking.clear()
        return recognizer

    def test_mock_audio_90_seconds_preserves_beginning_pause_and_end(self):
        recognizer = self._mock_microphone('hey tibia tudo coloca um timer de um minuto e meio')
        self.assertEqual(len(self.service._timers), 1)
        self.assertEqual(self.service._timers[0], (190, '90 segundos'))
        audio = recognizer.AcceptWaveform.call_args.args[0]
        self.assertEqual(len(audio), 4800)
        self.assertEqual(audio[:1000], b'\0\0' * 500)
        self.assertEqual(audio[-1600:], b'\0\0' * 800)

    def test_mock_audio_overflow_and_piper_never_execute(self):
        self._mock_microphone('hey tibia tudo timer de 30 segundos', overflow=True)
        self.assertEqual(self.service._timers, [])
        self.assertIn('interrompido', self.service.estado()['detalhe'])
        self._mock_microphone('hey tibia tudo timer de 30 segundos', speaking=True)
        self.assertEqual(self.service._timers, [])

    def test_microphone_failure_preserves_manual_timers(self):
        self.service.criar(2, 'minuto')
        sd = SimpleNamespace(query_devices=Mock(side_effect=OSError('missing')))
        vosk = SimpleNamespace(SetLogLevel=Mock(), Model=Mock())
        with patch.object(self.service, '_models', return_value=('.', '.')), patch('voz.PiperSpeech'), patch.dict('sys.modules', {'sounddevice': sd, 'vosk': vosk}):
            self.service._listen()
        self.assertEqual(self.service.estado()['estado'], 'erro')
        self.assertEqual(len(self.service._timers), 1)

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
        self.assertEqual(text, 'Timer de 1 segundo terminou.')
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


    def test_clarification_ttl_starts_after_long_question(self):
        with patch('voz.time.monotonic', return_value=100):
            self.service.criar(1, 'minuto')
            self.service.criar(2, 'minuto')
            while not self.service._falas.empty():
                self.service._falas.get_nowait()
            self.service.receber_texto('hey tibia tudo cancelar timer')
        self.service._speech = Mock()
        with patch('voz.time.monotonic', return_value=120), patch.object(self.service._stop, 'is_set', side_effect=[False, False, True]):
            self.service._say_loop()
        with patch('voz.time.monotonic', return_value=121):
            self.service.receber_texto('o de dois minutos')
        self.assertEqual([t[1] for t in self.service._timers], ['1 minuto'])

    def test_contextual_timer_selection_does_not_create_timer(self):
        for selection in ('o de dois minutos', 'o timer de dois minutos'):
            with self.subTest(selection=selection), patch('voz.time.monotonic', return_value=100):
                self.service._timers.clear()
                self.service.criar(1, 'minuto')
                self.service.criar(2, 'minuto')
                self.service.receber_texto('hey tibia tudo cancelar timer')
                self.service.receber_texto(selection)
                self.assertEqual([t[1] for t in self.service._timers], ['1 minuto'])

    def _online(self, transcript='crie um timer de um minuto e meio'):
        from voice.remote_ai_client import RemoteAIClient
        self.service._online_enabled = True
        self.service._online_client = Mock(spec=RemoteAIClient)
        self.service._online_client.transcribe.return_value = transcript
        return self.service._online_client

    def test_online_explicit_session_dispatches_portuguese_and_no_wake_never_uploads(self):
        client=self._online()
        pcm=struct.pack('<h',1000)*16000
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_audio('conversa sobre tibia tudo',pcm,16000)
            client.transcribe.assert_not_called()
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('unk',pcm,16000)
            self.assertEqual(self.service._timers,[(190,'90 segundos')])
            client.transcribe.assert_called_once()
            client.interpret.assert_not_called()

    def test_direct_online_rejects_silence_but_accepts_voiced_empty_vosk(self):
        client=self._online('timer de 30 segundos')
        self.service._ready.set()
        self.service.escutar()
        for pcm in (b'', b'\0\0'*16000, struct.pack('<h',299)*16000):
            self.service.receber_audio('',pcm,16000)
        client.transcribe.assert_not_called()
        # Quiet pre-roll/tail must not dilute a voiced block below the capture threshold.
        pcm=b'\0\0'*8000+struct.pack('<h',500)*1600+b'\0\0'*12800
        self.service.receber_audio('',pcm,16000)
        client.transcribe.assert_called_once()
        self.assertEqual(len(self.service._timers),1)

    def test_direct_online_continues_and_toggle_discards_inflight_result(self):
        client=self._online('timer de 30 segundos')
        self.service._ready.set()
        self.service.escutar()
        pcm=struct.pack('<h',1000)*16000
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_audio('unk',pcm,16000)
        with patch('voz.time.monotonic',return_value=200):
            self.service.receber_audio('unk',pcm,16000)
        self.assertEqual(client.transcribe.call_count,2)
        self.assertEqual(len(self.service._timers),2)
        client.transcribe.side_effect=lambda *args:(self.service.escutar(),'timer de 1 segundo')[1]
        self.service.receber_audio('unk',pcm,16000)
        self.assertFalse(self.service.estado()['direto'])
        self.assertEqual(len(self.service._timers),2)
        self.service.receber_audio('unk',pcm,16000)
        self.assertEqual(client.transcribe.call_count,3)
        self.ding.assert_not_called()

    def test_pause_during_ding_discards_combined_command(self):
        self.ding.side_effect=self.service._mic_stop.set
        self.service.receber_texto('hey tibia tudo timer de 30 segundos')
        self.assertEqual(self.service._timers,[])
        self.assertFalse(self.service._speaking.is_set())

    def test_online_same_phrase_cuts_wake_audio_and_requires_timestamps(self):
        client=self._online('alarme de meio minuto')
        prefix=struct.pack('<h',200)*8000
        command=struct.pack('<h',1000)*16000
        words=[{'word':'ei','start':0.,'end':.1},{'word':'tibia','start':.1,'end':.3},{'word':'tudo','start':.3,'end':.5},{'word':'unk','start':.5,'end':1.5}]
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_audio('ei tibia tudo unk',prefix+command,16000)
            client.transcribe.assert_not_called()
            self.service.receber_audio('ei tibia tudo unk',prefix+command,16000,words)
        import wave
        with wave.open(io.BytesIO(client.transcribe.call_args.args[0]),'rb') as audio:
            self.assertEqual(audio.readframes(16000),command)
        self.assertEqual(self.service._timers,[(130,'30 segundos')])

    def test_primary_wake_alone_in_direct_mode_is_local_only(self):
        client=self._online()
        self.service._direct_mode=True
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_audio('hey tibia',struct.pack('<h',1000)*16000,16000)
            self.assertEqual(self.service._armed_until,108)
        self.ding.assert_called_once()
        client.transcribe.assert_not_called()
        client.interpret.assert_not_called()
        self.assertTrue(self.service.estado()['direto'])
        self.assertEqual(self.service._timers,[])

    def test_primary_wake_audio_cuts_exact_two_words(self):
        client=self._online('timer de vinte segundos')
        prefix=struct.pack('<h',200)*8000
        command=struct.pack('<h',1000)*16000
        words=[{'word':'ei','start':0.,'end':.2},{'word':'tibia','start':.2,'end':.5},{'word':'unk','start':.5,'end':1.5}]
        self.service.receber_audio('ei tibia unk',prefix+command,16000,words)
        import wave
        with wave.open(io.BytesIO(client.transcribe.call_args.args[0]),'rb') as audio:
            self.assertEqual(audio.readframes(16000),command)
        self.assertEqual(self.service.estado()['timers'][0]['duracao'],20)
        self.ding.assert_called_once()

    def test_online_limit_preserved_when_local_unknown_and_ouvi_is_current(self):
        from voice.remote_ai_client import RemoteAIError
        for direct in (False,True):
            with self.subTest(direct=direct):
                client=self._online()
                self.service._direct_mode=direct
                self.service._ouvi='hey tibia tudo'
                self.service._armed_until=99999999999
                def unavailable(*args):
                    self.assertEqual(self.service.estado()['ouvi'],'unk')
                    raise RemoteAIError('Limite temporário ou diário do reconhecimento online atingido.')
                client.transcribe.side_effect=unavailable
                self.service.receber_audio('unk',struct.pack('<h',1000)*16000,16000)
                self.assertEqual(self.service.estado()['ouvi'],'unk')
                self.assertIn('Limite temporário ou diário',self.service.estado()['resposta'])
                self.assertNotIn('Não entendi',self.service.estado()['resposta'])
                client.transcribe.assert_called_once()
                client.interpret.assert_not_called()

    def test_pause_during_online_request_discards_remote_action(self):
        client=self._online()
        client.transcribe.side_effect=lambda *args:(self.service.parar(),'timer de 30 segundos')[1]
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('unk',struct.pack('<h',1000)*16000,16000)
        client.transcribe.assert_called_once()
        self.assertEqual(self.service._timers,[])
        self.assertEqual(self.service.estado()['estado'],'pausado')

    def test_online_nlu_only_unknown_and_ids_must_be_active(self):
        client=self._online('me lembre depois da pausa')
        client.interpret.return_value={'action':'create_timer','parameters':{'seconds':30},'needs_clarification':False,'clarification':None}
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('unk',struct.pack('<h',1000)*16000,16000)
        self.assertEqual(self.service._timers,[(130,'30 segundos')])
        client.interpret.assert_called_once()

    def test_clarification_rejects_new_order_even_with_wake(self):
        with patch('voz.time.monotonic',return_value=100):
            self.service.criar(1,'minuto');self.service.criar(2,'minuto')
            self.service.receber_texto('hey tibia tudo cancelar timer')
            self.service.receber_texto('hey tibia tudo timer de trinta segundos')
            self.assertEqual(len(self.service._timers),2)
            self.service.receber_texto('o ultimo')
            self.assertEqual(len(self.service._timers),1)

    def test_online_shared_and_cancel_use_local_dispatch_without_nlu(self):
        client=self._online('qual e minha shared no level 450')
        pcm=struct.pack('<h',1000)*16000
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('unk',pcm,16000)
            self.assertIn('300 até 675',self.service.estado()['resposta'])
            self.service.criar(30,'segundo')
            client.transcribe.return_value='cancela o ultimo timer'
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('unk',pcm,16000)
            self.assertEqual(self.service._timers,[])
        client.interpret.assert_not_called()

    def test_online_invalid_or_nonexistent_timer_intent_does_not_mutate(self):
        client=self._online('me lembre depois')
        pcm=struct.pack('<h',1000)*16000
        with patch('voz.time.monotonic',return_value=100):
            self.service.criar(30,'segundo')
            for intent in ({'action':'cancel_timer','parameters':{'timer_id':'missing'},'needs_clarification':False,'clarification':None},{'action':'create_timer','parameters':{'seconds':-1},'needs_clarification':False,'clarification':None}):
                client.interpret.return_value=intent
                self.service.receber_texto('hey tibia tudo')
                self.service.receber_audio('unk',pcm,16000)
                self.assertEqual(len(self.service._timers),1)

    def test_online_negation_silence_and_piper_never_upload(self):
        client=self._online()
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('nao crie um timer de trinta segundos',struct.pack('<h',1000)*16000,16000)
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('unk',b'\0\0'*16000,16000)
            self.service._speaking.set()
            self.service.receber_audio('hey tibia tudo timer de 30 segundos',struct.pack('<h',1000)*16000,16000)
        client.transcribe.assert_not_called()
        client.interpret.assert_not_called()
        self.assertEqual(self.service._timers,[])

    def test_online_timeout_local_fallback_once_and_network_holds_no_lock(self):
        from voice.remote_ai_client import RemoteAIError
        client=self._online()
        def unavailable(*args):
            self.assertFalse(self.service._lock._is_owned())
            raise RemoteAIError('indisponível')
        client.transcribe.side_effect=unavailable
        with patch('voz.time.monotonic',return_value=100):
            self.service.receber_texto('hey tibia tudo')
            self.service.receber_audio('timer de trinta segundos',struct.pack('<h',1000)*16000,16000)
            self.service.receber_audio('timer de trinta segundos',struct.pack('<h',1000)*16000,16000)
        self.assertEqual(self.service._timers,[(130,'30 segundos')])
        client.transcribe.assert_called_once()

    def test_online_configuration_persists_explicit_choice_without_exposing_token(self):
        with patch('voz.save_settings',return_value=(True,'a'*43)) as save:
            state=self.service.configurar_online('a'*43,True)
        save.assert_called_once_with(self.service.pasta,'a'*43,True)
        self.assertTrue(state['online_enabled'])
        self.assertTrue(state['online_configured'])
        self.assertNotIn('a'*43,json.dumps(state))

    def test_current_portuguese_negations_never_reach_cloud_or_execute(self):
        pcm=struct.pack('<h',1000)*16000
        for phrase in ('jamais crie timer de trinta segundos','evite criar timer de trinta segundos','deixe de criar timer de trinta segundos','sem criar timer de trinta segundos'):
            with self.subTest(phrase=phrase), patch('voz.time.monotonic',return_value=100):
                self.service._timers.clear()
                client=self._online(phrase)
                client.interpret.return_value={'action':'create_timer','parameters':{'seconds':30},'needs_clarification':False,'clarification':None}
                self.service.receber_texto('hey tibia tudo')
                self.service.receber_audio(phrase,pcm,16000)
                self.assertEqual(self.service._timers,[])
                client.transcribe.assert_not_called()
                client.interpret.assert_not_called()

    def test_configuration_invalidates_pending_http_before_slow_disk_write(self):
        client=self._online()
        saving=threading.Event();release=threading.Event()
        def slow_save(*args):
            saving.set()
            if not release.wait(2):
                raise OSError('test timeout')
            return False,'a'*43
        config_thread=RealThread(target=lambda:self.service.configurar_online('',False))
        def transcribe(*args):
            config_thread.start()
            self.assertTrue(saving.wait(1))
            return 'timer de trinta segundos'
        client.transcribe.side_effect=transcribe
        try:
            with patch('voz.save_settings',side_effect=slow_save), patch('voz.time.monotonic',return_value=100):
                self.service.receber_texto('hey tibia tudo')
                self.service.receber_audio('unk',struct.pack('<h',1000)*16000,16000)
                self.assertEqual(self.service._timers,[])
                self.assertFalse(self.service.estado()['online_enabled'])
                release.set();config_thread.join(1)
        finally:
            release.set()
            if config_thread.ident is not None:
                config_thread.join(1)

    def test_online_configuration_failure_keeps_runtime_off_and_clears_authorization(self):
        self._online()
        self.service._armed_until=999999999
        self.service._command_state['cancel']=True
        self.service._pending_prefix='timer de'
        with patch('voz.save_settings',side_effect=OSError('disk failure')):
            result=self.service.configurar_online('',False)
        self.assertIn('erro',result)
        self.assertFalse(self.service._online_enabled)
        self.assertIsNone(self.service._online_client)
        self.assertEqual(self.service._armed_until,0)
        self.assertEqual(self.service._command_state,{})
        self.assertEqual(self.service._pending_prefix,'')

if __name__ == '__main__':
    unittest.main()
