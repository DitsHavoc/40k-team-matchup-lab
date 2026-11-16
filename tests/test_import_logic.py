import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from import_metascribe_singles import army
from wtc_scoring import wtc_battle_points

class DataImportChecks(unittest.TestCase):
 def test_wtc_boundaries(self):
  for difference,expected in [(0,10),(5,10),(6,11),(10,11),(11,12),(15,12),(16,13),(50,19),(51,20),(100,20)]:
   self.assertEqual(wtc_battle_points(100,100-difference),(expected,20-expected))
   self.assertEqual(wtc_battle_points(100-difference,100),(20-expected,expected))
 def test_faction_without_disposition_is_retained(self):
  self.assertEqual(army("<td>Death Guard</td>"),("Death Guard",""))
  self.assertEqual(army("<td>NecronsPurge</td>"),("Necrons","Purge the Foe"))
 def test_marine_chapter_separation(self):
  for chapter in ["Blood Angels","Dark Angels","Space Wolves","Black Templars","Deathwatch","Space Marines"]:
   self.assertEqual(army("<td>"+chapter+"Take</td>"),(chapter,"Take and Hold"))
 def test_no_invention_for_unknown_faction(self):
  self.assertEqual(army("<td>Unknown Forge Army</td>"),(None,None))
 def test_invalid_vp_rejected(self):
  for a,b in [(-1,90),(101,80),(80,101)]:
   with self.assertRaises(ValueError):wtc_battle_points(a,b)
if __name__=="__main__":unittest.main()
