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


if __name__ == '__main__':
    unittest.main()
