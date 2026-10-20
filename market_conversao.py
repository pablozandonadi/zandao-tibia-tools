"""Conversão estimada local; não altera cotações ou histórico do Market."""
from decimal import Decimal, ROUND_HALF_UP, localcontext
import json
import os
from pathlib import Path
import re
import threading

DEFAULTS = {'gold_por_tc': '46600', 'tc_pacote': '250', 'reais_pacote': '50'}
LOCK = threading.Lock()


def numero(value, nome, *, gold=False, zero=False):
    text = str(value).strip().lower() if type(value) in (str, int, float) else ''
    if not text or len(text) > 48:
        raise ValueError(f'Informe {nome}.')
    match = re.fullmatch(r'(\d+(?:[.,]\d+)*)(?:\s*(kk|k|gp|gold))?', text)
    if not match or (match[2] and not gold):
        raise ValueError(f'{nome}: use um número válido' + (' em GP, K ou KK.' if gold else '.'))
    digits, suffix = match.groups()
    if ',' in digits:
        if not re.fullmatch(r'(?:\d+|\d{1,3}(?:\.\d{3})+),\d+', digits):
            raise ValueError(f'{nome}: confira os separadores.')
        digits = digits.replace('.', '').replace(',', '.')
    elif '.' in digits and suffix not in ('k', 'kk') and re.fullmatch(r'\d{1,3}(?:\.\d{3})+', digits):
        digits = digits.replace('.', '')
    elif digits.count('.') > 1:
        raise ValueError(f'{nome}: confira os separadores.')
    result = Decimal(digits) * {'k': 1000, 'kk': 1000000, 'gp': 1, 'gold': 1, None: 1}[suffix]
    if not result.is_finite() or result < (0 if zero else Decimal('0.000001')) or result > 10**12:
        raise ValueError(f'{nome}: informe um valor {"entre zero" if zero else "maior que zero"} e até 1 trilhão.')
    if gold and result != result.to_integral_value():
        raise ValueError(f'{nome}: o valor deve resultar em GP inteiros.')
    return result


def validar(valores):
    if not isinstance(valores, dict) or set(valores) != set(DEFAULTS):
        raise ValueError('Informe os três valores de conversão.')
    return {key: format(numero(valores[key], nome, gold=key == 'gold_por_tc'), 'f')
            for key, nome in [('gold_por_tc', 'Gold por TC'), ('tc_pacote', 'TC no pacote'), ('reais_pacote', 'Preço do pacote')]}


def calcular(gold, valores):
    valores = validar(valores)
    with localcontext() as context:
        context.prec = 60
        tc = numero(gold, 'Gold obtido', gold=True, zero=True) / Decimal(valores['gold_por_tc'])
        reais = tc * Decimal(valores['reais_pacote']) / Decimal(valores['tc_pacote'])
        return {key: format(value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), 'f') for key, value in [('tc', tc), ('reais', reais)]}


def carregar(directory):
    path = Path(directory) / 'market-conversao-tc.json'
    with LOCK:
        if not path.exists():
            return {'valores': dict(DEFAULTS)}
        try:
            if path.stat().st_size > 4096:
                raise ValueError()
            return {'valores': validar(json.loads(path.read_text(encoding='utf-8')))}
        except (ValueError, OSError):
            return {'valores': dict(DEFAULTS), 'aviso': 'Não foi possível ler os valores salvos. Padrões carregados; o arquivo foi preservado.'}


def salvar(directory, valores):
    valores = validar(valores)
    path = Path(directory) / 'market-conversao-tc.json'
    with LOCK:
        temp = path.with_suffix('.tmp')
        try:
            temp.write_text(json.dumps(valores), encoding='utf-8')
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
    return {'valores': valores, 'message': 'Valores de conversão salvos neste computador.'}
