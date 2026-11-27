"""Pair a public Pet Nest with its owner's Passport on a trusted home LAN."""
import argparse
import getpass
import hashlib
import hmac
import http.cookiejar
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import build_opener, HTTPCookieProcessor, Request

from PIL import Image, ImageOps
from device.pet_mood import TRAITS, compact
from prepare import PUBLIC, export
from portrait_assets import build_pet


def care(core, allowed, body):
    ids = body.get("pet_ids")
    if (body.get("scope") != "selected" or not isinstance(ids,list) or len(ids)!=1
            or not isinstance(ids[0],str) or ids[0] not in allowed
            or body.get("action") not in ("play","comfort","feed")
            or not re.fullmatch(r"passport-[a-f0-9]{32}",str(body.get("request_id","")))):
        raise ValueError("invalid care")
    reply = core("/api/care", {k:body[k] for k in ("action","scope","pet_ids","request_id")})
    return {"pantry":{"grains":reply["grains"]},"receipt_id":reply["receipt_id"],"results":reply["results"]}


def pocket_profile(p):
    t=p["traits"]
    wish="feed" if p["satiety"]<=40 else ("play" if t["energy"]+t["curiosity"]>t["calm"]+t["attachment"] else "comfort")
    return {"pet_id":p["id"],"personality":{k:t[k] for k in TRAITS},"wish":{"action":wish}}


class Room:
    def __init__(self,port,data):
        self.url="http://127.0.0.1:"+str(port)
        self.data=data
        self.session=build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.login()

    def login(self):
        token=json.loads((self.data/"credentials.json").read_text())["browser_token"]
        request=Request(self.url+"/api/session",data=b"",headers={"Authorization":"Bearer "+token})
        with self.session.open(request,timeout=8): pass

    def fetch(self,path,body=None):
        req=Request(self.url+path,data=None if body is None else json.dumps(body).encode(),
                    headers={"Content-Type":"application/json"})
        try:
            response=self.session.open(req,timeout=10)
        except HTTPError as e:
            if e.code!=401: raise
            self.login()
            response=self.session.open(req,timeout=10)
        with response:return response.read()

    def api(self,path,body=None):
        return json.loads(self.fetch(path,body))

    def pets(self):
        pets=[]
        while True:
            page=self.api("/api/nest?limit=100&offset="+str(len(pets)))
            pets.extend(page["pets"])
            if len(pets)>=page["total"]:return pets
            if not page["pets"]:raise ValueError("未读到完整名单")


def serve(room, config):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,body):
            raw=json.dumps(body,ensure_ascii=True,separators=(",",":")).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def handle_route(self):
            if self.headers.get("Origin") or not hmac.compare_digest(
                    self.headers.get("Authorization",""),"Bearer "+config["token"]):
                self.respond(403,{});return
            try:
                if self.command=="GET" and self.path=="/api/pet-nest/ecosystem":
                    self.respond(200,{"pets":[pocket_profile(p) for p in room.pets() if p["id"] in config["pets"]]})
                elif self.command=="POST" and self.path=="/api/pet-nest/care":
                    size=int(self.headers.get("Content-Length",0))
                    if not 0<size<=2048:raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    if not isinstance(body,dict):raise ValueError()
                    result=care(room.api,config["pets"],body)
                    self.respond(200,result)
                else:self.respond(404,{})
            except (TypeError,ValueError,KeyError):self.respond(400,{})
            except HTTPError as e:self.respond(e.code if e.code in (400,404,422) else 503,{})
            except OSError:self.respond(503,{})
        do_GET=do_POST=handle_route
    with HTTPServer((config["host"],config["port"]),Handler) as server:
        print("挂件已可连接。保持此窗口打开；按 Ctrl+C 可退出。",flush=True)
        server.serve_forever()


def personal_pack(dest,slot,chosen,room,wifi):
    from io import BytesIO
    group="link-"+slot
    nest=dest/"nest"/group
    portrait=dest/"portrait"/group
    portrait.mkdir(parents=True)
    original=Image.open(PUBLIC/"room-light.webp").convert("RGB")
    screen=ImageOps.fit(original,(240,320),centering=(.5,.69))
    roster=[];profiles={};index={}
    for i,p in enumerate(chosen):
        ref=p.get("asset_ref")
        if ref:
            atlas=Image.open(BytesIO(room.fetch("/api/assets/"+quote(ref,safe=""))))
        elif p["stage"]==0 and p["kind"] in ("cat","dog","egg"):
            atlas=Image.open(PUBLIC/(p["kind"]+"-sprites-light.webp"))
        else:raise ValueError("这只宠物的当前形象还未就绪")
        stem="p"+str(i)
        export(p,{},original,atlas,nest/stem,shared=nest)
        meta,_=build_pet(atlas,screen,portrait,stem,p["kind"]=="egg" and p["stage"]==0)
        meta["file"]=group+"/"+meta["file"]
        index[p["id"]]=meta
        profiles[p["id"]]=compact(pocket_profile(p))
        roster.append(dict(id=p["id"],name=p["name"],dir=group+"/"+stem+"/"))
    for name,obj in (("roster",{"pets":roster}),("portrait",index),("moods",profiles),("wifi",wifi)):
        (nest/(name+".json")).write_text(json.dumps(obj))
    return [*sorted(portrait.glob("*.bin")),*sorted(nest.glob("p*/pose*.rgb")),*sorted(nest.glob("*.json"))]


