import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import hunt
import historico
from web_api import API
TEXT = "Session: 01:00h\nXP Gain: 1000\nLooted Items:\n2x lump of earth\n3x rope belts\n4x unknown relics"
class HuntTaskItemsTests(unittest.TestCase):
    def test_classification_and_no_loot(self):
        a = hunt.montar({"solo": TEXT})
        self.assertEqual(a["task_itens"]["total"], 9)
        self.assertEqual(a["task_itens"]["groups"]["tasks"][0]["name"], "Lump of Earth")
        self.assertEqual(a["task_itens"]["groups"]["imbuements"][0]["quantity"], 3)
        self.assertEqual(a["task_itens"]["groups"]["other"][0]["quantity"], 4)
        self.assertNotIn("task_itens", hunt.montar({"solo": "Session: 01:00h\nXP Gain: 1000"}))
    def test_save_reopen_and_update(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(historico, "HIST_PATH", str(Path(folder)/"hunts.json")):
            api = API.__new__(API)
            api._dano_cache = {}
            result = api.hunt_salvar({"solo": TEXT, "nome": "Loot test"})
            self.assertTrue(result["ok"])
            saved = historico.obter(result["id"])
            self.assertEqual(saved["task_itens"]["total"], 9)
            reopened = api.hunt_abrir(result["id"])
            self.assertEqual(hunt.montar(reopened)["task_itens"], saved["task_itens"])
            reopened["solo"] = TEXT.replace("2x lump", "7x lump")
            api.hunt_salvar(reopened)
            self.assertEqual(historico.obter(result["id"])["task_itens"]["total"], 14)
