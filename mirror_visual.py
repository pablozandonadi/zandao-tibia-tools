"""Cached external halo and labels; crop pixels are always transparent."""
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFilter

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
