"""Keep the selected pet's offline records until their own home acknowledges them."""
import json
import time
from wear_journal import Journal, rtc_unix
from bridge_sync import BridgeSync


class PocketSession:
    def __init__(self,pet,now,config,starter):
        self.config=config
        self.starter=starter
        if starter:
            path='/starter-wear'
        else:
            import hashlib,binascii
            tag=binascii.hexlify(hashlib.sha256(config['token'].encode()).digest()[:8]).decode()
            path='/wear-'+tag
        self.book=Journal(path,pet,now,rtc_unix() if not starter else None)
        if starter:self.book.epoch=self.book.floor or 0
        self.net=BridgeSync()
        self.last_try=self.last_clock=None

    def clock(self,stamp,now):
        if stamp<1735689600:raise ValueError('invalid date')
        from machine import RTC
        date=time.gmtime(stamp-(946684800 if time.gmtime(0)[0]==2000 else 0))
        RTC().datetime((date[0],date[1],date[2],date[6],date[3],date[4],date[5],0))
        self.book.calibrate(stamp)
        self.last_clock=now

    def tick(self,now,online):
        book=self.book
        book.advance(now)
        if self.net.sock is not None:
            try:
                data=self.net.step(now)
                if data is None:return
                if self.net.path=='clock':
                    self.clock(int(data),now)
                    return
                row=self.net.entry
                result=json.loads(data.decode())
                if result.get('id')!=row['id']:raise ValueError('wrong receipt')
                book.ack(row['id'])
                return row,result
            except (OSError,ValueError,IndexError,KeyError,MemoryError):
                self.net.close()
                return
        if not self.starter:
            if not online or self.last_try is not None and time.ticks_diff(now,self.last_try)<1500:return
            if self.last_clock is None or time.ticks_diff(now,self.last_clock)>=3600000:
                self.last_try=now
                self.start('clock',b'',now)
                return
        if not any('boot' not in row and (row is not book.open_row or row['seconds']>=300) for row in book.rows):return
        row=book.front()
        if row is None:return
        if self.starter:
            from demo_care import demo_record
            result=demo_record('/starter-care.json',row)
            book.ack(row['id'])
            return row,result
        self.last_try=now
        self.net.entry=row
        body=json.dumps({k:v for k,v in row.items() if k!='outcome'}).encode()
        self.start('companion',body,now)

    def start(self,path,data,now):
        cfg=self.config
        self.net.start(cfg['host'],cfg['port'],cfg['token'],path,data,now)
