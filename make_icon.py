# Generates icon.ico / icon_preview.png: gradient rounded square + white H
from PIL import Image, ImageDraw, ImageFont

SIZE = 256
C_TOP = (91, 108, 255)    # #5b6cff
C_BOT = (139, 92, 246)    # #8b5cf6
RADIUS = 58

img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

grad = Image.new("RGBA", (SIZE, SIZE))
for y in range(SIZE):
    t = y / (SIZE - 1)
    c = tuple(int(C_TOP[i] + (C_BOT[i] - C_TOP[i]) * t) for i in range(3)) + (255,)
    for x in range(SIZE):
        grad.putpixel((x, y), c)

mask = Image.new("L", (SIZE, SIZE), 0)
d = ImageDraw.Draw(mask)
d.rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=RADIUS, fill=255)
img.paste(grad, (0, 0), mask)

draw = ImageDraw.Draw(img)
font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 148)
bbox = draw.textbbox((0, 0), "H", font=font)
w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
tx = (SIZE - w) // 2 - bbox[0]
ty = (SIZE - h) // 2 - bbox[1] - 6
draw.text((tx, ty), "H", font=font, fill=(255, 255, 255, 255))

line_y = SIZE - 44
for i, ln in enumerate((52, 34, 18)):
    a = 200 - i * 55
    draw.rounded_rectangle([SIZE - 20 - ln, line_y, SIZE - 20, line_y + 7],
                           radius=3, fill=(255, 255, 255, a))
    line_y += 13

img.save("icon.ico", sizes=[(256, 256), (128, 128), (96, 96), (64, 64),
                            (48, 48), (32, 32), (24, 24), (16, 16)])
img.save("icon_preview.png")
print("icon.ico written")
