import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import publicacao_beta as p
from instalador.promover_beta import preparar, finalizar, proxima_versao
import instalador.promover_beta as pipeline

SHA = 'a' * 40
TAG = 'v1.0.19-beta.5.1'


class PublicacaoBetaTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(p, 'CANAL_APP', 'beta'), patch.object(p, 'VERSAO_APP', TAG[1:]), patch.object(p, 'BUILD_SOURCE_SHA', SHA), patch.object(p, '_pendente', False), patch.object(p, '_run_ignorado', 0)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def responses(self, *args):
        if args[:2] == ('api', 'repos/' + p.REPO_GITHUB):
            return json.dumps({'permissions': {'push': True}})
        if args[:2] == ('release', 'view'):
            return json.dumps({'isPrerelease': True, 'isDraft': False, 'assets': [{'name': 'ZandaoTibiaToolsBetaSetup.exe'}]})
        if args[0] == 'api' and '/commits/' in args[1]:
            return json.dumps({'sha': SHA})
        if args[:2] == ('run', 'list'):
            return '[]'
        return ''

    def test_estavel_nao_mostra_botao_e_nao_publica(self):
        with patch.object(p, 'CANAL_APP', 'stable'), patch.object(p, '_gh') as gh:
            self.assertFalse(p.informacoes()['beta'])
            self.assertFalse(p.publicar()['ok'])
            gh.assert_not_called()

    def test_beta_local_sem_origem_nao_publica(self):
        with patch.object(p, 'BUILD_SOURCE_SHA', ''), patch.object(p, '_gh') as gh:
            self.assertFalse(p.informacoes()['disponivel'])
            self.assertFalse(p.publicar()['ok'])
            gh.assert_not_called()

    def test_tag_invalida_nao_chega_ao_cli(self):
        with patch.object(p, 'VERSAO_APP', '1.0.19; something'), patch.object(p, '_gh') as gh:
            self.assertFalse(p.publicar()['ok'])
            gh.assert_not_called()

    def test_publica_tag_instalada_e_sha_exato(self):
        with patch.object(p, '_gh', side_effect=self.responses) as gh:
            self.assertTrue(p.publicar()['ok'])
            dispatch = [c.args for c in gh.call_args_list if c.args[:2] == ('workflow', 'run')]
            self.assertEqual(len(dispatch), 1)
            self.assertIn(TAG, dispatch[0])
            self.assertIn('source_sha=' + SHA, dispatch[0])
            self.assertIn('publicar_original=true', dispatch[0])
            self.assertNotIn('develop', dispatch[0])

    def test_sha_diferente_nao_dispara(self):
        def response(*args):
            if args[0] == 'api' and '/commits/' in args[1]:
                return json.dumps({'sha': 'b' * 40})
            return self.responses(*args)
        with patch.object(p, '_gh', side_effect=response) as gh:
            self.assertFalse(p.publicar()['ok'])
            self.assertFalse(any(c.args[:2] == ('workflow', 'run') for c in gh.call_args_list))

    def test_sem_permissao_nao_dispara(self):
        with patch.object(p, '_gh', return_value=json.dumps({'permissions': {'push': False}})) as gh:
            self.assertFalse(p.publicar()['ok'])
            self.assertEqual(gh.call_count, 1)

    def test_release_estavel_ou_rascunho_nao_dispara(self):
        for prerelease, draft in ((False, False), (True, True)):
            def response(*args):
                if args[:2] == ('release', 'view'):
                    return json.dumps({'isPrerelease': prerelease, 'isDraft': draft, 'assets': []})
                return self.responses(*args)
            with self.subTest(prerelease=prerelease, draft=draft), patch.object(p, '_gh', side_effect=response) as gh:
                self.assertFalse(p.publicar()['ok'])
                self.assertFalse(any(c.args[:2] == ('workflow', 'run') for c in gh.call_args_list))

    def test_nao_duplica_publicacao_em_andamento_ou_concluida(self):
        for status, conclusion in [('in_progress', None), ('completed', 'success')]:
            previous = {'status': status, 'conclusion': conclusion, 'url': 'https://github.com/run/1'}
            with patch.object(p, '_gh', side_effect=self.responses) as gh, patch.object(p, '_execucao', return_value=previous):
                self.assertTrue(p.publicar()['ok'])
                self.assertFalse(any(c.args[:2] == ('workflow', 'run') for c in gh.call_args_list))

    def test_falha_de_autenticacao_retorna_erro(self):
        with patch.object(p, '_gh', side_effect=RuntimeError('sem login')):
            self.assertEqual(p.publicar(), {'ok': False, 'erro': 'sem login'})

    def test_retentativa_ignora_execucao_anterior_falhada(self):
        previous = {'status': 'completed', 'conclusion': 'failure', 'url': 'https://github.com/run/1', 'databaseId': 10}
        with patch.object(p, '_gh', side_effect=self.responses), patch.object(p, '_execucao', return_value=previous):
            self.assertTrue(p.publicar()['ok'])
            self.assertEqual(p._run_ignorado, 10)
        with patch.object(p, '_gh', return_value=json.dumps([dict(previous, displayTitle='Publicar original ' + TAG)])):
            self.assertEqual(p.estado()['status'], 'aguardando')

    def test_solicitacao_pendente_nao_duplica_dispatch(self):
        with patch.object(p, '_gh', side_effect=self.responses) as gh:
            self.assertTrue(p.publicar()['ok'])
            self.assertTrue(p.publicar()['ok'])
            self.assertEqual(sum(c.args[:2] == ('workflow', 'run') for c in gh.call_args_list), 1)

    def test_estado_distingue_falha_execucao_e_conclusao(self):
        for status, conclusion, expected in [('in_progress', None, 'executando'), ('completed', 'failure', 'falhou'), ('completed', 'success', 'concluido')]:
            with patch.object(p, '_execucao', return_value={'status': status, 'conclusion': conclusion, 'url': 'https://github.com/run/1'}):
                self.assertEqual(p.estado()['status'], expected)


