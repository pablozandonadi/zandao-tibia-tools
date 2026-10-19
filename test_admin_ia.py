import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import admin_ia as a

SENHA = 'A' * 43
CODIGO = 'C' * 43


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *x): self.close()


def http(code):
    return urllib.error.HTTPError(a.ENDPOINT, code, 'x', {}, io.BytesIO(json.dumps({'error': 'voice_unavailable', 'x': SENHA}).encode()))


class AdminIATests(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory(); self.addCleanup(self._d.cleanup)
        self.pasta = Path(self._d.name)

    def test_salvar_senha_guarda_so_criptografado(self):
        a.salvar_senha(self.pasta, SENHA)
        self.assertNotIn(SENHA.encode(), (self.pasta / 'admin-online.dpapi').read_bytes())
        self.assertEqual(a.carregar_senha(self.pasta), SENHA)
        self.assertEqual([p.name for p in self.pasta.iterdir()], ['admin-online.dpapi'])
        a.limpar_senha(self.pasta)
        self.assertIsNone(a.carregar_senha(self.pasta))

    def test_senha_invalida_e_recusada_antes_de_gravar(self):
        for ruim in ('curta', 'A' * 44, 'A' * 42 + '!', None):
            with self.assertRaises(a.AdminIAError):
                a.salvar_senha(self.pasta, ruim)
        self.assertEqual(list(self.pasta.iterdir()), [])

    def test_gerar_monta_post(self):
        a.salvar_senha(self.pasta, SENHA)
        with mock.patch.object(a._OPENER, 'open', return_value=Resp(json.dumps({'token': CODIGO}).encode())) as op:
            r = a.gerar(self.pasta, 'Ana', 'total', quota=100, expires=5)
        pedido = op.call_args.args[0]
        self.assertEqual(r, {'token': CODIGO})
        self.assertEqual((pedido.get_method(), pedido.full_url), ('POST', a.ENDPOINT + '/admin/tokens'))
        self.assertEqual(pedido.get_header('Authorization'), 'Bearer ' + SENHA)
        self.assertEqual(json.loads(pedido.data), {'subject': 'Ana', 'mode': 'total', 'quota': 100, 'expires': 5})
        self.assertEqual(op.call_args.kwargs['timeout'], 15)
        self.assertEqual(pedido.get_header('User-agent'), 'TibiaTudo/1.0')
        with mock.patch.object(a._OPENER, 'open', side_effect=lambda *a, **k: Resp(b'{}')) as op:
            a.gerar(self.pasta, 'Ana', 'unlimited')
            a.limite(self.pasta, 'Ana', 'total', quota=3, reset_used=True)
        self.assertEqual(json.loads(op.call_args_list[0].args[0].data), {'subject': 'Ana', 'mode': 'unlimited'})
        self.assertEqual(json.loads(op.call_args_list[1].args[0].data)['reset_used'], True)

    def test_limite_sempre_manda_expires_e_gerar_omite(self):
        # No limite, omitir expires manteria a validade no servidor; None aqui é "o admin limpou o campo".
        a.salvar_senha(self.pasta, SENHA)
        with mock.patch.object(a._OPENER, 'open', side_effect=lambda *a, **k: Resp(b'{}')) as op:
            a.limite(self.pasta, 'Ana', 'daily', quota=3)
            a.limite(self.pasta, 'Ana', 'daily', quota=3, expires=9)
            a.gerar(self.pasta, 'Ana', 'daily', quota=3)
        corpos = [json.loads(c.args[0].data) for c in op.call_args_list]
        self.assertEqual(corpos[0], {'subject': 'Ana', 'mode': 'daily', 'quota': 3, 'expires': None})
        self.assertEqual(corpos[1]['expires'], 9)
        self.assertNotIn('expires', corpos[2])

    def test_erros_mapeados_e_sem_vazamento(self):
        a.salvar_senha(self.pasta, SENHA)
        casos = [(http(401), 'Senha de administrador recusada.'),
            (http(400), 'Dados inválidos. No nome use só letras sem acento, números, _ ou -; a validade não pode estar no passado.'),
            (http(404), 'Esta pessoa não tem código ativo.'),
            (http(409),'Esta pessoa já tem um código ativo. Revogue antes de gerar outro.'),
            (http(429), 'Muitas tentativas. Aguarde um minuto.'),
            (http(503), 'Administração indisponível no servidor.'),
            (http(500), 'Não foi possível concluir. Tente novamente.'),
            (urllib.error.URLError(SENHA), 'Sem conexão com o servidor.'),
            (OSError(SENHA), 'Sem conexão com o servidor.')]
        for erro, msg in casos:
            with mock.patch.object(a._OPENER, 'open', side_effect=erro), self.assertRaises(a.AdminIAError) as c:
                a.listar(self.pasta)
            self.assertEqual(str(c.exception), msg)
            for s in (str(c.exception), repr(c.exception), repr(c.exception.args)):
                self.assertNotIn(SENHA, s)
                self.assertNotIn(CODIGO, s)
            self.assertIsNone(c.exception.__context__)
            self.assertIsNone(c.exception.__cause__)
        for corpo in (b'[1]', b'x' * 70000, json.dumps({'a': 'b' * 70000}).encode(), json.dumps({'token': CODIGO}).encode() + b'x'):
            with mock.patch.object(a._OPENER, 'open', return_value=Resp(corpo)), self.assertRaises(a.AdminIAError) as c:
                a.gerar(self.pasta, 'Ana', 'unlimited')
            self.assertNotIn(CODIGO, repr(c.exception))
            self.assertIsNone(c.exception.__context__)
            self.assertIsNone(c.exception.__cause__)

    def test_falha_do_dpapi_vira_admin_ia_error(self):
        for erro in (ValueError('código'), OSError('x'), AttributeError('x')):
            with mock.patch.object(a.voz_credenciais, '_proteger', side_effect=erro), self.assertRaises(a.AdminIAError) as c:
                a.salvar_senha(self.pasta, SENHA)
            self.assertIsNone(c.exception.__context__)
            self.assertEqual(list(self.pasta.iterdir()), [])

    def test_sem_senha_levanta(self):
        with self.assertRaisesRegex(a.AdminIAError, 'Informe a senha de administrador.'):
            a.revogar(self.pasta, 'Ana')


if __name__ == '__main__':
    unittest.main()
