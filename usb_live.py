"""Foreground USB connection to the locally running Cove. Writes only on physical care intent."""
import argparse
import json
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import serial


def serve(port, pet_ids, base):
    allowed = {pet_ids} if isinstance(pet_ids,str) else set(pet_ids)
    with serial.Serial(port, 115200, timeout=0.15, write_timeout=1) as device:
        ping = 0
        while True:
            if time.monotonic() >= ping:
                device.write(b"NEST_PING\n")
                ping = time.monotonic() + 2
            line = device.readline(4096)
            if not line.startswith(b"NEST_CARE "):
                continue
            try:
                body = json.loads(line[10:])
                if (body["action"] not in ("feed","play","comfort") or body["scope"] != "selected"
                        or not isinstance(body["pet_ids"], list) or len(body["pet_ids"]) != 1
                        or body["pet_ids"][0] not in allowed or not re.fullmatch("passport-[a-f0-9]{32}",body["request_id"])):
                    continue
                req = Request(base+"/api/pet-nest/care", data=json.dumps(body).encode(),
                              headers={"Content-Type":"application/json"})
                try:
                    with urlopen(req, timeout=5) as r:
                        reply = json.load(r)
                except HTTPError as e:
                    if e.code not in (400,403,404,422):
                        raise
                    reply = {"rejected":True}
                data = {"id":body["request_id"],"reply":reply}
                device.write(("NEST_REPLY "+json.dumps(data,ensure_ascii=True)+"\n").encode())
            except (OSError,ValueError,KeyError):
                print("等待下次确认",flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("manifest")
    parser.add_argument("--base",default="http://127.0.0.1:8081")
    args = parser.parse_args()
    with open(args.manifest) as f:
        manifest = json.load(f)
        pet_ids = {p["id"] for p in manifest["pets"]} if "pets" in manifest else {manifest["id"]}
    serve(args.port,pet_ids,args.base)
