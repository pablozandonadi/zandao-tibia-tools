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
from voice.vocabulario import cabecalho

ENDPOINT = 'https://tibia-tudo-voz.pablo-0af.workers.dev'
DOMAIN_SCHEMAS = json.loads(Path(__file__).with_name('domain_actions.json').read_text(encoding='utf-8'))

def _schema_valid(value, schema):
    kinds=schema['type'] if isinstance(schema['type'],list) else [schema['type']]
    kind='null' if value is None else 'boolean' if type(value) is bool else 'integer' if type(value) is int else 'string' if isinstance(value,str) else 'array' if isinstance(value,list) else 'object' if isinstance(value,dict) else 'invalid'
    if kind not in kinds:return False
    if kind=='null':return True
    if 'enum' in schema and value not in schema['enum']:return False
    if kind=='object':return set(value)==set(schema['properties']) and all(_schema_valid(v,schema['properties'][k]) for k,v in value.items())
    if kind=='integer':return schema.get('minimum',value)<=value<=schema.get('maximum',value)
    if kind=='string':return schema.get('minLength',0)<=len(value)<=schema.get('maxLength',len(value)) and ('pattern' not in schema or re.fullmatch(schema['pattern'],value) is not None)
    if kind=='array':return schema.get('minItems',0)<=len(value)<=schema.get('maxItems',len(value)) and all(_schema_valid(v,schema['items']) for v in value)
    return True

TOKEN = re.compile(r'[A-Za-z0-9_-]{43}')

class RemoteAIError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status if type(status) is int and 400 <= status <= 599 else None