class PromocaoPipelineTests(unittest.TestCase):
    def test_incrementa_patch_sem_mudar_major_minor(self):
        self.assertEqual(proxima_versao('VERSAO_APP = "1.0.19"'), '1.0.20')
        with self.assertRaises(ValueError):
            proxima_versao('VERSAO_APP = "1.0.19-beta.1.1"')

    def test_entradas_invalidas_nao_executam_comandos(self):
        with patch('instalador.promover_beta.run') as run:
            with self.assertRaises(ValueError):
                preparar('main; comando', SHA)
            with self.assertRaises(ValueError):
                finalizar(SHA, 'v1.0.20')
            run.assert_not_called()

    def test_main_mudou_nao_faz_commit_nem_push(self):
        with patch('instalador.promover_beta.run', side_effect=['', 'b' * 40]) as run:
            with self.assertRaisesRegex(ValueError, 'main mudou'):
                finalizar(SHA, '1.0.20')
            self.assertFalse(any('push' in c.args or 'commit' in c.args for c in run.call_args_list))

    def test_main_divergente_explica_bloqueio_sem_alterar_checkout(self):
        release = json.dumps({'isPrerelease': True, 'isDraft': False, 'assets': [{'name': 'ZandaoTibiaToolsBetaSetup.exe'}]})
        responses = [release, '', SHA, 'b' * 40, 'VERSAO_APP = "1.0.22"', RuntimeError('ancestralidade'), RuntimeError('ancestralidade')]
        with patch('instalador.promover_beta.run', side_effect=responses) as run:
            with self.assertRaisesRegex(ValueError, 'Integre a main em develop'):
                preparar(TAG, SHA)
            self.assertFalse(any('checkout' in c.args or 'push' in c.args for c in run.call_args_list))

    def test_tag_sha_divergente_nao_altera_fonte(self):
        release = json.dumps({'isPrerelease': True, 'isDraft': False, 'assets': [{'name': 'ZandaoTibiaToolsBetaSetup.exe'}]})
        with patch('instalador.promover_beta.run', side_effect=[release, '', 'b' * 40]) as run:
            with self.assertRaisesRegex(ValueError, 'commit solicitado'):
                preparar(TAG, SHA)
            self.assertFalse(any('checkout' in c.args for c in run.call_args_list))


