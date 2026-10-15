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


@lru_cache(maxsize=16)
def selection_hint(dpi=96,mode='quadrado',ready=False,width=620):
    scale=dpi/96
    width=max(120,min(round(620*scale),int(width)))
    height=round(100*scale);padding=max(4,round(10*scale))
    font=ImageFont.load_default(size=max(10,round(12*scale)))
    image=Image.new('RGBA',(width,height));draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((0,0,width-1,height-1),radius=padding,fill=(15,17,21,240),outline=(255,255,255,180))
    text='Arraste para selecionar; ajuste pelo interior ou alças.' if mode=='manual' else 'Clique para posicionar o quadrado.'
    draw.text((padding,padding),text,font=font,fill='white')
    draw.text((padding,padding+round(19*scale)),'Enter confirma | Esc cancela',font=font,fill='#d0d4da')
    top=round(55*scale);bottom=height-padding
    middle=width//2;gap=max(2,round(5*scale))
    confirm=(padding,top,middle-gap,bottom);cancel=(middle+gap,top,width-padding,bottom)
    for box,label,color in ((confirm,'Confirmar','#ff7033' if ready else '#52565c'),(cancel,'Cancelar','#353b45')):
        draw.rounded_rectangle(box,radius=max(3,round(5*scale)),fill=color,outline='#d0d4da')
        b=draw.textbbox((0,0),label,font=font);draw.text(((box[0]+box[2]-(b[2]-b[0]))/2,(box[1]+box[3]-(b[3]-b[1]))/2-b[1]),label,font=font,fill='white')
    return image,confirm,cancel
