"""Assets for motion comic v2 from the user's GPT images.

usage: python3 prep_v2.py SRC_DIR OUT_DIR
SRC_DIR holds st_neutral/st_talk/st_listen/st_smile/sit_point1/sit_point2.png (transparent) and bg_yard.png.
"""
import json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
INK = np.array([38, 33, 31], np.float32)
feat = json.load(open(f"{SRC}/features.json"))
meta = {}

def clean(name):
    """GPT cut-outs: interior alpha ~253, faint coloured matting halo. Make the interior opaque, drop the halo,
    and give every soft silhouette pixel the ink colour (every outer edge in this style is a dark outline)."""
    a = np.asarray(Image.open(f"{SRC}/{name}.png").convert("RGBA")).astype(np.float32)
    al = np.clip((a[..., 3] - 16) / (232 - 16), 0, 1)
    soft = al < 0.98
    rgb = a[..., :3].copy()
    rgb[soft] = INK
    out = np.dstack([rgb, al * 255]).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(f"{OUT}/v2_{name}.png", optimize=True)
    return out

def skin_ring(arr, box, pad=10):
    x0, y0, x1, y1 = box
    sub = arr[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad, :3].reshape(-1, 3).astype(int)
    r, g, b = sub[:, 0], sub[:, 1], sub[:, 2]
    s = sub[(r > 215) & (g > 160) & (b > 130) & (r - b > 30) & (r - b < 90)]
    return np.median(s, axis=0)

imgs = {n: clean(n) for n in ("st_neutral", "st_talk", "st_listen", "st_smile", "sit_point1", "sit_point2")}

# --- talking mouth for the standing shot: a feathered piece of st_talk pasted on st_neutral (heads match within 4 px)
m = feat["st_talk"]["mouth"]
cx, cy, hw, hh = m["x"], m["y"], 34, 24
box = (int(cx - hw), int(cy - hh), int(cx + hw), int(cy + hh))
piece = imgs["st_talk"][box[1]:box[3], box[0]:box[2]].copy()
fm = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
ImageDraw.Draw(fm).ellipse([6, 4, fm.width - 6, fm.height - 4], fill=255)
fm = np.asarray(fm.filter(ImageFilter.GaussianBlur(4))).astype(np.float32) / 255
piece[..., 3] = (piece[..., 3] * fm).astype(np.uint8)
Image.fromarray(piece, "RGBA").save(f"{OUT}/v2_st_talk_mouth.png")
meta["st_talk_mouth"] = {"x": box[0] + 4, "y": box[1] - 2}         # st_talk → st_neutral head offset (+4, −2)

