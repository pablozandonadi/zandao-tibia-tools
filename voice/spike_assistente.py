"""Teste isolado: voz offline, timer de sessão e leitura do shared salvo no app."""
import argparse
import base64
from collections import OrderedDict
import io
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import time
import unicodedata
import wave


NUMBERS = {'um': 1, 'uma': 1, 'dois': 2, 'duas': 2, 'tres': 3, 'quatro': 4,
               'cinco': 5, 'seis': 6, 'sete': 7, 'oito': 8, 'nove': 9, 'dez': 10,
               'onze': 11, 'doze': 12, 'treze': 13, 'quatorze': 14, 'catorze': 14,
               'quinze': 15, 'dezesseis': 16, 'dezessete': 17, 'dezoito': 18,
               'dezenove': 19, 'vinte': 20, 'trinta': 30, 'quarenta': 40,
               'cinquenta': 50, 'sessenta': 60, 'setenta': 70, 'oitenta': 80, 'noventa': 90}

TIMER_VERBS = ('ligar', 'liga', 'ligue', 'gerar', 'gera', 'gere', 'colocar', 'coloca', 'coloque',
               'criar', 'cria', 'crie', 'iniciar', 'inicia', 'inicie', 'ativar', 'ativa', 'ative')
TIMER_NAMES = ('temporizador', 'cronômetro', 'alarme', 'time', 'timer')
TIMER_LINKS = ('de', 'por', 'pra', 'para')
CANCEL_VERBS = ('cancelar', 'cancela', 'cancele', 'excluir', 'exclui', 'exclua',
                'apagar', 'apaga', 'apague', 'remover', 'remove', 'remova')


def tibiano(text):
    return text


UNKNOWN_REPLY = 'Não entendi. Fale Hey Tibia Tudo e tente novamente.'
GREETING = 'Pode falar.'


def normalize(text):
    text = ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', text).split())


def command_after_wake(text):
    match = re.fullmatch(r'(?:hey|ei|hei)\s+tibia\s+tudo(?:\s+(.*))?', normalize(text))
    return None if match is None else (match.group(1) or '')


def duration_from(text):
    if text == 'meio minuto':
        return 30, 'segundo'
    if text == 'um minuto e meio':
        return 90, 'segundo'
    # Match the entire duration: never silently use the suffix of an unknown number.
    match = re.fullmatch(r'(.+?)\s+(minutos?|segundos?)', text)
    if not match:
        return None
    number, unit = match[1], match[2].rstrip('s')
    value = number_from(number)
    return None if value is None else (value, unit)


def number_from(number):
    if number.isdecimal():
        return int(number)
    numbers = NUMBERS
    if number in numbers:
        return numbers[number]
    if number == 'cem':
        return 100
    if number.startswith('cento e '):
        rest = number_from(number[len('cento e '):])
        return 100 + rest if rest is not None and 1 <= rest <= 99 else None
    parts = number.split(' e ')
    if len(parts) == 2 and parts[0] in numbers and parts[1] in numbers:
        tens, units = numbers[parts[0]], numbers[parts[1]]
        if tens >= 20 and tens % 10 == 0 and 1 <= units <= 9:
            return tens + units
    return None


def minutes_from(text):
    duration = duration_from(text)
    return duration[0] if duration and duration[1] == 'minuto' else None


def duration_seconds(duration):
    value, unit = duration
    return value * (60 if unit == 'minuto' else 1)


def recognition_grammar():
    wakes = ['ei tíbia tudo', 'hei tíbia tudo']
    durations = set(NUMBERS)
    for tens, value in NUMBERS.items():
        if value >= 20 and value % 10 == 0:
            for unit, digit in NUMBERS.items():
                if 1 <= digit <= 9:
                    durations.add(f'{tens} e {unit}')
    durations.update(['cem'] + [f'cento e {number}' for number in list(durations) if number_from(number) <= 80])
    commands = ['qual é meu nível compartilhado', 'qual é o meu nível compartilhado',
                'qual meu compartilhado', 'qual é meu cher', 'qual é o meu cher',
                'até que nível divide experiência', 'até que nível compartilho experiência',
                'até que nível cher', 'novo', 'nova', 'último', 'o último', 'o', 'um']
    # Vosk concatenates these phrases; avoid a large Cartesian list of full commands.
    for verb in TIMER_VERBS:
        for noun in TIMER_NAMES:
            if noun == 'timer':
                continue  # The Portuguese Vosk model has no exact token for timer.
            commands.extend((f'{verb} um {noun} de', f'{verb} {noun} de'))
    commands.extend(['por favor', 'daqui a', 'me avisa daqui a', 'um minuto e meio', 'meio minuto', 'quanto falta naquele timer', 'não', 'não crie', 'não cancela', *TIMER_LINKS])
    commands.extend(noun for noun in TIMER_NAMES if noun != 'timer')
    for verb in CANCEL_VERBS:
        commands.append(verb)
        for noun in TIMER_NAMES:
            if noun != 'timer':
                commands.extend((f'{verb} {noun}', f'{verb} o {noun}',
                                 f'{verb} último {noun}', f'{verb} o último {noun}'))
    for duration in sorted(durations):
        spoken = duration.replace('tres', 'três')
        for unit in ('minuto', 'segundo'):
            suffix = unit if number_from(duration) == 1 else unit + 's'
            commands.append(f'{spoken} {suffix}')
    return wakes + commands + ['[unk]']


