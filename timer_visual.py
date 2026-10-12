"""Rasterização dos timers com transparência por pixel; sem acesso ao jogo."""
import os
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ESTILOS_TEXTO = ("contorno", "glow", "sombra", "simples")
ESTILOS_BARRA = ("classica", "arredondada", "minimalista", "glow")
FONTES = {"Verdana": "verdanab.ttf", "Segoe UI": "segoeuib.ttf", "Tahoma": "tahomabd.ttf", "Arial": "arialbd.ttf"}


def aparencia(d=None):
    d = d or {}
    return {"estilo": d.get("estilo") if d.get("estilo") in ESTILOS_TEXTO else "contorno",
            "familia": d.get("familia") if d.get("familia") in FONTES else "Verdana",
            "intensidade": max(1, min(30, int(d.get("intensidade") or 22)))}


@lru_cache(maxsize=128)
def fonte(familia, tamanho):
    path = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", FONTES.get(familia, FONTES["Verdana"]))
    try:
        return ImageFont.truetype(path, tamanho)
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", tamanho)


def texto(text, rgb, tamanho=34, visual=None, largura=None):
    v = aparencia(visual)
    f = fonte(v["familia"], tamanho)
    bbox = f.getbbox(text or " ")
    pad = max(6, v["intensidade"] * 2 if v["estilo"] == "glow" else 6)
    mask = Image.new("L", (max(1, bbox[2] - bbox[0]) + pad * 2, max(1, bbox[3] - bbox[1]) + pad * 2))
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text, font=f, fill=255)
    out = Image.new("RGBA", mask.size)
    if v["estilo"] == "glow":
        # Duas camadas: halo amplo e brilho próximo à letra (sem borda preta).
        halo = mask.filter(ImageFilter.GaussianBlur(v["intensidade"] / 3)).point(lambda a: min(217, a * 3))
        out.paste((*rgb, 255), (0, 0), halo)
    elif v["estilo"] == "contorno":
        out.paste((0, 0, 0, 255), (0, 0), mask.filter(ImageFilter.MaxFilter(5)))
    elif v["estilo"] == "sombra":
        shadow = Image.new("L", mask.size)
        shadow.paste(mask, (3, 3))
        out.paste((0, 0, 0, 230), (0, 0), shadow.filter(ImageFilter.GaussianBlur(2)))
    face = Image.new("RGBA", mask.size, (*rgb, 0))
    face.putalpha(mask)
    out = Image.alpha_composite(out, face)
    if largura and out.width > largura:
        out = out.resize((largura, max(1, round(out.height * largura / out.width))), Image.Resampling.LANCZOS)
    return out


def cor_progresso(frac):
    frac = max(0, min(1, frac))
    return (round(255 * min(1, (1-frac)*2)), round(230 * min(1, frac*2)), 60)


def barras(itens, cfg, cores):
    labels = cfg["nome"] or cfg.get("tempo", cfg["nome"])
    linha = cfg["espessura"] + (18 if labels else 0) + 6
    image = Image.new("RGBA", (cfg["largura"] + 8, linha * len(itens) + 4))
    draw = ImageDraw.Draw(image)
    style = cfg.get("estilo", "classica")
    for i, (nome, frac, tempo, cor) in enumerate(itens):
        frac = max(0, min(1, frac))
        rgb = cor_progresso(frac) if cfg.get("cor_tempo") else cores(cor)
        y = 2 + i * linha
        if labels:
            textos = ([(nome, (255,255,255), False)] if cfg["nome"] else []) + ([(tempo, rgb, True)] if cfg.get("tempo", cfg["nome"]) else [])
            for label, color, right in textos:
                im = texto(label, color, 13, {"estilo": cfg.get("texto_estilo", "contorno"), "familia": cfg.get("familia", "Verdana"), "intensidade": 6}, cfg["largura"] // 2)
                # Recorta a margem do efeito para manter o rótulo na sua linha.
                box = im.getbbox()
                if box:
                    im = im.crop(box)
                    image.alpha_composite(im, (4 + cfg["largura"] - im.width if right else 4, y + (17-im.height)//2))
            y += 18
        rect = (4, y, 4+cfg["largura"]-1, y+cfg["espessura"]-1)
        radius = min(6, cfg["espessura"]//2) if style in ("arredondada", "glow") else 0
        if style == "classica":
            draw.rectangle((2,y-2,6+cfg["largura"]-1,y+cfg["espessura"]+1), fill=(0,0,0,255))
        draw.rounded_rectangle(rect, radius, fill=(40,44,52,210), outline=(180,190,200,150) if style == "arredondada" else None)
        width = round(frac*cfg["largura"])
        if width:
            fill = Image.new("RGBA", image.size)
            ImageDraw.Draw(fill).rounded_rectangle((4,y,4+width-1,y+cfg["espessura"]-1), min(radius, width//2), fill=(*rgb,255))
            if style == "glow":
                image = Image.alpha_composite(image, fill.filter(ImageFilter.GaussianBlur(2)))
            image = Image.alpha_composite(image, fill)
            draw = ImageDraw.Draw(image)
    return image


def bgra_premultiplicado(image):
    """UpdateLayeredWindow exige BGRA com canais de cor multiplicados pelo alfa."""
    r, g, b, a = image.convert("RGBA").split()
    return Image.merge("RGBA", (ImageChops.multiply(b,a), ImageChops.multiply(g,a), ImageChops.multiply(r,a), a)).tobytes()
