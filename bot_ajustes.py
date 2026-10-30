"""Ajustes dos comandos do assistente feitos pelo administrador (ligar/desligar e texto da resposta).

Os ajustes vivem no servidor e valem para todos. A consulta nunca atrasa um comando: devolve o que já está em cache e, se estiver velho,
atualiza em segundo plano. Sem servidor (ou sem `iniciar`), tudo segue o padrão do app."""
import threading
import time

TTL = 300
MAX_TEXTO = 1500
CHAVES = ('bomdia', 'kill', 'boss', 'online', 'char', 'death', 'guild', 'exp', 'help', 'duelo', 'evolucao', 'precocoin', 'pt', 'xptop')
_lock = threading.Lock()
_buscador = None
_dados = {}
_em = 0.0
_ocupado = False


def iniciar(buscador):
    """buscador: função sem argumentos que devolve {comando: {'enabled': bool, 'text': str}} (ou levanta erro)."""
    global _buscador, _dados, _em
    with _lock:
        _buscador, _dados, _em = buscador, {}, 0.0


def _limpar(bruto):
    if not isinstance(bruto, dict):
        return {}
    saida = {}
    for chave, valor in bruto.items():
        if chave in CHAVES and isinstance(valor, dict) and isinstance(valor.get('enabled'), bool) and isinstance(valor.get('text', ''), str):
            saida[chave] = {'enabled': valor['enabled'], 'text': valor.get('text', '')[:MAX_TEXTO]}
    return saida


def _atualizar():
    global _dados, _em, _ocupado
    try:
        novos = _limpar(_buscador())
    except Exception:
        novos = None  # servidor fora do ar: mantém o último conhecido
    with _lock:
        if novos is not None:
            _dados = novos
        _em = time.monotonic()
        _ocupado = False


def ajuste(chave):
    """{'enabled': bool, 'text': str} do comando, ou {} quando segue o padrão."""
    global _ocupado
    with _lock:
        if _buscador is not None and not _ocupado and (_em == 0.0 or time.monotonic() - _em > TTL):
            _ocupado = True
            threading.Thread(target=_atualizar, daemon=True).start()
        return dict(_dados.get(chave, {}))

