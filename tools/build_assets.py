"""Сборка графики игры из листа ассетов (запускается один раз, вручную).

Нужны Pillow, numpy и scipy (в самой игре они не используются):

    python3 tools/build_assets.py лист_ассетов.webp [лист_выключателей.webp]

Скрипт вырезает спрайты персонажа и предметов, собирает ночной фон с
домиками, деревьями и рамкой поля и готовит светящиеся окна домиков.
Всё складывается в папку assets/ рядом с игрой.
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

WIN_W, WIN_H = 1280, 720
CELL = 28
FIELD = (206, 118, 868, 476)  # x, y, w, h — должно совпадать с design.py

SHEET_BOXES = {
    "head": (82, 32, 376, 244),
    "body": (495, 88, 934, 244),
    "tail": (1030, 8, 1411, 246),
    "bulb": (77, 247, 348, 542),
    "star": (1084, 267, 1262, 466),
    "leaf": (1323, 317, 1446, 459),
    "flower": (1226, 481, 1374, 613),
    "house": (5, 585, 536, 1012),
    "tree": (740, 615, 1195, 1000),
    "pause": (1255, 712, 1514, 978),
}

NIGHT_TINT = (0.50, 0.62, 0.86)
rng = random.Random(7)
nrng = np.random.default_rng(7)


def crop(sheet: Image.Image, name: str) -> Image.Image:
    """Вырезать спрайт из листа и обрезать пустые поля."""
    img = sheet.crop(SHEET_BOXES[name])
    if name == "tree":  # убираем следы лучей над кроной
        arr = np.array(img)
        arr[:22, :, 3] = 0
        img = Image.fromarray(arr)
    return img.crop(img.getbbox())


def scaled(img: Image.Image, width: int) -> Image.Image:
    height = round(img.height * width / img.width)
    return img.resize((width, height), Image.LANCZOS)


def tint(img: Image.Image, mul: tuple[float, float, float]) -> Image.Image:
    arr = np.array(img).astype(float)
    for i in range(3):
        arr[..., i] *= mul[i]
    return Image.fromarray(arr.clip(0, 255).astype("uint8"))


def noise(size: tuple[int, int], sigma: float) -> np.ndarray:
    """Мягкий шум 0..1 — имитация акварельных пятен."""
    base = nrng.random((size[1], size[0]))
    base = ndi.gaussian_filter(base, sigma)
    base -= base.min()
    return base / max(base.max(), 1e-6)


def save_sprites(sheet: Image.Image) -> dict[str, Image.Image]:
    sprites = {name: crop(sheet, name) for name in SHEET_BOXES}

    head = scaled(sprites["head"], 58)
    head.save(ASSETS / "characters/snake_head.png")

    body_src = sprites["body"].crop((150, 0, 305, sprites["body"].height))
    body = body_src.resize((32, 31), Image.LANCZOS)
    body.save(ASSETS / "characters/snake_body.png")

    scaled(sprites["tail"], 64).save(ASSETS / "characters/snake_tail.png")
    scaled(sprites["bulb"], 64).save(ASSETS / "objects/bulb.png")
    scaled(sprites["star"], 40).save(ASSETS / "effects/star.png")
    scaled(sprites["leaf"], 40).save(ASSETS / "ui/leaf.png")
    scaled(sprites["pause"], 68).save(ASSETS / "ui/pause.png")
    scaled(sprites["flower"], 34).save(ASSETS / "objects/flower.png")
    return sprites


SWITCH_BOXES = {
    "objects/switch.png": ((49, 109, 383, 481), 60),          # на стене, рычаг вверх
    "objects/switch_off.png": ((438, 109, 770, 481), 60),     # рычаг вниз
    "ui/switch_icon_on.png": ((797, 97, 1145, 484), 52),      # на подставке, вверх
    "ui/switch_icon_off.png": ((1174, 98, 1515, 484), 52),    # на подставке, вниз
    "effects/click_flash.png": ((20, 533, 394, 948), 220),    # вспышка-звезда
}


def save_switch_sprites(sheet: Image.Image) -> None:
    """Вырезать выключатели и эффекты щелчка из второго листа ассетов."""
    for name, (box, width) in SWITCH_BOXES.items():
        img = sheet.crop(box)
        img = img.crop(img.getbbox())
        scaled(img, width).save(ASSETS / name)


def lit_windows(house: Image.Image) -> list[np.ndarray]:
    """Найти окна дома (синие стёкла) и вернуть маски по окнам."""
    arr = np.array(house).astype(int)
    r, g, b, a = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    glass = (b > 120) & (b > r + 45) & (a > 200)
    merged = ndi.binary_dilation(glass, iterations=7)
    labels, count = ndi.label(merged)
    windows = []
    for i in range(1, count + 1):
        part = glass & (labels == i)
        if part.sum() > 120:
            windows.append(ndi.binary_dilation(part, iterations=1))
    windows.sort(key=lambda m: ndi.center_of_mass(m)[1])
    return windows


def glow_for_window(mask: np.ndarray, flip: bool, width: int,
                    origin: tuple[int, int], full_w: int) -> tuple:
    """Собрать RGBA-картинку светящегося окна и её позицию на экране."""
    img = Image.fromarray((mask * 255).astype("uint8"))
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    factor = width / full_w
    img = img.resize(
        (round(img.width * factor), round(img.height * factor)),
        Image.LANCZOS,
    )
    m = np.array(img).astype(float) / 255
    pad = 26
    h, w = m.shape
    canvas = np.zeros((h + pad * 2, w + pad * 2))
    canvas[pad:pad + h, pad:pad + w] = m
    halo = ndi.gaussian_filter(canvas, 9) * 1.5
    halo = np.clip(halo, 0, 1) * 0.6
    ys, xs = np.mgrid[0:canvas.shape[0], 0:canvas.shape[1]]
    cy, cx = ndi.center_of_mass(canvas)
    dist = np.hypot(xs - cx, ys - cy)
    dist /= max(dist[canvas > 0.5].max(), 1)
    warm = np.stack(
        [
            np.full_like(canvas, 255),
            255 - 55 * np.clip(dist, 0, 1),
            175 - 95 * np.clip(dist, 0, 1),
        ],
        axis=-1,
    )
    out = np.zeros(canvas.shape + (4,))
    out[..., :3] = warm
    alpha = np.maximum(canvas * 0.96, halo * (1 - canvas))
    out[..., 3] = alpha * 255
    ys_any, xs_any = np.nonzero(canvas > 0.5)
    pos = (origin[0] - pad, origin[1] - pad)
    return Image.fromarray(out.astype("uint8")), pos, (
        float(np.mean(xs_any)) + pos[0], float(np.mean(ys_any)) + pos[1])


def paint_sky(base: Image.Image) -> None:
    px = np.zeros((WIN_H, WIN_W, 3))
    top = np.array((5, 28, 38))
    mid = np.array((17, 68, 82))
    for y in range(WIN_H):
        t = min(1.0, y / 430)
        px[y, :, :] = top * (1 - t) + mid * t
    base.paste(Image.fromarray(px.astype("uint8")), (0, 0))


def paint_clouds(base: Image.Image) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    spots = [(70, 170, 1.0), (1150, 150, 1.0), (1210, 330, 0.8), (30, 330, 0.8)]
    for cx, cy, s in spots:
        for dx, dy, rw, rh in (
            (-60, 10, 70, 28), (0, -12, 90, 36), (65, 8, 70, 28), (10, 22, 110, 26)
        ):
            x, y = cx + dx * s, cy + dy * s
            d.ellipse((x - rw * s, y - rh * s, x + rw * s, y + rh * s),
                      fill=(70, 120, 140, 70))
    layer = layer.filter(ImageFilter.GaussianBlur(7))
    base.alpha_composite(layer)


def paint_stars(base: Image.Image, star: Image.Image) -> None:
    d = ImageDraw.Draw(base)
    for _ in range(95):
        x, y = rng.randint(0, WIN_W), rng.randint(0, 430)
        r = rng.choice((1, 1, 2))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 240, 201, 200))
    small = scaled(star, 22)
    for x, y in ((90, 76), (1160, 64), (1236, 214), (60, 250), (1100, 300)):
        base.alpha_composite(small, (x, y))


def hill(base: Image.Image, baseline: int, amp: int, color: tuple, seed: int,
         grain: float = 14) -> None:
    r = random.Random(seed)
    ph = [r.uniform(0, 6.28) for _ in range(3)]
    d_img = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(d_img)
    pts = [(0, WIN_H)]
    for x in range(0, WIN_W + 8, 8):
        y = baseline + amp * (
            0.6 * math.sin(x / 190 + ph[0]) + 0.3 * math.sin(x / 83 + ph[1])
            + 0.15 * math.sin(x / 41 + ph[2])
        )
        pts.append((x, y))
    pts.append((WIN_W, WIN_H))
    d.polygon(pts, fill=color + (255,))
    arr = np.array(d_img).astype(float)
    n = (noise(base.size, 6) - 0.5) * grain * 2
    arr[..., :3] += n[..., None]
    base.alpha_composite(Image.fromarray(arr.clip(0, 255).astype("uint8")))


def paste_bottom(base: Image.Image, sprite: Image.Image, x: int, bottom: int,
                 width: int, flip: bool = False, mul=NIGHT_TINT) -> tuple:
    img = scaled(sprite, width)
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    img = tint(img, mul)
    pos = (x, bottom - img.height)
    base.alpha_composite(img, pos)
    return pos


def paint_field(base: Image.Image, leaf: Image.Image) -> None:
    fx, fy, fw, fh = FIELD
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (fx - 6, fy - 2, fx + fw + 6, fy + fh + 12), 34, fill=(0, 12, 18, 120))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(9)))

    frame = Image.new("RGBA", base.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame)
    fd.rounded_rectangle((fx - 9, fy - 9, fx + fw + 9, fy + fh + 9), 30,
                         fill=(98, 160, 112, 255))
    fd.rounded_rectangle((fx - 5, fy - 5, fx + fw + 5, fy + fh + 5), 27,
                         fill=(44, 98, 82, 255))
    base.alpha_composite(frame)

    inner = np.zeros((fh, fw, 3))
    yy, xx = np.mgrid[0:fh, 0:fw]
    dist = np.hypot((xx - fw / 2) / (fw / 2), (yy - fh / 2) / (fh / 2))
    c0, c1 = np.array((16, 70, 84)), np.array((8, 42, 54))
    t = np.clip(dist, 0, 1.2)[..., None] / 1.2
    inner[:] = c0 * (1 - t) + c1 * t
    inner += ((noise((fw, fh), 5) - 0.5) * 9)[..., None]
    field = Image.fromarray(inner.clip(0, 255).astype("uint8")).convert("RGBA")

    # ненавязчивые силуэты растений на дне поля
    sil = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sil)
    for _ in range(26):
        x = rng.randint(0, fw)
        base_y = fh + rng.randint(-6, 10)
        height = rng.randint(34, 86)
        lean = rng.randint(-18, 18)
        for k in range(rng.randint(2, 4)):
            off = (k - 1) * 9
            sd.polygon([(x + off - 6, base_y),
                        (x + off + lean, base_y - height),
                        (x + off + 6, base_y)],
                       fill=(20, 80, 80, 70))
    field.alpha_composite(sil.filter(ImageFilter.GaussianBlur(1.2)))
    for _ in range(14):
        x, y = rng.randint(20, fw - 20), rng.randint(20, fh - 20)
        r = rng.choice((1, 1, 2))
        ImageDraw.Draw(field).ellipse((x - r, y - r, x + r, y + r),
                                      fill=(180, 230, 190, 40))
    mask = Image.new("L", (fw, fh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, fw - 1, fh - 1), 24, fill=255)
    base.paste(field.convert("RGB"), (fx, fy), mask)

    small = scaled(leaf, 30)
    for (x, y, rot, mirror) in (
        (fx - 18, fy - 14, 25, False), (fx + fw - 14, fy - 14, 155, True),
        (fx - 18, fy + fh - 22, -60, False), (fx + fw - 12, fy + fh - 26, 240, True),
    ):
        img = small.transpose(Image.FLIP_LEFT_RIGHT) if mirror else small
        img = img.rotate(rot, expand=True, resample=Image.BICUBIC)
        base.alpha_composite(img, (x, y))


def build_background(sprites: dict[str, Image.Image]) -> None:
    base = Image.new("RGBA", (WIN_W, WIN_H), (0, 0, 0, 255))
    paint_sky(base)
    paint_clouds(base)
    paint_stars(base, sprites["star"])
    hill(base, 470, 26, (22, 74, 66), 1)
    hill(base, 540, 22, (28, 92, 64), 2)

    house = sprites["house"]
    house_masks = lit_windows(house)
    assert len(house_masks) == 3, f"ожидалось 3 окна, найдено {len(house_masks)}"

    # деревья на заднем плане
    paste_bottom(base, sprites["tree"], -22, 372, 150, mul=(0.42, 0.55, 0.72))
    paste_bottom(base, sprites["tree"], 1140, 392, 150, flip=True,
                 mul=(0.42, 0.55, 0.72))

    placements = [
        # x, ground, width, flip — порядок: чередуем стороны
        (50, 430, 130, False),
        (1102, 450, 128, True),
        (6, 610, 196, False),
        (1078, 610, 196, True),
    ]
    windows: list[dict] = []
    order: list[list[dict]] = []
    for x, ground, width, flip in placements:
        pos = paste_bottom(base, house, x, ground, width, flip=flip)
        group = []
        for mask in house_masks:
            img, gpos, center = glow_for_window(mask, flip, width, pos, house.width)
            group.append({"image": img, "pos": gpos, "center": center})
        order.append(group)

    hill(base, 600, 10, (36, 108, 62), 3, grain=10)

    flower = Image.open(ASSETS / "objects/flower.png")
    for x, y in ((24, 636), (80, 662), (150, 640), (1110, 640), (1180, 664),
                 (1232, 632), (300, 672), (980, 676), (640, 690)):
        base.alpha_composite(tint(flower, (0.85, 0.85, 0.9)), (x, y))

    paint_field(base, sprites["leaf"])

    # зернистость гуаши по всей картинке
    arr = np.array(base.convert("RGB")).astype(float)
    arr += ((noise(base.size, 1.1) - 0.5) * 16)[..., None]
    arr += ((noise(base.size, 14) - 0.5) * 12)[..., None]
    yy, xx = np.mgrid[0:WIN_H, 0:WIN_W]
    vign = 1 - 0.22 * np.clip(
        np.hypot((xx - WIN_W / 2) / (WIN_W / 2), (yy - WIN_H / 2) / (WIN_H / 2)) - 0.55,
        0, 1)
    arr *= vign[..., None]
    Image.fromarray(arr.clip(0, 255).astype("uint8")).save(
        ASSETS / "backgrounds/background.png")

    # окна загораются по одному: левый дом, правый дом, и т. д.
    flat = []
    for slot in range(3):
        for group in order:
            flat.append(group[slot])
    meta = []
    for i, w in enumerate(flat):
        name = f"window_{i:02d}.png"
        w["image"].save(ASSETS / "backgrounds" / name)
        meta.append({"file": name, "pos": list(w["pos"]),
                     "center": list(w["center"])})
    (ASSETS / "backgrounds/windows.json").write_text(
        json.dumps(meta, indent=1), encoding="utf-8")


def main() -> None:
    sheet_path = Path(sys.argv[1])
    for sub in ("backgrounds", "characters", "objects", "effects", "ui", "fonts"):
        (ASSETS / sub).mkdir(parents=True, exist_ok=True)
    sheet = Image.open(sheet_path).convert("RGBA")
    sprites = save_sprites(sheet)
    build_background(sprites)
    if len(sys.argv) > 2:
        save_switch_sprites(Image.open(sys.argv[2]).convert("RGBA"))
    print("готово:", ASSETS)


if __name__ == "__main__":
    main()
