"""Guard the explicitly agreed passive Mirror boundary, including capture protection."""
import ast
from pathlib import Path
import unittest

class MirrorRulesTests(unittest.TestCase):
    def test_mirror_has_no_game_input_memory_injection_or_capture_bypass(self):
        forbidden={'SendInput','keybd_event','mouse_event','ReadProcessMemory','WriteProcessMemory',
                   'VirtualAllocEx','CreateRemoteThread','NtWriteVirtualMemory','SetWindowDisplayAffinity'}
        root=Path(__file__).resolve().parent
        for name in ('mirror_core.py','mirror_service.py','mirror_native.py','mirror_selector.py','mirror_visual.py'):
            tree=ast.parse((root/name).read_text(encoding='utf-8-sig'))
            used={node.attr for node in ast.walk(tree) if isinstance(node,ast.Attribute)}
            self.assertFalse(used & forbidden,name)
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='OpenProcess':
                    self.assertIsInstance(node.args[0],ast.Constant)
                    self.assertEqual(node.args[0].value,0x1000,'Only identity query permission is allowed.')

if __name__=='__main__':unittest.main()
