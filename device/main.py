"""Cove Pocket Pet for FoloToy AI Passport MicroPython v0.1.1."""
import gc
import json
import os
import select
import sys
import time
from machine import ADC, Pin
from st7789 import ST7789
from pet_core import accept_receipt, pending, start_action
from pet_link import post_care, get_profile, connect_wifi
from pet_mood import expression
from pocket_games import Round
from pet_labels import MESSAGES

BASE = "/nest/"
PENDING = "/care-pending.json"
ACTIONS = ("play", "feed", "comfort")
display = ST7789()
adc = ADC(Pin(0))
adc.atten(ADC.ATTN_11DB)
active_pack = pending("/pocket-pack.json") or {}
slot = active_pack.get("slot")
pack = BASE + "link-" + slot + "/" if slot in ("a", "b") else BASE
roster = pending(pack + "roster.json")
pets = roster["pets"] if roster else [pending(BASE + "pet.json")]
index = 0
picking = False
if roster:
    from esp32 import NVS
    preferences = NVS("cove_nest")
    saved_id = None
    saved = bytearray(256)
    try:
        length = preferences.get_blob("companion", saved)
        saved_id = bytes(saved[:length]).decode()
    except OSError as exc:
        if exc.args[0] not in (-4354, 4354, 2):
            raise
    unfinished = pending(PENDING)
    wanted = unfinished["pet_ids"][0] if unfinished else saved_id
    for i, member in enumerate(pets):
        if member["id"] == wanted:
            index = i
            break
    else:
        picking = not unfinished
pet = pets[index]
portraits = pending(pack + "portrait.json" if pack != BASE else "/portrait/index.json") or {}
standby = False
ambient_delay = 4000
last_input = time.ticks_ms()
if portraits:
    from pet_portrait import render, empty_room
    from ambient import next_pose, duration, AWAY
trips = {}
home_since = {}
profiles = pending(pack+"moods.json") or {}
has_games = bool(profiles)
recent_care = {}
turns = {}
round_now = None
round_result = None
last_fetch = None
last_reconnect = time.ticks_ms()
config = pending(pack+"wifi.json" if pack != BASE else "/nest-wifi.json")
wlan = None
if config:
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    try:
        connect_wifi(wlan,config)
    except OSError:
        pass

screen_power=session=None
if roster and pending(BASE+"pocket.json"):
    from pocket_screen import PocketScreen, OPTIONS
    from machine import PWM
    backlight=PWM(Pin(21),freq=5000,duty_u16=65535)
    try:timeout=preferences.get_i32("screenidle")
    except OSError:timeout=60
    screen_power=PocketScreen(timeout,last_input,lambda on:backlight.duty_u16(65535 if on else 0))
    if roster.get("starter") or (config and config.get("token")):
        from pocket_session import PocketSession
        session=PocketSession(None if picking else pet["id"],last_input,config,bool(roster.get("starter")))

poll = select.poll()
poll.register(sys.stdin, select.POLLIN)
buf = ""
serial_seen = None
serial_wait = None
selection = 0
pose = 0
message = "idle"
last_pose = time.ticks_ms()
notice_since = last_pose


def draw(file, y, height, x=0, width=240):
    with open(BASE + file + ".rgb", "rb") as f:
        for row in range(0, height, 8):
            n = min(8, height-row)
            display.blit(f.read(2*width*n), x, y+row, width, n)


def notice(key):
    global message, notice_since
    message = key
    notice_since = time.ticks_ms()
    if standby:
        return
    if key == "idle" and not picking and pet["id"] in trips:
        key = "away_hint"
    if key == "idle" and not picking and pet["id"] in profiles:
        profile = profiles[pet["id"]]
        key = expression(profile["traits"],profile["wish"],last_response(),turns.get(pet["id"],0))
    draw(key,240,32)


def growth_line(value):
    draw("growth-label",219,20)
    text=("%.2f"%value).rstrip("0").rstrip(".")
    with open(BASE+"growth-digits.rgb","rb") as digits:
        for i,char in enumerate(text[:16]):
            digits.seek("0123456789.".index(char)*400)
            display.blit(digits.read(400),48+10*i,219,10,20)


