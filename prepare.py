"""Prepare a private, display-sized copy of one selected Cove pet (read-only)."""
import os
import argparse
import io
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen
from PIL import Image, ImageDraw, ImageFont, ImageOps

FONT = os.environ.get("PASSPORT_FONT") or next((str(p) for p in (
    Path("/System/Library/Fonts/Hiragino Sans GB.ttc"),
    Path(os.environ.get("WINDIR","C:/Windows"))/"Fonts/msyh.ttc",
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
) if p.is_file()), "NotoSansCJK-Regular.ttc")
PUBLIC = Path(__file__).resolve().parent / "assets"
CREAM = "#f8f2e6"
INK = "#494137"


def art_url(pet):
    stage = int(pet["stage"])
    appearance = (pet.get("appearance") or {}).get("status")
    if appearance == "pending":
        return None
    asset = pet.get("current_asset") or {}
    resource = "/api/pet-nest/pets/%s/stages/%d/asset" % (quote(pet["id"], safe=""), stage)
    url = asset.get("asset_url") or ""
    if asset.get("stage") == stage and re.fullmatch(re.escape(resource) + r"(?:\?v=[a-f0-9]{16})?", url):
        return url
    if appearance != "ready" and stage == 0 and pet["kind"] in ("cat","dog","egg"):
        return "/public/pet-nest/%s-sprites-light.webp?v=1" % pet["kind"]


def rgb565(image):
    raw = bytearray()
    for r, g, b in image.convert("RGB").get_flattened_data():
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        raw.extend((v >> 8, v & 255))
    return raw


def label(image, xy, value, size=16, color=INK, anchor="la"):
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, size)
    draw.text(xy, value, font=font, fill=color, anchor=anchor)


def export(pet, pantry, room, atlas, dest, shared=None):
    dest.mkdir(parents=True, exist_ok=True)
    titles = ("陪它玩", "喂一口", "摸摸它", "换一只")
    for pose in (0,1,3,5):
        page = Image.new("RGB",(240,240), CREAM)
        background = ImageOps.fit(room.convert("RGB"), (240,190), centering=(0.5,0.68))
        if atlas:
            w,h = atlas.size
            col,row = pose % 3, pose // 3
            cell = atlas.crop((w*col//3,h*row//2,w*(col+1)//3,h*(row+1)//2)).convert("RGBA")
            box = cell.getbbox()
            if box:
                cell = ImageOps.contain(cell.crop(box), (124,139), Image.Resampling.LANCZOS)
                background.paste(cell, ((240-cell.width)//2,180-cell.height),cell)
        else:
            label(background,(120,105),"模样准备中",16,anchor="mm")
        page.paste(background,(0,0))
        label(page,(12,198),pet["name"][:11],19)
        label(page,(228,201),"阶段 %s" % pet["stage"],14,anchor="ra")
        if pet.get("starter"):
            label(page,(12,222),"随身示例 · 陪玩可获得口粮",12)
        else:
            label(page,(12,222),"成长 %s  ·  同步 %s" % (pet.get("growth",0), datetime.now().strftime("%m/%d %H:%M")),12)
        frame = page.crop((58,41,182,180)) if shared is not None and pose else page
        (dest/("pose%d.rgb" % pose)).write_bytes(rgb565(frame))
        if pose == 0:
            preview = Image.new("RGB",(240,320),CREAM)
            preview.paste(page)
    if shared is not None and (shared/"action0.rgb").exists():
        return
    ui = shared if shared is not None else dest
    for i, title in enumerate(titles):
        strip = Image.new("RGB",(240,48), "#e3ead9")
        label(strip,(120,6),title,18,anchor="ma")
        pen = ImageDraw.Draw(strip)
        pen.line([(39,13),(35,17),(39,21)],fill=INK,width=2)
        pen.line([(201,13),(205,17),(201,21)],fill=INK,width=2)
        label(strip,(120,37),"上下选择   ·   OK 确认",12,anchor="mm")
        (ui/("action%d.rgb" % i)).write_bytes(rgb565(strip))
        if i == 0:
            preview.paste(strip,(0,272))
    from device.pet_labels import MESSAGES
    for key, value in MESSAGES.items():
        strip = Image.new("RGB",(240,32),CREAM)
        label(strip,(120,15),value,14,anchor="mm")
        (ui/(key+".rgb")).write_bytes(rgb565(strip))
        if key == "idle":
            preview.paste(strip,(0,240))
    if shared is not None:
        strip = Image.new("RGB",(240,48),"#e3ead9")
        label(strip,(120,10),"今天带谁出门？",18,anchor="ma")
        label(strip,(120,37),"上下翻看   ·   OK 带它出门",12,anchor="mm")
        (ui/"picker.rgb").write_bytes(rgb565(strip))
        preview.paste(strip,(0,272))
        preview.save(shared.parent/"preview.png")
        return
    preview.save(dest.parent/"preview.png")
    (dest/"pet.json").write_text(json.dumps(dict(id=pet["id"], name=pet["name"], stage=pet["stage"],
        growth=pet.get("growth",0), grains=pantry["grains"]),ensure_ascii=False))


def prepare(base, name, dest, all_pets=False):
    def fetch(path):
        with urlopen(base.rstrip("/")+path, timeout=8) as r:
            return r.read()
    offset = 0
    version = None
    matches = []
    ids = set()
    while True:
        state = json.loads(fetch("/api/pet-nest/state?limit=30&offset=%s" % offset))
        if version is not None and version != state["state_version"]:
            raise ValueError("名单已更新，请重新同步")
        version = state["state_version"]
        for pet in state["pets"]:
            if pet["id"] in ids:
                raise ValueError("名单里有重复身份")
            ids.add(pet["id"])
            if all_pets or name in (pet["id"],pet["name"]):
                matches.append(pet)
        offset += len(state["pets"])
        if offset >= state["total_pets"]:
            break
        if not state["pets"]:
            raise ValueError("名单不完整")
    if all_pets:
        if not matches:
            raise ValueError("Cove 小窝当前没有灵宠")
        import tempfile
        import os
        if dest.exists():
            raise ValueError("请使用新的输出目录，保留上一份完整名单")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            build = Path(tmp)/"nest"
            roster = []
            with Image.open(PUBLIC/"room-light.webp") as room:
                for i, pet in enumerate(matches):
                    slot = "p%d/" % i
                    url = art_url(pet)
                    atlas = Image.open(io.BytesIO(fetch(url))) if url else None
                    export(pet, state["pantry"], room, atlas, build/slot, shared=build)
                    roster.append(dict(id=pet["id"], name=pet["name"], dir=slot))
            (build/"roster.json").write_text(json.dumps({"pets":roster},ensure_ascii=False))
            from game_assets import build as build_games
            build_games(build, json.loads(fetch("/api/pet-nest/ecosystem")))
            os.replace(build,dest)
            os.replace(Path(tmp)/"preview.png",dest.parent/"preview.png")
        return
    if len(matches) != 1:
        raise ValueError("请选择唯一名字或宠物 ID")
    pet = matches[0]
    url = art_url(pet)
    atlas = Image.open(io.BytesIO(fetch(url))) if url else None
    export(pet, state["pantry"], Image.open(PUBLIC/"room-light.webp"),atlas,dest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", nargs="?")
    parser.add_argument("dest",type=Path)
    parser.add_argument("--base",default="http://127.0.0.1:8081")
    parser.add_argument("--all",action="store_true",help="同步全家灵宠供挂件选择")
    a = parser.parse_args()
    prepare(a.base,a.name,a.dest,a.all)
