"""Publicação aprovada pelo proprietário da Beta, com credenciais locais do gh."""
import json
import os
import re
import shutil
import subprocess
import threading

from versao import CANAL_APP, VERSAO_APP, BUILD_SOURCE_SHA, REPO_GITHUB

WORKFLOW = 'publish-beta.yml'
BETA_RE = r'v\d+\.\d+\.\d+-beta\.\d+\.\d+'
_lock = threading.Lock()
_run_ignorado = 0
_pendente = False


def _gh(*args):
    executable = shutil.which('gh')
    if not executable:
        for root in (os.environ.get('ProgramFiles', ''), r'C:\Program Files'):
            candidate = os.path.join(root, 'GitHub CLI', 'gh.exe')
            if os.path.isfile(candidate):
                executable = candidate
                break
    if not executable:
        raise RuntimeError('Instale o GitHub CLI e entre com gh auth login para publicar.')
    result = subprocess.run([executable, *args], capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=30,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError('O GitHub recusou a operação. Confira a conexão, o login do GitHub CLI e a permissão de escrita/workflow no repositório.')
    return result.stdout


def _identidade():
    tag = 'v' + VERSAO_APP
    if CANAL_APP != 'beta':
        raise RuntimeError('A publicação está disponível apenas na Beta.')
    if not re.fullmatch(BETA_RE, tag) or not re.fullmatch(r'[0-9a-f]{40}', BUILD_SOURCE_SHA):
        raise RuntimeError('Esta Beta local não tem origem registrada. Instale a Beta oficial publicada no GitHub.')
    return tag, BUILD_SOURCE_SHA


def informacoes():
    if CANAL_APP != 'beta':
        return {'beta': False}
    try:
        tag, sha = _identidade()
        return {'beta': True, 'disponivel': True, 'versao': VERSAO_APP, 'source_sha': sha,
                'mensagem': 'Após verificar esta Beta, publique-a na versão original. O pipeline gera o instalador e o portátil atualizados.'}
    except RuntimeError as e:
        return {'beta': True, 'disponivel': False, 'mensagem': str(e)}


def _execucao(tag):
    runs = json.loads(_gh('run', 'list', '--repo', REPO_GITHUB, '--workflow', WORKFLOW,
                         '--event', 'workflow_dispatch', '--limit', '100',
                         '--json', 'displayTitle,status,conclusion,url,databaseId'))
    return next((r for r in runs if r['displayTitle'] == 'Publicar original ' + tag and r['databaseId'] > _run_ignorado), None)


def publicar():
    with _lock:
        return _publicar()


def _publicar():
    global _run_ignorado, _pendente
    try:
        tag, sha = _identidade()
        if _pendente:
            current = _execucao(tag)
            if not current or current['status'] != 'completed':
                return {'ok': True, 'mensagem': 'Publicação já solicitada. Aguardando o pipeline.'}
            _pendente = False
        repo = json.loads(_gh('api', 'repos/' + REPO_GITHUB))
        if not repo.get('permissions', {}).get('push'):
            raise RuntimeError('Sua conta do GitHub não tem permissão para publicar neste repositório.')
        release = json.loads(_gh('release', 'view', tag, '--repo', REPO_GITHUB,
                                 '--json', 'isPrerelease,isDraft,assets'))
        names = {a['name'] for a in release.get('assets', [])}
        if not release['isPrerelease'] or release['isDraft'] or 'ZandaoTibiaToolsBetaSetup.exe' not in names:
            raise RuntimeError('A Beta instalada não corresponde a uma publicação oficial concluída.')
        commit = json.loads(_gh('api', f'repos/{REPO_GITHUB}/commits/{tag}'))
        if commit['sha'] != sha:
            raise RuntimeError('A origem da Beta não corresponde à tag publicada. Reinstale a Beta oficial.')
        previous = _execucao(tag)
        if previous and (previous['status'] != 'completed' or previous['conclusion'] == 'success'):
            return {'ok': True, 'url': previous['url'], 'mensagem': 'Esta publicação já foi solicitada. Acompanhe o pipeline.'}
        _gh('workflow', 'run', WORKFLOW, '--repo', REPO_GITHUB, '--ref', tag,
            '--field', 'publicar_original=true', '--field', 'beta_tag=' + tag,
            '--field', 'source_sha=' + sha)
        _run_ignorado = previous['databaseId'] if previous else 0
        _pendente = True
        return {'ok': True, 'url': f'https://github.com/{REPO_GITHUB}/actions/workflows/{WORKFLOW}',
                'mensagem': 'Publicação solicitada. Aguardando testes, compilação e envio do instalador.'}
    except Exception as e:
        return {'ok': False, 'erro': str(e)}


def estado():
    global _pendente
    try:
        tag, _ = _identidade()
        run = _execucao(tag)
        if not run:
            return {'ok': True, 'status': 'aguardando', 'mensagem': 'Aguardando o GitHub iniciar a publicação.'}
        if run['status'] != 'completed':
            return {'ok': True, 'status': 'executando', 'url': run['url'], 'mensagem': 'Publicação em andamento: testes, instalador e versão portátil.'}
        _pendente = False
        if run['conclusion'] != 'success':
            return {'ok': True, 'status': 'falhou', 'url': run['url'], 'mensagem': 'A publicação não foi concluída. Veja o motivo no pipeline antes de tentar novamente.'}
        return {'ok': True, 'status': 'concluido', 'url': run['url'],
                'release_url': f'https://github.com/{REPO_GITHUB}/releases/latest',
                'mensagem': 'Versão original publicada com instalador e portátil. A instalação original já pode procurar atualização.'}
    except Exception as e:
        return {'ok': False, 'erro': str(e)}
