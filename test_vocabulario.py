import base64
import json
import unittest
from voice import vocabulario as v


class VocabularioTests(unittest.TestCase):
    def test_priority_bounds_charset_and_roundtrip(self):
        self.assertEqual(v.montar(['Drume'], ['Grand Master Oberon'])[:2], ['Grand Master Oberon', 'Drume'])
        self.assertEqual(len(v.montar([f'b{i}' for i in range(100)], [])), 40)
        terms=v.montar(['Drume', 'DRUME', 'x'*60, 'bad_header:', 'bad\nheader', 'Dra\u0301cula'], ['drume'])
        self.assertEqual(sum(t.casefold()=='drume' for t in terms), 1)
        self.assertNotIn('x'*60, terms)
        self.assertNotIn('bad_header:', terms)
        self.assertNotIn('bad\nheader', terms)
        self.assertIn('Drácula', terms)
        self.assertEqual(json.loads(base64.urlsafe_b64decode(v.cabecalho(['Ahau', 'Scarlett Etzel'])+'==')), ['Ahau', 'Scarlett Etzel'])
        self.assertEqual(v.montar([], [], 0), [])
        self.assertEqual(len(v.montar([f'b{i}' for i in range(100)], [], 100)), 40)
