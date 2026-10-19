import unittest
from unittest import mock

import admin_ia
import web_api

METODOS = [
    ('admin_ia_salvar_senha', ('segredo-ficticio',)),
    ('admin_ia_listar', ()),
    ('admin_ia_gerar', ('Ana', 'daily', 50, None)),
    ('admin_ia_limite', ('Ana', 'total', 100, None, True)),
    ('admin_ia_revogar', ('Ana',)),
]
NOMES_ADMIN = ('salvar_senha', 'carregar_senha', 'limpar_senha', 'listar', 'gerar', 'limite', 'revogar')


class AdminIAApiTests(unittest.TestCase):
    def setUp(self):
        self.api = web_api.API()

    def test_fora_do_beta_todas_recusam_e_nada_e_gravado(self):
        with mock.patch.object(web_api.versao, 'CANAL_APP', 'stable'), \
             mock.patch.multiple(admin_ia, **{n: mock.DEFAULT for n in NOMES_ADMIN}) as falsos:
            for nome, args in METODOS:
                self.assertEqual(getattr(self.api, nome)(*args), {'erro': 'Indisponível neste canal.'}, nome)
            self.assertEqual(self.api.admin_ia_estado(), {'beta': False, 'senha': False})
            for falso in falsos.values():
                falso.assert_not_called()

    def test_no_beta_repassa_os_argumentos_e_devolve_erro_sem_levantar(self):
        with mock.patch.object(web_api.versao, 'CANAL_APP', 'beta'), \
             mock.patch.multiple(admin_ia, salvar_senha=mock.DEFAULT, listar=mock.DEFAULT, gerar=mock.DEFAULT,
                                 limite=mock.DEFAULT, revogar=mock.DEFAULT) as f:
            f['listar'].return_value = {'tokens': []}
            f['gerar'].return_value = {'token': 'x'}
            self.assertEqual(self.api.admin_ia_listar(), {'tokens': []})
            self.assertEqual(self.api.admin_ia_gerar('Ana', 'daily', 50, None), {'token': 'x'})
            f['gerar'].assert_called_once_with(web_api.BASE_DIR, 'Ana', 'daily', 50, None)
            self.api.admin_ia_limite('Ana', 'total', 100, None, True)
            f['limite'].assert_called_once_with(web_api.BASE_DIR, 'Ana', 'total', 100, None, True)
            self.api.admin_ia_revogar('Ana')
            f['revogar'].assert_called_once_with(web_api.BASE_DIR, 'Ana')
            self.assertEqual(self.api.admin_ia_salvar_senha('segredo-ficticio'), {'ok': True})
            f['salvar_senha'].assert_called_once_with(web_api.BASE_DIR, 'segredo-ficticio')
            for n in ('listar', 'gerar', 'limite', 'revogar', 'salvar_senha'):
                f[n].side_effect = admin_ia.AdminIAError('Falhou.', 401)
            for nome, args in METODOS:
                self.assertEqual(getattr(self.api, nome)(*args), {'erro': 'Falhou.'}, nome)

    def test_estado_informa_se_ha_senha_sem_devolve_la(self):
        with mock.patch.object(web_api.versao, 'CANAL_APP', 'beta'):
            with mock.patch.object(admin_ia, 'carregar_senha', return_value='segredo-ficticio'):
                r = self.api.admin_ia_estado()
            self.assertEqual(r, {'beta': True, 'senha': True})
            with mock.patch.object(admin_ia, 'carregar_senha', return_value=None):
                self.assertEqual(self.api.admin_ia_estado(), {'beta': True, 'senha': False})


if __name__ == '__main__':
    unittest.main()
