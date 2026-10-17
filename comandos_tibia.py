"""Comandos de Tibia no chat do Assistente: bomdia, kill, boss, online, char, death, guild, exp. Só dados públicos (TibiaData e GuildStats).

Sem argumento, cada comando usa o personagem em uso (o mundo e a guild dele); com argumento, consulta o que foi pedido.
"""
import re
from string import capwords
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

import guild_stats
import tibia_info
import zandaobot
import zandaobot_report
import zandaobot_sources as sources

COMANDO = re.compile(r'\s*!?\s*(bom\s?dia|kill|boss|online|char|death|guild|exp)\b\s*(.*?)\s*', re.I | re.S)
MUNDO = re.compile(r'[A-Za-z]{2,40}')
NOME = re.compile(r"[A-Za-z][A-Za-z '\-.]{1,39}")
FALHA = 'Não consegui consultar a TibiaData agora (ou o nome não existe). Tente de novo em instantes.'
# Palavras de pergunta/pedido: o que vem depois do comando com elas é uma frase para a IA, não um nome.
PALAVRAS_DE_FRASE = {'como', 'qual', 'quais', 'quando', 'onde', 'quanto', 'quantos', 'quantas', 'porque', 'por', 'que', 'pra', 'para',
                     'tenho', 'tem', 'posso', 'devo', 'faco', 'faço', 'fazer', 'funciona', 'funcionam', 'preciso', 'quero', 'me', 'meu',
                     'minha', 'eu', 'é', 'sao', 'são', 'sobre', 'explica', 'explique', 'mostra', 'mostre', 'agora', 'hoje', 'ontem'}


def _arg_ok(rest):
    """Argumento com cara de nome (até 3 palavras, sem pergunta). Frase para a IA não vira comando."""
    palavras = rest.split()
    return bool(NOME.fullmatch(rest)) and len(palavras) <= 3 and not any(p.casefold() in PALAVRAS_DE_FRASE for p in palavras)
SEM_PERSONAGEM = 'Cadastre e escolha um personagem em Configurações, ou use: '
VOCACOES = ('Knight', 'Paladin', 'Sorcerer', 'Druid', 'Monk')
BRT = timezone(timedelta(hours=-3))
RANKING = 'https://guildstats.eu/top-experience?world={}&time=0'  # time=0 é "Yesterday"; só traz o top 500 do mundo


def _get(chave, endpoint):
    r = zandaobot._consultar(chave, endpoint)
    return r['dados'], r['velho']


def _data(texto, hora=False):
    try:
        d = datetime.fromisoformat(str(texto).replace('Z', '+00:00')).astimezone(BRT)
    except ValueError:
        return '❓'
    return d.strftime('%d/%m/%Y %H:%M' if hora else '%d/%m/%Y')


def _ficha(nome):
    """(personagem, mortes) ou None."""
    d, _ = _get('char:' + nome.lower(), '/character/' + quote(nome))
    bloco = d.get('character') or {}
    char = bloco.get('character') or {}
    if not char.get('name'):
        return None
    return char, bloco.get('deaths') if isinstance(bloco.get('deaths'), list) else []


def _guild_do_personagem(personagem):
    """(guild, mundo) do personagem em uso; (None, None) sem personagem, sem guild ou sem rede."""
    f = _ficha(personagem) if personagem and NOME.fullmatch(personagem) else None
    if not f:
        return None, None
    return (f[0].get('guild') or {}).get('name'), f[0].get('world')


def _mortes(deaths, limite):
    return [f"• {_data(m.get('time'))} — Lv {m.get('level', '?')} — {m.get('reason', '')}" for m in deaths[:limite] if isinstance(m, dict)]


def _kk(n):
    return f'{n / 1e9:.2f}kkk' if abs(n) >= 1e9 else f'{n / 1e6:.2f}kk'