def pair(room,config,port):
    from serial.tools.list_ports import comports
    if not port:
        ports=[p.device for p in comports() if (p.vid,p.pid)==(0x303a,0x1001)]
        if len(ports)!=1:raise ValueError("请只连接一台 AI Passport，并关闭安装网页的串口")
        port=ports[0]
    def mp(*args):
        return subprocess.check_output([sys.executable,"-m","mpremote","connect",port,*args],timeout=120,text=True)
    try:
        slot=mp("exec","import os,json; assert 'passport-public-v1' in os.listdir('/'); assert 'care-pending.json' not in os.listdir('/'); print(json.load(open('/pocket-pack.json'))['slot'] if 'pocket-pack.json' in os.listdir('/') else '-')").strip()
        if slot not in ('-','a','b'):raise ValueError("挂件资源格式未知")
        slot='b' if slot=='a' else 'a'
        ready=[p for p in room.pets() if p['status']=='ready']
        if not ready:raise ValueError("请先在灵宠屋领养一只伙伴")
        for i,p in enumerate(ready,1):print(i,p['name'])
        numbers=list(dict.fromkeys(int(i.strip()) for i in input("要带哪些？输入编号，用英文逗号分隔：").split(',')))
        if not numbers or any(i<1 or i>len(ready) for i in numbers):raise ValueError("无效的伙伴编号")
        chosen=[ready[i-1] for i in numbers]
        wifi={**{k:config[k] for k in ('host','port','token')},"ssid":input("2.4 GHz Wi-Fi 名称：").strip(),"password":getpass.getpass("Wi-Fi 密码（隐藏）：")}
        if not wifi['ssid']:raise ValueError("Wi-Fi 名称为空")
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)
            files=personal_pack(dest,slot,chosen,room,wifi)
            # The currently active bank stays intact throughout the transfer.
            free=int(mp("exec","import os;s=os.statvfs('/');print(s[0]*s[3])").strip())
            if sum(f.stat().st_size+4096 for f in files)+16384>free:
                raise ValueError("挂件空间不足，请减少同时带出的灵宠数量")
            for d in sorted({a for f in files for a in f.relative_to(dest).parents if a!=Path('.')},key=lambda p:len(p.parts)):
                mp("exec","import os\ntry:os.mkdir(%r)\nexcept OSError as e:\n if e.args[0]!=17:raise"%('/'+d.as_posix()))
            for f in files:
                target='/'+f.relative_to(dest).as_posix()
                mp("fs","cp",str(f),":"+target)
                check="import hashlib,binascii\nh=hashlib.sha256()\nwith open(%r,'rb') as f:\n while True:\n  b=f.read(2048)\n  if not b:break\n  h.update(b)\nassert binascii.hexlify(h.digest()).decode()==%r"%(target,hashlib.sha256(f.read_bytes()).hexdigest())
                mp("exec",check)
            mp("exec","import os,json;assert 'care-pending.json' not in os.listdir('/');f=open('/pocket-pack.new','w');json.dump({'slot':%r},f);f.close();os.rename('/pocket-pack.new','/pocket-pack.json')"%slot)
        config['pets']=[p['id'] for p in chosen]
    finally:
        mp("reset")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair',action='store_true')
    parser.add_argument('--host',help='电脑的家庭局域网 IPv4 地址')
    parser.add_argument('--device',help='指定 USB 串口')
    parser.add_argument('--core-port',type=int,default=8767)
    parser.add_argument('--data',type=Path,default=Path(os.environ.get('PET_NEST_DATA_DIR',Path.home()/'.local/share/cove-pet-nest')))
    args=parser.parse_args()
    room=Room(args.core_port,args.data)
    settings=args.data/'passport-bridge.json'
    config=json.loads(settings.read_text()) if settings.exists() else {"token":secrets.token_hex(32),"port":8768}
    if args.pair:
        host=ipaddress.IPv4Address(args.host or input("电脑的家庭局域网 IPv4 地址：").strip())
        if not any(host in net for net in map(ipaddress.IPv4Network,('192.168.0.0/16','10.0.0.0/8','172.16.0.0/12'))):
            raise ValueError("请输入家庭局域网地址")
        config["host"]=str(host)
        pair(room,config,args.device)
        temp=settings.with_suffix('.new')
        with open(os.open(temp,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600),'w') as f:json.dump(config,f)
        os.replace(temp,settings)
    elif not settings.is_file():raise ValueError("第一次运行请加 --pair")
    serve(room,config)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:pass
    except (OSError,ValueError,subprocess.SubprocessError) as e:sys.exit("连接未完成："+str(e))
