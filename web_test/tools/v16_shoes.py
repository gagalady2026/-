"""CUT 4: the official's shoes in the bench picture (the user's v14 picture) are drawn as white sneakers; everywhere else he
wears dark shoes (the character sheet's black loafers, the dark canvas sneakers of the CUT 7 pictures). This recolours them in
place: the upper, the three straps and the toe cap of each shoe take the dark grey of CUT 7's shoes, keeping the drawing's own
shading and outline; the seams between those pieces become light stitching; the soles stay light, as in CUT 7. Nothing else
in the picture changes (the trousers, the socks, the citizen's shoes, the bench).

usage: python3 -I tools/v16_shoes.py assets_v14/v14_bench_pair.png assets_v16
  → assets_v16/v16_bench_pair.png (same size and alpha) and v16_meta.json (the pieces recoloured)
"""
import json, os, sys
from collections import deque
import numpy as np
from PIL import Image

BOX = (820, 890, 1110, 1024)        # x0, y0, x1, y1: both of his shoes (picture px), under the trouser hems
FILL = np.array([80.0, 76.0, 82.0])  # the dark grey of his shoes in CUT 7 (measured there: about 89, 81, 86 in the warm light)
STITCH = np.array([138.0, 132.0, 136.0])
OUTLINE = np.array([14.0, 10.0, 9.0])  # the picture's own outline colour
WHITE_L = 242.0                       # the shoes' lit white


def label(mask):
    """4-connected components of a boolean mask (no scipy here): label image and count."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    n = 0
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not lab[y, x]:
                n += 1
                lab[y, x] = n
                q = deque([(y, x)])
                while q:
                    cy, cx = q.popleft()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = n
                            q.append((ny, nx))
    return lab, n


def near(mask, r):
    """Pixels within r (square) of a mask."""
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def main(src, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    im = np.asarray(Image.open(src).convert("RGBA")).astype(float)
    x0, y0, x1, y1 = BOX
    reg = im[y0:y1, x0:x1].copy()
    rgb, a = reg[..., :3], reg[..., 3]
    L = rgb.mean(-1)
    sat = rgb.max(-1) - rgb.min(-1)
    lab, n = label((L > 170) & (sat < 40) & (a > 200))
    pieces, soles, kept = [], [], []
    comps = []
    for i in range(1, n + 1):
        ys, xs = np.nonzero(lab == i)
        if ys.size < 12:
            continue
        c = rgb[lab == i].mean(0)
        comps.append(dict(i=i, n=int(ys.size), x=[int(xs.min() + x0), int(xs.max() + x0)], y=[int(ys.min() + y0), int(ys.max() + y0)],
                          warm=float(c[0] - c[2])))
    for c in comps:
        if c["y"][0] == y0 or c["warm"] > 20:          # the trouser legs (cream, reaching up out of the box)
            kept.append(c)
    shoes = [c for c in comps if c not in kept]
    for side in (lambda c: c["x"][0] < 990, lambda c: c["x"][0] >= 990):   # his right foot (screen left), his left foot
        mine = [c for c in shoes if side(c)]
        if not mine:
            continue
        sole = max(mine, key=lambda c: c["y"][1])      # each shoe's lowest piece is its sole
        soles.append(sole)
        pieces += [c for c in mine if c is not sole]
    up = np.isin(lab, [c["i"] for c in pieces])
    sole_m = np.isin(lab, [c["i"] for c in soles])
    # every pixel within 3 px of an upper piece that is not a piece itself: the outline, the seams and their soft edges
    ring = near(up, 3) & ~up & ~sole_m & ~np.isin(lab, [c["i"] for c in kept])
    count = np.zeros(L.shape, np.int32)
    for c in pieces:
        count += near(lab == c["i"], 3)
    seam = ring & (count >= 2) & (L >= 70)
    edge = ring & ~seam
    out = rgb.copy()
    shade = np.clip(L / WHITE_L, 0.78, 1.04)[..., None]
    out[up] = (FILL * shade)[up]
    t = np.clip((L - 40) / (200 - 40), 0, 1)[..., None]                    # toward the outline where the drawing is dark
    out[edge] = (OUTLINE + t * (FILL - OUTLINE))[edge]
    s = np.clip((200 - L) / (200 - 115), 0, 1)[..., None]                   # the seam's line, softened as the drawing has it
    out[seam] = (FILL + s * (STITCH - FILL))[seam]
    res = im.copy()
    res[y0:y1, x0:x1, :3] = out
    base = os.path.basename(src).replace("v14_", "v16_")
    Image.fromarray(np.clip(np.round(res), 0, 255).astype(np.uint8), "RGBA").save(os.path.join(out_dir, base))
    meta = {"source": os.path.basename(src), "box": BOX, "fill": FILL.tolist(), "stitch": STITCH.tolist(),
            "pieces_recoloured": [{k: c[k] for k in ("n", "x", "y")} for c in pieces],
            "soles_kept": [{k: c[k] for k in ("n", "x", "y")} for c in soles],
            "pixels_changed": int(up.sum() + ring.sum())}
    json.dump(meta, open(os.path.join(out_dir, "v16_meta.json"), "w"), indent=1)
    print(json.dumps({"pieces": len(pieces), "soles": len(soles), "changed_px": meta["pixels_changed"]}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
