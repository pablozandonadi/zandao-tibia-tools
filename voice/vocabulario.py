"""Vocabulário de nomes em memória; não armazena falas nem áudio."""
import base64
import json
import unicodedata

TERMOS_FIXOS = ('Tibia Tudo', 'stamina', 'shared', 'Bosstiary', 'boss', 'Market',
                'Tibia Coin', 'Gold Token', 'Silver Token', 'timer')


def montar(com_kills, recentes, limite=40):
    termos, vistos = [], set()
    limite = max(0, min(40, limite))
    for nome in (*recentes, *com_kills, *TERMOS_FIXOS):
        if not isinstance(nome, str):
            continue
        nome = unicodedata.normalize('NFC', nome).strip()
        if not 1 <= len(nome) <= 40 or not all(unicodedata.category(c)[0] in 'LN' or c in " '-." for c in nome):
            continue
        if nome.casefold() not in vistos and len(termos) < limite:
            termos.append(nome)
            vistos.add(nome.casefold())
    return termos


def cabecalho(termos):
    return base64.urlsafe_b64encode(json.dumps(termos, ensure_ascii=False).encode('utf-8')).decode('ascii').rstrip('=')
