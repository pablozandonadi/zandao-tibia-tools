"""Updates from official GitHub assets; never execute unverified bytes."""
import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import urllib.parse
import urllib.request
from versao import REPO_GITHUB, VERSAO_APP, CANAL_APP, NOME_INSTALADOR
from assinatura import verificar_assinatura
HEADERS = {"User-Agent": "TibiaTudo", "Accept": "application/vnd.github+json"}
MAX_INSTALLER_BYTES = 256 * 1024 * 1024
_DOWNLOAD_LOCK = threading.Lock()

def versao_para_tupla(versao):
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+)(?:\.(\d+))?)?", versao.strip(), re.I)
    if not m:
        raise ValueError("Versão inválida")
    major, minor, patch, build, attempt = m.groups()
    return (int(major), int(minor), int(patch), build is None, int(build or 0), int(attempt or 0))

def url_oficial(url, tag=None):
    try:
        u = urllib.parse.urlsplit(url)
        prefix = f"/{REPO_GITHUB}/releases/download/"
        if u.scheme != 'https' or u.netloc != 'github.com' or u.query or u.fragment:
            return False
        if not u.path.startswith(prefix):
            return False
        version, name = u.path[len(prefix):].split('/')
        if tag is not None and version != tag:
            return False
        return bool(re.fullmatch(r'v?\d+\.\d+\.\d+(?:-beta\.\d+\.\d+)?', version)) and name == NOME_INSTALADOR
    except (ValueError, TypeError, AttributeError):
        return False

def verificar_atualizacao():
    try:
        endpoint = "releases?per_page=100" if CANAL_APP == "beta" else "releases/latest"
        req = urllib.request.Request(f"https://api.github.com/repos/{REPO_GITHUB}/{endpoint}", headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            dados = json.load(response)
        releases = dados if isinstance(dados, list) else [dados]
        candidates = []
        for release in releases:
            if release.get('draft') or bool(release.get('prerelease')) != (CANAL_APP == 'beta'):
                continue
            tag = release.get('tag_name') or ''
            if ('-beta.' in tag) != (CANAL_APP == 'beta'):
                continue
            try:
                order = versao_para_tupla(tag)
            except ValueError:
                continue
            asset = next((x for x in release.get('assets', []) if x.get('name') == NOME_INSTALADOR), None)
            if not asset or not url_oficial(asset.get('browser_download_url'), tag):
                continue
            if order > versao_para_tupla(VERSAO_APP):
                candidates.append((order, release, asset))
        if not candidates:
            return None
        _, release, asset = max(candidates, key=lambda x: x[0])
        digest = asset.get('digest') or ''
        size = asset.get('size')
        verified = bool(re.fullmatch(r'sha256:[0-9a-fA-F]{64}', digest)) and type(size) is int and 0 < size <= MAX_INSTALLER_BYTES
        return {'versao': release['tag_name'], 'url_instalador': asset['browser_download_url'],
                'notas': release.get('body') or '', 'url_release': release.get('html_url') or '',
                'sha256': digest[7:].lower() if verified else None, 'tamanho': size if verified else None,
                'integridade_disponivel': verified}
    except Exception:
        return None

def validar_instalador(path, sha256, tamanho, *, verificar_publicador=True):
    if not re.fullmatch(r'[0-9a-fA-F]{64}', sha256 or '') or type(tamanho) is not int or not 0 < tamanho <= MAX_INSTALLER_BYTES:
        raise ValueError('A release não possui hash e tamanho válidos. Abra a página oficial da versão.')
    if os.path.getsize(path) != tamanho:
        raise ValueError('O tamanho do instalador não corresponde à release.')
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        if stream.read(2) != b'MZ':
            raise ValueError('O arquivo recebido não é um executável Windows.')
        stream.seek(0)
        for block in iter(lambda: stream.read(262144), b''):
            h.update(block)
    if h.hexdigest().lower() != sha256.lower():
        raise ValueError('O instalador foi alterado ou está incompleto (SHA-256 diferente).')
    if verificar_publicador:
        verificar_assinatura(path)

def baixar_instalador(url, callback_progresso=None, *, sha256=None, tamanho=None):
    """Unique private download; no usable EXE is left on any verification failure."""
    if not url_oficial(url):
        raise ValueError('Endereço de atualização não autorizado.')
    if not re.fullmatch(r'[0-9a-fA-F]{64}', sha256 or '') or type(tamanho) is not int or not 0 < tamanho <= MAX_INSTALLER_BYTES:
        raise ValueError('Atualização bloqueada: faltam hash e tamanho verificáveis na release.')
    if not _DOWNLOAD_LOCK.acquire(blocking=False):
        raise RuntimeError('Já existe uma atualização em download.')
    directory = None
    try:
        directory = tempfile.mkdtemp(prefix='tibia-tudo-update-')
        partial = os.path.join(directory, NOME_INSTALADOR + '.part')
        final = os.path.join(directory, NOME_INSTALADOR)
        req = urllib.request.Request(url, headers={'User-Agent': 'TibiaTudo'})
        with urllib.request.urlopen(req, timeout=30) as response, open(partial, 'xb') as stream:
            final_url = response.geturl() if hasattr(response, 'geturl') else url
            parsed = urllib.parse.urlsplit(final_url)
            if parsed.scheme != 'https' or parsed.hostname not in ('github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'):
                raise ValueError('O download foi redirecionado para um endereço não autorizado.')
            declared = response.headers.get('Content-Length') if hasattr(response, 'headers') else None
            if declared and int(declared) != tamanho:
                raise ValueError('O servidor informou um tamanho diferente da release.')
            received = 0
            while True:
                chunk = response.read(262144)
                if not chunk:
                    break
                received += len(chunk)
                if received > tamanho:
                    raise ValueError('O download excedeu o tamanho permitido.')
                stream.write(chunk)
                if callback_progresso:
                    callback_progresso(min(99, received * 100 // tamanho))
            stream.flush()
            os.fsync(stream.fileno())
        validar_instalador(partial, sha256, tamanho, verificar_publicador=False)
        os.replace(partial, final)
        verificar_assinatura(final)
        if callback_progresso:
            callback_progresso(100)
        return final
    except Exception:
        if directory:
            shutil.rmtree(directory, ignore_errors=True)
        raise
    finally:
        _DOWNLOAD_LOCK.release()
