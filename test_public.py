import tempfile
import unittest
from pathlib import Path
from device.demo_care import demo_reply


class StarterTests(unittest.TestCase):
    def test_one_offline_meal_survives_replay_and_reboot(self):
        with tempfile.TemporaryDirectory() as d:
            path = str(Path(d)/'demo.json')
            req = dict(action='feed',pet_ids=['starter-cat'],request_id='abc')
            a = demo_reply(path, req)
            self.assertEqual(a, demo_reply(path, req))
            self.assertEqual(a['results'][0]['status'],'fed')
            self.assertEqual(demo_reply(path, dict(req,request_id='def'))['pantry']['grains'],
                             a['pantry']['grains']-1)
