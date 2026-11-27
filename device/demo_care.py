"""Local starter pets share one small pantry. No network or account required."""
import json
import os


def demo_reply(path, body):
    try:
        with open(path) as f:
            state = json.load(f)
    except OSError as exc:
        if exc.args[0] != 2:
            raise
        state = {"grains": 12, "growth": {}, "last": None}
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
    with open(path + ".new", "w") as f:
        json.dump(state, f)
    os.rename(path + ".new", path)
    return reply
