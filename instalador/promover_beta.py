"""Prepara a promoção exata de uma Beta em um checkout isolado do GitHub Actions."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BETA_RE = r'v\d+\.\d+\.\d+-beta\.\d+\.\d+'


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode:
        raise RuntimeError(f'Falha em {args[0]} (código {result.returncode}): {result.stderr.strip() or result.stdout.strip() or chr(32).join(args[1:])}')
    return result.stdout.strip()


def proxima_versao(text):
    match = re.search(r'^VERSAO_APP\s*=\s*"(\d+)\.(\d+)\.(\d+)"', text, re.M)
    if not match:
        raise ValueError('Versão estável inválida na main.')
    major, minor, patch = map(int, match.groups())
    return f'{major}.{minor}.{patch + 1}'


def preparar(tag, sha):
    if not re.fullmatch(BETA_RE, tag) or not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Tag ou commit da Beta inválido.')
    release = json.loads(run('gh', 'release', 'view', tag, '--json', 'isPrerelease,isDraft,assets,body'))
    if not release['isPrerelease'] or release['isDraft']:
        raise ValueError('A origem precisa ser uma Beta oficial publicada.')
    assets = {a['name'] for a in release['assets']}
    if 'ZandaoTibiaToolsBetaSetup.exe' not in assets:
        raise ValueError('A Beta não possui instalador publicado.')
    run('git', 'fetch', 'origin', 'refs/heads/main:refs/remotes/origin/main', 'refs/heads/develop:refs/remotes/origin/develop', '--tags')
    if run('git', 'rev-parse', tag + '^{commit}') != sha:
        raise ValueError('O commit solicitado não corresponde à Beta aprovada.')
    base = run('git', 'rev-parse', 'origin/main')
    main_source = run('git', 'show', 'origin/main:versao.py')
    version = proxima_versao(main_source)
    checkout = sha
    try:
        run('git', 'merge-base', '--is-ancestor', base, sha)
    except RuntimeError:
        # A publicação dos artefatos pode falhar depois do push. Retomar só se
        # main contém exatamente a mesma Beta mais versão/notas desta promoção.
        try:
            run('git', 'merge-base', '--is-ancestor', sha, base)
        except RuntimeError as error:
            raise ValueError('A versão estável foi publicada em uma linha diferente da Beta aprovada. Integre a main em develop, publique uma nova Beta e analise essa versão antes de promover.') from error
        current = re.search(r'^VERSAO_APP\s*=\s*"(\d+\.\d+\.\d+)"', main_source, re.M)
        if not current:
            raise ValueError('Versão inválida na main.')
        version = current.group(1)
        notes_path = f'docs/releases/v{version}.md'
        changed = set(run('git', 'diff', '--name-only', sha, base).splitlines())
        if changed != {'versao.py', notes_path}:
            raise ValueError('A main divergiu da Beta aprovada. Gere e analise uma nova Beta.')
        existing_notes = run('git', 'show', 'origin/main:' + notes_path)
        if f'Beta aprovada: {tag}.\nCódigo analisado: {sha}.' not in existing_notes:
            raise ValueError('A main contém outra promoção. Gere e analise uma nova Beta.')
        checkout = base
    run('git', 'checkout', '--detach', checkout)
    path = Path('versao.py')
    source = path.read_text(encoding='utf-8')
    source, count = re.subn(r'^VERSAO_APP\s*=\s*"[^"\r\n]+"', f'VERSAO_APP = "{version}"', source, count=1, flags=re.M)
    if count != 1:
        raise ValueError('Não foi possível atualizar a versão.')
    path.write_text(source, encoding='utf-8')
    notes = Path('docs/releases') / f'v{version}.md'
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text(f'# Zandao Tibia Tools {version}\n\nBeta aprovada: {tag}.\nCódigo analisado: {sha}.\n\nInstalador e versão portátil recompilados para o canal estável.\n\n' + (release.get('body') or ''), encoding='utf-8')
    with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as output:
        output.write(f'version={version}\nbase={base}\n')


def finalizar(base, version):
    if not re.fullmatch(r'[0-9a-f]{40}', base) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('Estado de publicação inválido.')
    run('git', 'fetch', 'origin', 'refs/heads/main:refs/remotes/origin/main')
    if run('git', 'rev-parse', 'origin/main') != base:
        raise ValueError('A main mudou durante a compilação. Gere e analise uma nova Beta.')
    run('git', 'config', 'user.name', 'github-actions[bot]')
    run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    run('git', 'add', 'versao.py', f'docs/releases/v{version}.md')
    if run('git', 'diff', '--cached', '--name-only'):
        run('git', 'commit', '-m', f'Publicar Beta aprovada como v{version}')
    run('git', 'push', 'origin', 'HEAD:refs/heads/main')


if __name__ == '__main__':
    try:
        if sys.argv[1] == 'preparar':
            preparar(sys.argv[2], sys.argv[3])
        elif sys.argv[1] == 'finalizar':
            finalizar(sys.argv[2], sys.argv[3])
        else:
            raise ValueError('Operação inválida.')
    except Exception as error:
        print(error, file=sys.stderr)
        sys.exit(1)
