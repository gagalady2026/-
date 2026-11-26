"""The official's pointing arm as a layer of its own (assets_v13).

usage: python3 tools/v13_prep.py WEB OUT
  WEB  the folder holding the seated pair (assets_v4)
  writes
  OUT/v13_sit_p1_still.png, OUT/v13_sit_p2_still.png
                                 CUT 6: the seated official with his pointing arm taken out and the place it covered filled
                                 with the colours round it (diffused inward), the rest of the picture unchanged
  OUT/v13_sit_p1_arm.png, OUT/v13_sit_p2_arm.png
                                 … and that arm on its own (finger, hand, forearm and upper arm to the sleeve, with its ink
                                 outline), for the page to turn a hair about the sleeve as his finger presses the screen
  OUT/v13_sit_p1_panelmask.png, OUT/v13_sit_p2_panelmask.png
                                 the tablet-panel masks (v4) with the finger's notch filled: the screens are painted whole and
                                 the arm is drawn over them
  OUT/v13_meta.json              where each arm layer sits and the point it turns about
"""
import json, os, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

WEB, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
meta = {}


def diffuse_fill(rgb, hole, iters=500):
    """Fill the hole with the colours round it, diffused inward (no edges, no texture)."""
    F = rgb.copy()
    ring = np.asarray(Image.fromarray((hole * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    F[hole] = np.median(F[ring & ~hole], axis=0)
    for _ in range(iters):
        avg = (np.roll(F, 1, 0) + np.roll(F, -1, 0) + np.roll(F, 1, 1) + np.roll(F, -1, 1)) / 4
        F[hole] = avg[hole]
    return F


# ---------------------------------------------------------------- CUT 6: his pointing arm, a layer of its own
# seed: a skin point in his fist; quad: the tablet panel his finger is on (picture px, TL TR BR BL, as SIT in the page); mask_at:
# where the v4 panel mask sits in the picture
ARM = {"p1": {"seed": (480, 650), "quad": [(146, 517), (393, 520), (412, 662), (159, 661)], "mask_at": (122, 480)},
       "p2": {"seed": (420, 797), "quad": [(190, 738), (408, 728), (429, 863), (207, 877)], "mask_at": (100, 500)}}


def grow(m, r):
    return np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * r + 1))) > 0


def flood(free, seeds):
    """The pixels of `free` joined (4-way) to the seeds."""
    h, w = free.shape
    got = np.zeros_like(free)
    q = deque()
    for y, x in seeds:
        if free[y, x] and not got[y, x]:
            got[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < h and 0 <= xx < w and free[yy, xx] and not got[yy, xx]:
                got[yy, xx] = True; q.append((yy, xx))
    return got


for key, A in ARM.items():
    im = np.asarray(Image.open(f"{WEB}/assets_v4/v4_sit_{key}.png").convert("RGBA")).astype(np.float32)
    r, g, b, al = im[..., 0], im[..., 1], im[..., 2], im[..., 3]
    tot = r + g + b
    skin = (r > 200) & (g > 150) & (b > 120) & (r - b > 30) & (al > 200)
    arm = flood(skin, [A["seed"][::-1]])                       # the skin joined to his fist: finger to the sleeve
    ys, xs = np.nonzero(arm)
    y0, y1, x0, x1 = ys.min() - 14, ys.max() + 15, xs.min() - 14, xs.max() + 15
    box = ~arm[y0:y1, x0:x1]                                 # the ink lines inside his hand: what the outside cannot reach
    edge = [(y, x) for y in range(box.shape[0]) for x in (0, box.shape[1] - 1)] + [(y, x) for x in range(box.shape[1]) for y in (0, box.shape[0] - 1)]
    arm[y0:y1, x0:x1] |= ~flood(box, edge)
    arm |= grow(arm, 6) & (tot < 150)                       # his ink outline
    arm |= grow(arm, 2) & (tot < 600)                       # and its soft outer edge (not the white of the screen)
    # the sleeve end, where the arm turns: the top of its rightmost 90 columns
    cols = [x for x in range(xs.max() - 90, xs.max() + 1) if arm[:, x].any()]
    tops = [np.nonzero(arm[:, x])[0].min() for x in cols]
    pivot = [round(float(np.mean(cols)), 1), round(float(np.mean(tops)), 1)]
    # a hard-edged layer over a hole of exactly its shape: at rest the two make the picture as it was, pixel for pixel; turned,
    # the page's resampling softens its edge
    soft = arm.astype(np.float32)
    ys, xs = np.nonzero(arm)
    ay0, ay1, ax0, ax1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    layer = im[ay0:ay1, ax0:ax1].copy()
    layer[..., 3] = al[ay0:ay1, ax0:ax1] * soft[ay0:ay1, ax0:ax1]
    Image.fromarray(np.clip(layer + 0.5, 0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/v13_sit_{key}_arm.png", optimize=True)
    # the picture without it: what it covered filled from the shirt, tablet and screen round it
    hole = arm
    m = 24
    cy0, cy1, cx0, cx1 = max(0, ay0 - m), min(im.shape[0], ay1 + m), max(0, ax0 - m), min(im.shape[1], ax1 + m)
    still = im.copy()
    still[cy0:cy1, cx0:cx1, :3] = diffuse_fill(im[cy0:cy1, cx0:cx1, :3].copy(), hole[cy0:cy1, cx0:cx1], iters=1600)
    still[..., 3][hole & (al < 250)] = 0                     # on the figure's own outline the arm lies over nothing
    Image.fromarray(np.clip(still + 0.5, 0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/v13_sit_{key}_still.png", optimize=True)
    # the panel mask with the finger's notch filled (inside the panel only)
    pm = np.asarray(Image.open(f"{WEB}/assets_v4/v4_sit_{key}_panelmask.png").convert("RGBA")).astype(np.float32)
    mx, my = A["mask_at"]
    quad = Image.new("L", (pm.shape[1], pm.shape[0]), 0)
    ImageDraw.Draw(quad).polygon([(x - mx, y - my) for x, y in A["quad"]], fill=255)
    qd = np.asarray(quad).astype(np.float32)
    near = grow(arm, 4)[my:my + pm.shape[0], mx:mx + pm.shape[1]]
    before = int((pm[..., 3] > 127).sum())
    pm[..., 3] = np.maximum(pm[..., 3], qd * near)
    Image.fromarray(np.clip(pm + 0.5, 0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/v13_sit_{key}_panelmask.png", optimize=True)
    meta[f"sit_{key}_arm"] = {"at": [int(ax0), int(ay0)], "size": [int(ax1 - ax0), int(ay1 - ay0)], "pivot": pivot,
                              "arm_px": int(arm.sum()), "mask_px_before": before, "mask_px_after": int((pm[..., 3] > 127).sum())}
json.dump(meta, open(f"{OUT}/v13_meta.json", "w"), indent=1)
print("ok", json.dumps(meta))