def _ranking(mundo):
    """Top 500 de XP de ontem do mundo no GuildStats: [(nome, level, xp)] ou None."""
    def buscar():
        p = guild_stats.Tables()
        p.feed(sources.get_text(RANKING.format(quote(mundo)), 6_000_000))
        linhas = [(r[1], r[2], int(r[3].replace(',', ''))) for t in p.tables for r in t['rows']
                  if len(r) >= 7 and r[0].isdigit() and re.fullmatch(r'[+-]?[0-9,]+', r[3])]
        if not linhas:
            raise ValueError('Ranking vazio')
        return linhas
    return sources.cached('gs-topxp:' + mundo.lower(), buscar, ttl=1800)['dados']


def _linha_xp(i, nome, level, xp):
    return f"{i}. {nome} (Lv {str(level).replace(',', '.')}) — {'+' if xp >= 0 else '-'}{_kk(abs(xp))}"


def _xp_mundo(mundo):
    if not MUNDO.fullmatch(mundo or ''):
        return 'Informe o mundo, ex.: exp {mundo}.'
    ranking = _ranking(mundo)
    if ranking is None:
        return '🏆 Top 10 XP de ontem: indisponível agora (GuildStats).'
    top = sorted(ranking, key=lambda x: -x[2])[:10]
    return '\n'.join([f'🏆 Top 10 XP de ontem — 🌍 {mundo.capitalize()} (GuildStats)']
                     + [_linha_xp(i, n, lv, xp) for i, (n, lv, xp) in enumerate(top, 1)])


def _xp_guild(nome, mundo=None):
    """Top 10 de XP de ontem entre os membros da guild que aparecem no ranking do mundo dela."""
    d, _ = _get('guild:' + nome.lower(), '/guild/' + quote(nome))
    g = d.get('guild') or {}
    mundo = g.get('world') or mundo
    membros = {str(x.get('name', '')).casefold() for x in g.get('members') or [] if isinstance(x, dict)}
    ranking = _ranking(mundo) if membros and MUNDO.fullmatch(mundo or '') else None
    if ranking is None:
        return '🏆 Top XP de ontem: indisponível agora (GuildStats ou TibiaData).'
    achados = sorted((x for x in ranking if x[0].casefold() in membros), key=lambda x: -x[2])
    if not achados:
        return f'🏆 Top XP de ontem — {nome}: nenhum membro ficou no top 500 do mundo no GuildStats.'
    linhas = [f'🏆 Top XP de ontem — {nome} (GuildStats)']
    linhas += [_linha_xp(i, n, lv, xp) for i, (n, lv, xp) in enumerate(achados[:10], 1)]
    linhas.append(f'_{len(achados)} de {len(membros)} membros aparecem no top 500 de XP do mundo._')
    return '\n'.join(linhas)


def _ou(texto, rotulo):
    return f'{rotulo}: indisponível agora.' if texto == FALHA else texto


def _exp(rest, mundo, personagem=None, hoje=None):
    if rest:
        mundos = {w.casefold() for w in zandaobot.mundos()['mundos']}
        return _xp_mundo(rest) if rest.casefold() in mundos else _xp_guild(rest)
    partes = [_xp_mundo(mundo)] if mundo else []
    guild, _ = _guild_do_personagem(personagem)
    if guild:
        partes.append(_xp_guild(guild))
    return '\n\n'.join(partes) or SEM_PERSONAGEM + 'exp {mundo}.'


def _bomdia(rest, mundo, personagem=None, hoje=None):
    m = rest or mundo
    r = zandaobot.buscar(m)
    if r.get('erro'):
        return r['erro']
    msg = zandaobot_report.gerar(r, {'comunidade': 'tibianos', 'assinatura': personagem})
    extras = [_ou(_kill('', m), '⚔️ Criaturas mortas ontem')] if m and MUNDO.fullmatch(m) else []
    guild, mundo_guild = _guild_do_personagem(personagem)
    # a guild é do personagem em uso: com outro mundo explícito no comando, não se aplica
    if guild and (not rest or rest.casefold() == str(mundo_guild).casefold()):
        extras += [_ou(_guild_info(guild, hoje), '🏰 Guild'), _xp_guild(guild, mundo_guild or m)]
    if not extras:
        return msg
    corte = msg.rfind('⏰ Próximo SS')
    bloco = '\n\n'.join(extras)
    return msg + '\n\n' + bloco if corte < 0 else msg[:corte] + bloco + '\n\n' + msg[corte:]


