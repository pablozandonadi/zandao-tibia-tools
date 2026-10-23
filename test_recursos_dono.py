"""Recursos fechados do dono (menu Mensagens e Admin): arquivo local de liberação, ativação por código e o limite do que cada canal mostra."""
import json
import os
import tempfile
import unittest
from unittest import mock

import mensagem_automatica_access as acesso
import web_api


class RecursosDonoTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(web_api, 'BASE_DIR', tmp.name); patcher.start(); self.addCleanup(patcher.stop)
        self.dir = tmp.name; self.api = web_api.API()

    def escrever(self, conteudo):
        with open(os.path.join(self.dir, 'recursos-dono.json'), 'w', encoding='utf-8') as f: f.write(conteudo)

    def test_sem_arquivo_ou_com_arquivo_invalido_nada_e_liberado(self):
        self.assertEqual(self.api.recursos_liberados(), {'mensagens_automaticas': False, 'admin_ia': False})
        for ruim in ('{lixo', '[]', '{"mensagens_automaticas": "sim"}', '{"admin_ia": 1}'):
            self.escrever(ruim); self.assertEqual(self.api.recursos_liberados(), {'mensagens_automaticas': False, 'admin_ia': False}, ruim)

    def test_cada_recurso_liga_sozinho(self):
        self.escrever('{"mensagens_automaticas": true}')
        self.assertEqual(self.api.recursos_liberados(), {'mensagens_automaticas': True, 'admin_ia': False})

    def test_admin_aparece_na_versao_final_so_com_a_liberacao(self):
        with mock.patch.object(web_api.versao, 'CANAL_APP', 'stable'):
            self.assertEqual(self.api.admin_ia_estado(), {'beta': False, 'senha': False})
            self.assertEqual(self.api.admin_ia_listar(), {'erro': 'Indisponível neste canal.'})
            self.escrever('{"admin_ia": true}')
            with mock.patch.object(web_api.admin_ia, 'carregar_senha', return_value=None), mock.patch.object(web_api.admin_ia, 'listar', return_value={'tokens': []}):
                self.assertEqual(self.api.admin_ia_estado(), {'beta': True, 'senha': False})
                self.assertEqual(self.api.admin_ia_listar(), {'tokens': []})

    def test_abrir_a_gestao_exige_a_liberacao(self):
        with mock.patch('mensagem_automatica_access.open_management', return_value={'ok': True}) as aberto:
            self.assertIn('erro', self.api.mensagem_automatica_abrir_portal({})); aberto.assert_not_called()
            self.escrever('{"mensagens_automaticas": true}')
            self.assertEqual(self.api.mensagem_automatica_abrir_portal({}), {'ok': True})

    def test_codigo_aceito_grava_a_liberacao_e_codigo_ruim_nao(self):
        with mock.patch('mensagem_automatica_access.claim_code', side_effect=acesso.AccessError('Código inválido ou já usado.')):
            self.assertEqual(self.api.liberar_recursos('x' * 43), {'erro': 'Código inválido ou já usado.'})
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'recursos-dono.json')))
        with mock.patch('mensagem_automatica_access.claim_code', side_effect=RuntimeError('rede')):
            self.assertIn('erro', self.api.liberar_recursos('x' * 43))
        with mock.patch('mensagem_automatica_access.claim_code', return_value=True) as enviado:
            r = self.api.liberar_recursos('y' * 43)
        enviado.assert_called_once_with('y' * 43)
        self.assertEqual(r, {'ok': True, 'mensagens_automaticas': True, 'admin_ia': True})
        with open(os.path.join(self.dir, 'recursos-dono.json'), encoding='utf-8') as f: self.assertEqual(json.load(f), {'mensagens_automaticas': True, 'admin_ia': True})
        self.assertNotIn('y' * 43, json.dumps(self.api.recursos_liberados()))

    def test_codigo_de_cliente_abre_so_o_menu_mensagens(self):
        with mock.patch('mensagem_automatica_access.claim_code', return_value=False):
            r = self.api.liberar_recursos('c' * 43)
        self.assertEqual(r, {'ok': True, 'mensagens_automaticas': True, 'admin_ia': False})

    def test_gestao_de_codigos_de_clientes_exige_o_menu_admin(self):
        with mock.patch('mensagem_automatica_access.admin_request', return_value=[]) as pedido:
            for chamada in (self.api.admin_msg_listar, lambda: self.api.admin_msg_gerar('Ana', 1),
                            lambda: self.api.admin_msg_revogar('a' * 16), lambda: self.api.admin_msg_remover_conta('b' * 32)):
                self.assertEqual(chamada(), {'erro': 'Somente o administrador pode fazer isso.'})
            pedido.assert_not_called()
            self.escrever('{"mensagens_automaticas": true, "admin_ia": true}')
            self.assertEqual(self.api.admin_msg_listar(), {'codigos': [], 'contas': []})
            self.assertEqual([c.args for c in pedido.call_args_list], [('/v1/admin/claims', 'GET', None), ('/v1/admin/accounts', 'GET', None)])

    def test_gerar_revogar_e_remover_conta_chamam_as_rotas_certas(self):
        self.escrever('{"admin_ia": true}')
        with mock.patch('mensagem_automatica_access.admin_request', return_value={'code': 'k' * 43}) as pedido:
            self.assertEqual(self.api.admin_msg_gerar('Ana', 2), {'codigo': 'k' * 43})
            pedido.assert_called_once_with('/v1/admin/claims', 'POST', {'note': 'Ana', 'uses': 2})
        with mock.patch('mensagem_automatica_access.admin_request', return_value={}) as pedido:
            self.assertEqual(self.api.admin_msg_revogar('a' * 16), {'ok': True})
            pedido.assert_called_with('/v1/admin/claims/' + 'a' * 16, 'DELETE', None)
            self.assertEqual(self.api.admin_msg_remover_conta('b' * 32), {'ok': True})
            pedido.assert_called_with('/v1/admin/accounts/' + 'b' * 32, 'DELETE', None)
            for ruim in ('', '../x', 'A' * 16, 'a' * 15, None, 5):  # nada fora do formato chega ao servidor
                self.assertIn('erro', self.api.admin_msg_revogar(ruim)); self.assertIn('erro', self.api.admin_msg_remover_conta(ruim))
            self.assertEqual(pedido.call_count, 2)
        with mock.patch('mensagem_automatica_access.admin_request', side_effect=acesso.AccessError('Pedido recusado.')):
            self.assertEqual(self.api.admin_msg_gerar('', 1), {'erro': 'Pedido recusado.'})
        with mock.patch('mensagem_automatica_access.admin_request', side_effect=RuntimeError('rede')):
            self.assertIn('erro', self.api.admin_msg_listar())

    def test_formato_do_codigo_e_validado_antes_de_ir_ao_servidor(self):
        for ruim in ('', 'curto', 'x' * 44, 'x' * 42, None, 123):
            with self.assertRaises(acesso.AccessError): acesso.claim_code(ruim)

    def test_o_arquivo_de_liberacao_e_privado(self):
        import app_paths
        self.assertIn('recursos-dono.json', app_paths.PRIVATE_FILES)
        with open('.gitignore', encoding='utf-8') as f: self.assertIn('recursos-dono.json', f.read())

    def test_proxy_local_so_aceita_claim_por_post(self):
        self.assertTrue(acesso.ALLOWED['POST'].fullmatch('/v1/claim'))
        self.assertFalse(acesso.ALLOWED['GET'].fullmatch('/v1/claim'))

    def test_proxy_local_so_aceita_as_rotas_exatas_de_administracao(self):
        A = acesso.ALLOWED
        for metodo, caminho in (('GET', '/v1/admin/claims'), ('GET', '/v1/admin/accounts'), ('POST', '/v1/admin/claims'),
                                ('DELETE', '/v1/admin/claims/' + 'a' * 16), ('DELETE', '/v1/admin/accounts/' + 'b' * 32)):
            self.assertTrue(A[metodo].fullmatch(caminho), caminho)
        for metodo, caminho in (('POST', '/v1/admin/accounts'), ('PUT', '/v1/admin/claims'), ('DELETE', '/v1/admin/claims'),
                                ('DELETE', '/v1/admin/claims/' + 'a' * 15), ('DELETE', '/v1/admin/claims/' + 'a' * 17),
                                ('DELETE', '/v1/admin/accounts/' + 'b' * 16), ('GET', '/v1/admin/claims/' + 'a' * 16), ('GET', '/v1/admin/')):
            self.assertFalse(A.get(metodo) and A[metodo].fullmatch(caminho), caminho)


if __name__ == '__main__':
    unittest.main()
