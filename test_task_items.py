import unittest
import task_items as ti

class TaskItemsTests(unittest.TestCase):
    def items(self, text, people=1):
        r = ti.analyse(text, people)
        self.assertNotIn('erro', r)
        return {i['name']: i for g in r['groups'].values() for i in g}, r

    def test_full_analyser_ignores_monsters(self):
        items, r = self.items('Session Data: today\nKilled Monsters:\n50x werewolf\nLooted Items:\n13x werewolf fur\n2x a fur armor', 4)
        self.assertEqual(set(items), {'Werewolf Fur', 'Fur Armor'})
        self.assertEqual(items['Werewolf Fur']['each'], 3)
        self.assertEqual(items['Werewolf Fur']['remainder'], 1)
        self.assertEqual(items['Fur Armor']['each'], 0)
        self.assertEqual(r['total'], 15)

    def test_alias_plural_articles_aggregate(self):
        items, _ = self.items('1x a rope belt\n2x rope belts\n3x some vampire teeth\n4x a vampire tooth')
        self.assertEqual(items['Rope Belt']['quantity'], 3)
        self.assertEqual(items['Vampire Teeth']['quantity'], 7)
        self.assertIn('Powerful Vampirism', items['Vampire Teeth']['imbuements'])

    def test_three_categories(self):
        items, r = self.items('2x lump of earth\n3x rope belts\n4x unknown relics')
        self.assertEqual([i['name'] for i in r['groups']['tasks']], ['Lump of Earth'])
        self.assertTrue(items['Rope Belt']['imbuements'])
        self.assertEqual([i['name'] for i in r['groups']['imbuements']], ['Rope Belt'])
        self.assertEqual([i['name'] for i in r['groups']['other']], ['unknown relics'])

    def test_separator_and_case(self):
        items, _ = self.items('1,234x WEREWOLF FUR\n1.000x gold coins')
        self.assertEqual(items['Werewolf Fur']['quantity'], 1234)
        self.assertEqual(items['gold coins']['quantity'], 1000)

    def test_empty_and_monsters_only(self):
        for text in ['', 'nonsense', 'Killed Monsters:\n15x werewolf']:
            self.assertIn('erro', ti.analyse(text))

    def test_people_validation(self):
        for people in [0, -1, 1001, 'nan', '2.5', None]:
            self.assertIn('erro', ti.analyse('2x rope belts', people))

    def test_split_conserves_quantity(self):
        for people in [1, 4, 100]:
            items, _ = self.items('15x rope belts', people)
            item = items['Rope Belt']
            self.assertEqual(item['each'] * people + item['remainder'], item['quantity'])

    def test_unknown_markup_retained_as_data(self):
        items, _ = self.items('1x <img src=x onerror=alert(1)>')
        self.assertEqual(len(items), 1)

if __name__ == '__main__':
    unittest.main()
