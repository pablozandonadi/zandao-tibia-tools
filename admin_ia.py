"""Cliente do painel de administração dos códigos da IA online (só stdlib)."""
import contextlib
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
_MENSAGENS = {400: 'Dados inválidos. No nome use só letras sem acento, números, _ ou -; a validade não pode estar no passado.',
    401: 'Senha de administrador recusada.', 404: 'Esta pessoa não tem código ativo.',
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
        falhou = False
    except (OSError, ValueError, AttributeError):
        falhou = True
    finally:
        with contextlib.suppress(OSError):
            temporario.unlink(missing_ok=True)
    if falhou:  # fora do except: __context__ não guarda o erro original
        raise AdminIAError('Não foi possível salvar a senha.')


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
    cabecalhos = {'User-Agent': 'TibiaTudo/1.0', 'Authorization': 'Bearer ' + senha}
    if dados is not None:
        cabecalhos['Content-Type'] = 'application/json'
    pedido = urllib.request.Request(ENDPOINT + caminho, data=dados, method=metodo, headers=cabecalhos)
    generico = 'Não foi possível concluir. Tente novamente.'
    erro = status = resultado = None
    try:
        with _OPENER.open(pedido, timeout=15) as resposta:
            bruto = resposta.read(65537)
    except urllib.error.HTTPError as e:
        status = e.code
        erro = _MENSAGENS.get(status, generico)
        e.close()
    except (urllib.error.URLError, OSError):
        erro = 'Sem conexão com o servidor.'
    else:
        with contextlib.suppress(ValueError):
            resultado = json.loads(bruto) if len(bruto) <= 65536 else None
    # os raises ficam fora dos except: __context__ não guarda o erro original
    if erro:
        raise AdminIAError(erro, status=status)
    if not isinstance(resultado, dict):
        raise AdminIAError(generico)
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
    # Sempre manda expires: omitido, o servidor manteria a validade; None = o admin limpou o campo.
    return _chamar(pasta, 'POST', '/admin/tokens/limit', {**_corpo(subject, mode, quota, None, **extra), 'expires': expires})


def revogar(pasta, subject):
    return _chamar(pasta, 'POST', '/admin/tokens/revoke', {'subject': subject})
