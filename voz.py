"""Assistente local: timers compartilhados entre voz e interface, sem bloquear a janela."""
import hashlib
import json
from pathlib import Path
import queue
import threading
import time
import urllib.request
import uuid
import zipfile

from app_paths import data_dir
from voice.spike_assistente import (GREETING, UNKNOWN_REPLY, PiperSpeech, command_after_wake,
                                    dispatch, duration_from, duration_seconds, normalize,
                                    recognition_grammar, speak, tibiano, timer_prefix)


class Servico:
    def __init__(self, pasta=None):
        self.pasta = Path(pasta or data_dir())
        self._lock = threading.RLock()
        self._timers = []
        self._ids = {}
        self._estado = 'preparando'
        self._detalhe = 'Preparando o assistente local…'
        self._ouvi = ''
        self._resposta = ''
        self._stop = threading.Event()
        self._mic_stop = threading.Event()
        self._speaking = threading.Event()
        self._falas = queue.Queue()
        self._speech = speak
        self._mic = None
        self._watcher = threading.Thread(target=self._watch, daemon=True, name='voz-timers')
        self._speaker = threading.Thread(target=self._say_loop, daemon=True, name='voz-falas')
        self._watcher.start()
        self._speaker.start()

    def _status(self, estado, detalhe):
        with self._lock:
            if self._stop.is_set() or (self._mic_stop.is_set() and estado != 'pausado'):
                return
            self._estado, self._detalhe = estado, detalhe

    def _sync_ids(self):
        self._ids = {id(timer): self._ids.get(id(timer), uuid.uuid4().hex) for timer in self._timers}

    def estado(self):
        with self._lock:
            self._sync_ids()
            now = time.monotonic()
            timers = [{'id': self._ids[id(timer)], 'label': timer[1],
                       'duracao': duration_seconds(duration_from(timer[1])),
                       'restante': max(0, timer[0] - now)} for timer in self._timers if timer[0] > now]
            return {'estado': self._estado, 'detalhe': self._detalhe,
                    'ouvi': self._ouvi, 'resposta': self._resposta, 'timers': timers,
                    'microfone': bool(self._mic and self._mic.is_alive() and not self._mic_stop.is_set())}

    def _reply(self, text, wait=False):
        text = tibiano(text)
        with self._lock:
            self._resposta = text
        done = threading.Event()
        self._falas.put((text, done))
        if wait:
            while not done.wait(.1):
                if self._stop.is_set() or self._mic_stop.is_set():
                    break

    def _say_loop(self):
        while not self._stop.is_set():
            try:
                text, done = self._falas.get(timeout=.2)
            except queue.Empty:
                continue
            self._speaking.set()
            try:
                self._speech(text)
                self._stop.wait(.3)
            except Exception:
                with self._lock:
                    self._detalhe = 'A saída de voz falhou; acompanhe as respostas na tela.'
            finally:
                self._speaking.clear()
                done.set()

    def _watch(self):
        while not self._stop.wait(.1):
            with self._lock:
                now = time.monotonic()
                expired = [timer for timer in self._timers if timer[0] <= now]
                for timer in expired:
                    self._timers.remove(timer)
                self._sync_ids()
            for _, label in expired:
                self._reply(f'Timer de {label} terminou.')

    def comando(self, text, state=None):
        with self._lock:
            reply = dispatch(text, self.pasta, self._timers, time.monotonic(), state)
            self._sync_ids()
        return reply

    def criar(self, valor, unidade):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 1 <= valor <= 180 or int(valor) != valor:
            return {'erro': 'Informe um número inteiro de 1 a 180.'}
        if unidade not in ('segundo', 'minuto'):
            return {'erro': 'Escolha segundos ou minutos.'}
        reply = self.comando(f'timer de {int(valor)} {unidade}')
        self._reply(reply)
        return self.estado()

    def cancelar(self, timer_id):
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
            chunks = queue.Queue(maxsize=12)

            def callback(data, frames, timing, status):
                if not self._speaking.is_set() and not self._mic_stop.is_set():
                    try:
                        chunks.put_nowait(bytes(data))
                    except queue.Full:
                        pass

            def answer(text):
                self._reply(text, wait=True)
                while True:
                    try:
                        chunks.get_nowait()
                    except queue.Empty:
                        break
                recognizer.Reset()

            state, pending_prefix, armed_until = {}, '', 0
            self._cancelled()
            with sd.RawInputStream(samplerate=samplerate, blocksize=4000, dtype='int16', channels=1, callback=callback):
                self._cancelled()
                self._status('ouvindo', 'Diga “Hey Tibia Tudo”. Estou ouvindo, tibiano.')
                while not self._stop.is_set() and not self._mic_stop.is_set():
                    try:
                        audio = chunks.get(timeout=.2)
                    except queue.Empty:
                        continue
                    if self._speaking.is_set():
                        recognizer.Reset()
                        continue
                    if not recognizer.AcceptWaveform(audio):
                        continue
                    text = json.loads(recognizer.Result()).get('text', '')
                    if time.monotonic() > armed_until:
                        state.clear()
                        pending_prefix = ''
                    command = command_after_wake(text)
                    if command is None:
                        if time.monotonic() > armed_until or not text:
                            continue
                        command = text
                    else:
                        pending_prefix = ''
                        state.clear()
                    with self._lock:
                        self._ouvi = text
                    if not command:
                        answer(GREETING)
                        armed_until = time.monotonic() + 8
                    elif all(word == 'unk' for word in normalize(command).split()):
                        continue
                    elif timer_prefix(command):
                        pending_prefix = command
                        armed_until = time.monotonic() + 8
                    else:
                        if pending_prefix and duration_from(normalize(command)) is not None:
                            command = f'{pending_prefix} {command}'
                        pending_prefix = ''
                        reply = self.comando(command, state)
                        answer(reply)
                        armed_until = time.monotonic() + 8 if reply == UNKNOWN_REPLY or state.get('cancel') else 0
        except InterruptedError:
            pass
        except Exception as exc:
            if not self._stop.is_set() and not self._mic_stop.is_set():
                self._status('erro', f'Não consegui iniciar a voz ({type(exc).__name__}). Confira internet, microfone e permissão do Windows; use Tentar novamente. Timers manuais continuam disponíveis.')
