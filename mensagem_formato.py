"""Pedaços de formato comuns às mensagens do dia (manual e automática): data por extenso, frase e notícias."""
from datetime import date

DIAS = ('segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo')
MESES = ('janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro')
EMOJI_CATEGORIA = {'development': '🔥', 'community': '🗡️', 'support': '🛠️', 'technical': '⚙️'}


def data_hora(dia, hora=None):
    """'quinta-feira, 22 de outubro de 2026 às 08:17' (sem a hora se `hora` for None)."""
    texto = f'{DIAS[dia.weekday()]}, {dia.day} de {MESES[dia.month - 1]} de {dia.year}'
    return texto + (f' às {hora:%H:%M}' if hora else '')


def frase(texto):
    return f'💬 *Mensagem do dia:*\n"{texto}"'


def dia_mes(iso):
    try:
        return date.fromisoformat(str(iso)[:10]).strftime('%d/%m')
    except ValueError:
        return '❓'


def _resumo(texto, limite=80):
    """Primeira frase do aviso; se ainda for longa, corta numa palavra inteira."""
    frase_ = ' '.join(str(texto).split()).split('. ')[0].rstrip('.')
    return frase_ if len(frase_) <= limite else frase_[:limite].rsplit(' ', 1)[0] + '…'


def noticias(artigos, avisos=(), limite=3):
    """Bloco "O que rolou em Tibia". artigos = [{'titulo','data','categoria'}], avisos = [{'texto','data'}]; None se não houver nada."""
    linhas = [f"• {EMOJI_CATEGORIA.get(a.get('categoria'), '📰')} *{a['titulo']}* ({dia_mes(a.get('data'))})" for a in list(artigos)[:limite]]
    curtos = [f"{dia_mes(a.get('data'))}: {_resumo(a['texto'])}" for a in list(avisos)[:limite] if a.get('texto')]
    if curtos:
        linhas.append('⚡ ' + ' • '.join(curtos))
    return '📰 *O que rolou em Tibia*\n' + '\n'.join(linhas) if linhas else None