def picture(number):
    global pose, last_pose
    pose = number
    last_pose = time.ticks_ms()
    if not picking and pet["id"] in trips:
        empty_room(display,240)
        return
    member = pets[index] if picking else pet
    file = member.get("dir", "") + "pose%d" % number
    if roster and number:
        draw(file,41,139,58,124)
    else:
        draw(file,0,240)
        if session:
            value=member.get("growth")
            if session.starter:
                state=pending("/starter-care.json") or {}
                value=state.get("growth",{}).get(member["id"],0)
            if value is not None:growth_line(value)


def show_standby():
    global standby, picking, round_now, selection, pose, last_pose, ambient_delay, index
    meta = portraits.get(pet["id"])
    if not meta:
        return
    standby = True
    picking = False
    round_now = None
    index = pets.index(pet)
    selection = pose = 0
    pet_id = pet["id"]
    now = time.ticks_ms()
    expire_trip(now, redraw=False)
    if pet_id in trips:
        empty_room(display,320)
    else:
        render(display,meta,0,True)
    if pet_id not in home_since:
        home_since[pet_id] = now
    last_pose = time.ticks_ms()
    ambient_delay = duration(0,profiles.get(pet_id),last_response(),os.urandom(1)[0])


def expire_trip(now, redraw=True):
    pet_id = pet["id"]
    trip = trips.get(pet_id)
    if not trip or time.ticks_diff(now,trip[0]) < trip[1]:
        return
    del trips[pet_id]
    home_since[pet_id] = now
    if redraw and not picking:
        if standby:
            show_standby()
        else:
            picture(0)
            draw(footer(),272,48)
            notice("idle")


def open_menu():
    global standby, selection
    standby = False
    selection = -1 if pet["id"] in trips else 0
    picture(0)
    draw(footer(),272,48)
    notice("retry" if pending(PENDING) else "idle")


def tick_standby(now):
    global pose, ambient_delay, last_pose
    meta = portraits[pet["id"]]
    if pet["id"] in trips or not meta["ready"] or time.ticks_diff(now,last_pose) < ambient_delay:
        return
    profile = profiles.get(pet["id"]) or {}
    allow_away = (not pose and not meta["egg"] and serial_wait is None
                  and time.ticks_diff(now,home_since[pet["id"]]) >= 60000
                  and not pending(PENDING))
    roll,jitter = os.urandom(2)
    pose,ambient_delay = next_pose(pose,meta["egg"],profile,last_response(),roll,jitter,allow_away)
    if pose == AWAY:
        trips[pet["id"]] = (now,ambient_delay)
        empty_room(display,320)
    else:
        render(display,meta,pose,False)
    last_pose = time.ticks_ms()


def linked(now):
    return serial_seen is not None and time.ticks_diff(now, serial_seen) < 6500


def last_response():
    value = recent_care.get(pet["id"])
    if value and time.ticks_diff(time.ticks_ms(),value[1]) < 10*60*1000:
        return value[0]
    return None


def refresh_mind():
    global last_fetch
    last_fetch = time.ticks_ms()
    if wlan and wlan.isconnected():
        try:
            profile = get_profile(config["host"],config["port"],pet["id"],config.get("token"))
            if profile:
                profiles[pet["id"]] = profile
        except (OSError, ValueError, KeyError, IndexError, MemoryError):
            pass


def start_round(ignore_food=False):
    global round_now
    profile = profiles.get(pet["id"])
    if not profile:
        notice("m_unknown")
        return
    n = turns.get(pet["id"],0)
    side = 1+(os.urandom(1)[0] & 1)
    round_now = Round(profile,last_response(),n,time.ticks_ms(),side,ignore_food)
    draw(round_now.card,272,48)


def footer():
    if screen_power and selection==len(ACTIONS)+int(has_games)+int(bool(roster)):
        return "sleep"+str(screen_power.seconds)
    if selection == -1:
        return "summon" if pet["id"] in trips else "home_again"
    if roster and selection == len(ACTIONS)+int(has_games):
        return "action3"
    if has_games and selection == len(ACTIONS):
        return "listen"
    return "action%d" % selection


