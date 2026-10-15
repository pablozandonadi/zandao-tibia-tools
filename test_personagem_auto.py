"""Troca de personagem por título público do Windows, sem interação com o jogo."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import overlay
import personagens
import web_api


class DetectarPersonagemTests(unittest.TestCase):
    def setUp(self):
        self.native = Mock()
        self.kernel = Mock()
        self.patches = [patch.object(overlay.sys, "platform", "win32"),
                        patch.object(overlay, "_u32", self.native, create=True),
                        patch.object(overlay, "_k32", self.kernel, create=True)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.native.GetForegroundWindow.return_value = 123
        self.native.IsWindowVisible.return_value = True
        self.native.IsIconic.return_value = False
        self.kernel.OpenProcess.return_value = 456
        self.path = r"C:\Tibia\client.exe"
        self.title = "Tibia - Elite Nestos"
        def process(handle, flags, path, size):
            path.value = self.path
            return True
        def title(hwnd, text, length):
            text.value = self.title
            return len(self.title)
        self.kernel.QueryFullProcessImageNameW.side_effect = process
        self.native.GetWindowTextW.side_effect = title

    def test_reads_only_foreground_client_public_title(self):
        self.assertEqual(overlay.personagem_tibia_em_foco(), "Elite Nestos")
        self.native.GetWindowTextW.assert_called_once()
        self.kernel.CloseHandle.assert_called_once_with(456)

    def test_rejects_spoofed_titles_and_unrecognized_executable(self):
        self.path = "other.exe"
        self.assertEqual(overlay.personagem_tibia_em_foco(), "")
        self.native.GetWindowTextW.assert_not_called()

    def test_logged_out_or_wrong_title_keeps_no_candidate(self):
        for title in ("Tibia", "Tibia - ", "Other - Elite Nestos"):
            with self.subTest(title=title):
                self.title = title
                self.assertEqual(overlay.personagem_tibia_em_foco(), "")

    def test_no_foreground_minimized_hidden_or_inaccessible_client(self):
        self.native.GetForegroundWindow.return_value = None
        self.assertEqual(overlay.personagem_tibia_em_foco(), "")
        self.native.GetForegroundWindow.return_value = 123
        self.native.IsIconic.return_value = True
        self.assertEqual(overlay.personagem_tibia_em_foco(), "")
        self.native.IsIconic.return_value = False
        self.native.IsWindowVisible.return_value = False
        self.assertEqual(overlay.personagem_tibia_em_foco(), "")
        self.native.IsWindowVisible.return_value = True
        self.kernel.OpenProcess.return_value = None
        self.assertEqual(overlay.personagem_tibia_em_foco(), "")

    def test_focus_changed_during_read_is_discarded(self):
        self.native.GetForegroundWindow.side_effect = [123, 999]
        self.assertEqual(overlay.personagem_tibia_em_foco(), "")
        self.kernel.CloseHandle.assert_called_once()

    def test_pinned_application_is_not_a_tibia_client(self):
        with patch.object(overlay, "_hwnd_app_fixado", 123):
            self.path = "TibiaTudo.exe"
            self.assertEqual(overlay.personagem_tibia_em_foco(), "")


class TrocaAutomaticaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.file = os.path.join(self.tmp.name, "personagens.json")
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump({"lista": [{"nome": "Zandao"}, {"nome": "Elite Nestos"}], "atual": "Zandao"}, f)
        self.file_patch = patch.object(personagens, "ARQUIVO", self.file)
        self.file_patch.start()
        self.addCleanup(self.file_patch.stop)
        self.api = web_api.API.__new__(web_api.API)
        self.api._personagem_revisao = 0
        self.api._personagem_auto_stop = threading.Event()
        self.api._personagem_auto_thread = None
        self.api._audio = Mock()
        self.api._mirror = Mock()
        self.api._emit = Mock()
        self.detect_patch = patch.object(overlay, "personagem_tibia_em_foco", return_value="elite nestos")
        self.detect = self.detect_patch.start()
        self.addCleanup(self.detect_patch.stop)
        self.addCleanup(self.api._personagem_auto_parar)

    def test_matches_canonical_name_propagates_and_emits_once(self):
        self.api._personagem_auto_sincronizar()
        self.assertEqual(personagens.carregar()["atual"], "Elite Nestos")
        self.api._audio.definir_personagem.assert_called_once_with("Elite Nestos")
        self.api._mirror.definir_personagem.assert_called_once_with("Elite Nestos")
        state = self.api._emit.call_args.args[1]
        self.assertEqual(state["revisao"], 1)
        with patch.object(personagens, "_gravar") as write:
            self.api._personagem_auto_sincronizar()
            write.assert_not_called()
        self.api._emit.assert_called_once()

    def test_unknown_logged_out_or_background_does_not_clear_selection(self):
        for name in ("Unknown", ""):
            self.detect.return_value = name
            self.api._personagem_auto_sincronizar()
            self.assertEqual(personagens.carregar()["atual"], "Zandao")
        self.api._emit.assert_not_called()
        self.api._mirror.definir_personagem.assert_not_called()

    def test_removed_character_cannot_be_auto_selected(self):
        self.api.personagem_remover("Elite Nestos")
        self.api._personagem_auto_sincronizar()
        self.assertEqual(personagens.carregar()["atual"], "Zandao")
        self.api._emit.assert_not_called()

    def test_focus_recheck_discards_old_candidate(self):
        self.detect.side_effect = ["Elite Nestos", "Zandao"]
        self.api._personagem_auto_sincronizar()
        self.assertEqual(personagens.carregar()["atual"], "Zandao")

    def test_manual_change_after_auto_has_newer_revision(self):
        self.api._personagem_auto_sincronizar()
        old = self.api._emit.call_args.args[1]
        new = self.api.personagem_usar("Zandao")
        self.assertGreater(new["revisao"], old["revisao"])
        self.assertEqual(personagens.carregar()["atual"], "Zandao")

    def test_callback_is_outside_backend_lock(self):
        def emit(*args):
            acquired = []
            def acquire():
                with web_api.PERSONAGEM_LOCK:
                    acquired.append(True)
            t = threading.Thread(target=acquire)
            t.start()
            t.join(1)
            self.assertEqual(acquired, [True])
        self.api._emit.side_effect = emit
        self.api._personagem_auto_sincronizar()

    def test_failed_notification_retries_without_writing_or_resetting_consumers(self):
        self.api._emit.side_effect = [RuntimeError("page temporarily busy"), None]
        with self.assertRaises(RuntimeError):
            self.api._personagem_auto_sincronizar()
        pending = self.api._personagem_auto_pendente
        self.assertEqual(personagens.carregar()["atual"], "Elite Nestos")
        self.detect.return_value = ""
        with patch.object(personagens, "_gravar") as write:
            self.api._personagem_auto_sincronizar()
            write.assert_not_called()
        self.assertEqual(self.api._emit.call_count, 2)
        self.assertIs(self.api._emit.call_args.args[1], pending)
        self.assertIsNone(self.api._personagem_auto_pendente)
        self.assertEqual(self.api._personagem_revisao, 1)
        self.api._audio.definir_personagem.assert_called_once_with("Elite Nestos")
        self.api._mirror.definir_personagem.assert_called_once_with("Elite Nestos")
        self.api._personagem_auto_sincronizar()
        self.assertEqual(self.api._emit.call_count, 2)

    def test_manual_revision_discards_pending_retry(self):
        self.api._emit.side_effect = [RuntimeError("busy"), None]
        with self.assertRaises(RuntimeError):
            self.api._personagem_auto_sincronizar()
        new = self.api.personagem_usar("Zandao")
        self.detect.return_value = "Unknown"
        self.api._personagem_auto_sincronizar()
        self.api._emit.assert_called_once()
        self.assertIsNone(self.api._personagem_auto_pendente)
        self.assertEqual(new["revisao"], 2)
        self.assertEqual(personagens.carregar()["atual"], "Zandao")

    def test_stop_prevents_pending_notification(self):
        self.api._emit.side_effect = RuntimeError("busy")
        with self.assertRaises(RuntimeError):
            self.api._personagem_auto_sincronizar()
        self.api._personagem_auto_parar()
        self.api._personagem_auto_sincronizar()
        self.api._emit.assert_called_once()

    def test_start_is_idempotent_and_stop_releases_worker(self):
        self.api.personagem_auto_iniciar()
        t = self.api._personagem_auto_thread
        self.api.personagem_auto_iniciar()
        self.assertIs(self.api._personagem_auto_thread, t)
        self.api._personagem_auto_parar()
        self.assertFalse(t.is_alive())
        self.api._personagem_auto_sincronizar()
        self.api._emit.assert_not_called()

    def test_worker_survives_transient_detection_error(self):
        stop = Mock()
        stop.wait.side_effect = [False, False, True]
        self.api._personagem_auto_stop = stop
        self.api._personagem_auto_sincronizar = Mock(side_effect=[OSError("closed"), None])
        self.api._personagem_auto_monitorar()
        self.assertEqual(self.api._personagem_auto_sincronizar.call_count, 2)
        self.api._personagem_auto_thread = None


class PersonagemBridgeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js necessário para validar callback e revisão")
    def test_delayed_callback_and_response_cannot_overwrite_newer_state(self):
        source = (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")
        start = source.index("let MEUS =")
        end = source.index("// rodas, sets", start)
        js = "const assert = require('node:assert/strict'); const window = {}; let sync = 0; let renders = 0; function sincronizarPersonagem(){sync++;} function montarListaPersonagens(){renders++;}\n"
        js += source[start:end]
        js += "\nwindow.personagemEstado({atual:'A', lista:[], revisao:2}); window.personagemEstado({atual:'B', lista:[], revisao:1}); assert.equal(MEUS.atual,'A'); MEUS = receberPersonagens({atual:'C',lista:[],revisao:3}); window.personagemEstado({atual:'A', lista:[], revisao:2}); assert.equal(MEUS.atual,'C'); assert.equal(sync,3); assert.equal(renders,3);"
        result = subprocess.run([shutil.which("node"), "-e", js], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
