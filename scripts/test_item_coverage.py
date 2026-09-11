import unittest, json, io
from PIL import Image
from item_coverage import png_rgba, resolve_texture, repairs, ROOT

class CoverageTests(unittest.TestCase):
    def test_exact_rgba_png(self):
        data=bytes([255,1,2,255,0,0,0,0,5,6,7,128,100,200,42,255])
        with Image.open(io.BytesIO(png_rgba(2,2,data))) as im:
            self.assertEqual(im.convert('RGBA').tobytes(),data)
    def test_invalid_geometry(self):
        for w,h,data in [(0,1,b''),(41,1,b'\0'*164),(1,1,b'bad')]:
            with self.assertRaises(ValueError):png_rgba(w,h,data)
    def test_native_alias_chain(self):
        self.assertEqual(resolve_texture(3705,{'3705':3665,'3665':48}),48)
        with self.assertRaises(ValueError):resolve_texture(1,{'1':2,'2':1})
    def test_repair_set_and_full_crop_checksums(self):
        spec,seed,output,details=repairs()
        self.assertEqual(len(output),112)
        self.assertEqual(len(spec['missingAliasBefore']),62)
        self.assertEqual(spec['newThumbnails'],list(range(6147,6196)))
        for n in spec['newThumbnails']:
            with Image.open(io.BytesIO(output[n])) as im:
                self.assertTrue(im.getbbox()); self.assertEqual(im.mode,'RGBA')
        for n in spec['missingAliasBefore'] + spec.get('correctedExistingAliases', []):
            canonical=details[n]['sourceItemId']
            self.assertEqual(output[n],(ROOT/f'items/item_{canonical}.png').read_bytes())
    def test_source_contract(self):
        spec=json.loads((ROOT/'data/item-coverage-8255d346.json').read_text())
        self.assertEqual(spec['sourceCommit'],'8255d34616c780af12079425ac92a0a7aed87d71')
        self.assertEqual(spec['itemIdCount'],6196)
        self.assertEqual(len(spec['deprecated']),28)

if __name__=='__main__':unittest.main()
