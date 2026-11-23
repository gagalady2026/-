"""Small art fixes for the citizen shots of the 36-second animatic (assets_v6).

usage: python3 tools/v6_prep.py ASSETS_V4 OUT
  ASSETS_V4  assets_v4 (v4_cz_offer.png, v4_cz_given.png made by tools/v4_prep.py)
  writes
  OUT/v6_cz_offer_calm.png  CUT 4a: the tea-offering picture with the open laugh closed into a faint smile, so his mood
                            builds from a quiet smile (tea) to serious (his story) to relieved (after the explanation)
  OUT/v6_hand_cup.png       CUT 5a: the official's hand holding the paper cup, taken from the CUT 4b picture, for the
                            foreground of the citizen's close shot (pre-blurred a little: it is nearer than the focus)
"""
import json, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

V4, OUT = sys.argv[1], sys.argv[2]
meta = {}


def is_skin(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > 205) & (g > 150) & (b > 120) & (r - b > 25) & (r - b < 100)


# ---------------------------------------------------------------- CUT 4a: close the laugh
im = np.asarray(Image.open(f"{V4}/v4_cz_offer.png").convert("RGBA")).copy()
X0, Y0, X1, Y1 = 820, 260, 980, 380                         # around the mouth (3x picture pixels)
win = im[Y0:Y1, X0:X1].astype(int)
red = (win[..., 0] > 150) & (win[..., 1] < 160) & (win[..., 0] - win[..., 1] > 40) & (win[..., 3] > 200)
ys, xs = np.nonzero(red)
cy, cx = int(ys.mean()), int(xs.mean())
# the mouth = the connected non-skin region at the red centre (dark outline + inside), not the wrinkles beside it
notskin = ~is_skin(win[..., :3]) & (win[..., 3] > 200)
blob = np.zeros_like(notskin); blob[cy, cx] = True; q = deque([(cy, cx)])
while q:
    y, x = q.popleft()
    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
        if 0 <= ny < blob.shape[0] and 0 <= nx < blob.shape[1] and notskin[ny, nx] and not blob[ny, nx]:
            blob[ny, nx] = True; q.append((ny, nx))
bys, bxs = np.nonzero(blob)
mx0, mx1, my0, my1 = bxs.min(), bxs.max(), bys.min(), bys.max()
ring = win[max(0, my0 - 16):my1 + 16, max(0, mx0 - 16):mx1 + 16, :3].reshape(-1, 3)
skin = np.median(ring[is_skin(ring)], axis=0)
# fill the mouth (grown past its dark outline) by diffusing the skin around it inward (a harmonic fill): the cheek's
# shading and blush carry on through the patch with no ring at its edge
grown = np.asarray(Image.fromarray((blob * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(11))) > 0
region = win[..., :3].astype(np.float32)
F = region.copy()
edge_ring = np.asarray(Image.fromarray((grown * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(9))) > 0
F[edge_ring & ~grown & ~is_skin(win[..., :3])] = skin        # a wrinkle line next to the mouth must not bleed in
F[grown] = skin
for _ in range(600):
    avg = (np.roll(F, 1, 0) + np.roll(F, -1, 0) + np.roll(F, 1, 1) + np.roll(F, -1, 1)) / 4
    F[grown] = avg[grown]
soft = np.asarray(Image.fromarray((grown * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)[..., None] / 255
win_rgb = region * (1 - soft) + F * soft
patched = im.copy()
patched[Y0:Y1, X0:X1, :3] = np.clip(win_rgb, 0, 255).astype(np.uint8)
# a faint closed smile along the top of where the mouth was (the sheet's own mouth-line colour)
pim = Image.fromarray(patched, "RGBA")
d = ImageDraw.Draw(pim)
w = mx1 - mx0
ax, bx_ = X0 + mx0 + 0.18 * w, X0 + mx0 + 0.86 * w
ly = Y0 + my0 + 0.32 * (my1 - my0)
pts = [(ax + (bx_ - ax) * k / 20, ly + 5.5 * np.sin(np.pi * k / 20) - 2.0 * (k / 20)) for k in range(21)]
d.line(pts, fill=(150, 72, 58, 255), width=5, joint="curve")
pim.save(f"{OUT}/v6_cz_offer_calm.png", optimize=True)
meta["mouth_box"] = [int(X0 + mx0), int(Y0 + my0), int(X0 + mx1), int(Y0 + my1)]
meta["skin"] = [int(v) for v in skin]

# ---------------------------------------------------------------- CUT 5a: his hand and the cup, for the foreground
giv = Image.open(f"{V4}/v4_cz_given.png").convert("RGBA")
BOX = (1192, 330, giv.width, 600)                           # right of the citizen's fingers; the sleeve runs off the right edge
piece = np.asarray(giv.crop(BOX)).astype(np.float32)
a = piece[..., 3:4] / 255
blur = lambda ch: np.asarray(Image.fromarray(np.clip(ch, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(2.2))).astype(np.float32)
pre = np.dstack([blur(piece[..., c] * a[..., 0]) for c in range(3)])
al = blur(a[..., 0] * 255)[..., None] / 255
Image.fromarray(np.dstack([pre / np.maximum(al, 1e-3), al * 255]).clip(0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/v6_hand_cup.png", optimize=True)
meta["hand_cup"] = {"box": list(BOX), "cup_rim": [1279 - BOX[0], 391 - BOX[1]]}
json.dump(meta, open(f"{OUT}/v6_meta.json", "w"), indent=1)
print("ok", meta)
