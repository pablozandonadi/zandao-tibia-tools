"""Painel das mensagens automáticas: junta, por grupo de WhatsApp, os comandos, o alerta da guild e o bom dia.

Só metadados que o servidor já devolve (nomes de grupo e guild, horários, limites). Nenhum texto de mensagem passa por aqui.
"""
LIMITES = {'comandos': 3, 'alertas': 3, 'rotinas': 5}


def _lista(valor):
    return [x for x in valor if isinstance(x, dict)] if isinstance(valor, list) else []


def _texto(valor, limite=80):
    return str(valor)[:limite] if isinstance(valor, (str, int, float)) and not isinstance(valor, bool) else ''


def _numero(valor):
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) else None


def _origem(item):
    return 'grupo' if item.get('source') == 'group' else 'app'


def _comandos(item):
    desligados = [_texto(c, 20) for c in item.get('disabled', [])] if isinstance(item.get('disabled'), list) else []
    return {'estado': _texto(item.get('state'), 20), 'pausado': item.get('paused') is True, 'mundo': _texto(item.get('world'), 40), 'intervalo': _numero(item.get('cooldown')),
            'desligados': desligados, 'configPeloGrupo': item.get('groupConfig') is not False, 'ultimoUso': _numero(item.get('lastUse')),
            'ajustadoPeloGrupo': bool(item.get('changedByGroup'))}


def _alerta(item):
    return {'estado': _texto(item.get('state'), 20), 'guild': _texto(item.get('guild'), 60), 'level': _numero(item.get('milestone')), 'mortes': item.get('deaths') is True, 'ups': item.get('ups') is True,
            'limiteHora': _numero(item.get('hourlyCap')), 'limiteMinuto': _numero(item.get('perMinute')), 'origem': _origem(item), 'ultimoEnvio': _numero(item.get('lastSent')),
            'ajustadoPeloGrupo': bool(item.get('changedByGroup'))}


def _bomdia(item, ultimo):
    config = item.get('config') if isinstance(item.get('config'), dict) else {}
    return {'estado': _texto(item.get('state'), 20), 'envio': _texto(config.get('sendAt'), 5), 'fuso': _texto(config.get('timezone'), 40), 'mundo': _texto(config.get('mundo'), 40),
            'origem': _origem(item), 'ultimoEnvio': ultimo, 'ajustadoPeloGrupo': bool(item.get('changedByGroup'))}


def montar(conexao, subscriptions, watches, botgroups, runs):
    """Linhas do painel (uma por grupo de destino) e o resumo de uso dos limites."""
    ultimo_por_rotina = {}
    for r in _lista(runs):
        if r.get('state') in ('accepted', 'simulated') and isinstance(r.get('reference'), str):
            ultimo_por_rotina[r.get('subscription')] = max(ultimo_por_rotina.get(r.get('subscription'), ''), r['reference'])
    grupos = {}

    def linha(item):
        destino = _texto(item.get('destination'), 64)
        return grupos.setdefault(destino, {'destino': destino, 'grupo': '', 'comandos': None, 'alerta': None, 'bomdia': None})

    for tipo, itens in (('comandos', _lista(botgroups)), ('alerta', _lista(watches)), ('bomdia', _lista(subscriptions))):
        for item in itens:
            if item.get('state') == 'revoked':
                continue
            row = linha(item)
            row['grupo'] = row['grupo'] or _texto(item.get('destinationLabel'), 80)
            row[tipo] = _comandos(item) if tipo == 'comandos' else _alerta(item) if tipo == 'alerta' else _bomdia(item, ultimo_por_rotina.get(item.get('id')))
            if tipo == 'comandos':
                row['comandos']['origem'] = 'app'
    lista = sorted(grupos.values(), key=lambda g: (g['grupo'] or '~').casefold())
    for row in lista:
        row['grupo'] = row['grupo'] or 'Grupo sem nome'
    ativos = sum(1 for g in lista for k in ('comandos', 'alerta', 'bomdia') if g[k] and g[k]['estado'] == 'active' and not (k == 'comandos' and g[k]['pausado']))
    usados = {'comandos': sum(1 for g in lista if g['comandos']), 'alertas': sum(1 for g in lista if g['alerta']), 'rotinas': sum(1 for g in lista if g['bomdia'])}
    estado = conexao if isinstance(conexao, dict) else {}
    return {'conexao': {'estado': _texto(estado.get('state'), 20) or 'desconectado', 'simulado': estado.get('simulated') is True},
            'resumo': {'grupos': len(lista), 'botsAtivos': ativos, **{k: [usados[k], LIMITES[k]] for k in usados}}, 'grupos': lista}
