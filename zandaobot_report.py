"""Mensagem compartilhável construída apenas com dados atuais e campos manuais."""
from datetime import date, datetime, timezone, timedelta
import mensagem_formato
import mensagens_tibianas

BRT = timezone(timedelta(hours=-3))


def gerar(r, campos=None, extras=(), mini=True, agora=None):
    """extras = blocos de texto das consultas marcadas; mini = incluir a seção de Mini World Changes; agora = relógio de Brasília (teste)."""
    c = campos if isinstance(campos, dict) else {}
    agora = agora or datetime.now(BRT)
    def text(key, default='❓'):
        value = str(c.get(key) or '').strip().replace('\n', ' ')[:200]
        return value or default
    def day(value):
        try:
            return datetime.fromisoformat(value[:10]).strftime('%d/%m/%Y')
        except (ValueError, TypeError):
            return '❓'
    def linha(rotulo, valor):
        """Linha só quando há dado: o que não se sabe fica de fora em vez de aparecer como ❓."""
        return [f'{rotulo} {valor}'] if valor and '❓' not in valor else []
    board = r.get('world_board') or {}
    current = bool(board.get('valido'))
    events = board.get('eventos', []) if current else []
    ids = {e['id'] for e in events}
    def state(ident):
        return '🟢 Ativo' if ident in ids else '🔴 Inativo' if current and board.get('completo') else '❓'
    yasir = r.get('yasir') or {}
    y = '🟢 Ativo' if yasir.get('estado') == 'presente' else '🔴 Inativo' if yasir.get('estado') == 'ausente' else '❓'
    boosted = r.get('boostados') or {}
    def boost(key):
        return (boosted.get(key) or {}).get('nome', '❓') if not boosted.get('velho') and not boosted.get('aguardando') else '❓'
    try:
        dia = date.fromisoformat(str(r.get('dia', ''))[:10])
    except ValueError:
        dia = agora.date()
    comunidade = text('comunidade', 'tripulação')
    lines = [f'☀️ *Bom dia, {comunidade}!*', f'📅 {mensagem_formato.data_hora(dia, agora)}', '',
             mensagem_formato.frase(mensagens_tibianas.do_dia(dia, str(r.get('personagem') or '') + str(r.get('mundo') or ''))), '']
    lines += linha('🌍 *Mundo:*', r.get('mundo') or '❓')
    lines += linha('🧭 *Rashid:*', r.get('rashid') or '❓')
    lines += linha('🧬 *Criatura do dia:*', boost('criatura'))
    lines += linha('👑 *Boss do dia:*', boost('boss'))
    calendar = r.get('calendario') or {}
    active = [e for e in calendar.get('eventos', []) if e.get('estado') == 'ativo'] if not calendar.get('velho') else []
    for event in active:
        lines.append(f"🎉 *Evento:* {event['titulo']} (até {day(event['fim'])[:5]})")
        if event.get('descricao'):
            lines.append('_' + ' '.join(event['descricao'].split())[:350] + '_')
    lines += linha('🐪 *Yasir:*', y)
    dream = r.get('dream_court') or {}
    if not dream.get('velho') and dream.get('nome'):
        lines.append(f"🌙 *Dream Court:* {dream['nome']} · rotação prevista")
    kills = r.get('killstatistics') or {}
    if kills.get('estado') == 'disponivel':
        counts = '; '.join(f"{b['nome']}: {b['last_day_killed'] if b.get('last_day_killed') is not None else '❓'}" for b in kills.get('bosses', []))
        lines.append(f"📊 *Dream Court — mortes (Last Day):* {counts}")
    for rotulo, valor in (('🔱 *Boss Deeplings:*', text('deeplings')), ('🧭 *Região boostada:*', text('regiao')), ('⚙️ *Roshamuul:*', text('roshamuul')),
                          ('🚪 *Fury Gate:*', state('fury_gates')), ("🪓 *Bibby's Bloodbath:*", state('warpath')),
                          ('🏟️ *Tibia Drome:*', text('drome', 'Rotação termina no SS de ' + day(calendar['drome_fim']) if calendar.get('drome_fim') else '❓'))):
        lines += linha(rotulo, valor)
    if c.get('coin_compra') or c.get('coin_venda'):
        lines.append(f"🪙 *Tibia Coin ({text('coin_hora', 'agora')}):* comprar {text('coin_compra')} gp · vender {text('coin_venda')} gp")
    if mini:
        mudancas = [f"• {e.get('rotulo', e['nome'])} · {e.get('local', '')}" + (f" · {e['detalhe']}" if e.get('detalhe') else '') for e in events if e['id'] not in ('oriental_trader', 'fury_gates', 'warpath')]
        online = [n for n in yasir.get('mudancas') or [] if isinstance(n, str) and n != 'Oriental Trader']
        if current:
            observed = datetime.fromtimestamp(board['consulta'], BRT).strftime('%H:%M')
            nota = f"_World Board manual às {observed} (Brasília) · {'completo' if board.get('completo') else 'parcial'} · pode mudar após a consulta._"
        else:
            mudancas += [f'• {n}' for n in online]
            nota = ''
        if mudancas:
            lines += ['', '🌍 *Outras world changes:*', *mudancas, *([nota] if nota else [])]
    artigos = sorted([*(r.get('anuncios') or []), *(r.get('noticias') or [])], key=lambda x: str(x.get('data', '')), reverse=True)
    noticias = mensagem_formato.noticias(artigos, r.get('news_ticker') or [])
    if noticias:
        lines += ['', noticias]
    for bloco in extras:
        lines += ['', bloco]
    lines += ['', '━━━━━━━━━━━━━━', '✍️ ' + text('assinatura', r.get('personagem') or 'ZandaoBot')]
    return '\n'.join(lines)