def http_error(status, details=None):
    code = details.get('error') if isinstance(details, dict) else None
    if status == 403 and code == 'device_limit':return RemoteAIError('Este código já está em uso em outros computadores. Peça um novo ao administrador.', status=status)
    if status == 403 and code == 'code_expired':return RemoteAIError('Este código expirou. Peça um novo ao administrador.', status=status)
    if status == 429 and code == 'quota_exhausted' and isinstance(details, dict) and details.get('limit_reason') == 'token_total':return RemoteAIError('O limite de uso deste código acabou. Peça mais ao administrador.', status=status)
    if status == 429:
        reasons = {
            'user_daily_requests':'Limite diário de comandos online atingido.',
            'global_daily_requests':'Limite diário do serviço de IA atingido.',
            'user_daily_budget':'Limite diário de uso online atingido.',
            'global_daily_budget':'Limite diário de uso do serviço de IA atingido.',
            'user_burst':'Muitos comandos online em pouco tempo.',
            'ip_burst':'Muitos comandos online nesta conexão em pouco tempo.',
            'token_daily':'Limite diário de uso deste código atingido.'}
        details = details if isinstance(details, dict) else {}
        reason = details.get('limit_reason')
        message = reasons.get(reason, 'Limite temporário ou diário do serviço online atingido.') if isinstance(reason, str) else 'Limite temporário ou diário do serviço online atingido.'
        retry = details.get('retry_after_seconds')
        if isinstance(reason, str) and reason in reasons and type(retry) is int and 1 <= retry <= 86400:
            message += f' Tente novamente em {retry} segundos.'
        return RemoteAIError(message + ' Comandos locais continuam disponíveis.', status=status)
    if status == 401:return RemoteAIError('Acesso ao serviço online não autorizado. Confira o acesso em Configurações.', status=status)
    if status == 403:return RemoteAIError('Reconhecimento online bloqueado pelo servidor. Comandos locais continuam disponíveis.', status=status)
    if 500 <= status <= 599:return RemoteAIError('Servidor de serviço online indisponível. Comandos locais continuam disponíveis.', status=status)
    return RemoteAIError('Reconhecimento online indisponível. Use um comando local.', status=status)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def valid_intent(value):
    if not isinstance(value, dict) or set(value) != {'action','parameters','needs_clarification','clarification'}:
        return False
    action, parameters = value['action'], value['parameters']
    fields = {**{k:set(v['properties']) for k,v in DOMAIN_SCHEMAS.items()}, 'create_timer': {'seconds'}, 'cancel_last_timer': set(), 'cancel_timer': {'timer_id'}, 'query_timer': {'timer_id'}, 'shared': {'level'}, 'unknown': set()}
    if not isinstance(action,str) or action not in fields or not isinstance(parameters,dict) or set(parameters) != fields[action]:
        return False
    clarification=value['clarification']
    if type(value['needs_clarification']) is not bool or value['needs_clarification'] != (clarification is not None):
        return False
    if clarification is not None and (not isinstance(clarification,str) or not clarification.strip() or len(clarification)>300):
        return False
    if action in DOMAIN_SCHEMAS:return _schema_valid(parameters,DOMAIN_SCHEMAS[action])
    if action=='create_timer':
        return type(parameters['seconds']) is int and 1<=parameters['seconds']<=10800
    if action=='shared':
        return parameters['level'] is None or type(parameters['level']) is int and 1<=parameters['level']<=100000
    if action in ('cancel_timer','query_timer'):
        return isinstance(parameters['timer_id'],str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',parameters['timer_id']) is not None
    return True



def safe_temporal_intent(intent, text):
    import unicodedata
    if intent['needs_clarification']:return intent
    schema=DOMAIN_SCHEMAS.get(intent['action'],{})
    date_fields=[key for key in schema.get('properties',{}) if key.endswith('_at') or key=='target_datetime']
    normalized=''.join(c for c in unicodedata.normalize('NFD',text.lower()) if not unicodedata.combining(c))
    explicit=re.search(r'\b(?:ontem|amanha|hoje|ha|as|faz|atras|antes|depois|daqui)\b|\bmais\s+cedo\b|\b\d{1,2}:\d{2}\b|\d{4}-\d{2}-\d{2}t',normalized)
    if date_fields and (explicit or intent['action'] in ('boss.kill.correct_time','stamina.project','stamina.reverse')):
        return {'action':'unknown','parameters':{},'needs_clarification':True,'clarification':'Confirme a data pelo formulário. Datas do fallback online não são presumidas; use o comando local com horário explícito.'}
    return intent


def utf16_length(text):
    return len(text.encode('utf-16-le')) // 2


def truncate_utf16(text, limit):
    return text.encode('utf-16-le')[:limit * 2].decode('utf-16-le', errors='ignore')


def _valid_messages(messages):
    return isinstance(messages,list) and 1<=len(messages)<=6 and all(isinstance(m,dict) and set(m)=={'role','text'} and m['role'] in ('user','assistant') and isinstance(m['text'],str) and m['text'].strip() and utf16_length(m['text'])<=500 for m in messages) and messages[-1]['role']=='user'


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
    def __init__(self, token, device_id=None):
        if not isinstance(token,str) or not TOKEN.fullmatch(token): raise ValueError('Código de acesso inválido.')
        self._token=token
        self._device_id=device_id
        self._opener=urllib.request.build_opener(NoRedirect())

    def _post(self, route, body, request_id, content_type, extra_headers=None):
        try:
            if str(uuid.UUID(request_id,version=4))!=request_id.lower(): raise ValueError()
            request=urllib.request.Request(ENDPOINT+route,data=body,method='POST',headers={'User-Agent':'TibiaTudo/1.0','Authorization':'Bearer '+self._token,'X-Request-ID':request_id,'Content-Type':content_type})
            if self._device_id: request.add_header('X-Device-ID', self._device_id)
            for key, value in (extra_headers or {}).items():
                request.add_header(key, value)
            with self._opener.open(request,timeout=15) as response:
                if response.status!=200: raise http_error(response.status)
                raw=response.read(8193)
                if len(raw)>8192: raise ValueError()
                value=json.loads(raw.decode('utf-8'))
            if not isinstance(value,dict) or value.get('request_id')!=request_id: raise ValueError()
            return value
        except urllib.error.HTTPError as error:
            details = None
            if error.code in (403, 429):
                try:
                    raw = error.read(8193)
                    if len(raw) <= 8192: details = json.loads(raw.decode('utf-8'))
                except (OSError, ValueError, UnicodeError):
                    pass
            raise http_error(error.code, details) from None
        except OSError:
            raise RemoteAIError('Falha de conexão com o reconhecimento online. Comandos locais continuam disponíveis.') from None
        except (ValueError, TypeError, AttributeError):
            raise RemoteAIError('Reconhecimento online indisponível. Use o comando local ou tente novamente com nova ativação.') from None

    def transcribe(self, wav, request_id, vocabulario=()):
        headers={'X-Vocabulary':cabecalho(list(vocabulario))} if vocabulario else None
        result=self._post('/transcribe',wav,request_id,'audio/wav',headers)
        if set(result)!={'request_id','text'} or not isinstance(result['text'],str) or not result['text'].strip() or len(result['text'])>500:
            raise RemoteAIError('Resposta online inválida.')
        return result['text']

    def interpret(self, text, request_id):
        if not isinstance(text,str) or not text.strip() or len(text)>500: raise RemoteAIError('Texto de comando inválido.')
        result=self._post('/interpret',json.dumps({'request_id':request_id,'text':text},ensure_ascii=False).encode('utf-8'),request_id,'application/json')
        if set(result)!={'request_id','intent'} or not valid_intent(result['intent']): raise RemoteAIError('Resposta online inválida.')
        return safe_temporal_intent(result['intent'],text)

    def chat(self, messages, request_id):
        if not _valid_messages(messages): raise RemoteAIError('Mensagens de chat inválidas.')
        result=self._post('/chat',json.dumps({'request_id':request_id,'messages':messages},ensure_ascii=False).encode('utf-8'),request_id,'application/json')
        kind,text,intent=result.get('kind'),result.get('text'),result.get('intent')
        if set(result)!={'request_id','kind','text','intent'} or not (
                kind=='reply' and isinstance(text,str) and text.strip() and utf16_length(text)<=1800 and intent is None
                or kind=='action' and valid_intent(intent) and (text is None or isinstance(text,str) and utf16_length(text)<=600)
                or kind=='out_of_scope' and text is None and intent is None): raise RemoteAIError('Resposta online inválida.')
        return {'kind':kind,'text':text,'intent':safe_temporal_intent(intent,'\n'.join(m['text'] for m in messages if m['role']=='user')) if kind=='action' else None}