def _kill(rest, mundo, personagem=None, hoje=None):
    m = rest or mundo
    if not m:
        return SEM_PERSONAGEM + 'kill {mundo}.'
    if not MUNDO.fullmatch(m):
        return 'Nome de mundo inválido. Use só letras, ex.: kill Antica.'
    d, velho = _get('kills-todas:' + m.lower(), '/killstatistics/' + m)
    entradas = (d.get('killstatistics') or {}).get('entries')
    if not isinstance(entradas, list):
        return FALHA
    vivos = [(e['race'], e['last_day_killed']) for e in entradas if isinstance(e, dict) and isinstance(e.get('race'), str)
             and type(e.get('last_day_killed')) is int and e['last_day_killed'] > 0 and not e['race'].startswith('(')]
    if not vivos:
        return f'Sem abates registrados ontem em {m}.'
    top = sorted(vivos, key=lambda x: (-x[1], x[0]))[:10]
    linhas = [f'⚔️ Top 10 criaturas mortas ontem — 🌍 {m.capitalize()}' + (' (dados antigos)' if velho else '')]
    linhas += [f'{i}. {capwords(nome)} — {n:,} mortes'.replace(',', '.') for i, (nome, n) in enumerate(top, 1)]
    return '\n'.join(linhas)


def _boss(rest, mundo, personagem=None, hoje=None):
    m = rest or mundo
    b = tibia_info.boostados()
    linhas = ['👑 Bosses' + (f' — 🌍 {m.capitalize()}' if m else '')]
    linhas.append('⭐ Boss boosted: ' + ((b.get('boss') or {}).get('nome') or 'indisponível'))
    linhas.append('🧬 Criatura boosted: ' + ((b.get('criatura') or {}).get('nome') or 'indisponível'))
    if m:
        ks = zandaobot.killstatistics(m)
        mortos = [x['nome'] for x in ks.get('bosses', []) if (x.get('last_day_killed') or 0) > 0]
        if mortos:
            linhas.append('💀 Morreram ontem: ' + ', '.join(mortos))
        elif ks.get('consulta') is None:
            linhas.append('💀 Mortes de ontem indisponíveis agora.')
        else:
            linhas.append('💀 Nenhum boss monitorado morreu ontem.')
    else:
        linhas.append(SEM_PERSONAGEM + 'boss {mundo}.')
    return '\n'.join(linhas)


def _online_mundo(nome):
    """Texto do mundo, ou None se `nome` não for um mundo."""
    if not MUNDO.fullmatch(nome):
        return None
    d, _ = _get('mundo:' + nome.lower(), '/world/' + quote(nome))
    w = d.get('world') or {}
    return f"🟢 {w['name']}: {w.get('players_online', '?')} players online." if w.get('name') else None


def _online_guild(nome):
    d, _ = _get('guild:' + nome.lower(), '/guild/' + quote(nome))
    g = d.get('guild') or {}
    membros = g.get('members')
    if not isinstance(membros, list):
        return FALHA
    on = sorted((x for x in membros if isinstance(x, dict) and x.get('status') == 'online'), key=lambda x: -(x.get('level') or 0))
    linhas = [f"🟢 {g.get('name', nome)} online ({len(on)} de {len(membros)})"]
    linhas += [f"• Lv {x.get('level', '?')} {x.get('name', '?')} ({x.get('vocation', '?')})" for x in on[:15]]
    if len(on) > 15:
        linhas.append(f'… e mais {len(on) - 15}')
    return '\n'.join(linhas)


def _online(rest, mundo, personagem=None, hoje=None):
    if rest:
        return _online_mundo(rest) or _online_guild(rest)
    partes = [_online_mundo(mundo) or FALHA] if mundo else []
    guild, _ = _guild_do_personagem(personagem)
    if guild:
        partes.append(_online_guild(guild))
    return '\n\n'.join(partes) or SEM_PERSONAGEM + 'online {mundo}.'


