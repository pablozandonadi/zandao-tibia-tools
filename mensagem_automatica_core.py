"""Contrato compartilhado pela API, prévia e worker."""
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc
FIELDS = {'comunidade':'Comunidade', 'assinatura':'Assinatura', 'deeplings':'Boss Deeplings',
          'regiao':'Região boostada', 'roshamuul':'Roshamuul / robôs', 'drome':'Tibia Drome',
          'coin_compra':'TC: comprar (gp)', 'coin_venda':'TC: vender (gp)', 'coin_hora':'Horário dos preços'}
BLOCKS = ('dia','saudacao','frase','mundo','calendario','yasir','rashid','criatura','boss','dream','dream_mortes','mudancas_online','server_save')
EXTRAS = ('noticias','kill','exp_mundo','guild','exp_guild','online_guild','char','transfer')
MAX_AGE = 1800

class Invalid(ValueError):
    """Mensagem controlada, sem payloads ou exceções externas."""

class SourceUnavailable(Invalid):
    """Falha transitória antes de qualquer despacho, elegível a repetição limitada."""

def reference_day(now):
    local = now.astimezone(ZoneInfo('Europe/Berlin'))
    return (local.date() - timedelta(days=local.hour < 10)).isoformat()

def local_instant(day, clock, zone):
    """fold=0 escolhe primeira ocorrência; roundtrip rejeita horário inexistente."""
    naive = datetime.fromisoformat(day+'T'+clock)
    candidate = naive.replace(tzinfo=ZoneInfo(zone), fold=0).astimezone(UTC)
    return candidate if candidate.astimezone(ZoneInfo(zone)).replace(tzinfo=None) == naive else None

def validate(data, schedule=False):
    if not isinstance(data, dict) or set(data)-{'personagem','mundo','blocks','fields','values','extras','args','generateAt','sendAt','timezone','manualDate'}:
        raise Invalid('Configuração desconhecida.')
    c = {}
    for key, pattern in [('personagem',r"[A-Za-z][A-Za-z '\-.]{1,39}"),('mundo',r'[A-Za-z]{2,40}')]:
        value=data.get(key)
        if not isinstance(value,str) or not re.fullmatch(pattern,value.strip()): raise Invalid('Personagem ou mundo inválido.')
        c[key]=value.strip()
    for group, allowed in [('blocks',BLOCKS),('fields',FIELDS),('extras',EXTRAS)]:
        values=data.get(group,{})
        if not isinstance(values,dict) or set(values)-set(allowed) or any(type(v) is not bool for v in values.values()): raise Invalid('Seleção inválida.')
        c[group]={k: values.get(k,False) for k in allowed}
    for group, allowed, limit in [('values',FIELDS,200),('args',EXTRAS,40)]:
        values=data.get(group,{})
        if not isinstance(values,dict) or set(values)-set(allowed): raise Invalid('Campos inválidos.')
        c[group]={}
        for k,v in values.items():
            # só a assinatura pode ter quebra de linha (ex.: "TibiaTudo IA…" e "by Zandão" em linhas separadas)
            if not isinstance(v,str) or len(v)>limit or any(ord(x)<32 and not (k=='assinatura' and x=='\n') for x in v): raise Invalid('Texto inválido.')
            if group=='args' and v and not re.fullmatch(r"[A-Za-z][A-Za-z '\-.]{1,39}",v): raise Invalid('Argumento inválido.')
            c[group][k]=v.strip()
    for key in ['generateAt','sendAt']:
        v=data.get(key,'')
        if not isinstance(v,str) or (v and not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',v)): raise Invalid('Horário inválido.')
        c[key]=v
    c['timezone']=data.get('timezone','')
    if not isinstance(c['timezone'],str) or len(c['timezone'])>100: raise Invalid('Fuso inválido.')
    try:
        if c['timezone']: ZoneInfo(c['timezone'])
    except (ZoneInfoNotFoundError,ValueError): raise Invalid('Fuso inválido.') from None
    if (c['generateAt'] or c['sendAt'] or schedule) and not c['timezone']: raise Invalid('Informe o fuso horário.')
    if schedule and not(c['generateAt'] and c['sendAt']): raise Invalid('Informe geração e envio.')
    if c['generateAt'] and c['sendAt'] and c['sendAt']<c['generateAt']: raise Invalid('Envio anterior à geração.')
    manual=data.get('manualDate','')
    if not isinstance(manual,str): raise Invalid('Data manual inválida.')
    if manual:
        try: datetime.strptime(manual,'%Y-%m-%d')
        except (ValueError,TypeError): raise Invalid('Data manual inválida.') from None
    c['manualDate']=manual
    if not any(c[g][k] for g in ['blocks','fields','extras'] for k in c[g]): raise Invalid('Selecione algum conteúdo.')
    return c

def fresh(snapshot, now, expected):
    if not isinstance(snapshot,dict) or snapshot.get('reference_date')!=expected: raise Invalid('Data das fontes inválida.')
    for source in snapshot.get('sources',[]):
        age=now.timestamp()-source['fetched_at']
        if source.get('reference_date')!=expected or not -120<=age<=MAX_AGE: raise Invalid('Fontes expiradas.')
    if not snapshot.get('text'): raise Invalid('Mensagem vazia.')
