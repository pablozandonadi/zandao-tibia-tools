"""Optimizer da roda: roda o teste do motor (test_otimizador_roda.cjs) no Node com o HiGHS de verdade. Pulado sem Node."""

import os
import shutil
import subprocess
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))


class TestOtimizadorRoda(unittest.TestCase):
    def test_motor_com_highs(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node não instalado")
        r = subprocess.run([node, "test_otimizador_roda.cjs"], cwd=AQUI, capture_output=True, text=True, timeout=600)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("OK otimizador", r.stdout)

    def test_dados_das_cinco_vocacoes(self):
        import json
        with open(os.path.join(AQUI, "web", "roda_otimizador.json"), encoding="utf-8") as f:
            d = json.load(f)
        self.assertEqual(set(d["vocacoes"]), {"knight", "paladin", "sorcerer", "druid", "monk"})
        for nome, v in d["vocacoes"].items():
            ids = {f["id"] for f in v["fatias"]}
            self.assertEqual(len(v["fatias"]), 36, nome)
            self.assertEqual(sorted(f["w26"] for f in v["fatias"]), list(range(36)), nome)   # cada fatia numa posição do planner novo
            self.assertTrue(all(set(f["vizinhos"]) <= ids for f in v["fatias"]), nome)
            self.assertEqual(sum(f["custo"] for f in v["fatias"]), 4000, nome)
            self.assertEqual(sum(f["tipo"] == "gemVessel" for f in v["fatias"]), 8, nome)


if __name__ == "__main__":
    unittest.main()
