import importlib.util
import io
from pathlib import Path
import unittest
import zlib
from PIL import Image

class PortraitTests(unittest.TestCase):
    def test_each_packed_frame_has_room_for_clear_transparency_and_pixels(self):
        self.assertIsNotNone(importlib.util.find_spec("portrait_assets"),"缺少全屏精灵编码")
        from portrait_assets import pack_frame
        cell=Image.new("RGBA",(45,66),(0,0,0,0))
        cell.paste((255,46,80,255),(2,3,40,60))
        data=pack_frame(cell)
        colors=data[0] or 256
        plane=zlib.decompress(data[1+2*colors:])
        self.assertEqual(len(plane),45*66)
        self.assertEqual(plane[0],0)
        self.assertNotEqual(plane[4*45+3],0)

    def test_rest_never_shows_food_or_earned_affection(self):
        self.assertIsNotNone(importlib.util.find_spec("device.ambient"),"缺少待机姿势调度")
        from device.ambient import next_pose
        for egg in (True,False):
            poses={next_pose(0,egg,{},None,n,127,False)[0] for n in range(256)}
            if egg: self.assertEqual(poses,{1})
            else: self.assertTrue({1,2,4}<=poses)
            self.assertNotIn(3,poses)
            self.assertNotIn(5,poses)