class PromocaoIntegracaoTests(unittest.TestCase):
    def test_promove_codigo_exato_e_permite_retomar_publicacao_de_pacotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, source, checkout = root / 'remote.git', root / 'source', root / 'checkout'
            def git(*args, cwd=None):
                return subprocess.run(['git', *map(str, args)], cwd=cwd, check=True,
                                      capture_output=True, text=True, encoding='utf-8').stdout.strip()
            git('init', '--bare', remote)
            git('init', '--initial-branch=main', source)
            git('config', 'user.name', 'Teste', cwd=source)
            git('config', 'user.email', 'teste@example.com', cwd=source)
            (source / 'versao.py').write_text('VERSAO_APP = "1.0.19"\n', encoding='utf-8')
            (source / 'feature.txt').write_text('stable', encoding='utf-8')
            git('add', '.', cwd=source)
            git('commit', '-m', 'base', cwd=source)
            git('remote', 'add', 'origin', remote, cwd=source)
            git('push', 'origin', 'main', cwd=source)
            git('checkout', '-b', 'develop', cwd=source)
            (source / 'feature.txt').write_text('beta aprovada', encoding='utf-8')
            git('commit', '-am', 'beta', cwd=source)
            sha = git('rev-parse', 'HEAD', cwd=source)
            git('tag', TAG, cwd=source)
            git('push', 'origin', 'develop', '--tags', cwd=source)
            git('clone', '--branch', 'develop', '--single-branch', remote, checkout)
            original_run = pipeline.run
            def runner(*args):
                if args[0] == 'gh':
                    return json.dumps({'isPrerelease': True, 'isDraft': False, 'body': 'Beta de teste', 'assets': [{'name': 'ZandaoTibiaToolsBetaSetup.exe'}]})
                return original_run(*args)
            original_cwd = os.getcwd()
            self.addCleanup(os.chdir, original_cwd)
            os.chdir(checkout)
            try:
                with patch.object(pipeline, 'run', side_effect=runner), patch.dict(os.environ, {'GITHUB_OUTPUT': str(root / 'output')}):
                    preparar(TAG, sha)
                    base = git('rev-parse', 'origin/main')
                    self.assertIn('"1.0.20"', Path('versao.py').read_text(encoding='utf-8'))
                    self.assertEqual(Path('feature.txt').read_text(), 'beta aprovada')
                    finalizar(base, '1.0.20')
                    promoted = git('rev-parse', 'HEAD')
                    self.assertNotEqual(promoted, sha)
                    self.assertEqual(git('ls-remote', 'origin', 'refs/heads/main').split()[0], promoted)
                    # Retry after a package-upload failure keeps the same stable version.
                    preparar(TAG, sha)
                    self.assertIn('"1.0.20"', Path('versao.py').read_text(encoding='utf-8'))
                    finalizar(promoted, '1.0.20')
                    self.assertEqual(git('rev-parse', 'HEAD'), promoted)
                    self.assertEqual(git('branch', '--show-current', cwd=source), 'develop')
            finally:
                os.chdir(original_cwd)


