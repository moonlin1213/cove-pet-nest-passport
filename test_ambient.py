import unittest
from device.ambient import AWAY, next_pose, duration
from device.pet_mood import TRAITS


def profile(wish=None, **traits):
    return {"traits": dict(dict.fromkeys(TRAITS, 50), **traits), "wish": wish}


def choices(p, recent=None, egg=False, allow=True):
    return [next_pose(0, egg, p, recent, roll, 127, allow)[0] for roll in range(256)]


class AmbientTest(unittest.TestCase):
    def test_energy_exploration_and_long_quiet_rests(self):
        lively = profile("play", energy=90, curiosity=90, calm=10)
        quiet = profile("comfort", energy=10, curiosity=10, calm=90)
        self.assertGreater(choices(lively).count(AWAY), choices(quiet).count(AWAY))
        self.assertGreater(choices(quiet).count(2), choices(lively).count(2))
        for pose in (0, 2, 4):
            self.assertGreater(duration(pose, quiet, None, 100), duration(pose, lively, None, 100))
            self.assertGreater(duration(pose, quiet, None, 240), duration(pose, quiet, None, 10))

    def test_every_trait_and_current_care_change_both_rhythm_and_choices(self):
        neutral = profile()
        for trait in TRAITS:
            p = profile(**{trait:100})
            self.assertNotEqual(choices(p), choices(neutral), trait)
            self.assertNotEqual(duration(4,p,None,100), duration(4,neutral,None,100), trait)
        self.assertGreater(choices(neutral,"played").count(2), choices(neutral).count(2))
        self.assertGreater(duration(2,neutral,"played",127), duration(2,neutral,None,127))

    def test_eggs_hunger_and_grace(self):
        self.assertEqual(set(choices(profile(),egg=True)), {1})
        self.assertNotIn(AWAY, choices(profile("feed")))
        self.assertIn(AWAY, choices(profile("feed"),"fed"))
        self.assertNotIn(AWAY, choices(profile(),allow=False))
