"""Cached external halo and labels; crop pixels are always transparent."""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter, ImageFont

@lru_cache(maxsize=128)
def frame(width, height, color='#51cfff', intensity='med', name='', dpi=96):
    width, height = max(1,int(width)), max(1,int(height))
    margin = max(12, round(20*dpi/96))
    title = max(20,round(22*dpi/96)) if name else 0
    size = (width+2*margin,height+2*margin+title)
    image = Image.new('RGBA',size)
    rgb = tuple(int(color[i:i+2],16) for i in (1,3,5))
    box=(margin,margin+title,margin+width-1,margin+title+height-1)
    if intensity != 'off':
        radius,alpha={'min':(2,90),'med':(5,150),'max':(9,225)}.get(intensity,(5,150))
        mask=Image.new('L',size); draw=ImageDraw.Draw(mask)
        draw.rectangle((box[0]-2,box[1]-2,box[2]+2,box[3]+2),outline=alpha,width=3)
        halo=Image.new('RGBA',size,rgb+(0,)); halo.putalpha(mask.filter(ImageFilter.GaussianBlur(radius*dpi/96)))
        image.alpha_composite(halo)
        ImageDraw.Draw(image).rectangle((box[0]-1,box[1]-1,box[2]+1,box[3]+1),outline=rgb+(220,),width=1)
    # Explicitly clear interior after blur: no tint over the live DWM image.
    ImageDraw.Draw(image).rectangle(box,fill=(0,0,0,0))
    if name: ImageDraw.Draw(image).text((margin,margin),str(name),fill=rgb+(255,))
    return image, margin, title


@lru_cache(maxsize=8)
def selection_hint(dpi=96,mode='quadrado'):
    text = ('Arraste para selecionar; ajuste pelo interior ou alças | ' if mode=='manual' else 'Clique para posicionar | ') + 'Enter confirma | Esc cancela'
    font = ImageFont.load_default(size=max(10, round(12 * dpi / 96)))
    box = font.getbbox(text)
    padding = max(4, round(6 * dpi / 96))
    image = Image.new('RGBA', (box[2] - box[0] + 2 * padding, box[3] - box[1] + 2 * padding))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius=padding,
                           fill=(15,17,21,230), outline=(255,255,255,180))
    draw.text((padding - box[0], padding - box[1]), text, font=font, fill='white')
    return image
