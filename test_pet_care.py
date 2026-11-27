import tempfile
import unittest
from pathlib import Path
from device.wear_journal import Journal

class CareTests(unittest.TestCase):
    def test_visit_targets_only_the_guest(self):
        with tempfile.TemporaryDirectory() as d:
            book = Journal(d+'/wear','A',0,1700000000)
            book.advance(60000)
            book.care('comfort', target='B')
            book.advance(120000)
            self.assertEqual([(r['pet'],r['seconds']) for r in book.rows if r['op']=='wear'], [('A',60),('A',60)])
            self.assertEqual([r['pet'] for r in book.rows if r['op']=='comfort'], ['B'])
            from device.pet_care import Care
            c = Care(d+'/care')
            c.reward('B','comfort','event1'); c.reward('B','comfort','event1')
            self.assertEqual((c.bond('A'),c.bond('B')), (0,2))
            self.assertEqual(Care(d+'/care').bond('B'),2)

    def test_dirty_alert_survives_until_cleaned(self):
        from device.pet_care import Care
        with tempfile.TemporaryDirectory() as d:
            c=Care(d+'/care')
            pets=[dict(id='B',kind='cat',age_days=1),dict(id='egg',egg=True)]
            c.advance(0,pets,lambda:0); c.advance(4*3600,pets,lambda:0)
            self.assertEqual(c.alert(pets,'B'),('dirty','B'))
            self.assertEqual(c.clean('B'),'cleaned')
            self.assertIsNone(Care(d+'/care').alert(pets,'B'))
            self.assertEqual(c.clean('B'),'tidy')
            self.assertEqual(c.bond('B'),3)
            self.assertEqual(c.bond('egg'),0)

    def test_miss_threshold_probability_and_defer(self):
        from device.pet_care import Care, chance, interval
        self.assertEqual(chance(19),0)
        self.assertLess(chance(20),chance(90))
        self.assertLess(interval('cat',4,0),interval('cat',90,0))
        self.assertNotEqual(interval('cat',4,0),interval('dog',4,0))
        self.assertLess(interval('dog',4,0),interval('dog',4,255))
        with tempfile.TemporaryDirectory() as d:
            c=Care(d+'/care'); pets=[{'id':'A'},{'id':'B'}]
            for i in range(10):
                c.advance(600,pets,lambda:255)
                c.reward('B','comfort',str(i))
            c.advance(900,pets,lambda:0)
            self.assertEqual(c.alert(pets,'A'),('miss','B'))
            c.dismiss('miss','B')
            self.assertNotEqual(Care(d+'/care').alert(pets,'A'), ('miss','B'))

    def test_click_visit_defer_clean_and_return(self):
        from device.care_room import Room
        with tempfile.TemporaryDirectory() as d:
            a,b={'id':'A'},{'id':'B'}
            room=Room(d+'/local',[a,b],{}, {},0)
            room.care.pet('B')['dirty']=True
            self.assertEqual(room.refresh('A'),('dirty','B'))
            guest=room.enter(a)
            self.assertIs(guest,b)
            self.assertEqual(room.act('clean',guest),'cleaned')
            self.assertEqual(room.act('bath',guest),'bathed')
            self.assertEqual(room.leave(guest),a)
            self.assertIsNone(room.refresh('A'))
            self.assertEqual([room.care.bond(k) for k in ['A','B']],[0,6])

    def test_failed_local_affinity_save_keeps_food_receipt_replayable(self):
        import sys
        from unittest.mock import patch
        from types import SimpleNamespace as NS
        with patch.dict(sys.path_importer_cache),patch.object(sys,'path',[str(Path(__file__).parent/'device')]+sys.path):
            from pocket_session import PocketSession
            with tempfile.TemporaryDirectory() as d:
                book=Journal(d+'/wear','A',0,1700000000)
                key=book.care('feed',target='B')
                session=PocketSession.__new__(PocketSession)
                session.book,session.starter,session.net=book,True,NS(sock=None)
                import demo_care
                def full(*_):raise OSError('storage full')
                session.before_ack=full
                with patch.object(demo_care,'demo_record',return_value={'id':key,'status':'fed'}):
                    with self.assertRaises(OSError):session.tick(0,False)
                    self.assertEqual(Journal(d+'/wear','A',0,1700000000).rows[0]['id'],key)
                    session.before_ack=lambda *_:None
                    session.tick(0,False)
                    self.assertFalse(book.rows)

    def test_unselected_old_pet_does_not_block_active_pet(self):
        from device.care_room import Room
        from types import SimpleNamespace as NS
        with tempfile.TemporaryDirectory() as d:
            room=Room(d+'/care',[{'id':'B'}],{},{},0)
            room.care.reward('A','bath','a');room.care.reward('B','bath','b')
            room.net=NS(sock=None,start=lambda *a:sent.append(a))
            sent=[]
            room.sync(0,True,{'host':'fake','token':'test','port':1},False)
            import json
            self.assertEqual(json.loads(sent[0][-2])[0],'b')
            room.care.ack('b')
            self.assertEqual([r[0] for r in room.care.data['queue']],['a'])

    def test_delayed_receipt_does_not_reward_precredited_touch_again(self):
        from device.pet_care import Care
        with tempfile.TemporaryDirectory() as d:
            c=Care(d+'/care')
            c.credit('B','comfort','old',['old'])
            c.advance(700,[{'id':'B'}],lambda:255)
            c.credit('B','comfort','new',['old','new'])
            c.advance(700,[{'id':'B'}],lambda:255)
            c.credit('B','comfort','old',['old','new'])
            self.assertEqual(c.bond('B'),4)
