import sqlite3, tempfile, unittest
from pathlib import Path

class SyncTests(unittest.TestCase):
    def test_replayed_delivery_credits_only_the_named_pet_once(self):
        from affinity_sync import record,total
        with tempfile.TemporaryDirectory() as d, sqlite3.connect(Path(d)/'nest.sqlite') as db:
            event=['passport-'+'a'*32,'guest','clean',3]
            self.assertRaises(ValueError,record,db,['home'],event)
            self.assertEqual(record(db,['guest'],event),record(db,['guest'],event))
            self.assertEqual([total(db,key) for key in ['home','guest']],[0,3])
            self.assertRaises(ValueError,record,db,['guest'],event[:2]+['bath',3])
