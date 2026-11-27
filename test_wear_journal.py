import tempfile,unittest,os
from device.wear_journal import Journal
class JournalTests(unittest.TestCase):
 def test_switch_offline_care_retry_and_reboot(self):
  with tempfile.TemporaryDirectory() as d:
   path=d+'/book'
   j=Journal(path,'a',0,1800000000)
   j.advance(2400000);j.choose('b');j.advance(3600000)
   j.care('play');j.save()
   k=Journal(path,'b',0,1800005000)
   first=k.front();self.assertEqual((first['pet'],first['seconds']),('a',2400))
   self.assertEqual(k.front(),first)
   k.ack(first['id']);self.assertEqual(k.front()['pet'],'b')
   k.ack(k.front()['id']);self.assertEqual(k.front()['op'],'play')
 def test_uncalibrated_current_boot(self):
  with tempfile.TemporaryDirectory() as d:
   j=Journal(d+'/book','a',0,None);j.advance(90000);j.care('feed')
   self.assertIsNone(j.front())
   j.calibrate(1800000090);self.assertEqual(j.front()['at'],1800000000)
 def test_offline_restart_same_known_civil_day_can_be_reconciled(self):
  with tempfile.TemporaryDirectory() as d:
   path=d+'/book'
   j=Journal(path,'a',0,1800000000);j.advance(60000);j.save()
   k=Journal(path,'b',0,None);k.advance(20000);k.care('comfort')
   m=Journal(path,'a',0,1800000500);m.calibrate(1800000500)
   self.assertTrue(all('boot' not in row for row in m.rows))
   self.assertEqual(sum(r['seconds'] for r in m.rows),80)
 def test_corrupt_latest_snapshot_recovers_last_complete_revision(self):
  with tempfile.TemporaryDirectory() as d:
   path=d+'/book'
   j=Journal(path,'a',0,1800000000);j.advance(300000);j.advance(600000)
   with open(path+str(j.rev%2),'w') as f:f.write('[123,')
   recovered=Journal(path,'a',0,1800000700)
   self.assertEqual(recovered.front()['seconds'],300)
 def test_unselected_time_is_not_given_to_first_pet(self):
  with tempfile.TemporaryDirectory() as d:
   j=Journal(d+'/book',None,0,1800000000);j.advance(3600000);j.choose('b');j.care('play')
   self.assertEqual([(r['pet'],r['op']) for r in j.rows],[('b','play')])
