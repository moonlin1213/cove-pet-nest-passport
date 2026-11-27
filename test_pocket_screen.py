import unittest
from device.pocket_screen import PocketScreen

class SleepTests(unittest.TestCase):
    def test_dark_wake_press_is_consumed_until_release(self):
        lights=[]
        screen=PocketScreen(60,0,lights.append)
        screen.update(60000,0,False)
        self.assertTrue(screen.dark)
        for t,key in [(60100,3),(61000,3),(61200,0)]:
            self.assertTrue(screen.update(t,key,False))
        self.assertFalse(screen.update(61300,3,False))
        screen.update(122000,0,True)
        self.assertEqual(lights,[False,True])
