from pathlib import Path
import argparse
import json
from urllib.request import urlopen
from PIL import Image
from prepare import label,rgb565,CREAM
from device.pet_mood import compact

# (title, control hint) always fit the 240-pixel footer.
CARDS = {
 **{"sleep"+str(seconds):("息屏 · "+name,"OK 更改   ·   ▲▼ 选择") for seconds,name in [(30,"30 秒"),(60,"1 分钟"),(300,"5 分钟"),(0,"常亮")]},
 "summon":("召唤","OK 叫它回家   ·   ▲▼ 选择"),
 "home_again":("它自己回来啦","OK 看看它   ·   ▲▼ 选择"),
 "listen":("看看它的小心思","上下选择   ·   OK 听听"),
 "meal":("它闻了闻食盆","OK 喂一口   ·   ▼ 先陪伴   ·   ▲ 返回"),
 "hide_left":("星星藏在左手边","先看它的眼神   ·   OK 返回"),
 "hide_right":("星星藏在右手边","先看它的眼神   ·   OK 返回"),
 "find_star":("它藏的星星在哪儿？","▲ 左边   ·   ▼ 右边   ·   OK 返回"),
 "other_side":("它望向另一边…","▲ 左边   ·   ▼ 右边   ·   OK 返回"),
 "wait_paw":("等它伸出小爪…","看准时机再击掌   ·   ▲ 返回"),
 "paw_now":("它伸爪啦！","OK 击掌   ·   ▲ 返回"),
 "paw_again":("刚刚错过啦","OK 再试一次   ·   ▲ 返回"),
 "breathe_in":("陪它慢慢吸气","跟它待一小会儿   ·   ▲ 返回"),
 "breathe_out":("再一起慢慢呼气","放松一下   ·   ▲ 返回"),
 "quiet_now":("它安静地靠近了","OK 轻轻回应   ·   ▲ 返回"),
}
LINES = {
 "queued":"已记下，回到小窝后同步",
 "storage_full":"空间不足，先回小窝同步",
 "away_hint":"小窝空着，它溜出去玩啦",
 "call_first":"先叫它回来，再一起玩吧",
 "m_star":"东张西望，想找点新鲜事",
 "m_tap":"兴致正好，想和你打个招呼",
 "m_rain":"想靠你近一点，慢慢放松",
 "hungry_star":"肚子空了，在食盆边探头找粮",
 "hungry_tap":"见你靠近，立刻往食盆边跑",
 "hungry_rain":"安静守着食盆，抬眼望了望你",
 "r_star":"找到啦！它凑过来和你庆祝",
 "r_tap":"碰！你们击了个掌",
 "r_rain":"它挨着你，放松了一会儿",
 "m_unknown":"等连上小窝，再听它的心思",
}

def build(dest, snapshot):
    dest.mkdir(parents=True,exist_ok=True)
    strip=Image.new("RGB",(240,20),CREAM)
    label(strip,(12,10),"成长",13,anchor="lm")
    (dest/"growth-label.rgb").write_bytes(rgb565(strip))
    digits=bytearray()
    for char in "0123456789.":
        tile=Image.new("RGB",(10,20),CREAM)
        label(tile,(0,10),char,13,anchor="lm")
        digits.extend(rgb565(tile))
    (dest/"growth-digits.rgb").write_bytes(digits)
    for key,(title,hint) in CARDS.items():
        im=Image.new("RGB",(240,48),"#e3ead9")
        label(im,(120,6),title,17,anchor="ma")
        label(im,(120,37),hint,12,anchor="mm")
        (dest/(key+".rgb")).write_bytes(rgb565(im))
    for key,title in LINES.items():
        im=Image.new("RGB",(240,32),CREAM)
        label(im,(120,15),title,14,anchor="mm")
        (dest/(key+".rgb")).write_bytes(rgb565(im))
    profiles = {p["pet_id"]:compact(p) for p in snapshot["pets"] if compact(p)}
    (dest/"moods.json").write_text(json.dumps(profiles))
    return len(profiles)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("dest",type=Path)
    args=parser.parse_args()
    with urlopen("http://127.0.0.1:8081/api/pet-nest/ecosystem",timeout=8) as f:
        print("profiles",build(args.dest,json.load(f)))
