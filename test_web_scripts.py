"""Garante que as funções que o index.html e o sets.js chamam continuam definidas nos scripts da pasta web
(uma remoção grande por engano já derrubou a tela do Hunt Analyser sem nenhum teste de Python perceber)."""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


def _ler(nome):
    with open(os.path.join(WEB, nome), "r", encoding="utf-8") as f:
        return f.read()


class TestFuncoesDefinidas(unittest.TestCase):
    def test_funcoes_chamadas_no_sets_existem(self):
        tudo = "\n".join(_ler(n) for n in os.listdir(WEB) if n.endswith((".js", ".html")))
        sets = _ler("sets.js")
        chamadas = set(re.findall(r"\$\{(html[A-Z][A-Za-z]*)\(", sets))
        self.assertTrue(chamadas)
        for nome in chamadas:
            self.assertRegex(tudo, rf"(function\s+{nome}\s*\(|const\s+{nome}\s*=)", f"{nome} não está definida")

    def test_blocos_principais_do_hunt_analyser(self):
        sets = _ler("sets.js")
        for nome in ("htmlSkillsHunt", "htmlPosturaHunt", "htmlSetHunt", "htmlProfArma", "atualizarCombatHunt"):
            self.assertRegex(sets, rf"function\s+{nome}\s*\(", nome)


if __name__ == "__main__":
    unittest.main()
