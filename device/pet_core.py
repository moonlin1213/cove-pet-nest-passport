import binascii
import json
import os


def pending(path):
    try:
        with open(path) as f:
            return json.load(f)
    except OSError as e:
        if e.args[0] == 2:
            return None
        raise


def start_action(path, pet_id, action):
    old = pending(path)
    if old:
        return old
    if action not in ("play", "feed", "comfort"):
        raise ValueError("action")
    key = "passport-" + binascii.hexlify(os.urandom(16)).decode()
    body = dict(action=action, scope="selected", pet_ids=[pet_id], request_id=key)
    with open(path + ".new", "w") as f:
        f.write(json.dumps(body))
    os.rename(path + ".new", path)
    if hasattr(os, "sync"):
        os.sync()
    return body


def accept_receipt(path, body, reply, before_remove=None):
    results = reply.get("results", [])
    if (not reply.get("receipt_id") or len(results) != 1
            or results[0].get("pet_id") != body["pet_ids"][0]
            or pending(path) != body):
        raise ValueError("wrong receipt")
    result = results[0]
    status = result["status"]
    grains = int(reply["pantry"]["grains"])
    delta = int(result["growth_delta"])
    if before_remove:before_remove(body,status)
    os.remove(path)
    return status, grains, delta