def shared_reply(data_dir, level=None):
    try:
        data = {} if level is not None else json.loads((Path(data_dir) / 'meus_personagens.json').read_text(encoding='utf-8-sig'))
        chars = [p for p in data.get('lista', []) if isinstance(p, dict) and p.get('nome')]
        current = next((p for p in chars if p['nome'] == data.get('atual')), chars[0] if chars else None)
        level = level if level is not None else (current.get('level') if current else None)
        if isinstance(level, bool) or not isinstance(level, int) or level < 1:
            return tibiano('Selecione um personagem com level válido no Tibia Tudo.')
        from tibia_info import faixa_shared
        minimum, maximum = faixa_shared(level)
        return f'Seu shared vai do level {minimum} até {maximum}.'
    except (OSError, ValueError, AttributeError, TypeError):
        return tibiano('Não consegui ler os personagens. Confira a pasta de dados escolhida.')


def timer_prefix(text):
    text = re.sub(r'^(?:por favor\s+)|(?:\s+por favor)$', '', normalize(text))
    verbs = '|'.join(TIMER_VERBS)
    names = '|'.join(normalize(noun) for noun in TIMER_NAMES)
    links = '|'.join(TIMER_LINKS)
    return re.fullmatch(rf'(?:(?:{verbs})\s+)?(?:(?:um|novo|nova)\s+)?(?:{names})(?:\s+(?:{links}))?', text) is not None


def cancel_selection(text):
    return re.sub(r'^(?:o\s+(?:timer\s+)?de\s+|de\s+)', '', normalize(text))


def negated(text):
    return re.search(r'\b(?:nao|nunca|nem|jamais|sem|evite|evita|evitar)\b|\b(?:deixe|deixa) de\b', normalize(text)) is not None


def dispatch(text, data_dir, timers, now, state=None):
    text = normalize(text)
    if negated(text):
        return 'Tudo bem. Nenhuma ação executada.'
    if 'unk' in text.split():
        return UNKNOWN_REPLY
    text = re.sub(r'^(?:por favor\s+)|(?:\s+por favor)$', '', text)
    verbs = '|'.join(TIMER_VERBS)
    names = '|'.join(normalize(noun) for noun in TIMER_NAMES)
    links = '|'.join(TIMER_LINKS)
    cancel_verbs = '|'.join(CANCEL_VERBS)
    text = re.sub(rf'^({cancel_verbs}) o de ', r'\1 timer de ', text)
    cancel = re.fullmatch(rf'(?:{cancel_verbs})\s+(?:o\s+|um\s+)?(?:(ultimo)\s+)?(?:{names})(?:\s+(?:de\s+)?(.+))?', text)
    selection = cancel_selection(text)
    pending = state is not None and state.get('cancel', False)
    last = text in ('ultimo', 'o ultimo')
    if cancel or (pending and (duration_from(selection) is not None or last)):
        target = cancel[2] if cancel else (None if last else selection)
        duration = duration_from(target) if target else None
        if target and (duration is None or not 1 <= duration_seconds(duration) <= 10800):
            return UNKNOWN_REPLY
        active = [index for index, timer in enumerate(timers) if timer[0] > now]
        if state is not None:
            state['cancel'] = False
        if not active:
            return tibiano('Nenhum timer ativo.')
        if duration:
            seconds = duration_seconds(duration)
            active = [index for index in active if duration_seconds(duration_from(timers[index][1])) == seconds]
            if not active:
                return tibiano('Não existe timer ativo com essa duração.')
        if len(active) > 1 and not (last or (cancel and cancel[1])):
            if state is not None:
                state['cancel'] = True
            labels = ', '.join(timers[index][1] for index in active)
            return tibiano(f'Você tem {len(active)} timers ativos: {labels}. Qual deseja cancelar?')
        _, label = timers.pop(active[-1])
        return tibiano(f'Um timer de {label} cancelado.')
    if state is not None:
        state['cancel'] = False
    if re.fullmatch(r'quanto (?:falta|tempo falta)(?: naquele| no| nesse)? timer', text):
        active = [timer for timer in timers if timer[0] > now]
        if not active:
            return 'Nenhum timer ativo.'
        if len(active) != 1:
            return 'Qual timer? Consulte os timers na tela.'
        return f'Faltam {max(1, math.ceil(active[0][0] - now))} segundos.'
    text = re.sub(r'^me avisa daqui a ', 'timer de ', text)
    timer = re.fullmatch(rf'(?:(?:{verbs})\s+)?(?:(?:um|novo|nova)\s+)?(?:{names})\s+(?:(?:{links})\s+(?:e\s+)?)?(?:daqui a\s+)?(.+)', text)
    duration = duration_from(timer[1] if timer else text)
    if timer or duration is not None:
        if duration is None or not 1 <= duration_seconds(duration) <= 10800:
            return tibiano('Diga uma duração de 1 segundo a 180 minutos.')
        value, unit = duration
        label = f'{value} {unit}{"s" if value != 1 else ""}'
        timers.append((now + value * (60 if unit == 'minuto' else 1), label))
        return tibiano(f'Timer de {label} iniciado.')
    if any(word in text.split() for word in ('shared', 'share', 'shareio', 'cher', 'xer', 'compartilhado', 'compartilhada')) or 'divide experiencia' in text or 'compartilho experiencia' in text:
        explicit = re.search(r'\blevel (\d+)\b', text)
        return shared_reply(data_dir, int(explicit[1]) if explicit else None)
    return UNKNOWN_REPLY


