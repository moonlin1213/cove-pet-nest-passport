"""Make strip-decodable portraits without baking UI or room pixels into every pose."""
import argparse
import io
import json
import zlib
from pathlib import Path
from urllib.request import urlopen

from PIL import Image, ImageOps
from prepare import PUBLIC, art_url, rgb565

W, H = 204, 210
X, Y = (240-W)//2, 68


def pack_frame(cell):
    alpha = cell.getchannel("A")
    indexed = cell.convert("RGB").quantize(colors=95, method=Image.Quantize.MEDIANCUT)
    palette = bytes(indexed.getpalette())
    colors = len(palette)//3
    lut = bytearray(b"\x00\x00")
    for i in range(colors):
        r,g,b=palette[3*i:3*i+3]
        rgb=((r>>3)<<11)|((g>>2)<<5)|(b>>3)
        lut.extend(max(1,rgb).to_bytes(2,"big"))
    pixels = bytes((n+1 if a>8 else 0) for n,a in zip(indexed.tobytes(),alpha.tobytes()))
    return bytes([colors+1])+lut+zlib.compress(pixels,9)


def build_pet(atlas, room, dest, stem, egg):
    poses = (0,1) if egg else (0,1,2,4)
    cells={}
    if atlas:
        w,h=atlas.size
        for n in poses:
            cell=atlas.crop((w*(n%3)//3,h*(n//3)//2,w*(n%3+1)//3,h*(n//3+1)//2)).convert("RGBA")
            box=cell.getbbox()
            if box:
                cells[n]=cell.crop(box)
    scale=min([W/max(c.width for c in cells.values()), H/max(c.height for c in cells.values())]) if cells else 1
    frames={}
    with (dest/(stem+".bin")).open("wb") as f:
        for n in poses:
            rgba=Image.new("RGBA",(W,H))
            if n in cells:
                c=cells[n]
                c=c.resize((max(1,round(c.width*scale)),max(1,round(c.height*scale))),Image.Resampling.LANCZOS)
                rgba.alpha_composite(c,((W-c.width)//2,H-c.height))
            # Blend anti-aliased edges against the same background used on hardware.
            backdrop=room.crop((X,Y,X+W,Y+H)).convert("RGBA")
            blended=Image.alpha_composite(backdrop,rgba)
            blended.putalpha(rgba.getchannel("A"))
            if n == 0:
                preview=room.copy()
                preview.paste(rgba,(X,Y),rgba)
            frames[str(n)]=f.tell()
            f.write(pack_frame(blended))
    return dict(file=stem+".bin",frames=frames,egg=egg,ready=bool(cells)),preview


def build(dest, installed, base):
    dest.mkdir(parents=True,exist_ok=True)
    roster=json.loads(installed.read_text())["pets"]
    def fetch(path):
        with urlopen(base+path,timeout=8) as r: return r.read()
    pets={}
    offset=0
    version=None
    while True:
        s=json.loads(fetch("/api/pet-nest/state?limit=30&offset=%d"%offset))
        if version is not None and version!=s["state_version"]: raise ValueError("名单已更新")
        version=s["state_version"]
        pets.update((p["id"],p) for p in s["pets"])
        offset+=len(s["pets"])
        if offset>=s["total_pets"]: break
        if not s["pets"]: raise ValueError("名单不完整")
    room=ImageOps.fit(Image.open(PUBLIC/"room-light.webp").convert("RGB"),(240,320),centering=(.5,.69))
    (dest/"room.rgb").write_bytes(rgb565(room))
    catalog={}
    for i,item in enumerate(roster):
        pet=pets[item["id"]]
        url=art_url(pet)
        atlas=Image.open(io.BytesIO(fetch(url))) if url else None
        meta,preview=build_pet(atlas,room,dest,"p%d"%i,pet["kind"]=="egg" and pet["stage"]==0)
        catalog[pet["id"]]=meta
        if i==0: preview.save(dest.parent/"standby-preview.png")
    (dest/"index.json").write_text(json.dumps(catalog,separators=(",",":")))
    return sum(f.stat().st_size for f in dest.iterdir())


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("dest",type=Path)
    parser.add_argument("roster",type=Path)
    args=parser.parse_args()
    print("asset bytes:",build(args.dest,args.roster,"http://127.0.0.1:8081"))
