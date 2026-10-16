import json
import queue
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

if __package__:
    from . import spike_assistente
    # Keep standalone mock targets pointed at the package module during root discovery.
    sys.modules.setdefault('spike_assistente', spike_assistente)

from spike_assistente import command_after_wake, dispatch, minutes_from, shared_reply, speak, recognition_grammar, PiperSpeech, main, TIMER_VERBS, TIMER_NAMES, TIMER_LINKS, timer_prefix, GREETING


class VoiceSpikeTests(unittest.TestCase):
    def test_new_timers_cancel_selection_and_remaining_timer(self):
        timers, state = [], {}
        dispatch('novo timer de 40 segundos', '.', timers, 100, state)
        dispatch('coloca timer de dois minutos', '.', timers, 100, state)
        reply = dispatch('cancelar timer', '.', timers, 100, state)
        self.assertIn('2 timers ativos: 40 segundos, 2 minutos', reply)
        self.assertTrue(state['cancel'])
        self.assertIn('cancelado', dispatch('de dois minutos', '.', timers, 100, state))
        self.assertEqual(timers, [(140, '40 segundos')])
        self.assertFalse(state['cancel'])
        self.assertIn('cancelado', dispatch('apagar alarme', '.', timers, 100, state))
        self.assertEqual(timers, [])
        self.assertIn('Nenhum timer ativo', dispatch('remover timer', '.', timers, 100, state))

    def test_cancel_matches_duration_latest_and_ignores_expired(self):
        timers = [(90, '1 minuto'), (200, '2 minutos'), (300, '120 segundos'), (400, '40 segundos')]
        dispatch('cancelar timer de dois minutos', '.', timers, 100)
        self.assertEqual(timers, [(90, '1 minuto'), (200, '2 minutos'), (400, '40 segundos')])
        dispatch('excluir o último timer', '.', timers, 100)
        self.assertEqual(timers, [(90, '1 minuto'), (200, '2 minutos')])
        for invalid in ('cancelar timer de [unk] dois minutos', 'cancelar timer de vinte e onze minutos', 'cancelar timer de nove segundos'):
            dispatch(invalid, '.', timers, 100)
            self.assertEqual(timers, [(90, '1 minuto'), (200, '2 minutos')])
        dispatch('cancelar timer', '.', timers, 100)
        self.assertEqual(timers, [(90, '1 minuto')])

    def test_shared_question_variations_and_all_replies_address_tibiano(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'meus_personagens.json').write_text('{"lista":[{"nome":"A","level":300}]}', encoding='utf-8')
            for text in ('até que level shareio', 'qual é o meu share', 'até que level divide experiência', 'qual meu compartilhado'):
                reply = dispatch(text, tmp, [], 100)
                self.assertIn('200 até 450', reply)
                self.assertEqual(reply.count('tibiano'), 1)
            for text in ('novo timer de 20 segundos', 'timer de 181 minutos', 'cancelar timer', 'não sei'):
                self.assertEqual(dispatch(text, tmp, [], 100).count('tibiano'), 1)

    def test_voice_windows_start_after_spoken_greeting_and_selection(self):
        clock = [100]
        phrases = iter(((0, 'ei tíbia tudo'), (6, 'novo alarme de dois minutos'),
                        (0, 'ei tíbia tudo novo alarme de quarenta segundos'),
                        (0, 'ei tíbia tudo cancelar alarme'), (6, 'dois minutos'),
                        (0, 'ei tíbia tudo cancelar alarme'),
                        (0, 'ei tíbia tudo novo alarme de dois minutos'),
                        (0, 'ei tíbia tudo novo alarme de três minutos'),
                        (0, 'ei tíbia tudo cancelar alarme'), (9, 'dois minutos'),
                        (0, 'ei tíbia tudo novo alarme de quatro minutos'),
                        (0, 'ei tíbia tudo cancelar alarme')))
        recognizer = Mock()
        recognizer.AcceptWaveform.return_value = True
        def result():
            try:
                delay, text = next(phrases)
                clock[0] += delay
                return json.dumps({'text': text})
            except StopIteration:
                raise KeyboardInterrupt
        recognizer.Result.side_effect = result
        chunks = Mock()
        chunks.get.return_value = b'audio'
        chunks.get_nowait.side_effect = queue.Empty
        sd = SimpleNamespace(query_devices=lambda **kwargs: {'default_samplerate': 16000}, RawInputStream=Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock(return_value=False))))
        vosk = SimpleNamespace(SetLogLevel=Mock(), Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer))
        spoken = []
        def speech(text):
            spoken.append(text)
            # A slow greeting/question must not consume the eight-second command window.
            if text == GREETING or 'Qual deseja cancelar' in text:
                clock[0] += 10
        with tempfile.TemporaryDirectory() as model, patch.dict('sys.modules', {'sounddevice': sd, 'vosk': vosk}), patch('sys.argv', ['spike', '--model', model, '--channel', 'source']), patch('spike_assistente.prepare_speech', return_value=speech), patch('spike_assistente.time.monotonic', side_effect=lambda: clock[0]), patch('spike_assistente.time.sleep'), patch('spike_assistente.queue.Queue', return_value=chunks), patch('builtins.print'):
            with self.assertRaises(KeyboardInterrupt):
                main()
        self.assertEqual(spoken[0], GREETING)
        self.assertTrue(any('2 timers ativos' in reply for reply in spoken))
        self.assertIn('Um timer de 2 minutos cancelado, tibiano.', spoken)
        self.assertIn('Um timer de 40 segundos cancelado, tibiano.', spoken)
        # Expired follow-up is ignored, then a fresh wake command creates normally.
        self.assertIn('Timer de 4 minutos iniciado, tibiano.', spoken)
        self.assertIn('Você tem 3 timers ativos: 2 minutos, 3 minutos, 4 minutos. Qual deseja cancelar, tibiano?', spoken)

    def test_wake_and_accents(self):
        self.assertEqual(command_after_wake('Hey Tíbia Tudo ligar um timer de 30 minutos'), 'ligar um timer de 30 minutos')
        self.assertEqual(command_after_wake('ei tibia tudo'), '')
        self.assertIsNone(command_after_wake('ligar um timer de 30 minutos'))
        self.assertIsNone(command_after_wake('conversa hey tibia tudo'))

    def test_portuguese_minutes(self):
        for text, expected in [('trinta minutos', 30), ('vinte e cinco minutos', 25), ('1 minuto', 1), ('setenta minutos', 70), ('oitenta e dois minutos', 82)]:
            self.assertEqual(minutes_from(text), expected)
        self.assertEqual(minutes_from('cento e vinte minutos'), 120)
        for unsupported in ('trinta e onze minutos', 'vinte e quinze minutos', 'cento e cento minutos'):
            self.assertIsNone(minutes_from(unsupported))

    def test_timer_only_in_memory(self):
        timers = []
        self.assertIn('30 minutos iniciado', dispatch('ligar um timer de trinta minutos', '.', timers, 100))
        self.assertEqual(timers, [(1900, '30 minutos')])
        dispatch('timer de 0 minutos', '.', timers, 100)
        dispatch('timer de 181 minutos', '.', timers, 100)
        self.assertEqual(len(timers), 1)

    def test_seconds_variable_minutes_and_timer_names(self):
        timers = []
        dispatch('ligar um cronômetro de e vinte e nove minutos', '.', timers, 100)
        self.assertEqual(timers, [(1840, '29 minutos')])
        timers = []
        dispatch('ligar um cronômetro de e cento e vinte minutos', '.', timers, 100)
        self.assertEqual(timers, [(7300, '120 minutos')])
        for invalid in ('ligar um cronômetro de e duzentos e vinte minutos', 'ligar um cronômetro de e cento e cento minutos'):
            dispatch(invalid, '.', timers, 100)
        self.assertEqual(len(timers), 1)
        for name in ('timer', 'temporizador', 'cronômetro', 'alarme', 'time'):
            timers = []
            self.assertIn('30 segundos iniciado', dispatch(f'colocar um {name} de trinta segundos', '.', timers, 100))
            self.assertEqual(timers, [(130, '30 segundos')])
        for duration, expected in [('dois', 2), ('três', 3), ('dez', 10), ('vinte e nove', 29), ('cento e oitenta', 180)]:
            timers = []
            dispatch(f'gere um timer de {duration} minutos', '.', timers, 100)
            self.assertEqual(timers, [(100 + expected * 60, f'{expected} minutos')])
        timers = []
        self.assertIn('1 segundo iniciado', dispatch('iniciar um alarme de um segundo', '.', timers, 0))
        for invalid in ('ligar um timer de zero segundos', 'timer de 181 segundos', 'timer de 0 minutos', 'time aleatório de 30 segundos'):
            dispatch(invalid, '.', timers, 0)
        self.assertEqual(len(timers), 1)

    def test_natural_timer_variations(self):
        for verb in TIMER_VERBS:
            for noun in TIMER_NAMES:
                for link in (*TIMER_LINKS, ''):
                    for article in ('um ', ''):
                        with self.subTest(verb=verb, noun=noun, link=link, article=article):
                            timers = []
                            dispatch(f'por favor {verb} {article}{noun} {link} trinta segundos por favor', '.', timers, 100)
                            self.assertEqual(timers, [(130, '30 segundos')])
        for text in ('um alarme para daqui a trinta segundos', 'alarme trinta segundos', 'coloca um alarme pra dois minutos'):
            timers = []
            dispatch(text, '.', timers, 100)
            self.assertEqual(timers, [(220, '2 minutos')] if 'dois' in text else [(130, '30 segundos')])

    def test_uncertain_or_invalid_duration_never_starts_timer(self):
        for text in ('cria um alarme de [unk] trinta segundos',
                     'liga um timer de duzentos e trinta segundos',
                     'coloca um alarme de trinta segundos qualquer coisa',
                     'coloca um alarme de trinta e onze segundos',
                     'coloca um alarme de trinta por vinte segundos',
                     'alarme [unk] de trinta segundos',
                     'qual meu compartilhado [unk]', '[unk]'):
            with self.subTest(text=text):
                timers = []
                dispatch(text, '.', timers, 100)
                self.assertEqual(timers, [])

    def test_armed_retry_ignores_unknown_noise_and_shows_recognition(self):
        phrases = iter(('conversa ambiente', 'ei tíbia tudo', '[unk]', '[unk] [unk]',
                        'outra frase', 'cria um alarme pra trinta segundos', 'conversa ambiente'))
        recognizer = Mock()
        recognizer.AcceptWaveform.return_value = True
        def result():
            try:
                return json.dumps({'text': next(phrases)})
            except StopIteration:
                raise KeyboardInterrupt
        recognizer.Result.side_effect = result
        def stream(**kwargs):
            return Mock(__enter__=Mock(), __exit__=Mock(return_value=False))
        chunks = Mock()
        chunks.get.return_value = b'audio'
        chunks.get_nowait.side_effect = queue.Empty
        sd = SimpleNamespace(query_devices=lambda **kwargs: {'default_samplerate': 16000}, RawInputStream=stream)
        vosk = SimpleNamespace(SetLogLevel=Mock(), Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer))
        with tempfile.TemporaryDirectory() as model, patch.dict('sys.modules', {'sounddevice': sd, 'vosk': vosk}), patch('sys.argv', ['spike', '--model', model, '--channel', 'source', '--no-speech']), patch('spike_assistente.time.monotonic', return_value=100), patch('spike_assistente.queue.Queue', return_value=chunks), patch('builtins.print') as output:
            with self.assertRaises(KeyboardInterrupt):
                main()
        lines = [call.args[0] for call in output.call_args_list]
        self.assertEqual(lines.count(GREETING), 1)
        self.assertEqual(lines.count('Não entendi. Repita o comando, tibiano.'), 1)
        self.assertEqual(lines.count('Timer de 30 segundos iniciado, tibiano.'), 1)
        self.assertNotIn('Ouvi: conversa ambiente', lines)
        self.assertIn('Ouvi: cria um alarme pra trinta segundos', lines)
        self.assertIn(GREETING, lines)

    def test_split_timer_prefix_and_strict_duration(self):
        for prefix in ('ligar alarme', 'ligar cronômetro de', 'um alarme', 'coloca um temporizador pra'):
            self.assertTrue(timer_prefix(prefix), prefix)
            timers = []
            dispatch(prefix + ' trinta segundos', '.', timers, 100)
            self.assertEqual(timers, [(130, '30 segundos')])
        for text in ('ligar', 'alarme [unk]', 'ligar alarme de trinta'):
            self.assertFalse(timer_prefix(text), text)
        timers = []
        dispatch('dois minutos', '.', timers, 100)
        self.assertEqual(timers, [(220, '2 minutos')])

    def test_split_voice_commands_keep_microphone_listening(self):
        phrases = iter(('ei tíbia tudo', 'ligar alarme', 'trinta segundos',
                        'ei tíbia tudo ligar cronômetro de', 'vinte e nove minutos',
                        'ei tíbia tudo', 'dois minutos'))
        recognizer = Mock()
        recognizer.AcceptWaveform.return_value = True
        def result():
            try:
                return json.dumps({'text': next(phrases)})
            except StopIteration:
                raise KeyboardInterrupt
        recognizer.Result.side_effect = result
        chunks = Mock()
        chunks.get.return_value = b'audio'
        chunks.get_nowait.side_effect = queue.Empty
        sd = SimpleNamespace(query_devices=lambda **kwargs: {'default_samplerate': 16000}, RawInputStream=Mock(return_value=Mock(__enter__=Mock(), __exit__=Mock(return_value=False))))
        vosk = SimpleNamespace(SetLogLevel=Mock(), Model=Mock(), KaldiRecognizer=Mock(return_value=recognizer))
        with tempfile.TemporaryDirectory() as model, patch.dict('sys.modules', {'sounddevice': sd, 'vosk': vosk}), patch('sys.argv', ['spike', '--model', model, '--channel', 'source']), patch('spike_assistente.prepare_speech') as prepare, patch('spike_assistente.time.monotonic', return_value=100), patch('spike_assistente.time.sleep'), patch('spike_assistente.queue.Queue', return_value=chunks), patch('builtins.print') as output:
            with self.assertRaises(KeyboardInterrupt):
                main()
        lines = [call.args[0] for call in output.call_args_list]
        self.assertEqual(lines.count('Aguardando duração (8 segundos).'), 2)
        self.assertEqual(prepare.return_value.call_count, 5)
        self.assertEqual([call.args[0] for call in prepare.return_value.call_args_list], [GREETING, 'Timer de 30 segundos iniciado, tibiano.', 'Timer de 29 minutos iniciado, tibiano.', GREETING, 'Timer de 2 minutos iniciado, tibiano.'])
        self.assertEqual(recognizer.Reset.call_count, 5)

    def test_real_schema_selected_and_reloaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'meus_personagens.json'
            data = {'lista': [{'nome': 'A', 'level': 99}, {'nome': 'B', 'level': 101}], 'atual': 'B'}
            path.write_text(json.dumps(data), encoding='utf-8')
            original = path.read_bytes()
            self.assertIn('68 até 151', shared_reply(tmp))
            self.assertIn('68 até 151', dispatch('qual e meu nivel compartilhado', tmp, [], 0))
            self.assertEqual(original, path.read_bytes())
            data['lista'][1]['level'] = 300
            path.write_text(json.dumps(data), encoding='utf-8')
            self.assertIn('200 até 450', shared_reply(tmp))

    def test_grammar_covers_commands_and_rejects_unknown(self):
        grammar = recognition_grammar()
        self.assertIn('[unk]', grammar)
        self.assertIn('ei tíbia tudo', grammar)
        self.assertIn('ligar um temporizador de', grammar)
        self.assertIn('colocar um cronômetro de', grammar)
        for verb in TIMER_VERBS:
            self.assertIn(f'{verb} um alarme de', grammar)
        for link in TIMER_LINKS:
            self.assertIn(link, grammar)
        self.assertIn('por favor', grammar)
        self.assertIn('daqui a', grammar)
        self.assertIn('alarme', grammar)
        self.assertIn('um minuto', grammar)
        self.assertIn('noventa e nove minutos', grammar)
        self.assertIn('cento e oitenta segundos', grammar)
        self.assertIn('qual é meu nível compartilhado', grammar)
        self.assertFalse(any(word in phrase.split() for phrase in grammar for word in ('hey', 'timer', 'shared', 'level')))
        for phrase in grammar:
            if phrase.endswith((' minuto', ' minutos', ' segundo', ' segundos')):
                timers = []
                dispatch('ligar um temporizador de ' + phrase, '.', timers, 0)
                self.assertEqual(len(timers), 1, phrase)

    def test_speech_failure_does_not_abort_session(self):
        for error in (OSError('missing'), subprocess.TimeoutExpired('powershell', 30)):
            with patch('spike_assistente.subprocess.run', side_effect=error), patch('builtins.print'):
                speak('Resposta de teste')

    def test_piper_load_once_warmup_and_bounded_cache(self):
        def synthesize(text, wav):
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(22050)
            wav.writeframes(b'\x00\x00' * 20)

        voice = Mock()
        voice.synthesize_wav.side_effect = synthesize
        loader = Mock(return_value=voice)
        playback = Mock()
        with patch.dict('sys.modules', {'piper': SimpleNamespace(PiperVoice=SimpleNamespace(load=loader)),
                                       'winsound': SimpleNamespace(PlaySound=playback, SND_MEMORY=4)}), patch('builtins.print'):
            speech = PiperSpeech(Path('model.onnx'))
            speech.warmup()
            speech(GREETING)
            speech(GREETING)
            loader.assert_called_once_with('model.onnx', use_cuda=False)
            self.assertEqual(voice.synthesize_wav.call_count, 1)
            self.assertEqual(playback.call_count, 2)
            self.assertTrue(playback.call_args.args[0].startswith(b'RIFF'))
            for index in range(33):
                speech.audio(f'Frase {index}')
            self.assertEqual(len(speech.cache), 32)
            self.assertNotIn(GREETING, speech.cache)

    def test_piper_failure_falls_back_to_windows(self):
        with patch.dict('sys.modules', {'piper': SimpleNamespace(PiperVoice=SimpleNamespace(load=Mock(side_effect=OSError())))}), patch('spike_assistente.speak') as fallback, patch('builtins.print'):
            speech = PiperSpeech(Path('missing.onnx'))
            speech('Resposta')
            fallback.assert_called_once_with('Resposta')
        speech.voice = Mock()
        with patch.object(speech, 'audio', side_effect=RuntimeError()), patch.dict('sys.modules', {'winsound': SimpleNamespace(PlaySound=Mock(), SND_MEMORY=4)}), patch('spike_assistente.speak') as fallback, patch('builtins.print'):
            speech('Resposta')
            fallback.assert_called_once_with('Resposta')
            self.assertIsNone(speech.voice)

    def test_no_speech_text_does_not_load_piper(self):
        with patch('sys.argv', ['spike', '--channel', 'source', '--text', 'Ei Tíbia Tudo ligar um timer de 30 minutos', '--no-speech']), patch('spike_assistente.PiperSpeech') as piper, patch('spike_assistente.speak') as windows, patch('builtins.print') as output:
            main()
            piper.assert_not_called()
            windows.assert_not_called()
            self.assertIn('30 minutos iniciado', output.call_args.args[0])

    def test_missing_invalid_and_fallback_character(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn('Não consegui ler', shared_reply(tmp))
            path = Path(tmp) / 'meus_personagens.json'
            for invalid in ['[]', '{', '{"lista": null}', '{"lista": [{"nome":"A", "level": true}]}']:
                path.write_text(invalid, encoding='utf-8')
                self.assertNotIn('Seu shared', shared_reply(tmp))
            path.write_text('{"lista": [{"nome":"A", "level": 100}], "atual":"ausente"}', encoding='utf-8')
            self.assertIn('67 até 150', shared_reply(tmp))


if __name__ == '__main__':
    unittest.main()
