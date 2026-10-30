from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acquire_candidates import TableParser

class TableIntegrityTests(unittest.TestCase):
    def test_units_exponents_and_merged_cells_remain_distinguishable(self):
        parser=TableParser()
        parser.feed('<p>Таблица 5.2 — Концентрации, мг/м<sup>3</sup></p><table><tr><th rowspan="2">Вещество</th><th colspan="2">Показатель</th></tr><tr><td>10<sup>-3</sup></td><td>не более 0,1</td></tr></table>')
        table=parser.tables[0]
        self.assertEqual(table['label'],'Таблица 5.2')
        self.assertIn('м^{3}',table['preceding_context'])
        self.assertEqual(table['rows'][0][0]['rowspan'],2)
        self.assertEqual(table['rows'][0][1]['colspan'],2)
        self.assertEqual(table['rows'][1][0]['text'],'10^{-3}')
        self.assertEqual(table['rows'][1][1]['text'],'не более 0,1')

    def test_formula_image_is_flagged_instead_of_silently_lost(self):
        parser=TableParser();parser.feed('<table><tr><td><img src="/formula.png"></td></tr></table>')
        cell=parser.tables[0]['rows'][0][0]
        self.assertTrue(cell['images'][0]['requires_review'])
        self.assertIn('FORMULA/IMAGE',cell['text'])

if __name__=='__main__':unittest.main()
