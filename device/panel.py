"""Stream public RGB565 assets into one LCD window per update."""

def present(display,x,y,width,height,parts):
    # One RAMWR command per rectangle. Keep the old pixels until the
    # first buffer is ready, and always release the bus on a read error.
    window=getattr(display,'_window',None)
    sent=0
    end=width*height*2
    active=False
    try:
        for part in parts:
            n=len(part)
            if not n or sent+n>end or n%(2*width):
                raise ValueError('invalid display rows')
            if window:
                if not active:
                    window(x,y,x+width-1,y+height-1)
                    display.dc(1)
                    display.cs(0)
                    active=True
                display.spi.write(part)
            else:
                display.blit(part,x,y+sent//(2*width),width,n//(2*width))
            sent+=n
        if sent!=end:raise ValueError('incomplete display frame')
    finally:
        if active:display.cs(1)


def rows(stream, count, buffer):
    while count:
        part = buffer[:min(count, len(buffer))]
        if stream.readinto(part) != len(part):
            raise ValueError('short RGB image')
        yield part
        count -= len(part)


def paint(display, path, x, y, width, height):
    with open(path, 'rb') as stream:
        buffer = memoryview(bytearray(width * 2 * min(height, 8)))
        present(display, x, y, width, height, rows(stream, width*height*2, buffer))


def menu(display, base, image, status, buttons, growth):
    with open(base+image+'.rgb','rb') as photo, open(base+status+'.rgb','rb') as note, open(base+buttons+'.rgb','rb') as foot:
        buffer = memoryview(bytearray(480*8))
        label = None
        if growth is not None:
            with open(base+'growth-label.rgb','rb') as stream:
                label = bytearray(stream.read(480*20))
            text = ('%.2f' % growth).rstrip('0').rstrip('.')[:16]
            with open(base+'growth-digits.rgb','rb') as digits:
                for i,char in enumerate(text):
                    digits.seek('0123456789.'.index(char)*400)
                    glyph = memoryview(digits.read(400))
                    for row in range(20):
                        start = row*480+96+i*20
                        label[start:start+20] = glyph[row*20:row*20+20]
        def page():
            if label is None:
                yield from rows(photo, 240*480, buffer)
            else:
                yield from rows(photo, 219*480, buffer)
                yield label
                photo.seek(239*480)
                yield from rows(photo,480,buffer)
            yield from rows(note,32*480,buffer)
            yield from rows(foot,48*480,buffer)
        present(display,0,0,240,320,page())


def restore(display, path):
    with open(path,'rb') as photo:
        photo.seek(41*480)
        source = memoryview(bytearray(8*480))
        crop = memoryview(bytearray(8*248))
        def pet_rows():
            for part in rows(photo,139*480,source):
                height = len(part)//480
                for n in range(height):
                    start = n*480+116
                    crop[n*248:(n+1)*248] = part[start:start+248]
                yield crop[:height*248]
        present(display,58,41,124,139,pet_rows())
