"""Assemble a clean starter filesystem solely from this checkout's allowlist."""
import json
import sys
from pathlib import Path
from hashlib import sha256
from PIL import Image, ImageOps
import littlefs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prepare import PUBLIC, export, rgb565
from portrait_assets import build_pet
from game_assets import build
from device.pet_mood import TRAITS

MODULES = ("ambient","demo_care","main","pet_core","pet_labels","pet_link","pet_mood","pet_portrait","pocket_games")
BASE_DIGEST = "2b09a9ee8d1595af244f50699363377517960f38fd146d56d5de98a0cf58e68f"
STARTERS = [
    ("cat", "团团", [72,83,88,65,25,40], "play"),
    ("dog", "麦麦", [82,36,45,80,90,60], "comfort"),
]


def assemble(work, firmware, site):
    if sha256(firmware).hexdigest() != BASE_DIGEST:
        raise ValueError("FoloToy v0.1.1 firmware checksum mismatch")
    for item in json.loads((PUBLIC/"manifest.json").read_text()):
        if sha256((PUBLIC/item["file"]).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError("starter art checksum mismatch")
    nest, portraits = work/"nest", work/"portrait"
    portraits.mkdir(parents=True)
    nest.mkdir()
    members, profiles, index = [], [], {}
    room = Image.open(PUBLIC/"room-light.webp").convert("RGB")
    screen = ImageOps.fit(room,(240,320),centering=(.5,.69))
    (portraits/"room.rgb").write_bytes(rgb565(screen))
    for i,(kind,name,values,wish) in enumerate(STARTERS):
        key, slot = "starter-"+kind, "p%d" % i
        pet = dict(id=key,name=name,kind=kind,stage=0,starter=True)
        sprite = Image.open(PUBLIC/(kind+"-sprites-light.webp"))
        export(pet,{},room,sprite,nest/slot,shared=nest)
        index[key],preview = build_pet(sprite,screen,portraits,slot,False)
        if i == 0:
            preview.save(site/"starter.png")
        members.append(dict(id=key,name=name,dir=slot+"/"))
        profiles.append(dict(pet_id=key,personality=dict(zip(TRAITS,values)),wish={"action":wish}))
    build(nest,{"pets":profiles})
    (nest/"roster.json").write_text(json.dumps({"starter":True,"pets":members}))
    (portraits/"index.json").write_text(json.dumps(index))
    files={p.relative_to(work).as_posix():p.read_bytes() for folder in (nest,portraits) for p in folder.rglob("*") if p.is_file()}
    files.update({s+".py":(ROOT/"device"/(s+".py")).read_bytes() for s in MODULES})
    files["passport-public-v1"] = b"0.1.0"
    # ESP32 flashbdev uses 4096-byte blocks. Pin the LittleFS v2.0 disk format.
    fs=littlefs.LittleFS(block_size=4096,block_count=1280,prog_size=32,read_size=32,disk_version=0x00020000)
    for name,data in sorted(files.items()):
        parent=Path(name).parent.as_posix()
        if parent!=".":
            fs.makedirs(parent,exist_ok=True)
        with fs.open(name,"wb") as f: f.write(data)
    fs.unmount()
    fs.mount()
    for name,data in files.items():
        with fs.open(name,"rb") as f:
            if f.read()!=data: raise ValueError(name)
    fs.unmount()
    image=firmware.ljust(0x300000,b"\xff")+bytes(fs.context.buffer)
    assert len(image)==8*1024*1024
    (site/"passport.bin").write_bytes(image)
    (site/"image.json").write_text(json.dumps({"version":"0.1.0","sha256":sha256(image).hexdigest(),"size":len(image)})+"\n")
    print(len(files),"files verified; firmware sha256",sha256(image).hexdigest())


if __name__=="__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        assemble(Path(folder),Path(sys.argv[1]).read_bytes(),ROOT/"docs/install")