# --- closed-mouth patches for the two seated poses (they are drawn talking)
for name in ("sit_point1", "sit_point2"):
    arr = imgs[name]
    mo = feat[name]["mouth"]
    mx, my = mo["x"], mo["y"]
    # the mouth = the connected non-skin blob under the detected mouth centre (outline + inside), not the jaw line
    WX, WY = int(mx - 60), int(my - 40)
    win = arr[WY:WY + 80, WX:WX + 120].astype(int)
    r, g, b = win[..., 0], win[..., 1], win[..., 2]
    notskin = ~((r > 215) & (g > 150) & (b > 120) & (r - b > 25) & (r - b < 95))
    from collections import deque
    sy, sx = int(my) - WY, int(mx) - WX
    cand = np.argwhere(notskin)
    sy, sx = cand[np.argmin(((cand - [sy, sx]) ** 2).sum(axis=1))]
    blob = np.zeros_like(notskin); blob[sy, sx] = True; q = deque([(sy, sx)])
    while q:
        y, x = q.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < blob.shape[0] and 0 <= nx < blob.shape[1] and notskin[ny, nx] and not blob[ny, nx]:
                blob[ny, nx] = True; q.append((ny, nx))
    ys, xs = np.nonzero(blob)
    x0, x1, y0, y1 = int(xs.min() + WX), int(xs.max() + WX), int(ys.min() + WY), int(ys.max() + WY)
    w, h = x1 - x0 + 1, y1 - y0 + 1
    pad = 6
    bx0, by0, bx1, by1 = x0 - pad, y0 - pad, x1 + pad + 1, y1 + pad + 1
    col = skin_ring(arr, (x0, y0, x1, y1), 14)
    pw, ph = bx1 - bx0, by1 - by0
    patch = np.zeros((ph, pw, 4), np.float32)
    patch[..., :3] = col
    # cover the mouth blob (grown a little); never paint over other lines inside the box (the jaw)
    cover = np.zeros((ph, pw), np.float32)
    cover[(ys + WY - by0), (xs + WX - bx0)] = 1.0
    cover = np.asarray(Image.fromarray((cover * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32)
    sub = arr[by0:by1, bx0:bx1].astype(int)
    other = ~((sub[..., 0] > 215) & (sub[..., 1] > 150) & (sub[..., 2] > 120) & (sub[..., 0] - sub[..., 2] > 25) & (sub[..., 0] - sub[..., 2] < 95))
    other &= ~(np.asarray(Image.fromarray((cover > 0).astype(np.uint8) * 255, "L")) > 0)
    cover[other] = 0
    patch[..., 3] = cover
    img = Image.fromarray(patch.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    # closed gentle smile where the upper lip line was
    sx0, sx1, sy = pad + w * 0.16, pad + w * 0.84, pad + h * 0.30
    pts = [(sx0 + (sx1 - sx0) * k / 20, sy + 4.5 * np.sin(np.pi * k / 20) + 0.0) for k in range(21)]
    d.line(pts, fill=(112, 50, 40, 255), width=5, joint="curve")
    img.save(f"{OUT}/v2_{name}_closed.png")
    meta[name + "_closed"] = {"x": bx0, "y": by0, "skin": [int(v) for v in col]}
    print(name, "mouth box", (x0, y0, x1, y1), "skin", col)

# --- tablet panels: quads read off the images (TL, TR, BR, BL) + fingertips; masks = panel surface minus finger/outline
PANELS = {
    "sit_point1": {"p1": [(728, 520), (975, 517), (962, 661), (709, 662)], "p2": [(703, 691), (947, 690), (931, 825), (684, 820)], "tip": (753, 589)},
    "sit_point2": {"p1": [(721, 574), (952, 576), (935, 705), (701, 697)], "p2": [(691, 729), (929, 735), (913, 880), (667, 872)], "tip": (751, 801)},
}
for name, P in PANELS.items():
    arr = imgs[name].astype(int)
    H, W = arr.shape[:2]
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    surface = (lum > 150) & ~((r - b > 28) & (r > 170)) & (arr[..., 3] > 200)
    full = np.zeros((H, W), np.uint8)
    for key in ("p1", "p2"):
        q = np.array(P[key], float); c = q.mean(axis=0)
        qs = [tuple(c + (p - c) * 0.965) for p in q]        # stay inside the drawn border
        m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).polygon(qs, fill=255)
        full |= (np.asarray(m) > 0) & surface
    mimg = Image.fromarray((full * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.8))
    x0, y0, x1, y1 = 620, 480, 1000, 900
    crop = mimg.crop((x0, y0, x1, y1))
    rgba = Image.merge("RGBA", (Image.new("L", crop.size, 255),) * 3 + (crop,))
    rgba.save(f"{OUT}/v2_{name}_panelmask.png", optimize=True)
    meta[name + "_panels"] = {"p1": P["p1"], "p2": P["p2"], "tip": P["tip"], "mask": [x0, y0]}

# --- background plates (yard by the jade gate; house wall by the bench), pre-blurred for depth of field
bg = Image.open(f"{SRC}/bg_yard.png").convert("RGB")
for key, (x0, y0, sc) in {"gate": (560, 228, 2.0), "wall": (40, 150, 2.0)}.items():
    W, H = 1920 * 1.06, 1080 * 1.06
    rw, rh = W / sc, H / sc
    cx, cy = x0 + 960 / sc, y0 + 540 / sc
    box = (cx - rw / 2, cy - rh / 2, cx + rw / 2, cy + rh / 2)
    crop = bg.crop(tuple(int(round(v)) for v in box)).resize((int(W), int(H)), Image.LANCZOS)
    crop.filter(ImageFilter.GaussianBlur(4.5)).save(f"{OUT}/v2_bg_{key}.jpg", quality=88, optimize=True)
    meta["bg_" + key] = {"src_box": [round(v, 1) for v in box], "size": [int(W), int(H)]}
meta["features"] = feat
json.dump(meta, open(f"{OUT}/v2_meta.json", "w"), indent=1)
print("ok")