def speak(text):
    # EncodedCommand avoids interpreting recognized text as PowerShell source.
    literal = text.replace("'", "''")
    script = "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
    script += "try { $s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, [System.Speech.Synthesis.VoiceAge]::NotSet, 0, [System.Globalization.CultureInfo]::GetCultureInfo('pt-BR')) } catch {}; "
    script += f"$s.Speak('{literal}'); $s.Dispose()"
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand',
                                 base64.b64encode(script.encode('utf-16-le')).decode('ascii')],
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                                capture_output=True, timeout=30)
        if result.returncode:
            print('A resposta em voz falhou; use o texto exibido.')
    except (subprocess.TimeoutExpired, OSError):
        print('A resposta em voz falhou; use o texto exibido. O teste continua.')


class PiperSpeech:
    def __init__(self, model_path):
        self.voice = None
        self.cache = OrderedDict()
        started = time.perf_counter()
        try:
            from piper import PiperVoice
            self.voice = PiperVoice.load(str(model_path), use_cuda=False)
            print(f'Piper carregado na CPU em {time.perf_counter() - started:.2f} s.')
        except Exception as exc:
            print(f'Piper indisponível ({type(exc).__name__}); usando a voz do Windows.')

    def audio(self, text):
        started = time.perf_counter()
        cached = text in self.cache
        if cached:
            self.cache.move_to_end(text)
        else:
            if self.voice is None:
                raise RuntimeError('Piper indisponível')
            buffer = io.BytesIO()
            with wave.open(buffer, 'wb') as wav:
                self.voice.synthesize_wav(text, wav)
            self.cache[text] = buffer.getvalue()
            if len(self.cache) > 32:
                self.cache.popitem(last=False)
        audio = self.cache[text]
        elapsed = time.perf_counter() - started
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            duration = wav.getnframes() / wav.getframerate()
        print(f'Piper: {"cache" if cached else "geração"} {elapsed:.3f} s; áudio {duration:.2f} s (sem contar reprodução).')
        return audio

    def warmup(self):
        if self.voice is not None:
            try:
                self.audio(GREETING)
            except Exception as exc:
                self.voice = None
                print(f'Piper falhou ({type(exc).__name__}); usando a voz do Windows.')

    def __call__(self, text):
        if self.voice is not None:
            try:
                import winsound
                winsound.PlaySound(self.audio(text), winsound.SND_MEMORY)
                return
            except Exception as exc:
                self.voice = None
                print(f'Piper falhou ({type(exc).__name__}); usando a voz do Windows.')
        speak(text)


