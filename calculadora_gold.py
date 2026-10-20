"""Conta local gold -> reais pelo preço do Tibia Coin. Caller: chat.py. Dados: conversao-tc.json {pacote_tc:int, reais_min:str, reais_max:str}."""
import json
import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ARQUIVO = 'conversao-tc.json'
PADRAO = {'pacote_tc': 250, 'reais_min': Decimal('49'), 'reais_max': Decimal('52')}
MAX_TEXTO = 300
VALOR = re.compile(r'\d[\d.,]*\s*(?:kk|gp|gold)\b')
PACOTE = re.compile(r'^pacote de (\d+) tc custa (\d+(?:[.,]\d+)?)(?: a (\d+(?:[.,]\d+)?))? reais?$')
MILHAR = re.compile(r'^\d{1,3}([.,]\d{3})+$')
VARIAVEIS = {'variaveis do tc', 'variaveis tc', 'conversao tc', 'variaveis do tibia coin'}
NAO_ENTENDI = 'Não entendi. Exemplo: "pacote de 250 tc custa 50 a 55 reais".'


def _norm(texto):
    return unicodedata.normalize('NFKD', texto.lower()).encode('ascii', 'ignore').decode().strip(' ?!.')


def _numero(texto):
    texto = texto.strip(' .,')
    texto = re.sub(r'[.,]', '', texto) if MILHAR.match(texto) else texto.replace(',', '.')
    return Decimal(texto)


def _fmt(valor, casas=2, fixo=True):
    valor = valor.quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)
    texto = f'{valor:,.{casas}f}'.replace(',', '#').replace('.', ',').replace('#', '.')
    if not fixo and ',' in texto:
        texto = texto.rstrip('0').rstrip(',')
    return texto


def _reais(valor):
    return 'R$ ' + _fmt(valor)


def _faixa(minimo, maximo):
    return _reais(minimo) if minimo == maximo else f'{_reais(minimo)} a {_reais(maximo)}'


def _carregar(pasta):
    try:
        bruto = json.loads((Path(pasta) / ARQUIVO).read_text(encoding='utf-8'))
        pacote, minimo, maximo = bruto['pacote_tc'], Decimal(bruto['reais_min']), Decimal(bruto['reais_max'])
        if type(pacote) is int and 0 < pacote <= 10000 and 0 < minimo <= maximo <= 100000:
            return {'pacote_tc': pacote, 'reais_min': minimo, 'reais_max': maximo}
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation):
        pass
    return dict(PADRAO)


def _salvar(pasta, pacote, minimo, maximo):
    destino = Path(pasta) / ARQUIVO
    tmp = destino.with_suffix('.tmp')
    tmp.write_text(json.dumps({'pacote_tc': pacote, 'reais_min': str(minimo), 'reais_max': str(maximo)}), encoding='utf-8')
    os.replace(tmp, destino)


def _pacote_txt(v):
    return f"pacote de {v['pacote_tc']} TC por {_faixa(v['reais_min'], v['reais_max'])}"


def _definir(pasta, m):
    try:
        pacote, minimo = int(m.group(1)), _numero(m.group(2))
        maximo = _numero(m.group(3)) if m.group(3) else minimo
        if not (0 < pacote <= 10000 and 0 < minimo <= maximo <= 100000):
            return NAO_ENTENDI
        _salvar(pasta, pacote, minimo, maximo)
    except OSError:
        return 'Não consegui salvar. Nenhuma alteração foi confirmada.'
    return 'Salvo: ' + _pacote_txt({'pacote_tc': pacote, 'reais_min': minimo, 'reais_max': maximo}) + '.'


def _gold(achado):
    unidade = re.search(r'(kk|gp|gold)$', achado.strip()).group(1)
    return _numero(achado.strip()[:-len(unidade)]) * (1_000_000 if unidade == 'kk' else 1)


def _gold_txt(gold):
    return _fmt(gold / 1_000_000, 2, False) + 'kk' if gold >= 1_000_000 else _fmt(gold, 0) + ' gold'


def responder(texto, pasta, preco_tc):
    """Texto da conta, ou None se não for uma conta. preco_tc() -> (Decimal gold por TC, origem); só é chamado numa conta de verdade."""
    if not isinstance(texto, str) or len(texto) > MAX_TEXTO:
        return None
    n = _norm(texto)
    v = _carregar(pasta)
    if n in VARIAVEIS:
        preco, origem = preco_tc()
        return f"Variáveis do TC: {_pacote_txt(v)}. Preço do TC: {_fmt(preco / 1000, 1, False)}k ({origem}). Para mudar: \"pacote de 250 tc custa 50 a 55 reais\"."
    if n.startswith('pacote de ') and ' tc' in n:
        m = PACOTE.match(n)
        return _definir(pasta, m) if m else NAO_ENTENDI
    achados = VALOR.findall(n)
    if len(achados) != 1 or not re.search(r'\breais\b|r\$', n):
        return None
    try:
        gold = _gold(achados[0])
    except InvalidOperation:
        return None
    if gold <= 0:
        return None
    preco, origem = preco_tc()
    tc = gold / preco
    por_tc = Decimal(v['pacote_tc'])
    minimo, maximo = tc * v['reais_min'] / por_tc, tc * v['reais_max'] / por_tc
    return (f"{_gold_txt(gold)} ≈ {_fmt(tc, 2, False)} TC (TC a {_fmt(preco / 1000, 1, False)}k, {origem}).\n"
            f"Em reais: {_faixa(minimo, maximo)} ({_pacote_txt(v)}).")
