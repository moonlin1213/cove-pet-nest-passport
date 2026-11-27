import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


def load(name):
    path = Path(__file__).parent / (name + ".py")
    if path.exists():
        spec = importlib.util.spec_from_file_location("under_test", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m


class PocketPetTests(unittest.TestCase):
    def test_lost_reply_and_reboot_reuse_original_care(self):
        m = load("device/pet_core")
        self.assertIsNotNone(m, "需要能在重启后读取未确认的照顾")
        with TemporaryDirectory() as tmp:
            file = tmp + "/pending.json"
            a = m.start_action(file, "p1", "feed")
            b = m.start_action(file, "p1", "play")
            self.assertEqual(a, b)
            self.assertEqual(a["pet_ids"], ["p1"])
            self.assertEqual(a["scope"], "selected")
            with self.assertRaises(ValueError):
                m.accept_receipt(file, a, {"results":[]})
            self.assertEqual(m.pending(file), a)
            r = {"receipt_id":"r1", "results":[{"pet_id":"p1","status":"full","grain_delta":0,"growth_delta":0}], "pantry":{"grains":11}}
            self.assertEqual(m.accept_receipt(file, a, r), ("full", 11, 0))
            self.assertIsNone(m.pending(file))

    def test_use_current_appearance_only(self):
        m = load("prepare")
        self.assertIsNotNone(m, "需要从同一只宠物的当前阶段选择图集")
        p = {"id":"k", "stage":2, "kind":"cat", "appearance":{"status":"ready"}}
        url = "/api/pet-nest/pets/k/stages/2/asset?v=1234567890abcdef"
        p["current_asset"] = {"stage":2, "asset_url":url}
        self.assertEqual(m.art_url(p), url)
        p["stage"] = 3
        self.assertIsNone(m.art_url(p))
        p["stage"] = 2
        p["current_asset"]["asset_url"] = url.replace("/k/", "/other/")
        self.assertIsNone(m.art_url(p))
        p["appearance"]["status"] = "pending"
        self.assertIsNone(m.art_url(p))

    def test_scene_stream_matches_display_byte_order(self):
        m = load("prepare")
        self.assertIsNotNone(m, "屏幕需要大端 RGB565")
        from PIL import Image
        self.assertEqual(m.rgb565(Image.new("RGB",(1,1),"red")), b"\xf8\x00")

if __name__ == "__main__":
    unittest.main()
