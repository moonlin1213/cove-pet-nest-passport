"""Three-button interactions. A finished round returns one existing Cove care action."""
from pet_mood import invitation


class Round:
    def __init__(self, profile, recent, turn, now, side, ignore_food=False):
        self.kind, self.pace = invitation(profile["traits"], None if ignore_food else profile["wish"], recent, turn)
        self.start = now
        self.side = side
        self.phase = "start"
        self.card = {
            "meal":"meal", "star":"hide_left" if side == 1 else "hide_right",
            "tap":"wait_paw", "rain":"breathe_in",
        }[self.kind]

    def tick(self, elapsed):
        if self.phase == "start" and elapsed >= self.pace:
            if self.kind == "meal": return
            self.phase = "ready"
            self.card = {"star":"find_star","tap":"paw_now","rain":"breathe_out"}[self.kind]
        if self.kind == "rain" and self.phase == "ready" and elapsed >= 2*self.pace:
            self.phase, self.card = "finish","quiet_now"
        if self.kind == "tap" and self.phase == "ready" and elapsed > self.pace + 2400:
            self.phase, self.card = "again","paw_again"

    def press(self, key):
        if self.kind == "meal":
            return "feed" if key == 3 else ("another" if key == 2 else "back")
        if self.kind == "star":
            if key == 3: return "back"
            if self.phase == "ready":
                if key == self.side: return "play"
                self.card = "other_side"
            return None
        if key != 3: return "back"
        if self.kind == "tap":
            if self.phase == "ready": return "play"
            if self.phase == "again": return "repeat"
        if self.kind == "rain" and self.phase == "finish": return "comfort"
        return None
