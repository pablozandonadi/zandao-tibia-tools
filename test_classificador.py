"""Testes do classificador de dano embutido (página da comunidade baixada no PC + sessão salva por hunt).  Rodar: python -m unittest"""

import json
import os
import tempfile
import time
import unittest

import classificador as cl

INDEX = """<!DOCTYPE html><html><head><title>Classificador</title>
<link href="https://fonts.googleapis.com/css2?family=Inter" rel="stylesheet">
<link rel="stylesheet" href="css/style.css"></head><body>
<textarea id="clsLocalInput"></textarea><textarea id="clsServerInput"></textarea><button id="btnClassify">ok</button><div id="clsResults"></div>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<script src="js/a.js"></script>
<script src="js/b.js"></script>
</body></html>"""
SITE = {"index.html": INDEX, "css/style.css": "body{color:red}", "js/a.js": "var a=1; var s='</script>';", "js/b.js": "var b=2;"}


class TestArquivos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = os.path.join(self.tmp.name, "cache")
        self.baixados = []

    def tearDown(self):
        self.tmp.cleanup()

    def _baixar(self, url):
        self.baixados.append(url)
        return SITE[url.replace(cl.BASE, "")].encode("utf-8")

    def test_baixa_o_index_e_o_que_ele_usa_e_guarda_no_cache(self):
        r = cl.arquivos(self.pasta, self._baixar)
        self.assertTrue(r["ok"])
        self.assertEqual(set(r["arquivos"]), {"index.html", "css/style.css", "js/a.js", "js/b.js"})
        self.assertTrue(all(u.startswith("https://lucasporfz.github.io/classificador/") for u in self.baixados))
        n = len(self.baixados)
        cl.arquivos(self.pasta, self._baixar)
        self.assertEqual(len(self.baixados), n)                               # 2ª vez: tudo do cache

    def test_cache_velho_sem_internet_e_pagina_de_erro(self):
        cl.arquivos(self.pasta, self._baixar)
        velho = time.time() - cl.VALIDADE - 10
        for raiz, _, nomes in os.walk(self.pasta):
            for n in nomes:
                os.utime(os.path.join(raiz, n), (velho, velho))

        def sem_internet(url):
            raise OSError("sem internet")
        self.assertTrue(cl.arquivos(self.pasta, sem_internet)["ok"])           # usa o velho
        nova = os.path.join(self.tmp.name, "outra")
        r = cl.arquivos(nova, lambda u: b"<html>404 Not Found</html>" if u.endswith(".js") else SITE[u.replace(cl.BASE, "")].encode("utf-8"))
        self.assertFalse(r["ok"])                                              # um .js que é página de erro não é guardado
        self.assertFalse(cl.arquivos(os.path.join(self.tmp.name, "vazia"), sem_internet)["ok"])


class TestPagina(unittest.TestCase):
    def test_monta_a_pagina_com_tudo_embutido(self):
        arq = {k: v for k, v in SITE.items()}
        html = cl.montar_pagina(arq)
        self.assertIn("body{color:red}", html)                                 # css embutido
        self.assertIn("var b=2;", html)                                        # js embutido
        self.assertNotIn('src="js/a.js"', html)
        self.assertIn("cdn.jsdelivr.net/npm/chart.js", html)                   # a biblioteca de gráficos continua vindo da internet
        self.assertIn("fonts.googleapis.com", html)
        self.assertEqual(html.count("</script>"), 3)                           # o "</script>" dentro de uma string do js não fecha a tag: foi escapado
        self.assertIn("<" + chr(92) + "/script>", html)

    def test_pagina_do_resultado_salvo(self):
        html = cl.pagina_resultado(SITE, "<table><tr><td>42</td></tr></table>")
        self.assertIn("body{color:red}", html)
        self.assertIn("<td>42</td>", html)
        self.assertNotIn("clsLocalInput", html)                                # só o resultado, sem a tela de colar logs
        self.assertNotIn("<script", html.replace("<script></script>", ""))     # sem script nenhum