def _char(rest, mundo, personagem=None, hoje=None):
    nome = rest or personagem
    if not nome:
        return SEM_PERSONAGEM + 'char {personagem}.'
    if not NOME.fullmatch(nome):
        return 'Use: char {personagem}.'
    f = _ficha(nome)
    if not f:
        return FALHA
    c, deaths = f
    linhas = [f"📜 {c['name']}", f"🛡️ {c.get('vocation', '?')} · 🏆 Level {c.get('level', '?')} · 🌍 {c.get('world', '?')}"]
    if (c.get('guild') or {}).get('name'):
        linhas.append(f"⚔️ Guilda: {c['guild']['name']}")
    if c.get('last_login'):
        linhas.append(f"⏰ Último login: {_data(c['last_login'], True)} (BRT)")
    m = _mortes(deaths, 3)
    linhas += ['💀 Mortes recentes:', *m] if m else ['💀 Sem mortes nos últimos 30 dias.']
    return '\n'.join(linhas)


def _death(rest, mundo, personagem=None, hoje=None):
    nome = rest or personagem
    if not nome:
        return SEM_PERSONAGEM + 'death {personagem}.'
    if not NOME.fullmatch(nome):
        return 'Use: death {personagem}.'
    f = _ficha(nome)
    if not f:
        return FALHA
    c, deaths = f
    m = _mortes(deaths, 10)
    return '\n'.join([f"☠️ Mortes — {c['name']} (30 dias)", *m]) if m else f"☠️ {c['name']} não morreu nos últimos 30 dias."


def _guild_info(nome, hoje):
    if not NOME.fullmatch(nome):
        return 'Use: guild {guild}.'
    d, _ = _get('guild:' + nome.lower(), '/guild/' + quote(nome))
    g = d.get('guild') or {}
    membros = [x for x in g.get('members') or [] if isinstance(x, dict)]
    if not membros:
        return FALHA
    on = sum(1 for x in membros if x.get('status') == 'online')
    voc = ' · '.join(f"{v}: {sum(1 for x in membros if v in str(x.get('vocation')))}" for v in VOCACOES)
    corte = hoje - timedelta(days=7)
    novos = []
    for x in membros:
        try:
            if date.fromisoformat(str(x.get('joined'))[:10]) >= corte:
                novos.append(x)
        except ValueError:
            pass
    novos.sort(key=lambda x: x['joined'], reverse=True)
    linhas = [f"🏰 {g.get('name', nome)}", f"📅 Fundada em {g.get('founded', '❓')} · 🌍 {g.get('world', '❓')}",
              f'🟢 {on} de {len(membros)} online', f'🧙 {voc}']
    linhas += ['➕ Entraram (7 dias):', *[f"• {x.get('name', '?')} — Lv {x.get('level', '?')} ({_data(x['joined'])})" for x in novos]] if novos else ['➕ Entraram (7 dias): ninguém.']
    return '\n'.join(linhas)


def _guild(rest, mundo, personagem=None, hoje=None):
    nome = rest or _guild_do_personagem(personagem)[0]
    return _guild_info(nome, hoje) if nome else 'Informe a guild, ex.: guild {guild} (ou use um personagem que tenha guild).'


HANDLERS = {'bomdia': _bomdia, 'kill': _kill, 'boss': _boss, 'online': _online, 'char': _char, 'death': _death, 'guild': _guild, 'exp': _exp}


def responder(texto, mundo='', hoje=None, personagem=''):
    """Resposta em texto, ou None quando a mensagem não é um destes comandos."""
    m = COMANDO.fullmatch(texto or '')
    if not m:
        return None
    cmd, rest = re.sub(r'\s', '', m[1].lower()), m[2]
    # só vale digitado sozinho (ou com um nome): uma frase para a IA que comece com a palavra do comando segue para a IA
    so_mundo = cmd in ('bomdia', 'kill', 'boss')
    if rest and not (MUNDO.fullmatch(rest) if so_mundo else _arg_ok(rest)):
        return None
    try:
        return HANDLERS[cmd](rest, mundo, personagem, hoje or date.today())
    except Exception:
        return FALHA
