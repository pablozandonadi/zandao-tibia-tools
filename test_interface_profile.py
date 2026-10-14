"""Regression: a new build must not reuse the previous build's WebView profile."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import zandao_tibia_tools as app

class InterfaceProfileTests(unittest.TestCase):
    def test_each_build_opens_with_a_fresh_profile(self):
        profiles=[]
        with tempfile.TemporaryDirectory() as directory:
            api=MagicMock();api._rede.config={'enabled':False}
            with patch.object(app,'initialize_data'), patch.object(app,'data_dir',return_value=directory), \
                 patch('recovery.record_startup'), patch('web_api.API',return_value=api), \
                 patch('web_api.ler_prefs',return_value={}), patch('tray_app.TrayController'), \
                 patch.object(app.webview,'create_window'), patch.object(app.webview,'start') as start:
                for version in ('1.0.25-beta.52.1','1.0.25-beta.53.1'):
                    with patch.object(app,'VERSAO_APP',version):
                        app.main()
                        profiles.append(Path(start.call_args.kwargs['storage_path']))
            self.assertNotEqual(profiles[0],profiles[1])
            self.assertTrue(all(Path(directory) in p.parents for p in profiles))
            self.assertTrue(all(p.parent.name=='webview_session' for p in profiles))

if __name__=='__main__':unittest.main()