class TestApi(unittest.TestCase):
    def setUp(self):
        import web_api
        self.tmp = tempfile.TemporaryDirectory()
        self.api = object.__new__(web_api.API)
        self.sessoes = os.path.join(self.tmp.name, "s.json")
        from unittest import mock
        self.mock = mock.patch.object(cl, "SESSOES_PATH", self.sessoes)
        self.mock.start()

    def tearDown(self):
        self.mock.stop()
        self.tmp.cleanup()

    def test_salvar_ler_e_apagar_pela_api(self):
        self.assertIsNone(self.api.classificador_sessao("h1"))
        self.assertTrue(self.api.classificador_salvar("h1", "chat", "log", "<p>x</p>"))
        s = self.api.classificador_sessao("h1")
        self.assertEqual((s["local"], s["server"], s["tem_resultado"], s["linhas_local"]), ("chat", "log", True, 1))
        self.assertNotIn("html", s)                                            # o resultado (grande) só vem quando pedido
        self.assertTrue(self.api.classificador_apagar("h1"))
        self.assertIsNone(self.api.classificador_sessao("h1"))

    def test_apagar_a_hunt_apaga_a_sessao(self):
        import historico
        from unittest import mock
        arq = os.path.join(self.tmp.name, "h.json")
        with mock.patch.object(historico, "HIST_PATH", arq):
            h = historico.salvar({"nome": "x", "entrada": {"party": "p"}, "resumo": {}, "assinatura": "a1"})
            cl.salvar_sessao(h["id"], "chat", "log", None)
            self.assertTrue(self.api.hunt_apagar(h["id"]))
        self.assertIsNone(cl.obter_sessao(h["id"]))

    def test_pagina_e_resultado_salvo(self):
        from unittest import mock
        site = {"ok": True, "arquivos": SITE}
        with mock.patch.object(cl, "arquivos", return_value=site):
            p = self.api.classificador_pagina()
            self.assertTrue(p["ok"] and "var b=2;" in p["html"])
            self.assertFalse(self.api.classificador_resultado("h1")["ok"])      # ainda não tem resultado salvo
            cl.salvar_sessao("h1", "chat", "log", "<table>42</table>")
            r = self.api.classificador_resultado("h1")
            self.assertTrue(r["ok"] and "<table>42</table>" in r["html"] and "body{color:red}" in r["html"])
        with mock.patch.object(cl, "arquivos", return_value={"ok": False, "erro": "sem internet"}):
            self.assertEqual(self.api.classificador_pagina()["erro"], "sem internet")


class TestSessao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = os.path.join(self.tmp.name, "s.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_salvar_obter_apagar(self):
        self.assertIsNone(cl.obter_sessao("h1", self.arq))
        self.assertTrue(cl.salvar_sessao("h1", "linha local\nb", "server", "<p>r</p>", self.arq))
        s = cl.obter_sessao("h1", self.arq)
        self.assertEqual((s["local"], s["server"], s["html"]), ("linha local\nb", "server", "<p>r</p>"))
        self.assertEqual((s["linhas_local"], s["linhas_server"]), (2, 1))
        self.assertEqual(cl.obter_sessao("h1", self.arq)["t"] > 0, True)
        cl.salvar_sessao("h1", "novo", "", None, self.arq)                      # sem html: guarda os logs e mantém o resultado antigo
        s = cl.obter_sessao("h1", self.arq)
        self.assertEqual((s["local"], s["html"]), ("novo", "<p>r</p>"))
        self.assertTrue(cl.apagar_sessao("h1", self.arq))
        self.assertFalse(cl.apagar_sessao("h1", self.arq))
        self.assertIsNone(cl.obter_sessao("h1", self.arq))

    def test_limites_e_lixo(self):
        self.assertFalse(cl.salvar_sessao("", "x", "y", None, self.arq))       # sem hunt
        self.assertFalse(cl.salvar_sessao("h1", "", "", None, self.arq))       # sem nada para guardar
        grande = "x" * (cl.MAX_TEXTO + 10)
        cl.salvar_sessao("h2", grande, "s", "h" * (cl.MAX_HTML + 10), self.arq)
        s = cl.obter_sessao("h2", self.arq)
        self.assertEqual(len(s["local"]), cl.MAX_TEXTO)                         # cortado no limite
        self.assertEqual(s["html"], "")                                         # resultado grande demais não é guardado
        with open(self.arq, "w", encoding="utf-8") as f:
            f.write("{quebrado")
        self.assertIsNone(cl.obter_sessao("h2", self.arq))


if __name__ == "__main__":
    unittest.main()