def settle(body, reply):
    global round_result, last_fetch
    if reply.get("rejected") is True:
        os.remove(PENDING)
        round_result = None
        notice("refused")
        return
    status, grains, growth = accept_receipt(PENDING, body, reply)
    if status in ("fed", "played", "comforted"):
        if not standby:
            picture(3 if status == "fed" else 5)
    recent_care[pet["id"]] = (status,time.ticks_ms())
    last_fetch = None
    if round_result and status in ("comforted","played"):
        notice("r_"+round_result)
    else:
        notice(status if status in MESSAGES else "checked")
    round_result = None


def command(key, long_press=False):
    global selection, serial_wait, picking, index, pet, round_now, round_result, last_fetch
    if serial_wait is not None:
        return
    if standby:
        if key == 3:
            open_menu()
        return
    if long_press and key == 3 and pet["id"] in portraits and not (session and session.book.pet is None):
        show_standby()
        return
    existing = pending(PENDING)
    if picking:
        if key == 3:
            chosen = pets[index]
            preferences.set_blob("companion", chosen["id"].encode())
            preferences.commit()
            if session:session.book.choose(chosen["id"])
            pet = chosen
            last_fetch = None
            picking = False
            selection = 0
            if pet["id"] in portraits:
                show_standby()
                return
            draw("action0",272,48)
            notice("idle")
        else:
            index = (index + (-1 if key == 1 else 1)) % len(pets)
        picture(0)
        return
    if round_now:
        result = round_now.press(key)
        if not result:
            draw(round_now.card,272,48)
            return
        if result in ("another","repeat"):
            start_round(True)
            return
        kind = round_now.kind
        round_now = None
        draw(footer(),272,48)
        if result == "back":
            return
        turns[pet["id"]] = turns.get(pet["id"],0)+1
        round_result = kind if kind != "meal" else None
        send_action(result, existing)
        return
    if key < 3:
        if existing:
            notice("retry")
            return
        first = -1 if pet["id"] in trips else 0
        count = len(ACTIONS) + int(bool(roster)) + int(has_games) + int(bool(screen_power))
        selection = first + (selection-first + (-1 if key == 1 else 1)) % (count-first)
        draw(footer(),272,48)
        return
    if screen_power and footer().startswith("sleep"):
        value=OPTIONS[(OPTIONS.index(screen_power.seconds)+1)%len(OPTIONS)]
        preferences.set_i32("screenidle",value)
        preferences.commit()
        screen_power.seconds=value
        draw(footer(),272,48)
        return
    if selection == -1:
        if pet["id"] in trips:
            del trips[pet["id"]]
            home_since[pet["id"]] = time.ticks_ms()
        show_standby()
        return
    if pet["id"] in trips and not (roster and selection == len(ACTIONS)+int(has_games)):
        notice("call_first")
        return
    if has_games and selection == len(ACTIONS) and not existing:
        refresh_mind()
        start_round()
        return
    if roster and selection == len(ACTIONS)+int(has_games) and not existing:
        picking = True
        picture(0)
        draw("picker",272,48)
        notice("choose")
        return
    send_action(existing["action"] if existing else ACTIONS[selection], existing)


def send_action(action, existing):
    global serial_wait, round_result
    if session and not existing:
        try:session.book.care(action,round_result)
        except OSError:
            notice("storage_full")
            return
        round_result=None
        notice("sending" if session.starter else "queued")
        return
    if roster and roster.get("starter") and pet["id"].startswith("starter-"):
        from demo_care import demo_reply
        body = start_action(PENDING, pet["id"], action)
        settle(body, demo_reply("/starter-care.json", body))
        return
    # Prefer the configured wireless path even while USB supplies power.
    wireless = bool(wlan and wlan.isconnected())
    usb = not wireless and linked(time.ticks_ms())
    if not usb and not wireless:
        round_result = None
        notice("retry" if existing else "offline")
        return
    body = start_action(PENDING, pet["id"], action)
    notice("sending")
    if usb:
        serial_wait = time.ticks_ms()
        print("NEST_CARE " + json.dumps(body))
        return
    try:
        settle(body, post_care(config["host"], config["port"], body,config.get("token")))
    except (OSError, ValueError, KeyError, IndexError):
        notice("retry")


