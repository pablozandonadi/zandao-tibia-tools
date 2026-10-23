"""Motor de modelos dos bots: variáveis entre chaves, linhas opcionais e passada única."""
import unittest

from modelos import renderizar, usa_variaveis


class ModelosTests(unittest.TestCase):
    def test_troca_variaveis_e_deixa_desconhecidas_como_estao(self):
        self.assertEqual(renderizar('Oi {nome}, {mundo}! {x}', {'nome': 'Ana', 'mundo': 'Antica'}), 'Oi Ana, Antica! {x}')

    def test_linha_so_de_variaveis_vazias_some_e_buracos_sao_fechados(self):
        modelo = '📜 *{nome}*\n{guilda}\n{casas}\n\n{mortes}'
        self.assertEqual(renderizar(modelo, {'nome': 'Ana', 'guilda': '', 'casas': '', 'mortes': 'nenhuma'}), '📜 *Ana*\n\nnenhuma')
        self.assertEqual(renderizar('a\n{x}\n\n\n\nb', {'x': ''}), 'a\n\nb')
        self.assertEqual(renderizar('Guilda: {g}', {'g': ''}), 'Guilda:', 'linha com texto fixo é mantida')

    def test_passada_unica_nao_expande_valor_que_tem_chaves(self):
        self.assertEqual(renderizar('{a} {b}', {'a': '{b}', 'b': 'ok'}), '{b} ok')

    def test_blocos_com_varias_linhas_e_espacos_internos_sao_preservados(self):
        tabela = '```\nLevel   10   20\n  XP    1    2\n```'
        self.assertEqual(renderizar('T\n{t}', {'t': tabela}), 'T\n' + tabela)

    def test_usa_variaveis(self):
        self.assertTrue(usa_variaveis('oi {x}')); self.assertFalse(usa_variaveis('oi {X} { x } {}')); self.assertFalse(usa_variaveis('texto fixo'))


if __name__ == '__main__':
    unittest.main()
