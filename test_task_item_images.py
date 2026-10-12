import base64
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import task_item_images as sprites

class ItemImagesTests(unittest.TestCase):
    def test_screenshot_items_available_offline(self):
        names=['Brimstone Fangs','Brimstone Shell','Poisonous Slime','Wereboar Hooves','bear paw','beetle necklace','berserk potion','brown mushroom','epee','furry club','gold coin','great mana potion','haunted piece of wood','honeycomb','legionnaire flags','lizard leather','lump of dirt','magic sulphur','platinum coin','red lantern','rusted armor','small amethyst','small emerald','small enchanted ruby','star herb','stealth ring','stone skin amulet','strong health potion','strong mana potion','tome of knowledge','troll green','ultimate health potion','werebadger skull','werebear trophy','werewolf amulet','werewolf fangs','wolf paw','zaoan halberd']
        with patch.object(sprites, 'download', side_effect=AssertionError('offline test')):
            images = sprites.resolve([{'name':n} for n in names])
        self.assertEqual(len(images),len(names))
        self.assertTrue(all(images[n].startswith('data:image/gif;base64,') for n in names))

    def test_all_catalog_and_imbuement_materials_have_sprite(self):
        items=json.loads(Path('data/task_items.json').read_text(encoding='utf-8'))
        for imb in json.loads(Path('data/imbuements.json').read_text(encoding='utf-8')):
            items.extend({'name':i['name']} for i in imb['items'])
        with patch.object(sprites,'download',side_effect=AssertionError('offline test')):
            images=sprites.resolve(items)
        self.assertTrue(all(images.values()))

    def test_animation_bytes_preserved(self):
        manifest=json.loads(Path('web/assets/item_images.json').read_text())
        original=(Path('web/assets/items')/manifest['gold coin']).read_bytes()
        images=sprites.resolve([{'name':'gold coin'}])
        self.assertEqual(base64.b64decode(images['gold coin'].split(',',1)[1]), original)

    def test_plurals_use_bundled_image_without_network(self):
        with patch.object(sprites,'download',side_effect=AssertionError('offline test')):
            images=sprites.resolve([{'name':'gold coins'},{'name':'tomes of knowledge'},{'name':'rope belts'}])
        self.assertTrue(images['gold coins'])
        self.assertTrue(images['rope belts'])
        self.assertTrue(images['tomes of knowledge'])

if __name__=='__main__':unittest.main()