def prepare_speech(args):
    if args.no_speech:
        return None
    if args.tts == 'windows':
        return speak
    speech = PiperSpeech(args.piper_model)
    speech.warmup()
    return speech



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path)
    parser.add_argument('--channel', choices=['stable', 'beta', 'source'], default='stable')
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--text', help='Testa um comando com ativação, sem abrir o microfone.')
    parser.add_argument('--no-speech', action='store_true')
    parser.add_argument('--tts', choices=['piper', 'windows'], default='piper')
    parser.add_argument('--piper-model', type=Path, default=Path(os.environ.get('TEMP', '.')) / 'tibia-tudo-voice-spike' / 'piper' / 'pt_BR-faber-medium.onnx')
    parser.add_argument('--benchmark-tts', action='store_true', help='Mede Piper sem abrir microfone nem reproduzir áudio.')
    args = parser.parse_args()
    if args.benchmark_tts:
        if args.no_speech or args.tts != 'piper':
            parser.error('--benchmark-tts requer --tts piper e não aceita --no-speech.')
        speech = PiperSpeech(args.piper_model)
        if speech.voice is None:
            raise RuntimeError('Piper indisponível para medição')
        for text in ('Pode falar.', 'Timer de 30 minutos iniciado.', 'Seu shared vai do level 135 até 303. Pelo level salvo no aplicativo.', 'Pode falar.'):
            print(text)
            speech.audio(text)
        return
    if args.data_dir:
        data_dir = args.data_dir
    elif args.channel == 'source':
        data_dir = Path(__file__).resolve().parent.parent
    else:
        if not os.environ.get('LOCALAPPDATA'):
            parser.error('LOCALAPPDATA indisponível; informe --data-dir.')
        data_dir = Path(os.environ['LOCALAPPDATA']) / 'TibiaTudo' / args.channel
    timers = []
    if args.text is not None:
        command = command_after_wake(args.text)
        reply = tibiano('Inclua Ei Tíbia Tudo antes do comando.') if command is None else (GREETING if not command else dispatch(command, data_dir, timers, time.monotonic()))
        print(reply)
        if not args.no_speech:
            prepare_speech(args)(reply)
        return
    if args.model is None or not args.model.is_dir():
        parser.error('Modelo ausente. Execute iniciar_teste.ps1 para preparar o teste.')
    speech = prepare_speech(args)
    import sounddevice as sd
    import vosk
    vosk.SetLogLevel(-1)
    model = vosk.Model(str(args.model))
    samplerate = int(sd.query_devices(kind='input')['default_samplerate'])
    recognizer = vosk.KaldiRecognizer(model, samplerate, json.dumps(recognition_grammar(), ensure_ascii=False))
    chunks = queue.Queue(maxsize=12)
    listening = True

    def callback(data, frames, timing, status):
        if listening:
            try:
                chunks.put_nowait(bytes(data))
            except queue.Full:
                pass

    def answer(text):
        nonlocal listening
        text = tibiano(text)
        print(text)
        listening = False
        try:
            if not args.no_speech:
                speech(text)
                time.sleep(0.3)
        finally:
            while True:
                try:
                    chunks.get_nowait()
                except queue.Empty:
                    break
            recognizer.Reset()
            listening = True

    print('Teste de voz ativo. Diga Ei Tíbia Tudo. Ctrl+C encerra e apaga os timers.')
    print('O áudio é processado localmente; este teste não grava áudio nem altera o app.')
    armed_until = 0
    pending_prefix = ''
    state = {'cancel': False}
    with sd.RawInputStream(samplerate=samplerate, blocksize=4000, dtype='int16', channels=1, callback=callback):
        while True:
            now = time.monotonic()
            expired = [(deadline, label) for deadline, label in timers if deadline <= now]
            for timer in expired:
                timers.remove(timer)
                answer(f'Timer de {timer[1]} terminou.')
            try:
                data = chunks.get(timeout=0.2)
            except queue.Empty:
                continue
            if not recognizer.AcceptWaveform(data):
                continue
            text = json.loads(recognizer.Result()).get('text', '')
            if time.monotonic() > armed_until:
                state['cancel'] = False
                pending_prefix = ''
            command = command_after_wake(text)
            if command is None:
                if time.monotonic() > armed_until:
                    pending_prefix = ''
                    continue
                if not text:
                    continue
                command = text
            else:
                pending_prefix = ''
                state['cancel'] = False
            print(f'Ouvi: {text}')
            if not command:
                print(GREETING)
                armed_until = time.monotonic() + 8
            elif all(word == 'unk' for word in normalize(command).split()):
                print('Áudio não reconhecido; aguardando o comando.')
            elif timer_prefix(command):
                pending_prefix = command
                armed_until = time.monotonic() + 8
                print('Aguardando duração (8 segundos).')
            else:
                if pending_prefix and duration_from(normalize(command)) is not None:
                    command = f'{pending_prefix} {command}'
                pending_prefix = ''
                reply = dispatch(command, data_dir, timers, time.monotonic(), state)
                answer(reply)
                armed_until = time.monotonic() + 8 if state['cancel'] else 0


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nTeste encerrado. Timers de teste descartados.')
    except Exception as exc:
        print(f'Não foi possível continuar o teste ({type(exc).__name__}). Confira microfone, modelo e saída de áudio.')
        raise SystemExit(1)
