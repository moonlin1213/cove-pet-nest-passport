"""Drive the real menu handlers with a temporary store and two named pets."""
import ast
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from device.care_room import Room
from device.wear_journal import Journal


def exercise(test, root):
    source = (root/'device/main.py').read_text()
    tree = ast.parse(source)
    names = {'command','show_standby','send_action','footer','care_footer_start','standby_notice'}
    tree.body = [n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    device_time = NS(ticks_ms=lambda:60000,ticks_diff=lambda a,b:a-b)
    with tempfile.TemporaryDirectory() as tmp:
        a,b = {'id':'A','dir':'a/'},{'id':'B','dir':'b/'}
        portraits = {m['id']:{'ready':True,'egg':False} for m in (a,b)}
        room = Room(tmp+'/care',[a,b],portraits,{},0)
        book = Journal(tmp+'/wear','A',0,1700000000)
        book.advance(60000)
        room.care.pet('B')['dirty']=True
        room.care.data['miss']='B'
        room.refresh('A')
        events = []
        def show(tag):
            return lambda *args:events.append((tag,*args))
        def open_menu():
            g.update(standby=False,selection=0)
        g=dict(care_room=room,pet=a,pets=[a,b],portraits=portraits,trips={},home_since={},has_games=False,
               roster=True,profiles={},serial_wait=None,round_now=None,round_result=None,standby=True,
               index=0,picking=False,ACTIONS=('play','feed','comfort'),PENDING='pending',pending=lambda p:None,
               journal=book,session=NS(book=book,starter=False),screen_power=NS(seconds=60),
               time=device_time,draw=show('draw'),notice=show('notice'),picture=show('picture'),open_menu=open_menu,
               paint_standby=show('home'),render=show('render'),display=None,duration=lambda *a:6000,
               last_response=lambda:None,os=__import__('os'),expire_trip=lambda *a,**kw:None,
               last_input=0,voice=None,outdoor=None,wlan=None,linked=lambda n:False,care_progress=lambda *a:'queued')
        exec(compile(tree,'menu handlers','exec'),g)
        press=g['command']
        press(3)
        test.assertIs(g['pet'],b)
        test.assertEqual(g['selection'],2)
        press(3)  # 摸摸
        # Reach bath using only the real ▼ navigation.
        for _ in range(12):
            if g['footer']()=='care_bath':break
            press(2)
        test.assertEqual(g['footer'](),'care_bath')
        press(3)
        press(3,True)
        test.assertIs(g['pet'],a)
        test.assertEqual(room.refresh('A'),('dirty','B'))
        press(3)
        test.assertEqual(g['footer'](),'care_clean')
        press(3)
        test.assertIn(('notice','cleaned'),events)
        press(3)
        test.assertIn(('notice','tidy'),events)
        g['show_standby']()  # The idle timeout uses this same exit.
        test.assertIs(g['pet'],a)
        test.assertIsNone(room.refresh('A'))
        book.advance(120000)
        test.assertEqual([room.care.bond(k) for k in ('A','B')],[0,8])
        test.assertEqual({r['pet'] for r in book.rows if r['op']=='wear'},{'A'})
        test.assertEqual(sum(r['seconds'] for r in book.rows if r['op']=='wear'),120)
        test.assertEqual([r['pet'] for r in book.rows if r['op']=='comfort'],['B'])


class VisitTest(unittest.TestCase):
    def test_two_pet_visit(self):
        exercise(self,Path(__file__).parent)
