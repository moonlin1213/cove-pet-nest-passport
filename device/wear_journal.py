"""Crash-recoverable pocket companion journal. Times on the wire are Unix UTC."""
import binascii
import json
import os
import time

def ident():
    return 'passport-'+binascii.hexlify(os.urandom(16)).decode()

def rtc_unix():
    if time.gmtime()[0]<2025:
        return None
    return int(time.time())+(946684800 if time.gmtime(0)[0]==2000 else 0)

class Journal:
    def __init__(self,path,pet,tick,epoch):
        self.path,self.pet,self.tick=path,pet,tick
        self.boot=ident()
        self.elapsed=self.fraction=self.saved_at=0
        self.epoch=epoch
        self.rev,self.rows,self.floor=0,[],None
        for i in range(2):
            try:
                with open(path+str(i)) as f:
                    rev,rows,floor=json.load(f)
                if rev>self.rev:
                    self.rev,self.rows,self.floor=rev,rows,floor
            except (OSError,ValueError):
                pass
        self.open_row=None

    def save(self):
        target=self.path+str((self.rev+1)%2)
        with open(target+'.tmp','w') as f:
            json.dump([self.rev+1,self.rows,self.epoch+self.elapsed if self.epoch is not None else self.floor],f)
        os.rename(target+'.tmp',target)
        self.rev+=1
        self.saved_at=self.elapsed

    def advance(self,tick):
        delta=(time.ticks_diff(tick,self.tick) if hasattr(time,'ticks_diff') else tick-self.tick)
        self.tick=tick
        secs,self.fraction=divmod(self.fraction+max(0,delta),1000)
        if self.pet is None:
            self.elapsed+=secs
            return
        while secs:
            row=self.open_row
            if row is None or row['seconds']==86400:
                row=self.add('wear')
                self.open_row=row
            n=min(secs,86400-row['seconds'])
            row['seconds']+=n
            secs-=n
            self.elapsed+=n
        if self.elapsed-self.saved_at>=300:self.save()

    def add(self,op):
        row={'id':ident(),'op':op,'pet':self.pet,'seconds':0,'at':self.elapsed}
        if self.epoch is None:
            row['boot']=self.boot
            row['floor']=self.floor
        else:row['at']+=self.epoch
        self.rows.append(row)
        return row

    def choose(self,pet):
        self.open_row=None
        self.pet=pet
        self.save()

    def care(self,op,outcome=None,target=None):
        if self.pet is None:raise ValueError("choose a companion")
        self.open_row=None
        row=self.add(op)
        if target is not None:row["pet"]=target
        if outcome:row["outcome"]=outcome
        try:self.save()
        except OSError:
            self.rows.pop()
            raise
        return row['id']

    def calibrate(self,now):
        self.epoch=now-self.elapsed
        changed=False
        for row in self.rows:
            if 'boot' not in row:continue
            if row['boot']==self.boot:
                start=self.epoch
            else:
                # Unknown power-off duration is never credited. If both bounds
                # fall on one Shanghai day, that day's award is unambiguous.
                start=row.get('floor')
                if start is None or (start+28800)//86400!=(now+28800)//86400 or start+row['at']+row['seconds']>now:
                    continue
            row.pop('boot')
            row.pop('floor',None)
            row['at']+=start
            changed=True
        if changed:self.save()

    def front(self):
        for row in self.rows:
            if 'boot' not in row:
                if row is self.open_row:
                    self.open_row=None
                    self.save()
                return row
        return None

    def ack(self,key):
        for i,row in enumerate(self.rows):
            if row['id']==key:
                self.rows.pop(i)
                try:self.save()
                except OSError:
                    self.rows.insert(i,row)
                    raise
                return
        raise ValueError('unknown companion receipt')
