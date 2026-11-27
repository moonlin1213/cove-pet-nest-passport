import time
OPTIONS=(30,60,300,0)
class PocketScreen:
    def __init__(self,seconds,now,light):
        self.seconds=seconds if seconds in OPTIONS else 60
        self.active=now
        self.light=light
        self.dark=False
        self.consume=False

    def update(self,now,key,busy):
        if self.dark and (key or busy):
            self.light(True)
            self.dark=False
            self.consume=bool(key)
        if key or busy or self.consume:
            self.active=now
        elif self.seconds and not self.dark:
            delta=time.ticks_diff(now,self.active) if hasattr(time,'ticks_diff') else now-self.active
            if delta>=self.seconds*1000:
                self.light(False)
                self.dark=True
        if self.consume:
            if not key:self.consume=False
            return True
        return False