def serial_input():
    global serial_seen, serial_wait, buf
    for i in range(512):
        if not poll.poll(0):
            break
        ch = sys.stdin.read(1)
        if not ch:
            break
        if ch != "\n":
            buf = (buf+ch)[-4096:]
            continue
        line, buf = buf.strip(), ""
        if line == "NEST_PING":
            serial_seen = time.ticks_ms()
        if line.startswith("NEST_REPLY "):
            body = pending(PENDING)
            if not body:
                continue
            try:
                r = json.loads(line[11:])
                if r["id"] != body["request_id"]:
                    continue
                serial_wait = None
                settle(body,r["reply"])
            except (ValueError, KeyError, IndexError, OSError):
                notice("retry")


if pet["id"] in portraits and not (session and picking):
    show_standby()
else:
    picture(0)
    draw("picker" if picking else "action0",272,48)
    notice("retry" if pending(PENDING) else "choose" if picking else "idle")
print("NEST_READY")
candidate = stable = 0
pressed_at = time.ticks_ms()
changed = time.ticks_ms()
while True:
    serial_input()
    now = time.ticks_ms()
    if session:
        try:
            settled=session.tick(now,bool(wlan and wlan.isconnected()))
            if settled:
                row,receipt=settled
                if "growth" in receipt:
                    for member in pets:
                        if member["id"]==row["pet"]:
                            member["growth"]=receipt["growth"]
                            if not standby and not picking and not screen_power.dark and member is pet:
                                growth_line(receipt["growth"])
                            break
                if row["pet"]==pet["id"] and row["op"]!="wear":
                    status=receipt["status"]
                    recent_care[pet["id"]]=(status,now)
                    last_fetch=None
                    if not standby and not picking and not round_now and not screen_power.dark:
                        if status in ("fed","played","comforted"):picture(3 if status=="fed" else 5)
                        notice("r_"+row["outcome"] if row.get("outcome") and status in ("played","comforted") else status if status in MESSAGES else "checked")
        except (OSError,ValueError,MemoryError):pass
    if trips:
        expire_trip(now,redraw=not (screen_power and screen_power.dark))
    if serial_wait is not None and time.ticks_diff(now, serial_wait) > 8500:
        serial_wait = None
        notice("retry")
    if round_now:
        previous_card = round_now.card
        round_now.tick(time.ticks_diff(now,round_now.start))
        if round_now.card != previous_card:
            draw(round_now.card,272,48)
            if round_now.card in ("paw_now","quiet_now"):
                picture(5)
    if config and wlan and not wlan.isconnected() and time.ticks_diff(now,last_reconnect)>30000:
        last_reconnect = now
        try:
            connect_wifi(wlan,config)
        except OSError:
            pass
    if has_games and wlan and wlan.isconnected() and not picking and not round_now and not serial_wait and (
        last_fetch is None or time.ticks_diff(now,last_fetch)>90000):
        refresh_mind()
        if message == "idle":
            notice("idle")
    mv = adc.read_uv() // 1000
    key = 1 if mv < 150 else 2 if mv < 447 else 3 if mv < 1900 else 0
    if screen_power:
        was_dark=screen_power.dark
        consumed=screen_power.update(now,key,bool(round_now or serial_wait))
        if was_dark and not screen_power.dark and standby:show_standby()
        if consumed or screen_power.dark:
            stable=candidate=0
            if consumed:last_input=now
            time.sleep_ms(25)
            continue
    if key != candidate:
        candidate, changed = key, now
    elif key != stable and time.ticks_diff(now, changed) >= 55:
        previous, stable = stable, key
        if stable:
            pressed_at = now
            last_input = now
        if previous and not stable:
            last_input = now
            command(previous, time.ticks_diff(now,pressed_at)>=800)
    if standby:
        tick_standby(now)
        time.sleep_ms(20)
        continue
    if (pet["id"] in portraits and not (session and session.book.pet is None) and not stable and not round_now and serial_wait is None
            and time.ticks_diff(now,last_input)>=18000):
        show_standby()
        continue
    if pose and time.ticks_diff(now,last_pose) > (260 if pose == 1 else 1600):
        picture(0)
    elif not pose and (picking or pet["id"] not in trips) and time.ticks_diff(now,last_pose) > 5800:
        picture(1)
    if message not in ("idle","retry","sending","choose") and time.ticks_diff(now,notice_since) > 5500:
        notice("idle")
    time.sleep_ms(20)
