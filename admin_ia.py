"""Cliente do painel de administração dos códigos da IA online (só stdlib)."""
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

import voz_credenciais
from voice.remote_ai_client import ENDPOINT, NoRedirect

SENHA = re.compile(r'[A-Za-z0-9_-]{43}')
_ARQUIVO = 'admin-online.dpapi'
_OPENER = urllib.request.build_opener(NoRedirect())
_MENSAGENS = {401: 'Senha de administrador recusada.',
    409: 'Esta pessoa já tem um código ativo. Revogue antes de gerar outro.',
    429: 'Muitas tentativas. Aguarde um minuto.', 503: 'Administração indisponível no servidor.'}


class AdminIAError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def salvar_senha(pasta, senha):
    if not isinstance(senha, str) or not SENHA.fullmatch(senha):
        raise AdminIAError('Senha de administrador inválida.')
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / _ARQUIVO
    temporario = pasta / (_ARQUIVO + '.tmp')
    try:
        temporario.write_bytes(voz_credenciais._proteger(senha))
        temporario.replace(destino)
    except OSError:
        raise AdminIAError('Não foi possível salvar a senha.') from None
    finally:
        temporario.unlink(missing_ok=True)


def carregar_senha(pasta):
    try:
        dados = (Path(pasta) / _ARQUIVO).read_bytes()
        if not 1 <= len(dados) <= 16384:
            return None
        senha = voz_credenciais._desproteger(dados)
    except (OSError, ValueError, AttributeError, TypeError, UnicodeError):
        return None
    return senha if isinstance(senha, str) and SENHA.fullmatch(senha) else None


def limpar_senha(pasta):
    for nome in (_ARQUIVO, _ARQUIVO + '.tmp'):
        (Path(pasta) / nome).unlink(missing_ok=True)


def _chamar(pasta, metodo, caminho, corpo=None):
    senha = carregar_senha(pasta)
    if not senha:
        raise AdminIAError('Informe a senha de administrador.')
    dados = json.dumps(corpo).encode('utf-8') if corpo is not None else None
    cabecalhos = {'Authorization': 'Bearer ' + senha}
    if dados is not None:
        cabecalhos['Content-Type'] = 'application/json'
    pedido = urllib.request.Request(ENDPOINT + caminho, data=dados, method=metodo, headers=cabecalhos)
    try:
        with _OPENER.open(pedido, timeout=15) as resposta:
            bruto = resposta.read(65537)
    except urllib.error.HTTPError as erro:
        raise AdminIAError(_MENSAGENS.get(erro.code, 'Não foi possível concluir. Tente novamente.'), status=erro.code) from None
    except (urllib.error.URLError, OSError):
        raise AdminIAError('Sem conexão com o servidor.') from None
    try:
        resultado = json.loads(bruto) if len(bruto) <= 65536 else None
    except ValueError:
        resultado = None
    if not isinstance(resultado, dict):
        raise AdminIAError('Não foi possível concluir. Tente novamente.')
    return resultado


def _corpo(subject, mode, quota, expires, **extra):
    corpo = {'subject': subject, 'mode': mode, **extra}
    if quota is not None:
        corpo['quota'] = quota
    if expires is not None:
        corpo['expires'] = expires
    return corpo


def listar(pasta):
    return _chamar(pasta, 'GET', '/admin/tokens')


def gerar(pasta, subject, mode, quota=None, expires=None):
    return _chamar(pasta, 'POST', '/admin/tokens', _corpo(subject, mode, quota, expires))


def limite(pasta, subject, mode, quota=None, expires=None, reset_used=False):
    extra = {'reset_used': True} if reset_used else {}
    return _chamar(pasta, 'POST', '/admin/tokens/limit', _corpo(subject, mode, quota, expires, **extra))


def revogar(pasta, subject):
    return _chamar(pasta, 'POST', '/admin/tokens/revoke', {'subject': subject})
