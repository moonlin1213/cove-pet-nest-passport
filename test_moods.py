import io
import unittest
from unittest.mock import patch
from device import pet_link
try:
    from device import pet_mood as mood
except ImportError:
    mood = None


class MoodTests(unittest.TestCase):
    def test_six_live_traits_each_change_scores_and_timing(self):
        self.assertIsNotNone(mood)
        base = dict.fromkeys(mood.TRAITS, 50)
        original = mood.scores(base, None, None)
        self.assertEqual(len(base), 6)
        for trait in base:
            changed = dict(base, **{trait:90})
            self.assertNotEqual(original, mood.scores(changed,None,None),trait)
        energetic = dict(base,energy=90,curiosity=85,calm=10,attachment=20)
        calm = dict(base,energy=10,curiosity=20,calm=95,sensitivity=83)
        self.assertNotEqual(mood.invitation(energetic,None,None,0)[0],mood.invitation(calm,None,None,0)[0])

    def test_hunger_and_recent_care_change_invitation(self):
        self.assertIsNotNone(mood)
        base = dict.fromkeys(mood.TRAITS, 50)
        self.assertEqual(mood.invitation(base,'feed',None,0)[0],'meal')
        self.assertNotEqual(mood.scores(base,'comfort',None), mood.scores(base,'play',None))
        self.assertNotEqual(mood.scores(base,None,'comforted'), mood.scores(base,None,'played'))

    def test_bounded_profile_stream_handles_escaped_strings_and_other_pets(self):
        self.assertTrue(hasattr(pet_link,'read_profile'))
        import json
        fake = dict(pet_id='first',name='奇}妙" ]',family={'text':'x'*800})
        target = dict(pet_id='second',personality=dict.fromkeys(mood.TRAITS,60),wish={'action':'feed'})
        f = io.BytesIO(json.dumps({'pets':[fake,target],'events':['x'*100000]}).encode())
        result = pet_link.read_profile(f, 'second')
        self.assertEqual(result['wish'],'feed')
        self.assertEqual(result['traits'],target['personality'])
        self.assertLess(f.tell(),4096)

    def test_same_hunger_can_look_different_for_two_pets(self):
        self.assertTrue(hasattr(mood,'expression'))
        base=dict.fromkeys(mood.TRAITS,50)
        shy=dict(base,calm=90,sensitivity=80,energy=5)
        bright=dict(base,energy=90,sociability=95,calm=5)
        self.assertNotEqual(mood.expression(shy,'feed',None,0),mood.expression(bright,'feed',None,0))
        self.assertEqual(mood.invitation(shy,'feed',None,0)[0],'meal')

    def test_unknown_trait_values_do_not_give_an_invented_profile(self):
        self.assertIsNotNone(mood)
        self.assertIsNone(mood.compact({'personality':{'energy':60}}))

if __name__ == '__main__':
    unittest.main()
