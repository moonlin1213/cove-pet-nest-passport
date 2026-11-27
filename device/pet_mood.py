"""Choose pocket interactions from Cove's six current traits and care signals."""
TRAITS = ("attachment", "energy", "curiosity", "sociability", "calm", "sensitivity")
GAMES = ("star", "tap", "rain")


def compact(profile):
    traits = profile.get("personality") or {}
    for key in TRAITS:
        value = traits.get(key)
        if not isinstance(value, (int, float)) or not 0 <= value <= 100:
            return None
    wish = (profile.get("wish") or {}).get("action")
    return {"traits": {k:traits[k] for k in TRAITS}, "wish":wish}


def scores(t, wish, recent):
    a, e, c, s, q, v = [t[k] / 100 for k in TRAITS]
    weights = {
        "star": .40*c + .23*e + .14*v + .13*(1-s) + .10*(1-q),
        "tap": .34*s + .26*e + .18*a + .12*(1-q) + .10*(1-v),
        "rain": .32*q + .22*v + .22*a + .14*(1-e) + .10*(1-c),
    }
    if wish == "comfort":
        weights["rain"] += .26
    elif wish == "play":
        weights["star"] += .16
        weights["tap"] += .16
    if recent == "played":
        weights["rain"] += .20
    elif recent == "comforted":
        weights["star"] += .14
        weights["tap"] += .10
    return weights


def invitation(traits, wish, recent, turn):
    if wish == "feed" and recent not in ("fed","full"):
        return "meal", 0
    weights = scores(traits,wish,recent)
    # A modest rotating curiosity bonus gives nearby scores different turns.
    weights[GAMES[turn % len(GAMES)]] += .09
    game = max(GAMES,key=lambda k:weights[k])
    if game == "star":
        pace = 1200 + 12*(100-traits["curiosity"]) + 5*traits["sensitivity"]
    elif game == "tap":
        pace = 650 + 8*(100-traits["energy"]) + 4*(100-traits["sociability"])
    else:
        pace = 1300 + 14*traits["calm"] + 6*traits["attachment"]
    return game, int(pace)


def expression(traits, wish, recent, turn):
    game,_ = invitation(traits,wish,recent,turn)
    if game == "meal":
        manner,_ = invitation(traits,None,recent,turn)
        return "hungry_"+manner
    return "m_"+game
