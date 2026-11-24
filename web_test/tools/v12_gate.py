"""The gate in CUT 2 opens (assets_v12).

usage: python3 tools/v12_gate.py WEB OUT
  WEB  the folder holding assets_v3/v3_plate_gate.jpg (the closed gate seen from the yard), assets_v5/v5_stairs.jpg (the alley
       he came up) and assets_v2/v2_st_neutral.png (the official, standing, front view)
  writes
  OUT/v12_gate_leaf.png    the gate's right leaf (the one with the ring), cut out of the plate with the whole ring on it, for the
                           page to swing inward about its hinge (the right edge)
  OUT/v12_gate_open.jpg    the plate with what the swinging leaf uncovers: behind it, the alley in daylight (the stairs plate,
                           softened and a little brighter) and the official standing at the gate, close behind it, so his face
                           shows in the opening; on the left leaf, the sliver of the ring that overlapped the seam is painted
                           over with the leaf's own boards
  OUT/v12_meta.json        the leaf's box in the plate, its hinge, top and bottom (plate pixels)

At rest the leaf sits exactly where it was cut from, so the closed gate is the plate as it was.
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageFilter

WEB, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
plate = Image.open(f"{WEB}/assets_v3/v3_plate_gate.jpg").convert("RGB")
P = np.asarray(plate).astype(np.float32)
H, W = P.shape[:2]
r, g, b = P[..., 0], P[..., 1], P[..., 2]

# the right leaf: boards (teal), their ink outline and the hinge plates, between the seam and the right pillar
X0, X1, Y0, Y1 = 1363, 1667, 366, 972
teal = (g > r + 40) & (b > r + 20) & (g > 100) & (r < 140)
dark = (r + g + b) < 200
gate = np.zeros((H, W), bool)
gate[Y0:Y1, X0:X1] = (teal | dark)[Y0:Y1, X0:X1]
cols = []                                       # per column, the top and bottom of the leaf
for x in range(X0, X1):
    ys = np.nonzero(gate[:, x])[0]
    cols.append((ys.min(), ys.max()) if len(ys) > 40 else None)
mask = np.zeros((H, W), np.float32)
for i, c in enumerate(cols):
    if c:
        mask[c[0]:c[1] + 1, X0 + i] = 1
# the whole ring (it overlaps the seam onto the left leaf by a few pixels): it goes with the leaf
RING = (1347, 592, 1432, 700)
rx0, ry0, rx1, ry1 = RING
ring = ~teal[ry0:ry1, rx0:rx1] | (P[ry0:ry1, rx0:rx1].sum(-1) > 600)
mask[ry0:ry1, rx0:rx1] = np.maximum(mask[ry0:ry1, rx0:rx1], ring.astype(np.float32))
mask = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32) / 255
ys, xs = np.nonzero(mask > 0.01)
bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
leaf = np.dstack([P[by0:by1, bx0:bx1], mask[by0:by1, bx0:bx1, None] * 255]).astype(np.uint8)
Image.fromarray(leaf, "RGBA").save(f"{OUT}/v12_gate_leaf.png", optimize=True)

# the left leaf where the ring was: its own boards from just left of it, and the seam's ink line from above
O = P.copy()
O[ry0:ry1, 1340:1359] = P[ry0:ry1, 1318:1337]
seam = P[ry0 - 60:ry0, 1359:1363].mean(axis=0)
O[ry0:ry1, 1359:1363] = seam

# what the leaf uncovers: the alley outside in daylight, and the official close behind the gate
stairs = Image.open(f"{WEB}/assets_v5/v5_stairs.jpg").convert("RGB")
sw, sh = stairs.size
box = (int(sw * 0.58), int(sh * 0.18), int(sw * 0.82), int(sh * 0.86))           # a wall, steps and sky beyond the gate
bh = by1 - by0 + 40
bwid = int(bh * (box[2] - box[0]) / (box[3] - box[1]))
out = stairs.crop(box).resize((bwid, bh), Image.LANCZOS).filter(ImageFilter.GaussianBlur(5))
o = np.asarray(out).astype(np.float32)
o = 255 - (255 - o) * 0.72                                                         # brighter: the sunlit street
o *= np.array([1.03, 1.0, 0.95])
outside = Image.fromarray(np.clip(o, 0, 255).astype(np.uint8))
behind = Image.new("RGBA", (W, H), (0, 0, 0, 0))
behind.paste(outside, (bx0 + (bx1 - bx0) // 2 - bwid // 2, by0 - 20))
off = Image.open(f"{WEB}/assets_v2/v2_st_neutral.png").convert("RGBA")
k = 0.463                                                                          # a 1.7 m figure behind a 1.8 m gate
offs = off.resize((int(off.width * k), int(off.height * k)), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0.8))
behind.alpha_composite(offs, (int(1396 - 543 * k), int(398 - 20 * k)))              # his face centred on the opening
B = np.asarray(behind).astype(np.float32)
leaf_area = mask > 0.5
leaf_area[ry0:ry1, rx0:1363] = False                                               # (the ring's sliver over the left leaf stays boards)
a = B[..., 3:4] / 255 * leaf_area[..., None]
O = O * (1 - a) + B[..., :3] * a
Image.fromarray(np.clip(O, 0, 255).astype(np.uint8)).save(f"{OUT}/v12_gate_open.jpg", quality=92)

top = [c[0] for c in cols if c]; bot = [c[1] for c in cols if c]
meta = {"leaf_box": [bx0, by0, bx1, by1], "hinge_x": 1662, "free_x": 1363, "top": int(np.median(top)), "bottom": int(np.median(bot)), "ring": list(RING)}
json.dump(meta, open(f"{OUT}/v12_meta.json", "w"), indent=1)
print("ok", json.dumps(meta))
