"""Consultas do app, sem ponte WhatsApp e sem operações administrativas de grupo."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from assistente_consultas import NEW_COMMANDS, HELP, parse_command
from comandos_tibia import MODELOS, responder
from .botcmds import Bot, MODELS
from .xp_sources import XPProvider
from .domain import Invalid

CATALOG={**MODELOS,**{key:{**MODELS[key]} for key in NEW_COMMANDS}}
CATALOG['help']={**CATALOG['help'],'template':HELP}


def execute(store,text,world='',character='',override=None):
    if not isinstance(text,str) or not 1<=len(text)<=180 or any(ord(c)<32 for c in text):raise Invalid('Comando inválido.')
    if not isinstance(world,str) or world and not re.fullmatch(r'[A-Za-z]{2,40}',world):raise Invalid('Mundo inválido.')
    if not isinstance(character,str) or character and not re.fullmatch(r"[A-Za-z][A-Za-z '\-.]{1,39}",character):raise Invalid('Personagem inválido.')
    parsed=parse_command(text)
    if not parsed:raise Invalid('Comando de consulta desconhecido.')
    cmd,arg=parsed
    saved=store.bot_settings('assistente');setting=override if override is not None else saved.get(cmd,{})
    if setting.get('enabled') is False:return {'command':cmd,'text':'Este comando está desativado no Assistente.'}
    today=datetime.now(ZoneInfo('America/Sao_Paulo')).date()
    if cmd in ('char','online'):
        result=responder(cmd+(' '+arg if arg else ''),world,today,character,ajuste=setting)
    else:
        bot=Bot(experience=XPProvider(store).report,settings=lambda:{cmd:setting})
        if cmd=='help':
            import modelos
            result=modelos.renderizar(setting.get('text') or HELP,{'resposta':HELP})
        else:result=bot.handle('!'+cmd+(' '+arg if arg else ''),world,today)
    if not isinstance(result,str) or not result:result='Não consegui consultar agora. Tente novamente em instantes.'
    return {'command':cmd,'text':result[:12000]}
