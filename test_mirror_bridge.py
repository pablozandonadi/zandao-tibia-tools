"""Execute the real Python emitter against Mirror's browser callback contract."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import Mock

class MirrorBridgeTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node.js necessário para a regressão da ponte JavaScript')
    def test_python_emitter_reaches_browser_renderer(self):
        from web_api import API
        api = API.__new__(API)
        api._window = Mock()
        payload = {'personagem':'Atual', 'perfis':[], 'clientes':[],
                   'estado':{'mensagem':'Atualização nativa recebida'}}
        api._emit('mirrorEstado', payload)
        script = api._window.evaluate_js.call_args.args[0]
        self.assertEqual(script, f'mirrorEstado({json.dumps(payload, ensure_ascii=False)})')
        env = dict(os.environ, MIRROR_CALLBACK_SCRIPT=script)
        root = Path(__file__).resolve().parent
        result = subprocess.run([shutil.which('node'), str(root/'test_mirror_ui.cjs')],
                                cwd=root, env=env, capture_output=True, text=True, timeout=20,
                                encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('native callback', result.stdout)

if __name__ == '__main__':
    unittest.main()
