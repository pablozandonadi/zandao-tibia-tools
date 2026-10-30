"""Comandos de consulta do Assistente: parser compartilhado, sem segredos nem engine no app."""
import re
import unicodedata

ALIASES={'help':'help','ajuda':'help','comandos':'help','duelo':'duelo','evolucao':'evolucao','evo':'evolucao','precocoin':'precocoin','tc':'precocoin','pt':'pt','party':'pt','char':'char','personagem':'char','online':'online','xptop':'xptop'}
NEW_COMMANDS=('help','duelo','evolucao','precocoin','pt','xptop')
HELP='📖 *Assistente Tibiano — consultas*\n\n!duelo Nome Um x Nome Dois\n!evolucao Nome (ou !evo)\n!pt Nome [vocação] (ou !party)\n!xptop Nome\n!precocoin Mundo (ou !tc)\n!char Nome (ou !personagem)\n!online Mundo ou Guild\n!help\n\nTambém funcionam sem !. Timers, shared, stamina, bosses e Market continuam no Help do aplicativo. Configurações e alertas de grupos ficam em Mensagens.'
GROUP_ONLY='Esse comando precisa de um grupo e de permissão de administrador. Use Mensagens para configurar o WhatsApp.'


def parse_command(text):
    if not isinstance(text,str) or len(text)>180:return None
    match=re.fullmatch(r'!?\s*([^\s!]+)(?:\s+(.*))?',text.strip())
    if not match:return None
    token=''.join(c for c in unicodedata.normalize('NFKD',match[1].casefold()) if not unicodedata.combining(c))
    key=ALIASES.get(token)
    return (key,' '.join((match[2] or '').split())) if key else None


def responder(text,context):
    explicit=isinstance(text,str) and text.strip().startswith('!')
    if explicit and re.match(r'!\s*(set|alerta|bomdia)(?:\s|$)',text.strip(),re.I):return GROUP_ONLY
    parsed=parse_command(text)
    if not parsed:return None
    cmd,arg=parsed
    # As consultas legadas e o shared numérico local conservam sua interpretação.
    if not explicit and ((cmd=='char' and text.strip().split()[0].casefold()=='char' or cmd=='online') or cmd=='pt' and (not arg or re.search(r'\d',arg)) or cmd=='help' and arg):return None
    if not explicit and cmd=='precocoin' and text.strip().split()[0].casefold()=='tc' and arg and (not re.fullmatch(r'[A-Za-z]{2,40}',arg) or arg.casefold() in ('ta','tá','vale','quanto','preco','preço','gold','reais')):return None
    context=context if isinstance(context,dict) else {}
    world=context.get('world_id') or '';character=context.get('character_id') or ''
    world=world if isinstance(world,str) and re.fullmatch(r'[A-Za-z]{2,40}',world) else ''
    character=character if isinstance(character,str) and re.fullmatch(r"[A-Za-z][A-Za-z '\-.]{1,39}",character) else ''
    if cmd in ('char','pt','evolucao','xptop') and not arg and re.fullmatch(r"[A-Za-z][A-Za-z '\-.]{1,39}",character):arg=character
    command='!'+cmd+(' '+arg if arg else '')
    try:
        from mensagem_automatica_access import assistant_command
        return assistant_command(command,world,character)['text']
    except Exception:
        return 'Não consegui consultar agora. Tente novamente em instantes; nenhum dado de XP foi estimado.'
