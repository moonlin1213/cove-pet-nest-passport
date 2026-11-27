"""Offline care clock. All durations are powered-on seconds, including screen sleep."""
import binascii
import json
import os


def chance(bond):
    return 0 if bond < 20 else 8 + (bond - 20) * 56 // 80


def interval(kind, age, roll):
    # Game intervals in minutes; a broad jitter keeps each individual on its own clock.
    base = {'dog': 180, 'cat': 240, 'rabbit': 120, 'bird': 90, 'parrot': 95, 'dragon': 300,
            'snow_leopard': 280, 'snake': 480, 'fantasy': 265, 'hamster': 100}.get(kind, 210)
    if age < 30:
        base = base * 2 // 3
    return base * 60 + base * 36 * roll // 255


def new_id():
    return 'passport-' + binascii.hexlify(os.urandom(16)).decode()


class Care:
    def __init__(self, path):
        self.path = path
        self.load()

    def load(self):
        try:
            with open(self.path) as f:
                self.data = json.load(f)
        except OSError as exc:
            if exc.args[0] != 2:
                raise
            self.data = {'clock':0, 'roll':900, 'next_miss':0, 'miss':'', 'pets':{}, 'queue':[]}
        self.saved = self.data['clock']

    def save(self):
        try:
            with open(self.path+'.new','w') as f:
                json.dump(self.data,f)
            os.rename(self.path+'.new',self.path)
        except (OSError, MemoryError):
            self.load()
            raise
        self.saved = self.data['clock']

    def pet(self, key):
        records = self.data['pets']
        if key not in records:
            records[key] = {'bond':0, 'due':0, 'dirty':False, 'since':self.data['clock'], 'last':{}}
        return records[key]

    def bond(self, key):
        return self.pet(key)['bond']

    def advance(self, seconds, pets, rand):
        d = self.data
        now = d['clock'] + seconds
        d['clock'] = now
        changed = False
        candidates = []
        check = now >= d['roll']
        if d['miss'] and not any(m['id']==d['miss'] and not m.get('egg') for m in pets):
            d['miss']=''
            changed=True
        for member in pets:
            if member.get('egg'):
                continue
            key = member['id']
            state = self.pet(key)
            if not state['dirty']:
                if not state['due']:
                    age = member.get('age_days', 7 if member.get('stage',0)==0 else 60)
                    age += (now - state['since']) // 86400
                    born=member.get('born')
                    if born:
                        import time
                        epoch=int(time.time())+(946684800 if time.gmtime(0)[0]==2000 else 0)
                        if epoch>=born:age=(epoch-born)//86400
                    state['due'] = now + interval(member.get('kind'),age,rand())
                    changed = True
                elif now >= state['due']:
                    state['dirty'] = changed = True
            if check and not d['miss'] and now >= max(d['next_miss'],state.get('next_miss',0)):
                if chance(state['bond']) > rand():
                    candidates.append(key)
        if check:
            d['roll'] = now + 900
            if candidates:
                key = candidates[rand()%len(candidates)]
                d['miss'] = key
                d['next_miss'] = now+7200
                self.pet(key)['next_miss'] = now+21600
                changed = True
        if changed or now-self.saved>=300:
            self.save()

    def alert(self, pets, current):
        miss = self.data['miss']
        if miss and any(m['id']==miss and not m.get('egg') for m in pets):
            return ('miss',miss)
        first = None
        for m in pets:
            s = self.data['pets'].get(m['id'])
            if not m.get('egg') and s and s['dirty'] and self.data['clock']>=s.get('later',0):
                if m['id']==current:
                    return ('dirty',current)
                if first is None:
                    first = ('dirty',m['id'])
        return first

    def dismiss(self, kind, key):
        if kind=='miss':
            self.data['miss']=''
        else:
            self.pet(key)['later']=self.data['clock']+900
        self.save()

    def add(self, key, op, event):
        s = self.pet(key)
        now = self.data['clock']
        last = s['last'].get(op)
        if last and (event==last[1] or now-last[0]<600):
            return False
        gain = min(100-s['bond'],3 if op in ('clean','bath') else 2)
        s['bond'] += gain
        s['last'][op] = [now,event]
        if gain:
            self.data['queue'].append([event,key,op,gain])
        return True

    def reward(self, key, op, event):
        if self.add(key,op,event):
            self.save()

    def credit(self,key,op,event,pending_ids):
        # Persist the effect and its replay marker together, before acknowledging a care row.
        seen = self.data.get('credited',[])
        if event in seen:return
        keep = set(pending_ids)
        self.data['credited'] = [old for old in seen if old in keep] + [event]
        self.add(key,op,event)
        self.save()

    def clean(self, key):
        s = self.pet(key)
        if not s['dirty']:
            return 'tidy'
        s['dirty'] = False
        s['due'] = s['later'] = 0
        self.add(key,'clean',new_id())
        self.save()
        return 'cleaned'

    def ack(self, event):
        queue = self.data['queue']
        for index,row in enumerate(queue):
            if row[0]==event:
                queue.pop(index)
                self.save()
                return
