import unittest
from companion import care, pocket_profile


class BridgeTests(unittest.TestCase):
    def test_only_one_selected_pet_and_original_id_reach_owner_care(self):
        calls = []
        def core(path,body):
            calls.append((path,body.copy()))
            return {'receipt_id':'r','grains':11,'results':[{'status':'fed','pet_id':'pet-1','growth_delta':2}]}
        body=dict(action='feed',scope='selected',pet_ids=['pet-1'],request_id='passport-'+'7'*32)
        self.assertEqual(care(core,{'pet-1'},body)['pantry']['grains'],11)
        self.assertEqual(calls,[('/api/care',body)])
        for change in ({'scope':'all'},{'pet_ids':['pet-2']},{'pet_ids':['pet-1','pet-2']}):
            with self.assertRaises(ValueError): care(core,{'pet-1'},dict(body,**change))
        self.assertEqual(len(calls),1)
    def test_hungry_public_pet_keeps_its_six_traits(self):
        from device.pet_mood import TRAITS
        traits=dict.fromkeys(TRAITS,55)
        p=pocket_profile(dict(id='a',traits=traits,satiety=12))
        self.assertEqual((p['personality'],p['wish']['action']),(traits,'feed'))
