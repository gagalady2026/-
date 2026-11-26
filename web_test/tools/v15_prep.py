"""The citizen's close-ups for CUT 5 (second line) and CUT 6, from the user's six GPT pictures (assets_v15).

usage: python3 -I tools/v15_prep.py ATTENTIVE HEAVY HEAVY_TALK RELIEF SMILE SMILE_TALK OUT
  the six pictures (1254x1254, transparent): his 3/4 face turned right, head and shoulders, as everywhere else in the film
  (bald on top, short dark grey hair at the back and sides, a grey crew neck under the olive sweater):
  ATTENTIVE   listening, calm, mouth shut                 HEAVY       the arrears: eyes down, brows sad, mouth shut
  HEAVY_TALK  the same, talking (only its mouth is used)  RELIEF      eyes closed, the relieved smile
  SMILE       eyes open, a gentle smile                    SMILE_TALK  smiling and talking (only its mouth is used)
  writes OUT/v15_cz_{attentive,heavy,heavy_talk,relief,smile,smile_talk}.png and OUT/v15_meta.json
  - transparency cleaned as in v14 (a faint haze, alpha 1-24, cleared; the 1-4% see-through body made opaque)
  - each picture moved by whole pixels onto the attentive one (the best match over his hair, ear and sweater: they were
    drawn 0-2 px apart), so one drawing can follow another without the head jumping
  - the talking faces are his shut-mouthed faces with only the mouth changed: HEAVY_TALK's and SMILE_TALK's open mouths laid
    into HEAVY and SMILE through a feathered oval round the mouth (the skin there is one flat colour). Their own eyes and
    brows differ a little (HEAVY_TALK's eyes are wider), so the mouth can flap without the eyes flickering
  - meta: the shifts, the mouth ovals, his eyes [x, y, w, h] and the skin round them (for blinks)
"""
import json, os, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

names = ["attentive", "heavy", "heavy_talk", "relief", "smile", "smile_talk"]
paths, OUT = sys.argv[1:7], sys.argv[7]
os.makedirs(OUT, exist_ok=True)


def keep_big(solid, min_px):
    h, w = solid.shape
    seen = np.zeros_like(solid); keep = np.zeros_like(solid)
    for y0, x0 in zip(*np.nonzero(solid)):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)]); seen[y0, x0] = True; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < h and 0 <= xx < w and solid[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True; q.append((yy, xx))
        if len(pts) >= min_px:
            ys, xs = zip(*pts); keep[list(ys), list(xs)] = True
    return keep


def clean(p):
    a = np.asarray(Image.open(p).convert("RGBA")).astype(np.float32)
    al = a[..., 3]
    al = np.where(al <= 24, 0, np.where(al >= 246, 255, al))
    a[..., 3] = np.where(keep_big(al > 0, 1500), al, 0)
    return a


def prem(a):
    return np.dstack([a[..., :3] * a[..., 3:4] / 255, a[..., 3]])


def shift(a, dx, dy):
    """a moved by (dx, dy) whole pixels (what was at x lands at x + dx), empty where nothing comes in."""
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = a[ys, xs]
    return out


pics = {n: clean(p) for n, p in zip(names, paths)}
base = prem(pics["attentive"])
REG = [(180, 120, 560, 800), (150, 900, 1150, 1230)]                 # his hair and ear; his sweater
meta = {"shifts": {}}
for n in names[1:]:
    P = prem(pics[n]); best = None
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            e = sum(np.abs(base[y0:y1, x0:x1] - P[y0 + dy:y1 + dy, x0 + dx:x1 + dx]).mean() for x0, y0, x1, y1 in REG)
            if best is None or e < best[0]:
                best = (e, dx, dy)
    _, dx, dy = best
    pics[n] = shift(pics[n], -dx, -dy)
    meta["shifts"][n] = [-dx, -dy]


def oval(cx, cy, rx, ry, feather):
    m = Image.new("L", (1254, 1254), 0)
    ImageDraw.Draw(m).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(feather))).astype(np.float32)[..., None] / 255


MOUTHS = {"heavy_talk": ("heavy", (880, 718, 62, 38)), "smile_talk": ("smile", (868, 713, 78, 42))}
for talk, (shut, (cx, cy, rx, ry)) in MOUTHS.items():
    m = oval(cx, cy, rx, ry, 5)
    A, B = prem(pics[shut]), prem(pics[talk])
    C = A * (1 - m) + B * m
    al = C[..., 3:4]
    pics[talk] = np.dstack([np.where(al > 0, C[..., :3] * 255 / np.maximum(al, 1), 0), al[..., 0]])
    meta.setdefault("mouth_ovals", {})[talk] = {"into": shut, "oval": [cx, cy, rx, ry], "feather": 5}

for n in names:
    Image.fromarray(np.clip(pics[n] + 0.5, 0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/v15_cz_{n}.png", optimize=True)


def skin_round(a, ex, ey, h):
    r = int(h * 0.9) + 12
    yy, xx = np.mgrid[int(ey - r):int(ey + r), int(ex - r):int(ex + r)]
    ring = ((xx - ex) ** 2 + (yy - ey) ** 2 > (h * 0.8) ** 2) & ((xx - ex) ** 2 + (yy - ey) ** 2 < r ** 2)
    px = a[yy[ring], xx[ring]]
    keep = (px[:, 3] > 250) & (px[:, :3].sum(-1) > 600)
    return [int(v) for v in np.median(px[keep][:, :3], axis=0)]


EYES = {"attentive": [[776.0, 533.0, 41, 93], [931.0, 494.5, 29, 82]], "heavy": [[770.5, 543.0, 50, 81], [929.5, 512.0, 38, 69]]}
meta["eyes"] = {k: {"eyes": v, "skin": skin_round(pics[k], v[0][0], v[0][1], v[0][3])} for k, v in EYES.items()}
json.dump(meta, open(f"{OUT}/v15_meta.json", "w"), indent=1)
print(json.dumps(meta))
