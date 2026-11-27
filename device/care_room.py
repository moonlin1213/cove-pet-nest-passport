"""Temporary visits are display state only. The wear journal owns the permanent companion."""
import os
import time
try:
    from pet_care import Care, new_id
except ImportError:
    from .pet_care import Care, new_id


class Room:
    def __init__(self,path,pets,portraits,metadata,now):
        self.care = Care(path)
        self.members = pets
        self.profiles = []
        for pet in pets:
            key = pet['id']
            profile = dict(metadata.get(key,{}))
            profile.update(pet)
            profile['egg'] = portraits.get(key,{}).get('egg',profile.get('kind')=='egg' and not profile.get('stage'))
            self.profiles.append(profile)
            baseline = min(100,max(0,int(profile.get('bond',0))))
            self.care.pet(key)['bond']=max(baseline,self.care.bond(key))
        self.home = self.shown = None
        self.tick = now
        self.net = self.last_try = None

    def advance(self,now):
        elapsed = time.ticks_diff(now,self.tick)
        if elapsed >= 1000:
            self.tick = time.ticks_add(self.tick, (elapsed//1000)*1000)
            self.care.advance(elapsed//1000,self.profiles,lambda:os.urandom(1)[0])

    def refresh(self,current):
        self.shown = self.care.alert(self.profiles,current)
        return self.shown

    def enter(self,current):
        kind,key = self.shown
        member = next(m for m in self.members if m['id']==key)
        if kind=='miss':self.care.dismiss(kind,key)
        self.shown = None
        self.home = current
        return member

    def later(self):
        self.care.dismiss(*self.shown)
        self.shown = None

    def leave(self,current):
        result = self.home or current
        self.home = self.shown = None
        return result

    def act(self,op,member):
        key = member['id']
        if any(p.get('egg') for p in self.profiles if p['id']==key):
            return 'care_egg'
        if op=='clean':
            return self.care.clean(key)
        self.care.reward(key,'bath',new_id())
        return 'bathed'

    def sync(self,now,online,config,starter):
        queue = self.care.data['queue']
        if not queue:
            return
        row=next((item for item in queue if any(m['id']==item[1] for m in self.members)),None)
        if row is None:return
        if starter:
            self.care.ack(row[0])
            return
        if not online or not config:
            return
        import json
        try:
            if self.net and self.net.sock is not None:
                reply = self.net.step(now)
                if reply is not None:
                    event = json.loads(reply.decode()).get('id')
                    if event==row[0]:
                        self.care.ack(event)
                        self.last_try = None
                return
            if self.last_try is not None and time.ticks_diff(now,self.last_try)<60000:
                return
            self.last_try = now
            if self.net is None:
                from bridge_sync import BridgeSync
                self.net = BridgeSync()
            self.net.start(config['host'],config['port'],config['token'],'care-log',json.dumps(row).encode(),now)
        except (OSError,ValueError,KeyError,MemoryError):
            if self.net:self.net.close()

    def draw_bond(self,display,key):
        # Pixel lettering for the three digits beside the pre-rendered 亲密 label.
        glyphs = (31599,11415,29671,29647,23497,31183,31215,29257,31727,31695)
        text = str(self.care.bond(key))
        width,height = 24,12
        ink = bytes((74,7))
        pixels = bytearray(bytes((255,156))*(width*height))
        for i,char in enumerate(text):
            bits = glyphs[int(char)]
            for bit in range(15):
                if bits & (1<<(14-bit)):
                    x=i*8+(bit%3)*2
                    y=1+(bit//3)*2
                    for offset in (0,width*2):
                        start=2*(y*width+x)+offset
                        pixels[start:start+4]=ink*2
        display.blit(pixels,211,250,width,height)
