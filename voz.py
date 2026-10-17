"""Assistente local: timers compartilhados entre voz e interface, sem bloquear a janela."""
import assistente_tibiano as assistente
import chat
import hashlib
import json
import math
from pathlib import Path
import queue
import threading
import time
import urllib.request
import uuid
import zipfile

from app_paths import data_dir
from voice.audio_capture import Capture, has_voice
from voice import vocabulario
from voice.remote_ai_client import RemoteAIClient, RemoteAIError, load_settings, pcm_wav, save_settings, valid_intent
from voice.spike_assistente import (GREETING, UNKNOWN_REPLY, PiperSpeech, command_after_wake, play_wake_sound,
                                    cancel_selection, dispatch, duration_from, duration_seconds, negated, normalize,
                                    recognition_grammar, shared_reply, speak, tibiano, timer_prefix)


class Servico:
    def __init__(self, pasta=None, store=None, silencioso=False):
        self.pasta = Path(pasta or data_dir())
        self._lock = threading.RLock()
        self.store = store
        self._silencioso = silencioso
        self._avisos = []
        self._command_context = None
        self._domain_request_id = None
        self._timers = []
        self._ids = {}
        self._estado = 'texto' if silencioso else 'preparando'
        self._detalhe = 'Assistente de texto pronto.' if silencioso else 'Preparando o assistente local…'
        self._ouvi = ''
        self._resposta = ''
        self._entendi = ''
        self._recentes = {}
        self._recentes_context = None
        self._stop = threading.Event()
        self._mic_stop = threading.Event()
        self._speaking = threading.Event()
        self._ready = threading.Event()
        self._audio_reset = threading.Event()
        self._falas = queue.Queue()
        self._speech = speak
        self._mic = None
        self._armed_until = 0
        self._direct_mode = False
        self._pending_prefix = ''
        self._command_state = {}
        self._clarification_done = None
        self._generation = 0
        self._remote_busy = False
        self._online_enabled, token = load_settings(self.pasta)
        self._online_client = RemoteAIClient(token) if token else None
        self._watcher = threading.Thread(target=self._watch, daemon=True, name='voz-timers')
        self._speaker = None if silencioso else threading.Thread(target=self._say_loop, daemon=True, name='voz-falas')
        self._watcher.start()
        if self._speaker:
            self._speaker.start()

    def _status(self, estado, detalhe):
        with self._lock:
            if self._stop.is_set() or (self._mic_stop.is_set() and estado != 'pausado'):
                return
            self._estado, self._detalhe = estado, detalhe

    def _wait_status(self):
        self._status('espera', 'Aguardando comando, sem ativação.' if self._direct_mode else 'Aguardando comando: Hey Tibia')

    def _sync_ids(self):
        self._ids = {id(timer): self._ids.get(id(timer), uuid.uuid4().hex) for timer in self._timers}

    def estado(self):
        with self._lock:
            self._sync_ids()
            now = time.monotonic()
            timers = [{'id': self._ids[id(timer)], 'label': timer[1],
                       'duracao': duration_seconds(duration_from(timer[1])),
                       'restante': max(0, timer[0] - now)} for timer in self._timers if timer[0] > now]
            if self.store:
                context = self.store.context()
                timers = [{'id': t['id'], 'label': t['label'], 'duracao': t['duration_seconds'], 'restante': t['remaining_seconds']} for t in self.store.execute('timer.list', {}, context)['timers'] if t['status']=='active' and t['remaining_seconds']>0]
            return {'estado': 'falando' if self._speaking.is_set() and self._estado != 'pausado' else self._estado, 'detalhe': self._detalhe,
                    'avisos': list(self._avisos),
                    'ouvi': self._ouvi, 'entendi': self._entendi, 'resposta': self._resposta, 'timers': timers,
                    'direto': self._direct_mode,
                    'microfone': bool(self._mic and self._mic.is_alive() and not self._mic_stop.is_set()),
                    'online_enabled': self._online_enabled, 'online_configured': self._online_client is not None}

    def _reply(self, text, wait=False):
        text = tibiano(text)
        with self._lock:
            self._resposta = text
        done = threading.Event()
        if self._silencioso:
            with self._lock:
                self._avisos = [*self._avisos, {'id':uuid.uuid4().hex, 'texto':text}][-20:]
            done.set()
            return done
        self._falas.put((text, done))
        if wait:
            while not done.wait(.1):
                if self._stop.is_set() or self._mic_stop.is_set():
                    break
        return done

    def _say_loop(self):
        while not self._stop.is_set():
            try:
                text, done = self._falas.get(timeout=.2)
            except queue.Empty:
                continue
            self._audio_reset.set()
            self._speaking.set()
            try:
                self._speech(text)
                self._stop.wait(.3)
            except Exception:
                with self._lock:
                    self._detalhe = 'A saída de voz falhou; acompanhe as respostas na tela.'
            finally:
                self._audio_reset.set()
                self._speaking.clear()
                with self._lock:
                    if self._clarification_done is done:
                        if not self._stop.is_set() and not self._mic_stop.is_set() and self._command_state.get('cancel'):
                            self._armed_until = time.monotonic() + 8
                        self._clarification_done = None
                done.set()

    def _watch(self):
        while not self._stop.wait(.1):
            if self.store:
                try:
                    for alert in self.store.poll(): self._reply(alert['message'])
                except (ValueError, OSError):
                    self._status('erro', 'Não consegui salvar os alertas. Dados preservados; tente novamente.')
                self._stop.wait(.9)
                continue
            with self._lock:
                now = time.monotonic()
                expired = [timer for timer in self._timers if timer[0] <= now]
                for timer in expired:
                    self._timers.remove(timer)
                self._sync_ids()
            for _, label in expired:
                self._reply(f'Timer de {label} terminou.')

    def _recentes_do_contexto(self, context):
        profile = (context.get('character_id'), context.get('world_id'))
        if profile != self._recentes_context:
            self._recentes.clear()
            self._recentes_context = profile
        now = time.monotonic()
        self._recentes = {name: at for name, at in self._recentes.items() if now - at < 3600}
        return sorted(self._recentes, key=self._recentes.get, reverse=True)

    def registrar_resultado(self, intent, args, result, context, mostrar_entendi=True):
        with self._lock:
            self._recentes_do_contexto(context)
            if (args or {}).get('boss_id') and result.get('boss'):
                self._recentes[result['boss']['name']] = time.monotonic()
            if mostrar_entendi:
                self._entendi = chat.entendi_de(intent, args, result)

    def _vocabulario(self, context):
        recentes = self._recentes_do_contexto(context)
        try:
            bosses = self.store.execute('boss.cooldown.list', {}, context)['bosses'] if self.store else []
            com_kills = [boss['name'] for boss in bosses if boss['progress'] > 0]
        except (ValueError, OSError):
            com_kills = []
        return vocabulario.montar(com_kills, recentes)

    def comando(self, text, state=None, source="voice"):
        with self._lock:
            self._entendi = ''
            if self.store:
                try:
                    command = assistente.parse(text, self.store.clock())
                    if command is None: return 'Não entendi. Tente: timer de dois minutos.' if self._direct_mode else UNKNOWN_REPLY
                    intent, arguments = command
                    context = self._command_context if self._command_context is not None else self.store.context()
                    result = self.store.execute(intent, arguments, context, self._domain_request_id, source=source)
                    self.registrar_resultado(intent, arguments, result, context)
                    return assistente.reply(result)
                except (ValueError, OSError) as error:
                    return str(error) if isinstance(error, ValueError) else 'Não consegui salvar. Nenhuma alteração foi confirmada.'
            reply = dispatch(text, self.pasta, self._timers, time.monotonic(), state)
            self._sync_ids()
            try:
                parsed = assistente.parse(text)
                if parsed and reply != UNKNOWN_REPLY:
                    self._entendi = assistente.describe(*parsed)
            except ValueError:
                pass
        return 'Não entendi. Tente: timer de dois minutos.' if self._direct_mode and reply == UNKNOWN_REPLY else reply

    def _wake_ding(self):
        if self._silencioso:return
        self._audio_reset.set()
        self._speaking.set()
        try:
            play_wake_sound()
            self._stop.wait(.15)
        except Exception:
            self._detalhe = 'O sinal de ativação falhou; acompanhe o estado na tela.'
        finally:
            self._audio_reset.set()
            self._speaking.clear()

    def receber_texto(self, text):
        with self._lock:
            if self._speaking.is_set() or self._mic_stop.is_set() or self._stop.is_set():
                return
            now = time.monotonic()
            if now > self._armed_until:
                self._command_state.clear()
                self._pending_prefix = ''
            command = command_after_wake(text)
            if self._command_state.get('cancel') and command is not None:
                return
            if command is None:
                if (not self._direct_mode and now > self._armed_until) or not text:
                    return
                if self._command_state.get('cancel') and normalize(text) not in ('ultimo', 'o ultimo') and duration_from(cancel_selection(text)) is None:
                    return
                if self._pending_prefix and duration_from(normalize(text)) is None:
                    return
                command = text
                if self._direct_mode and not self._command_state and not self._pending_prefix:
                    self._generation += 1
                    self._command_context = self.store.context() if self.store else None
                    self._domain_request_id = str(uuid.uuid4())
            else:
                self._wake_ding()
                if self._stop.is_set() or self._mic_stop.is_set():
                    return
                now = time.monotonic()
                self._generation += 1
                self._command_context = self.store.context() if self.store else None
                self._domain_request_id = str(uuid.uuid4())
                self._pending_prefix = ''
                self._command_state.clear()
            self._ouvi = text
            if not command:
                self._armed_until = now + 8
                self._status('escutando', 'Pode falar o comando.')
                return
            if all(word == 'unk' for word in normalize(command).split()):
                return
            if timer_prefix(command):
                self._pending_prefix = command
                self._armed_until = now + 8
                self._status('escutando', 'Diga a duração do timer.')
                return
            if self._pending_prefix and duration_from(normalize(command)) is not None:
                command = f'{self._pending_prefix} {command}'
            self._pending_prefix = ''
            self._status('processando', 'Processando comando…')
            reply = self.comando(command, self._command_state)
            done = self._reply(reply)
            self._clarification_done = done if self._command_state.get('cancel') else None
            self._armed_until = now + 8 if self._command_state.get('cancel') else 0
            self._wait_status()

    def configurar_online(self, token, enabled):
        # Revoke in-flight authorization before slow DPAPI/disk I/O.
        with self._lock:
            self._generation += 1
            generation = self._generation
            self._armed_until = 0
            self._command_state.clear()
            self._pending_prefix = ''
            self._clarification_done = None
            self._online_enabled = False
            self._online_client = None
        try:
            enabled, stored = save_settings(self.pasta, token, enabled)
        except (OSError, ValueError, AttributeError, TypeError):
            return {'erro': 'Não consegui salvar o acesso protegido. Reconhecimento online desligado nesta sessão.'}
        with self._lock:
            if generation != self._generation:
                return {'erro': 'Essa configuração foi substituída por outra interação. Tente salvar novamente.'}
            self._online_enabled = enabled
            self._online_client = RemoteAIClient(stored) if stored else None
        return self.estado()

    def _remote_current(self, generation):
        return generation == self._generation and not self._stop.is_set() and not self._mic_stop.is_set() and not self._speaking.is_set()

    def _intent_reply(self, intent):
        self._entendi = ''
        if not valid_intent(intent):
            raise RemoteAIError('Resposta online inválida.')
        if intent['needs_clarification']:
            return intent['clarification']
        action, parameters = intent['action'], intent['parameters']
        if self.store and action != 'unknown':
            context = self._command_context or self.store.context()
            return chat.executar_intencao(self.store, action, parameters, context, self._domain_request_id, source='voice',
                                          ao_executar=lambda i, a, r: self.registrar_resultado(i, a, r, context))[0]
        if action == 'create_timer':
            return self.comando(f"timer de {parameters['seconds']} segundos")
        if action == 'cancel_last_timer':
            return self.comando('cancelar ultimo timer')
        if action == 'shared':
            return shared_reply(self.pasta, parameters['level'])
        if action in ('cancel_timer', 'query_timer'):
            self._sync_ids()
            selected = next((timer for timer in self._timers if self._ids[id(timer)] == parameters['timer_id'] and timer[0] > time.monotonic()), None)
            if selected is None:
                return 'Esse timer já terminou ou não foi identificado. Consulte os timers na tela.'
            if action == 'query_timer':
                return f'Faltam {max(1, math.ceil(selected[0] - time.monotonic()))} segundos.'
            self._timers.remove(selected)
            self._sync_ids()
            return f'Um timer de {selected[1]} cancelado.'
        return UNKNOWN_REPLY

    def receber_audio(self, text, pcm, samplerate, words=None):
        with self._lock:
            if self._remote_busy or self._speaking.is_set() or self._mic_stop.is_set() or self._stop.is_set():
                return
            command = command_after_wake(text)
            now = time.monotonic()
            if not self._online_enabled or self._online_client is None or self._command_state.get('cancel') or self._pending_prefix or negated(text):
                self.receber_texto(text)
                return
            if command == '' or (command is None and not self._direct_mode and now > self._armed_until):
                self.receber_texto(text)
                return
            if command is not None:
                # Only aligned Vosk words authorize cutting a wake from the same segment.
                try:
                    wake_words = len(normalize(text).split()) - len(command.split())
                    if not isinstance(words, list) or len(words) <= wake_words or [normalize(w['word']) for w in words] != normalize(text).split():
                        raise ValueError()
                    previous = 0.0
                    for word in words:
                        start, end = word['start'], word['end']
                        if type(start) not in (int, float) or type(end) not in (int, float) or not math.isfinite(start) or not math.isfinite(end) or not previous <= start < end <= len(pcm) / (samplerate * 2):
                            raise ValueError()
                        previous = end
                    pcm = pcm[math.ceil(words[wake_words - 1]['end'] * samplerate) * 2:]
                except (KeyError, TypeError, ValueError, ZeroDivisionError):
                    self.receber_texto(text)
                    return
            try:
                wav = pcm_wav(pcm, samplerate)
                block = max(1, samplerate // 10) * 2
                if not any(has_voice(pcm[start:start + block]) for start in range(0, len(pcm), block)):
                    return
            except ValueError:
                self.receber_texto(text)
                return
            if command is not None:
                self._wake_ding()
                if self._stop.is_set() or self._mic_stop.is_set():
                    return
            self._generation += 1
            if command is not None or self._direct_mode or self._command_context is None:
                self._command_context = self.store.context() if self.store else None
            self._domain_request_id = str(uuid.uuid4())
            generation = self._generation
            client = self._online_client
            self._remote_busy = True
            self._armed_until = 0
            self._command_state.clear()
            terms = self._vocabulario(self._command_context or {})
            self._ouvi = text or 'Comando capturado; aguardando transcrição.'
            self._entendi = ''
            self._status('transcrevendo', 'Reconhecendo o comando online…')
        request_id = str(uuid.uuid4())
        transcript = None
        try:
            transcript = client.transcribe(wav, request_id, terms)
            with self._lock:
                if not self._remote_current(generation):
                    return
                self._ouvi = transcript
                reply = self.comando(transcript, self._command_state)
            if reply in (UNKNOWN_REPLY, 'Não entendi. Tente: timer de dois minutos.'):
                self._status('interpretando', 'Interpretando o comando…')
                intent = client.interpret(transcript, request_id)
                with self._lock:
                    if not self._remote_current(generation):
                        return
                    reply = self._intent_reply(intent)
            with self._lock:
                if not self._remote_current(generation):
                    return
                done = self._reply(reply)
                self._clarification_done = done if self._command_state.get('cancel') else None
                self._armed_until = time.monotonic() + 8 if self._command_state.get('cancel') else 0
                self._wait_status()
        except (RemoteAIError, OSError, ValueError, TypeError) as error:
            with self._lock:
                if self._remote_current(generation):
                    # Never retry a possibly billed request; retain deterministic local fallback.
                    local = transcript or (command if command is not None else text)
                    reply = self.comando(local, self._command_state) if local else UNKNOWN_REPLY
                    if reply in (UNKNOWN_REPLY, 'Não entendi. Tente: timer de dois minutos.'):
                        reply = str(error) if isinstance(error, RemoteAIError) else 'Reconhecimento online indisponível. Tente um comando local.'
                    self._reply(reply)
                    self._armed_until = 0
                    self._command_state.clear()
                    self._wait_status()
        finally:
            with self._lock:
                self._remote_busy = False
                self._audio_reset.set()

    def escutar(self):
        if self._silencioso:return {'erro':'A voz está pausada nesta versão. Use o chat.'}
        with self._lock:
            if not self._ready.is_set() or self._mic_stop.is_set():
                return {'erro': 'O microfone ainda está preparando. Aguarde e tente novamente.'}
            self._generation += 1
            self._direct_mode = not self._direct_mode
            self._armed_until = 0
            self._command_context = None
            self._domain_request_id = None
            self._command_state.clear()
            self._pending_prefix = ''
            self._clarification_done = None
            self._audio_reset.set()
            self._wait_status()
        return self.estado()

    def criar(self, valor, unidade):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 1 <= valor <= 180 or int(valor) != valor:
            return {'erro': 'Informe um número inteiro de 1 a 180.'}
        if unidade not in ('segundo', 'minuto'):
            return {'erro': 'Escolha segundos ou minutos.'}
        if self.store:
            self._command_context = self.store.context()
            self._domain_request_id = str(uuid.uuid4())
        reply = self.comando(f'timer de {int(valor)} {unidade}', source='manual')
        self._reply(reply)
        return self.estado()

    def cancelar(self, timer_id):
        if self.store:
            try:
                result=self.store.execute('timer.cancel', {'timer_id':timer_id}, self.store.context(), str(uuid.uuid4()))
                self._reply(assistente.reply(result))
                return self.estado()
            except (ValueError,OSError) as error: return {'erro':str(error)}
        with self._lock:
            self._sync_ids()
            selected = next((timer for timer in self._timers if self._ids[id(timer)] == timer_id and timer[0] > time.monotonic()), None)
            if selected is None:
                return {'erro': 'Esse timer já terminou ou foi cancelado.'}
            self._timers.remove(selected)
            self._sync_ids()
        self._reply(f'Um timer de {selected[1]} cancelado.')
        return self.estado()

    def iniciar(self):
        if self._silencioso:return {'erro':'A voz está pausada nesta versão. Use o chat.'}
        with self._lock:
            if self._stop.is_set() or (self._mic and self._mic.is_alive()):
                return self.estado()
            self._mic_stop.clear()
            self._status('preparando', 'Preparando o assistente local…')
            self._mic = threading.Thread(target=self._listen, daemon=True, name='voz-microfone')
            self._mic.start()
        return self.estado()

    def parar(self):
        self._mic_stop.set()
        self._ready.clear()
        with self._lock:
            self._generation += 1
            self._direct_mode = False
            self._armed_until = 0
            self._pending_prefix = ''
            self._command_state.clear()
            self._clarification_done = None
        self._status('pausado', 'Microfone pausado. Seus timers continuam contando.')
        return self.estado()

    def close(self):
        self._stop.set()
        self._mic_stop.set()
        for worker in (self._mic, self._watcher, self._speaker):
            if worker and worker is not threading.current_thread():
                worker.join(timeout=.5)

    def _cancelled(self):
        if self._stop.is_set() or self._mic_stop.is_set():
            raise InterruptedError()

    def _download(self, url, target, label, expected_size, expected_hash):
        if target.is_file():
            with target.open('rb') as existing:
                if target.stat().st_size == expected_size and hashlib.file_digest(existing, 'sha256').hexdigest() == expected_hash:
                    return
            target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + '.download')
        try:
            with urllib.request.urlopen(url, timeout=15) as response, part.open('wb') as output:
                size = int(response.headers.get('Content-Length') or 0)
                read = 0
                digest = hashlib.sha256()
                while True:
                    self._cancelled()
                    block = response.read(256 * 1024)
                    if not block:
                        break
                    output.write(block)
                    read += len(block)
                    if read > expected_size:
                        raise OSError('Modelo maior que o esperado')
                    digest.update(block)
                    progress = f'{round(read * 100 / size)}%' if size else f'{read // 1024 // 1024} MB'
                    self._status('preparando', f'Baixando {label}: {progress}. Só no primeiro uso.')
                if read != expected_size or digest.hexdigest() != expected_hash:
                    raise OSError('Integridade do modelo inválida')
            self._cancelled()
            part.replace(target)
        finally:
            part.unlink(missing_ok=True)

    def _models(self):
        root = self.pasta / 'voice_models'
        model = root / 'vosk-model-small-pt-0.3'
        if not (model / '.ready').is_file():
            archive = root / 'vosk.zip'
            self._download('https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip', archive, 'reconhecimento (31 MB)', 32453112, '6e1ce909032e1afa7a88e68a3d628ecafff302bdf195befab308826c395e93b7')
            with zipfile.ZipFile(archive) as zipped:
                for entry in zipped.infolist():
                    self._cancelled()
                    target = (root / entry.filename).resolve()
                    if not target.is_relative_to(root.resolve()) or Path(entry.filename).parts[0] != model.name:
                        raise ValueError('Caminho inválido no modelo de voz')
                    zipped.extract(entry, root)
            (model / '.ready').write_text('vosk-model-small-pt-0.3', encoding='ascii')
            archive.unlink()
        voice = root / 'pt_BR-faber-medium.onnx'
        base = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx'
        for suffix, size, digest in (('', 63201294, '858555e3a064209c57088fe6bd70c4c3dc54d03eaa00c45d5ecaf43a33f95aa7'),
                                     ('.json', 4855, '7e694de195ae3fc36dd732c445eb04fb49b649854893cb5506b978f0d50a1d6f')):
            self._download(base + suffix, Path(str(voice) + suffix), 'voz brasileira (63 MB)', size, digest)
        return model, voice

    def _listen(self):
        try:
            model_path, voice_path = self._models()
            self._cancelled()
            self._speech = PiperSpeech(voice_path)
            self._speech.warmup()
            self._cancelled()
            import sounddevice as sd
            import vosk
            vosk.SetLogLevel(-1)
            model = vosk.Model(str(model_path))
            samplerate = int(sd.query_devices(kind='input')['default_samplerate'])
            recognizer = vosk.KaldiRecognizer(model, samplerate, json.dumps(recognition_grammar(), ensure_ascii=False))
            recognizer.SetWords(True)
            chunks = queue.Queue(maxsize=32)
            overflow = threading.Event()
            capture = Capture(samplerate)

            def callback(data, frames, timing, status):
                if status:
                    overflow.set()
                if not self._speaking.is_set() and not self._remote_busy and not self._mic_stop.is_set():
                    try:
                        chunks.put_nowait(bytes(data))
                    except queue.Full:
                        overflow.set()

            self._cancelled()
            with sd.RawInputStream(samplerate=samplerate, blocksize=max(1, samplerate // 10), dtype='int16', channels=1, callback=callback):
                self._cancelled()
                self._ready.set()
                self._wait_status()
                while not self._stop.is_set() and not self._mic_stop.is_set():
                    if self._armed_until and time.monotonic() > self._armed_until and not self._speaking.is_set():
                        with self._lock:
                            self._armed_until = 0
                            self._pending_prefix = ''
                            self._command_state.clear()
                        self._wait_status()
                    try:
                        audio = chunks.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if self._speaking.is_set() or self._audio_reset.is_set() or overflow.is_set():
                        capture.reset()
                        self._audio_reset.clear()
                        recognizer.Reset()
                        while True:
                            try:
                                chunks.get_nowait()
                            except queue.Empty:
                                break
                        if overflow.is_set():
                            overflow.clear()
                            with self._lock:
                                self._armed_until = 0
                                self._command_state.clear()
                                self._pending_prefix = ''
                            self._status('espera', 'Áudio interrompido. Repita Hey Tibia e o comando.')
                        continue
                    segment = capture.feed(audio)
                    if capture.exceeded:
                        capture.exceeded = False
                        with self._lock:
                            self._armed_until = 0
                            self._pending_prefix = ''
                            self._command_state.clear()
                        self._status('espera', 'Comando muito longo. Repita Hey Tibia e um comando curto.')
                    if segment is None:
                        continue
                    self._status('processando', 'Reconhecendo comando local…')
                    recognizer.AcceptWaveform(segment)
                    result = json.loads(recognizer.FinalResult())
                    text = result.get('text', '')
                    recognizer.Reset()
                    self.receber_audio(text, segment, samplerate, result.get('result'))
                    if time.monotonic() > self._armed_until:
                        self._wait_status()
        except InterruptedError:
            pass
        except Exception as exc:
            if not self._stop.is_set() and not self._mic_stop.is_set():
                self._status('erro', f'Não consegui iniciar a voz ({type(exc).__name__}). Confira internet, microfone e permissão do Windows; use Tentar novamente. Timers manuais continuam disponíveis.')

        finally:
            self._ready.clear()
