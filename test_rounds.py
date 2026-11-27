from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).parent/"device"))
from pocket_games import Round

class RoundTests(unittest.TestCase):
    def make(self, kind, **kw):
        t=dict.fromkeys(("attachment","energy","curiosity","sociability","calm","sensitivity"),25)
        t.update(kw)
        r=Round({"traits":t,"wish":"feed" if kind=="meal" else None},None,0,0,2)
        self.assertEqual(r.kind,kind)
        return r

    def test_star_only_the_hidden_side_completes_play(self):
        r=self.make("star",curiosity=99)
        self.assertIsNone(r.press(2))
        r.tick(r.pace)
        self.assertIsNone(r.press(1))
        self.assertEqual(r.press(2),"play")

    def test_tap_needs_a_timed_response(self):
        r=self.make("tap",energy=95,sociability=98,curiosity=10)
        self.assertIsNone(r.press(3))
        r.tick(r.pace)
        self.assertEqual(r.press(3),"play")
        r.tick(r.pace+2500)
        self.assertEqual(r.press(3),"repeat")

    def test_breathing_waits_for_both_phases(self):
        r=self.make("rain",calm=95,attachment=95,sensitivity=80)
        r.tick(r.pace)
        self.assertIsNone(r.press(3))
        r.tick(2*r.pace)
        self.assertEqual(r.press(3),"comfort")

    def test_hunger_offers_feed_or_another_activity(self):
        r=self.make("meal")
        self.assertEqual(r.press(2),"another")
        self.assertEqual(r.press(3),"feed")
