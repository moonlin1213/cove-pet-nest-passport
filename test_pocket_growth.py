import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from pocket_growth import settle
from device.demo_care import demo_record


def event(n, op, pet='cat', at=1795737600, seconds=0):
    return dict(id='passport-'+str(n).zfill(32),pet=pet,op=op,at=at,seconds=seconds)


class GrowthTests(unittest.TestCase):
    def test_paired_growth_is_per_pet_capped_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            room=SimpleNamespace(data=Path(d))
            with sqlite3.connect(room.data/'pets.sqlite3') as db:
                db.execute('CREATE TABLE pets(id TEXT PRIMARY KEY,growth REAL)')
                db.executemany('INSERT INTO pets VALUES(?,0)',[('cat',),('dog',)])
            room.api=lambda path,body: {'results':[{'status':'played','pet_id':'cat'}]}
            def send(row):
                return settle(room,{'cat','dog'},row,now=1795810000)
            for pet in ['cat','dog']:
                self.assertEqual(send(event(1 if pet=='cat' else 2,'wear',pet,seconds=1800))['bonus'],0)
            row=event(3,'wear',seconds=1800)
            self.assertEqual(send(row)['bonus'],1)
            self.assertEqual(send(row)['bonus'],1)
            self.assertEqual(send(event(4,'wear',seconds=18000))['bonus'],3)
            for n in range(4):
                self.assertEqual(send(event(10+n,'play'))['bonus'],int(n<3))
            with sqlite3.connect(room.data/'pets.sqlite3') as db:
                self.assertEqual(dict(db.execute('SELECT * FROM pets')),{'cat':7,'dog':0})
            with self.assertRaises(ValueError):send(dict(row,seconds=3600))

    def test_starter_counts_offline_wear_and_successful_care(self):
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'demo.json')
            for i in range(4):
                row=event(i,'play',at=1)
                self.assertEqual(demo_record(path,row)['bonus'],int(i<3))
                self.assertEqual(demo_record(path,row)['bonus'],int(i<3))
            self.assertEqual(demo_record(path,event(9,'wear',at=2,seconds=3600))['bonus'],1)
            self.assertEqual(json.loads(Path(path).read_text())['growth']['cat'],8)
