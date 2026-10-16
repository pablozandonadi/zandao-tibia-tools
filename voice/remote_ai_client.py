"""Gateway fixo de voz; nenhum segredo OpenAI ou áudio em disco."""
from array import array
import io
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import uuid
import wave

import voz_credenciais

ENDPOINT = 'https://tibia-tudo-voz.pablo-0af.workers.dev'
TOKEN = re.compile(r'[A-Za-z0-9_-]{43}')

class RemoteAIError(Exception):
    pass

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_intent(value):
    if not isinstance(value, dict) or set(value) != {'action','parameters','needs_clarification','clarification'}:
        return False
    action, parameters = value['action'], value['parameters']
    fields = {'create_timer': {'seconds'}, 'cancel_last_timer': set(), 'cancel_timer': {'timer_id'}, 'query_timer': {'timer_id'}, 'shared': {'level'}, 'unknown': set()}
    if not isinstance(action,str) or action not in fields or not isinstance(parameters,dict) or set(parameters) != fields[action]:
        return False
    clarification=value['clarification']
    if type(value['needs_clarification']) is not bool or value['needs_clarification'] != (clarification is not None):
        return False
    if clarification is not None and (not isinstance(clarification,str) or not clarification.strip() or len(clarification)>300):
        return False
    if action=='create_timer':
        return type(parameters['seconds']) is int and 1<=parameters['seconds']<=10800
    if action=='shared':
        return parameters['level'] is None or type(parameters['level']) is int and 1<=parameters['level']<=100000
    if action in ('cancel_timer','query_timer'):
        return isinstance(parameters['timer_id'],str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',parameters['timer_id']) is not None
    return True


def load_settings(folder):
    path=Path(folder)
    try:
        settings=json.loads((path/'voice-online.json').read_text(encoding='utf-8'))
        encrypted=(path/'voice-online.dpapi').read_bytes()
        if not 1<=len(encrypted)<=16384:
            return False,None
        token=voz_credenciais._desproteger(encrypted)
        if not TOKEN.fullmatch(token):
            return False,None
        return settings.get('enabled') is True,token
    except (OSError, ValueError, AttributeError, TypeError, UnicodeError):
        return False,None


def save_settings(folder, token, enabled):
    if type(enabled) is not bool or not isinstance(token,str):
        raise ValueError('Configuração online inválida.')
    path=Path(folder)
    if not token:
        _,token=load_settings(path)
    if not token and not enabled:
        path.mkdir(parents=True,exist_ok=True)
        (path/'voice-online.json').write_text(json.dumps({'enabled':False}),encoding='utf-8')
        return False,None
    if not token or not TOKEN.fullmatch(token):
        raise ValueError('Informe o código de acesso individual válido.')
    encrypted=voz_credenciais._proteger(token)
    path.mkdir(parents=True,exist_ok=True)
    secret=path/'voice-online.dpapi'
    temporary=secret.with_suffix('.tmp')
    try:
        temporary.write_bytes(encrypted)
        temporary.replace(secret)
        settings=path/'voice-online.json'
        temporary=settings.with_suffix('.tmp')
        temporary.write_text(json.dumps({'enabled':enabled}),encoding='utf-8')
        temporary.replace(settings)
    finally:
        temporary.unlink(missing_ok=True)
    return enabled,token


def pcm_wav(pcm, samplerate):
    if type(samplerate) is not int or not 1000<=samplerate<=192000 or not pcm or len(pcm)%2 or len(pcm)>samplerate*2*15:
        raise ValueError('Áudio de comando inválido.')
    samples=array('h');samples.frombytes(pcm)
    if sys.byteorder!='little': samples.byteswap()
    if not any(samples): raise ValueError('Áudio de comando vazio.')
    if samplerate!=16000:
        count=len(samples)*16000//samplerate
        output=array('h')
        for index in range(count):
            position=index*samplerate/16000
            low=int(position);high=min(low+1,len(samples)-1)
            output.append(round(samples[low]+(samples[high]-samples[low])*(position-low)))
        samples=output
    if sys.byteorder!='little': samples.byteswap()
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as output:
        output.setnchannels(1);output.setsampwidth(2);output.setframerate(16000);output.writeframes(samples.tobytes())
    return buffer.getvalue()


class RemoteAIClient:
    def __init__(self, token):
        if not isinstance(token,str) or not TOKEN.fullmatch(token): raise ValueError('Código de acesso inválido.')
        self._token=token
        self._opener=urllib.request.build_opener(NoRedirect())

    def _post(self, route, body, request_id, content_type):
        try:
            if str(uuid.UUID(request_id,version=4))!=request_id.lower(): raise ValueError()
            request=urllib.request.Request(ENDPOINT+route,data=body,method='POST',headers={'User-Agent':'TibiaTudo/1.0','Authorization':'Bearer '+self._token,'X-Request-ID':request_id,'Content-Type':content_type})
            with self._opener.open(request,timeout=15) as response:
                if response.status!=200: raise ValueError()
                raw=response.read(8193)
                if len(raw)>8192: raise ValueError()
                value=json.loads(raw.decode('utf-8'))
            if not isinstance(value,dict) or value.get('request_id')!=request_id: raise ValueError()
            return value
        except (OSError, ValueError, TypeError, AttributeError, urllib.error.URLError):
            raise RemoteAIError('Reconhecimento online indisponível. Use o comando local ou tente novamente com nova ativação.') from None

    def transcribe(self, wav, request_id):
        result=self._post('/transcribe',wav,request_id,'audio/wav')
        if set(result)!={'request_id','text'} or not isinstance(result['text'],str) or not result['text'].strip() or len(result['text'])>500:
            raise RemoteAIError('Resposta online inválida.')
        return result['text']

    def interpret(self, text, request_id):
        if not isinstance(text,str) or not text.strip() or len(text)>500: raise RemoteAIError('Texto de comando inválido.')
        result=self._post('/interpret',json.dumps({'request_id':request_id,'text':text},ensure_ascii=False).encode('utf-8'),request_id,'application/json')
        if set(result)!={'request_id','intent'} or not valid_intent(result['intent']): raise RemoteAIError('Resposta online inválida.')
        return result['intent']
