import unittest
import numpy as np
from urban_heat_explorer.analysis import analyse_scene,derive_ndvi,validate_scene
from urban_heat_explorer.data import UrbanScene,make_synthetic_scene
class TestHeat(unittest.TestCase):
 def test_ndvi(self): self.assertAlmostEqual(float(derive_ndvi(np.array([.2]),np.array([.6]))[0]),.5)
 def test_scene(self):
  ndvi,uhi,priority,land,rows,scenarios,summary=analyse_scene(make_synthetic_scene());self.assertEqual(len(land),4);self.assertEqual(len(rows),5);self.assertEqual(len(scenarios),3);self.assertGreater(np.count_nonzero(priority),0);self.assertEqual(summary['ndvi_lst_regression']['sample_size'],200);self.assertTrue(np.all((-1<=ndvi)&(ndvi<=1)))
 def test_outside_pixels_are_excluded(self):
  s=make_synthetic_scene(); cover=s.land_cover.copy(); cover[:,:20]=0; lst=s.lst_c.copy(); lst[:,:20]=99.0
  ndvi,uhi,priority,land,rows,scenarios,summary=analyse_scene(UrbanScene(s.red,s.nir,lst,cover))
  self.assertEqual(summary['pixels'],int(np.count_nonzero(cover)));self.assertLess(summary['mean_lst_c'],40);self.assertTrue(np.all(uhi[:,:20]==0));self.assertTrue(np.all(priority[:,:20]==0));self.assertAlmostEqual(sum(r['area_pct'] for r in rows),100,delta=.05)
 def test_bad_shape(self):
  with self.assertRaises(ValueError): validate_scene(UrbanScene(np.ones((2,2)),np.ones((3,2)),np.ones((2,2)),np.ones((2,2))))
if __name__=='__main__': unittest.main()
