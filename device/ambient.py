"""Choose a small, visible episode from current temperament and care signals."""
AWAY = -1


def tendencies(profile, recent):
    profile = profile or {}
    traits = profile.get("traits") or {}
    a, e, c, s, q, v = [traits.get(k, 50)/100 for k in
                          ("attachment","energy","curiosity","sociability","calm","sensitivity")]
    wish = profile.get("wish")
    hungry = wish == "feed" and recent not in ("fed","full")
    movement = .38*e + .26*c + .12*s + .14*(1-q) + .06*(1-a) + .04*(1-v)
    rest = .38*q + .22*(1-e) + .12*a + .12*v + .10*(1-c) + .06*(1-s)
    if wish == "play":
        movement += .16
    elif wish == "comfort":
        rest += .20
    if recent == "played":
        rest += .24
    elif recent == "comforted":
        movement += .12
    elif recent in ("fed","full"):
        rest += .14
    return movement, rest, hungry, (a+s)/2


def _duration(pose, mood, jitter):
    move, rest, hungry, closeness = mood
    if pose == 1:
        base = 155 + 65*rest
    elif pose == 2:
        base = 7500 + 17500*rest/(.65+move)
    elif pose == 4:
        base = 2200 + 8000*rest/(.55+move) + 1300*hungry
    elif pose == AWAY:
        base = 8500 + 13500*move/(1+rest+closeness)
    else:
        base = 1900 + 5300*(.25+rest)/(.65+move)
    return int(base*(.70 + .60*jitter/255))


def duration(pose, profile, recent, jitter):
    return _duration(pose, tendencies(profile,recent), jitter)


def next_pose(current, egg, profile, recent, roll, jitter, allow_away):
    mood = tendencies(profile,recent)
    move, rest, hungry, _ = mood
    pose = 0
    if current == 0:
        if egg:
            pose = 1
        else:
            blink = 35 + 60*move
            nap = 5 + 40*rest/(.5+move)
            crouch = 12 + 22*rest + 55*hungry
            explore = 0
            if allow_away and not hungry and profile and profile.get("traits"):
                explore = 1 + 10*move*move/(.5+rest)
            point = (roll+.5)/256*(blink+nap+crouch+explore)
            if point < blink:
                pose = 1
            elif point < blink+nap:
                pose = 2
            elif point < blink+nap+crouch:
                pose = 4
            else:
                pose = AWAY
    return pose, _duration(pose,mood,jitter)
