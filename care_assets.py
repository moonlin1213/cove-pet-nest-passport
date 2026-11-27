"""Small shared cards for the care menu and standby notices."""
from PIL import Image, ImageDraw
from prepare import label, rgb565, CREAM

CARDS = {
    'care_bath': ('洗澡','上下选择  ·  OK 确认'),
    'care_clean': ('清理便便','上下选择  ·  OK 确认'),
    'care_return': ('回到原伙伴','OK 返回'),
    'dirty_card': ('有便便需要清理','OK 去清理  ·  ▼ 稍后'),
    'miss_card': ('想你啦','OK 去看看  ·  ▼ 稍后'),
}
NOTES = {'bathed':'洗好啦，香喷喷！','cleaned':'便便清好啦','tidy':'房间很干净','care_egg':'蛋宝宝还不需要清洁','visiting':'探望中  ·  长按 OK 返回'}

def build(folder):
    for key,(title,controls) in CARDS.items():
        im=Image.new('RGB',(240,48),'#e3ead9')
        label(im,(120,3),title,18,anchor='ma')
        label(im,(120,35),controls,12,anchor='mm')
        (folder/(key+'.rgb')).write_bytes(rgb565(im))
    for key,text in NOTES.items():
        im=Image.new('RGB',(240,32),CREAM)
        if key=='bathed':
            draw=ImageDraw.Draw(im)
            for x,y,r in [(24,15,6),(32,6,3),(151,8,3)]:
                draw.ellipse((x-r,y-r,x+r,y+r),outline='#759b9d',width=2)
        label(im,(93,16),text,14,anchor='mm')
        if key!='care_egg':label(im,(184,16),'亲密',12,anchor='mm')
        (folder/(key+'.rgb')).write_bytes(rgb565(im))
