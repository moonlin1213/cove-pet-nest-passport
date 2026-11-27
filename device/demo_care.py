"""Local starter pets share one small pantry. No network or account required."""
import json
import os


def load(path):
    try:
        with open(path) as f:
            state = json.load(f)
    except OSError as exc:
        if exc.args[0] != 2:
            raise
        state = {"grains": 12, "growth": {}, "last": None}
    return state

def apply_care(state,body):
    key = body["request_id"]
    if state["last"] and state["last"]["receipt_id"] == key:
        return state["last"]
    pet_id = body["pet_ids"][0]
    action = body["action"]
    status = {"feed": "fed", "play": "played", "comfort": "comforted"}[action]
    delta = 1
    if action == "feed":
        if state["grains"]:
            state["grains"] -= 1
        else:
            status, delta = "no_food", 0
    elif action == "play":
        state["grains"] = min(99, state["grains"] + 1)
    state["growth"][pet_id] = state["growth"].get(pet_id, 0) + delta
    reply = {"receipt_id": key, "pantry": {"grains": state["grains"]},
             "results": [{"pet_id": pet_id, "status": status, "growth_delta": delta}]}
    state["last"] = reply
    return reply

def save(path,state):
    with open(path + ".new", "w") as f:
        json.dump(state, f)
    os.rename(path + ".new", path)

def demo_reply(path,body):
    state=load(path)
    reply=apply_care(state,body)
    save(path,state)
    return reply

def demo_record(path,row):
    state=load(path)
    previous=state.get('record')
    if previous and previous['id']==row['id']:return previous
    pet=row['pet']
    stats=state.setdefault('companions',{}).setdefault(pet,{'remainder':0})
    at=row['at']
    def today():
        day=at//86400
        if stats.get('day')!=day:stats.update(day=day,wear=0,care=0)
    bonus=0
    if row['op']=='wear':
        status='worn'
        seconds=row['seconds']
        while seconds:
            today()
            span=min(seconds,86400-at%86400)
            hours,stats['remainder']=divmod(stats['remainder']+span,3600)
            gain=min(hours,4-stats['wear'])
            stats['wear']+=gain
            bonus+=gain
            at+=span
            seconds-=span
    else:
        today()
        reply=apply_care(state,dict(request_id=row['id'],action=row['op'],pet_ids=[pet]))
        status=reply['results'][0]['status']
        if status in ('played','fed','comforted') and stats['care']<3:
            stats['care']+=1
            bonus=1
    state['growth'][pet]=state['growth'].get(pet,0)+bonus
    state['record']={'id':row['id'],'status':status,'bonus':bonus,'growth':state['growth'][pet]}
    save(path,state)
    return state['record']
