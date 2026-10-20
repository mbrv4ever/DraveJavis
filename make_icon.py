# Maakt assets/icon.png + assets/icon.ico (eigen ontwerp: ringen met een gouden kern). Pillow nodig.
# Copyright (C) 2026 Dravenlock (Roger & Claudio). Licensed under the GNU GPL v3.0 or later - see LICENSE.
import os
from PIL import Image, ImageDraw, ImageFilter
HIER = os.path.dirname(os.path.abspath(__file__))
N = 512
img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse((16, 16, N - 16, N - 16), fill=(5, 10, 20, 255), outline=(31, 111, 153, 255), width=10)
gloed = Image.new("RGBA", (N, N), (0, 0, 0, 0))
g = ImageDraw.Draw(gloed)
g.ellipse((96, 96, N - 96, N - 96), fill=(57, 208, 255, 150))
gloed = gloed.filter(ImageFilter.GaussianBlur(40))
img = Image.alpha_composite(img, gloed)
d = ImageDraw.Draw(img)
c, r = N / 2, 196
for i in range(12):
    a0 = i * 30 + 4
    d.arc((c - r, c - r, c + r, c + r), a0, a0 + 20, fill=(57, 208, 255, 255), width=26)
r2 = 140
for i in range(3):
    a0 = i * 120 + 20
    d.arc((c - r2, c - r2, c + r2, c + r2), a0, a0 + 80, fill=(255, 179, 71, 255), width=14)
d.ellipse((c - 70, c - 70, c + 70, c + 70), fill=(57, 208, 255, 255))
d.ellipse((c - 40, c - 40, c + 40, c + 40), fill=(235, 250, 255, 255))
os.makedirs(os.path.join(HIER, "assets"), exist_ok=True)
img.save(os.path.join(HIER, "assets", "icon.png"))
img.save(os.path.join(HIER, "assets", "icon.ico"), format="ICO",
         sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icoon klaar")
