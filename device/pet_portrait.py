"""Paint the full-screen room in strips; only redraw the pet's band on a pose change."""
import deflate
import framebuf

WIDTH, HEIGHT = 240, 320
SPRITE_W, SPRITE_H = 204, 210
LEFT, TOP = 18, 68
ROWS = 6


def render(display, meta, pose, full):
    with open("/portrait/room.rgb","rb") as room, open("/portrait/"+meta["file"],"rb") as raw:
        raw.seek(meta["frames"][str(pose)])
        colors = raw.read(1)[0]
        palette = framebuf.FrameBuffer(bytearray(raw.read(2*colors)),colors,1,framebuf.RGB565)
        stripe = bytearray(WIDTH*ROWS*2)
        pixels = bytearray(SPRITE_W*ROWS)
        dest = framebuf.FrameBuffer(stripe,WIDTH,ROWS,framebuf.RGB565)
        src = framebuf.FrameBuffer(pixels,SPRITE_W,ROWS,framebuf.GS8)
        first = 0 if full else TOP
        room.seek(first*WIDTH*2)
        with deflate.DeflateIO(raw,deflate.ZLIB) as stream:
            # Keep stripe boundaries aligned exactly to the top/bottom of the pet.
            bands = [(0,TOP),(TOP,TOP+SPRITE_H),(TOP+SPRITE_H,HEIGHT)] if full else [(TOP,TOP+SPRITE_H)]
            for start,end in bands:
                for y in range(start,end,ROWS):
                    h=min(ROWS,end-y)
                    target=memoryview(stripe)[:WIDTH*h*2]
                    if room.readinto(target)!=len(target):
                        raise ValueError("short room")
                    if start==TOP:
                        source=memoryview(pixels)[:SPRITE_W*h]
                        if stream.readinto(source)!=len(source):
                            raise ValueError("short sprite")
                        dest.blit(src,LEFT,0,0,palette)
                    display.blit(target,0,y,WIDTH,h)


def empty_room(display, height):
    with open("/portrait/room.rgb","rb") as room:
        for y in range(0,height,8):
            rows = min(8,height-y)
            display.blit(room.read(WIDTH*rows*2),0,y,WIDTH,rows)
