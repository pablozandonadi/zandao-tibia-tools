"""Baixa os GIFs de bosses que faltam em web/assets/creatures (TibiaWiki BR, depois EN).

Uso: python baixar_imagens_bosses.py [--dry-run] [--relatorio caminho.json]
Idempotente: nunca sobrescreve arquivos existentes; só biblioteca padrão.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import boss_catalog

RAIZ = Path(__file__).resolve().parent
DESTINO = RAIZ / 'web' / 'assets' / 'creatures'
APIS = ('https://www.tibiawiki.com.br/api.php', 'https://tibia.fandom.com/api.php')
HEADERS = {'User-Agent': 'TibiaTudo-bossimages/1.0 (app de Tibia; contato via GitHub pablozandonadi)'}
MIN_BYTES, MAX_BYTES = 200, 300 * 1024


def nome_arquivo(name):
    """Mesma regra de bossImage em web/assistente.js."""
    return re.sub(r'[^a-z0-9]+', '_', name.split(' (')[0].lower()).strip('_') + '.gif'


def gif_valido(data):
    return data.startswith(b'GIF8') and MIN_BYTES <= len(data) <= MAX_BYTES


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=30) as r:
        return r.status, r.read(MAX_BYTES + 1)


def resolver_urls(api, titulos):
    """titulo (sem 'File:') -> URL real do arquivo, em lotes de 50."""
    urls = {}
    for i in range(0, len(titulos), 50):
        lote = titulos[i:i + 50]
        q = urllib.parse.urlencode(dict(action='query', prop='imageinfo', iiprop='url', format='json', redirects=1,
                                        titles='|'.join('File:' + t + '.gif' for t in lote)))
        with urllib.request.urlopen(urllib.request.Request(api + '?' + q, headers=HEADERS), timeout=30) as r:
            dados = json.load(r)
        ida = {}  # titulo normalizado/redirecionado -> titulo pedido
        for lista in (dados['query'].get('normalized', []), dados['query'].get('redirects', [])):
            for m in lista:
                ida[m['to']] = ida.get(m['from'], m['from'])
        for p in dados['query']['pages'].values():
            info = p.get('imageinfo')
            if info:
                # volta ao titulo pedido ("File:X.gif"); a wiki devolve o namespace local ("Arquivo:")
                urls[re.sub(r'^[^:]+:', '', ida.get(p['title'], p['title']))[:-4]] = info[0]['url']
        time.sleep(1.1)
    return urls


def faltantes():
    """arquivo -> nome da wiki (sem sufixo) para cada boss sem imagem."""
    alvo = {}
    for entry in boss_catalog.BOSSES:
        arq = nome_arquivo(entry[0])
        if not (DESTINO / arq).exists():
            alvo.setdefault(arq, entry[0].split(' (')[0].strip())
    return alvo


def executar(dry_run=False):
    alvo = faltantes()
    rel = dict(baixados=[], nao_encontrados=[], invalidos=[], total_faltante=len(alvo))
    if dry_run:
        rel['nao_encontrados'] = sorted(alvo)
        return rel
    pendentes = dict(alvo)
    for api in APIS:
        if not pendentes:
            break
        urls = resolver_urls(api, sorted(set(pendentes.values())))
        for arq, titulo in list(pendentes.items()):
            url = urls.get(titulo.replace('_', ' '))
            if not url:
                continue
            try:
                status, data = _get(url)
            except OSError as e:
                data, status = b'', getattr(e, 'code', 0)
            time.sleep(0.4)
            if status == 200 and gif_valido(data):
                destino = DESTINO / arq
                if not destino.exists():
                    destino.write_bytes(data)
                    rel['baixados'].append(dict(arquivo=arq, titulo=titulo, url=url))
                del pendentes[arq]
            else:
                rel['invalidos'].append(dict(arquivo=arq, url=url, status=status, bytes=len(data)))
    rel['nao_encontrados'] = sorted(pendentes)
    return rel


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--relatorio')
    args = ap.parse_args()
    resultado = executar(args.dry_run)
    texto = json.dumps(resultado, ensure_ascii=False, indent=1)
    if args.relatorio:
        Path(args.relatorio).write_text(texto, encoding='utf-8')
    print(f"faltavam {resultado['total_faltante']}, baixados {len(resultado['baixados'])}, "
          f"sem imagem {len(resultado['nao_encontrados'])}, invalidos {len(resultado['invalidos'])}")
    sys.exit(0)
