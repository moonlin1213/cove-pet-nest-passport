import io
import json
import sys
import unittest
from unittest.mock import patch

from device import pet_core
import usb_live


class StopLoop(Exception):
    pass


class Cable:
    def __init__(self, attempts):
        self.data = iter(attempts)
        self.written = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def readline(self, _):
        try:
            packet = next(self.data)
        except StopIteration:
            raise StopLoop
        return b"NEST_CARE " + json.dumps(packet).encode() + b"\n"

    def write(self, data):
        self.written.append(data)


class USBTests(unittest.TestCase):
    def test_lost_reply_replay_and_restrict_other_pet(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            path = tmp+"/pending.json"
            body = pet_core.start_action(path, "fiction", "feed")
            cable = Cable([dict(body, pet_ids=["wrong"]), body, body])
            seen = []
            pantry = {"grains":7}
            receipts = {}

            def cove(request, timeout):
                packet = json.loads(request.data)
                seen.append(packet)
                key = packet["request_id"]
                if key not in receipts:
                    pantry["grains"] -= 1
                    receipts[key] = dict(receipt_id="r", pantry=pantry.copy(),
                        results=[dict(pet_id="fiction",status="fed",grain_delta=-1,growth_delta=2)])
                    raise TimeoutError("committed but reply lost")
                return io.BytesIO(json.dumps(receipts[key]).encode())

            with patch.object(usb_live.serial, "Serial", return_value=cable), patch.object(usb_live,"urlopen",cove):
                with self.assertRaises(StopLoop):
                    usb_live.serve("/fake",{"first","fiction"},"http://fiction.invalid")
            self.assertEqual(seen, [body, body])
            replies = [json.loads(x[11:]) for x in cable.written if x.startswith(b"NEST_REPLY ")]
            self.assertEqual(len(replies),1)
            self.assertEqual(replies[0]["id"],body["request_id"])
            self.assertEqual(pet_core.accept_receipt(path,body,replies[0]["reply"]),("fed",6,2))
