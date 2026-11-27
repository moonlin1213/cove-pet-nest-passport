"""Run the device entry point with synthetic ADC samples, strips and a serial peer."""
import builtins
import contextlib
import io
import json
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class EndOfTrace(Exception):
    pass


class Screen:
    def __init__(self):
        self.status = []

    def blit(self, data, x, y, w, h):
        assert len(data) == 2*w*h
        if y == 240:
            self.status.append(data[:1])


class ButtonsTest(unittest.TestCase):
    def test_play_requires_online_button_and_actual_receipt(self):
        self.trace(False)

    def test_choose_second_pet_offline_then_play_with_that_pet(self):
        self.trace(True)

    def test_switch_again_and_restore_choice_on_next_boot(self):
        stored = self.trace(True, again=True)
        self.trace(True, saved=stored)

    def test_portrait_wakes_only_with_ok_then_returns_without_care(self):
        self.trace(False, portrait=True)

    def test_away_ok_menu_then_ok_summons_or_acknowledges_natural_return(self):
        for summon in (True, False):
            self.trace(False, portrait=True, outing=True, summon=summon)

    def trace(self, multi, again=False, saved=None, portrait=False, outing=False, summon=True):
        root = Path(__file__).parent.resolve()
        with tempfile.TemporaryDirectory() as tmp:
            fs = Path(tmp)
            nest = fs/"nest"
            nest.mkdir()
            (nest/"pet.json").write_text('{"id":"fiction","name":"Mooncat"}')
            ids = ["fiction", "second"]
            if multi:
                (nest/"roster.json").write_text(json.dumps({"pets":[
                    {"id":pet_id, "dir":"p%d/" % i, "name":pet_id} for i,pet_id in enumerate(ids)]}))
            stored = {} if saved is None else saved.copy()
            class NVS:
                def __init__(self, ns): pass
                def get_blob(self, key, buf):
                    if key not in stored:
                        raise OSError(-4354)
                    value = stored[key]
                    buf[:len(value)] = value
                    return len(value)
                def set_blob(self, key, value): stored[key] = bytes(value)
                def commit(self): pass
            paintings = []
            ui_files = []
            if portrait:
                (fs/"portrait").mkdir()
                (fs/"portrait/index.json").write_text('{"fiction":{"egg":false,"ready":true}}')
            if outing:
                (nest/"moods.json").write_text(json.dumps({"fiction":{"traits": dict.fromkeys(
                    ("energy","calm","attachment","sensitivity","sociability","curiosity"),50),"wish":"play"}}))
            tick = [0]
            rx = []
            tx = []
            screen = Screen()
            source_open = builtins.open
            def device_open(path, *args, **kwargs):
                if isinstance(path,str) and path.startswith("/"):
                    if path.endswith(".rgb"):
                        ui_files.append((tick[0],Path(path).stem))
                        marker = {"played":b"Y","offline":b"N"}.get(Path(path).stem,b"x")
                        return io.BytesIO(marker*115200)
                    path = fs/path.lstrip("/")
                return source_open(path,*args,**kwargs)
            def advance(ms):
                tick[0] += ms
                if tick[0] == (900 if multi else 400):
                    rx.extend("NEST_PING\n")
                if tick[0] > (120000 if outing else 45000 if portrait else 3200 if again else 1500):
                    raise EndOfTrace
            def unit_print(*args, **kwargs):
                line = str(args[0])
                if line.startswith("NEST_CARE "):
                    body = json.loads(line[10:])
                    tx.append(body)
                    receipt = {"receipt_id":"one","results":[{"pet_id":body["pet_ids"][0],"status":"played","growth_delta":2}],
                               "pantry":{"grains":5}}
                    rx.extend("NEST_REPLY "+json.dumps({"id":body["request_id"],"reply":receipt})+"\n")
            class ADC:
                ATTN_11DB=3
                def __init__(self,pin): pass
                def atten(self,v): pass
                def read_uv(self):
                    if outing:
                        empty_at = next((t for t, pose, full in paintings if pose == -1), None)
                        if empty_at is not None:
                            dt=tick[0]-empty_at
                            if 100 < dt < 260 or (500 if summon else 12500) < dt < (660 if summon else 12660):
                                return 900000
                        return 3100000
                    if portrait:
                        if 90<tick[0]<260: return 300000
                        if 10800<tick[0]<11000 or 11200<tick[0]<12500 or 17000<tick[0]<17200: return 900000
                        return 3100000
                    if multi:
                        if saved:
                            return 900000 if 1000 <= tick[0] < 1120 else 3100000
                        if again:
                            if 1600 <= tick[0] < 1740: return 50000
                            if 1900 <= tick[0] < 2050 or 2500 <= tick[0] < 2640 or 2800 <= tick[0] < 2960: return 900000
                            if 2200 <= tick[0] < 2340: return 300000
                        if 80 <= tick[0] < 200: return 300000
                        if 350 <= tick[0] < 470 or 1000 <= tick[0] < 1120: return 900000
                        return 3100000
                    return 900000 if (80 <= tick[0] < 210 or 520 <= tick[0] < 670) else 3100000
            machine = types.SimpleNamespace(ADC=ADC,Pin=lambda n:n)
            poll = types.SimpleNamespace(register=lambda *a:None,poll=lambda wait:bool(rx))
            fake_time=types.SimpleNamespace(ticks_ms=lambda:tick[0],ticks_diff=lambda a,b:a-b,sleep_ms=advance)
            import os
            real_rename, real_remove = os.rename, os.remove
            with contextlib.ExitStack() as s:
                for obj in [
                    patch.dict(sys.modules,{"machine":machine,"pet_portrait":types.SimpleNamespace(empty_room=lambda display,height:paintings.append((tick[0],-1,height==320)), render=lambda display,meta,pose,full:paintings.append((tick[0],pose,full))),"esp32":types.SimpleNamespace(NVS=NVS),"st7789":types.SimpleNamespace(ST7789=lambda:screen),
                                          "select":types.SimpleNamespace(poll=lambda:poll,POLLIN=1),"time":fake_time}),
                    patch.object(sys,"stdin",types.SimpleNamespace(read=lambda n:rx.pop(0))),
                    patch.object(builtins,"open",device_open),patch.object(builtins,"print",unit_print),
                    patch.object(os,"rename",lambda a,b:real_rename(fs/a.lstrip("/"),fs/b.lstrip("/"))),
                    patch.object(os,"remove",lambda a:real_remove(fs/a.lstrip("/"))),
                    patch.object(sys,"path",[str(root/"device")]+sys.path)]:
                    s.enter_context(obj)
                if outing:
                    s.enter_context(patch.object(os,"urandom",lambda n:(bytes([255,0])*n)[:n]))
                with self.assertRaises(EndOfTrace):
                    runpy.run_path(str(root/"device"/"main.py"),run_name="__main__")
            if outing:
                self.assertIn("summon",[name for _,name in ui_files])
                self.assertEqual(tx,[])
                self.assertFalse((fs/"care-pending.json").exists())
                self.assertTrue(any(pose==0 and full and t>0 for t,pose,full in paintings))
                if not summon:
                    self.assertIn("home_again",[name for _,name in ui_files])
                return
            if portrait:
                self.assertEqual(tx, [])
                self.assertTrue(paintings)
                self.assertEqual(paintings[0],(0,0,True))
                self.assertTrue(any(pose for t,pose,_ in paintings if t<10800))
                self.assertTrue(all(t>=11000 for t,name in ui_files))
                self.assertEqual(len([1 for t,pose,full in paintings if full]),3)
                return
            self.assertEqual([b["action"] for b in tx],["play","play"] if again else ["play"])
            if multi:
                if again:
                    self.assertEqual([b["pet_ids"] for b in tx], [["second"],["fiction"]])
                else:
                    self.assertEqual(tx[0]["pet_ids"], ["fiction"] if saved else ["second"])
                self.assertIn(tx[-1]["pet_ids"][0].encode(), stored.values())
            else:
                self.assertIn(b"N",screen.status)
            self.assertIn(b"Y",screen.status)
            self.assertFalse((fs/"care-pending.json").exists())
            return stored