class ReconciliacaoDevelopTests(unittest.TestCase):
    """Após promover, a develop precisa receber a promoção; senão a próxima Beta diverge da main."""

    def git(self, *args, cwd=None):
        return subprocess.run(['git', *map(str, args)], cwd=cwd, check=True,
                              capture_output=True, text=True, encoding='utf-8').stdout.strip()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.remote, self.source, self.checkout = root / 'remote.git', root / 'source', root / 'checkout'
        git = self.git
        git('init', '--bare', self.remote)
        git('init', '--initial-branch=main', self.source)
        git('config', 'user.name', 'Teste', cwd=self.source)
        git('config', 'user.email', 'teste@example.com', cwd=self.source)
        (self.source / 'versao.py').write_text('VERSAO_APP = "1.0.19"\n', encoding='utf-8')
        (self.source / 'feature.txt').write_text('stable', encoding='utf-8')
        git('add', '.', cwd=self.source)
        git('commit', '-m', 'base', cwd=self.source)
        git('remote', 'add', 'origin', self.remote, cwd=self.source)
        git('push', 'origin', 'main', cwd=self.source)
        git('checkout', '-b', 'develop', cwd=self.source)
        self.sha = self.commit_na_fonte('feature.txt', 'beta aprovada', 'beta')
        git('tag', TAG, cwd=self.source)
        git('push', 'origin', 'develop', '--tags', cwd=self.source)
        git('clone', '--branch', 'develop', '--single-branch', self.remote, self.checkout)
        original_run = pipeline.run

        def runner(*args):
            if args[0] == 'gh':
                return json.dumps({'isPrerelease': True, 'isDraft': False, 'body': 'Beta de teste', 'assets': [{'name': 'ZandaoTibiaToolsBetaSetup.exe'}]})
            return original_run(*args)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.checkout)
        for item in (patch.object(pipeline, 'run', side_effect=runner), patch.dict(os.environ, {'GITHUB_OUTPUT': str(root / 'output')})):
            item.start()
            self.addCleanup(item.stop)
        preparar(TAG, self.sha)
        finalizar(git('rev-parse', 'origin/main'), '1.0.20')
        self.promovido = git('rev-parse', 'HEAD')

    def commit_na_fonte(self, arquivo, conteudo, mensagem):
        (self.source / arquivo).write_text(conteudo, encoding='utf-8')
        self.git('add', arquivo, cwd=self.source)
        self.git('commit', '-m', mensagem, cwd=self.source)
        return self.git('rev-parse', 'HEAD', cwd=self.source)

    def nova_beta(self, tag, arquivo, conteudo):
        """Simula novo trabalho na develop (como outro assistente) e a Beta publicada dele."""
        self.git('fetch', 'origin', cwd=self.source)
        self.git('merge', '--ff-only', 'origin/develop', cwd=self.source)
        sha = self.commit_na_fonte(arquivo, conteudo, 'novo trabalho ' + tag)
        self.git('tag', tag, cwd=self.source)
        self.git('push', 'origin', 'develop', '--tags', cwd=self.source)
        return sha

    def develop_remota(self):
        return self.git('ls-remote', 'origin', 'refs/heads/develop').split()[0]

    def test_sem_reconciliar_a_proxima_beta_fica_bloqueada(self):
        sha = self.nova_beta('v1.0.20-beta.6.1', 'novo.txt', 'a')
        with self.assertRaisesRegex(ValueError, 'Integre a main em develop'):
            preparar('v1.0.20-beta.6.1', sha)

    def test_reconciliar_traz_a_promocao_e_a_proxima_beta_pode_ser_promovida(self):
        self.nova_beta('v1.0.20-beta.6.1', 'novo.txt', 'trabalho que entrou depois')
        pipeline.reconciliar('1.0.20')
        self.git('fetch', 'origin', cwd=self.source)
        self.git('merge-base', '--is-ancestor', self.promovido, 'origin/develop', cwd=self.source)
        self.assertEqual(self.git('show', 'origin/develop:novo.txt', cwd=self.source), 'trabalho que entrou depois')
        self.assertIn('"1.0.20"', self.git('show', 'origin/develop:versao.py', cwd=self.source))
        self.assertTrue(self.git('show', 'origin/develop:docs/releases/v1.0.20.md', cwd=self.source))
        sha = self.nova_beta('v1.0.20-beta.7.1', 'novo.txt', 'outra rodada')
        preparar('v1.0.20-beta.7.1', sha)
        self.assertIn('"1.0.21"', Path('versao.py').read_text(encoding='utf-8'))
        self.assertEqual(Path('novo.txt').read_text(encoding='utf-8'), 'outra rodada')

    def test_reconciliar_avanca_sem_commit_extra_quando_a_develop_nao_andou(self):
        pipeline.reconciliar('1.0.20')
        self.assertEqual(self.develop_remota(), self.promovido)

    def test_reconciliar_e_idempotente(self):
        pipeline.reconciliar('1.0.20')
        antes = self.develop_remota()
        self.assertIn('já contém', pipeline.reconciliar('1.0.20'))
        self.assertEqual(self.develop_remota(), antes)

    def test_conflito_nao_publica_e_limpa_o_checkout(self):
        self.git('fetch', 'origin', cwd=self.source)
        self.git('merge', '--ff-only', 'origin/develop', cwd=self.source)
        self.commit_na_fonte('versao.py', 'VERSAO_APP = "1.0.99"\n', 'versao divergente')
        self.git('push', 'origin', 'develop', cwd=self.source)
        antes = self.develop_remota()
        with self.assertRaisesRegex(ValueError, 'conflito'):
            pipeline.reconciliar('1.0.20')
        self.assertEqual(self.develop_remota(), antes)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_versao_invalida_nao_executa_comandos(self):
        with patch.object(pipeline, 'run') as run:
            with self.assertRaises(ValueError):
                pipeline.reconciliar('v1.0.20')
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
