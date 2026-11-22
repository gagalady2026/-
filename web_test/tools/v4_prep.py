"""Assets for the citizen shots and the redrawn tablet pose of the 36-second animatic (assets_v4).

usage: python3 tools/v4_prep.py SRC ASSETS_V2 OUT
  SRC        citizen_turnaround.png, citizen_expr.png, citizen_poses.png   the citizen sheets (cream paper, 1672x941)
             sit_point1.png        the first seated tablet pose (tablet on the right, pointing at ①)
             sit_point2_v3.png     the redrawn second pose (tablet on the left, pointing at ②, bag on the left hip)
  ASSETS_V2  assets_v2 (v2_meta.json and v2_sit_point1_closed.png are reused for the mirrored first pose)
  OUT        writes v4_*.png and v4_meta.json

The redrawn ② pose holds the tablet on the screen-left side, so the ① pose is mirrored to match: the tablet stays on the
same side through the swap, and the bag (hidden below the frame) no longer changes sides.
Sheet cells are keyed off the paper (flood fill from the cell edges, with the light dashed guide lines counted as paper),
small loose marks (speech lines, panel numbers) are dropped, and each piece is upscaled 3x with a smoothed silhouette.
"""
import json, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC, V2, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
INK = np.array([38, 33, 31], np.float32)
K = 3
meta = {}


def components(mask, min_area=1):
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)]); seen[y0, x0] = True; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; q.append((ny, nx))
        if len(pts) >= min_area:
            out.append(np.array(pts))
    return out


def is_skin(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return (r > 205) & (g > 150) & (b > 120) & (r - b > 25) & (r - b < 100)


def find_eyes(arr, box):
    """Black oval eyes enclosed by skin, inside box (x0, y0, x1, y1). Returns [[cx, cy, w, h], ...] left to right."""
    x0, y0, x1, y1 = box
    sub = arr[y0:y1, x0:x1].astype(int)
    lum = sub[..., :3] @ np.array([0.299, 0.587, 0.114])
    dark = (lum < 70) & (sub[..., 3] > 200)
    skin = is_skin(sub)
    eyes = []
    for c in components(dark, 25):
        ys, xs = c[:, 0], c[:, 1]
        w, h = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        if not (5 <= w <= 60 and 8 <= h <= 80 and h >= w * 0.9):
            continue
        cy, cx = int(ys.mean()), int(xs.mean())
        dn = skin[ys.max() + 2:ys.max() + 12, cx].any()
        side = skin[cy, max(0, xs.min() - 10):xs.min()].any() and skin[cy, xs.max() + 1:xs.max() + 11].any()
        if dn and side:
            eyes.append((len(c), [round(float(xs.mean()) + x0, 1), round(float(ys.mean()) + y0, 1), int(w), int(h)]))
    eyes = [e for _, e in sorted(eyes, key=lambda t: -t[0])[:2]]
    return sorted(eyes, key=lambda e: e[0])


def skin_near(arr, box, pad=12):
    x0, y0, x1, y1 = box
    sub = arr[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad, :3].reshape(-1, 3).astype(int)
    s = sub[is_skin(sub)]
    return [int(v) for v in np.median(s, axis=0)]


# ------------------------------------------------------------------ seated pair: mirrored ① + redrawn ②
def clean(path):
    """GPT cut-outs: interior alpha ~253 and a faint matting halo. Opaque interior, ink-coloured soft silhouette."""
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
    al = np.clip((a[..., 3] - 16) / (232 - 16), 0, 1)
    rgb = a[..., :3].copy()
    rgb[al < 0.98] = INK
    return np.dstack([rgb, al * 255]).astype(np.uint8)


v2 = json.load(open(f"{V2}/v2_meta.json"))
p1 = clean(f"{SRC}/sit_point1.png")[:, ::-1].copy()
H1, W1 = p1.shape[:2]
Image.fromarray(p1, "RGBA").save(f"{OUT}/v4_sit_p1.png", optimize=True)
mx = lambda x: round(W1 - 1 - x, 1)
q1 = v2["sit_point1_panels"]
def mquad(q):          # mirror a TL, TR, BR, BL quad and keep it reading left to right
    tl, tr, br, bl = q
    return [[mx(tr[0]), tr[1]], [mx(tl[0]), tl[1]], [mx(bl[0]), bl[1]], [mx(br[0]), br[1]]]
cl = Image.open(f"{V2}/v2_sit_point1_closed.png").transpose(Image.FLIP_LEFT_RIGHT)
cl.save(f"{OUT}/v4_sit_p1_closed.png")
c1 = v2["sit_point1_closed"]
pm = Image.open(f"{V2}/v2_sit_point1_panelmask.png").transpose(Image.FLIP_LEFT_RIGHT)
pm.save(f"{OUT}/v4_sit_p1_panelmask.png", optimize=True)
m1x, m1y = q1["mask"]
meta["p1"] = {
    "eyes": find_eyes(p1, (380, 250, 800, 520)),
    "closed": [W1 - (c1["x"] + cl.width), c1["y"]], "skin": skin_near(p1, (480, 380, 600, 440)),
    "a": mquad(q1["p1"]), "b": mquad(q1["p2"]), "tip": [mx(q1["tip"][0]), q1["tip"][1]],
    "mask": [W1 - (m1x + pm.width), m1y],
}

p2 = clean(f"{SRC}/sit_point2_v3.png")
H2, W2 = p2.shape[:2]
Image.fromarray(p2, "RGBA").save(f"{OUT}/v4_sit_p2.png", optimize=True)
lum2 = p2[..., :3].astype(int) @ np.array([0.299, 0.587, 0.114])
# tablet panels: the two large light regions inside the tablet (upper grey ①, lower blue ②); corners = diagonal extremes
light = (lum2 > 205) & (p2[..., 3] > 200)
light[:440] = False; light[1000:] = False; light[:, :60] = False; light[:, 560:] = False
quads = []
for c in sorted(components(light, 1500), key=len, reverse=True)[:6]:
    ys, xs = c[:, 0], c[:, 1]
    col = p2[ys, xs, :3].astype(int).mean(axis=0)
    if col[2] - col[0] > 25 or (abs(col[0] - col[2]) < 12 and col.mean() < 248):        # blue ② panel, or the grey ① panel
        s, d = xs + ys, xs - ys
        q = [c[np.argmin(s)][::-1], c[np.argmax(d)][::-1], c[np.argmax(s)][::-1], c[np.argmin(d)][::-1]]
        quads.append((float(ys.mean()), [[int(v) for v in p] for p in q]))
quads.sort()
assert len(quads) == 2, quads
qa, qb = quads[0][1], quads[1][1]
# fingertip: leftmost point of the skin region that reaches into the lower panel
skin2 = is_skin(p2[..., :3].astype(int)) & (p2[..., 3] > 200)
hand = max(components(skin2[700:950, 300:620], 2000), key=len)
tip_i = np.argmin(hand[:, 1])
tip = [int(hand[tip_i, 1] + 300 + 4), int(hand[tip_i, 0] + 700)]
# closed-mouth patch: the connected non-skin mouth blob (outline + inside) painted over with skin and a closed smile line
def closed_patch(arr, mxy, name):
    mxc, myc = mxy
    WX, WY = int(mxc - 60), int(myc - 40)
    win = arr[WY:WY + 80, WX:WX + 120].astype(int)
    notskin = ~is_skin(win)
    cand = np.argwhere(notskin)
    sy, sx = cand[np.argmin(((cand - [myc - WY, mxc - WX]) ** 2).sum(axis=1))]
    blob = np.zeros_like(notskin); blob[sy, sx] = True; q = deque([(sy, sx)])
    while q:
        y, x = q.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < blob.shape[0] and 0 <= nx < blob.shape[1] and notskin[ny, nx] and not blob[ny, nx]:
                blob[ny, nx] = True; q.append((ny, nx))
    ys, xs = np.nonzero(blob)
    x0, x1, y0, y1 = int(xs.min() + WX), int(xs.max() + WX), int(ys.min() + WY), int(ys.max() + WY)
    w, h, pad = x1 - x0 + 1, y1 - y0 + 1, 6
    bx0, by0, bx1, by1 = x0 - pad, y0 - pad, x1 + pad + 1, y1 + pad + 1
    col = skin_near(arr, (x0, y0, x1, y1), 14)
    pw, ph = bx1 - bx0, by1 - by0
    patch = np.zeros((ph, pw, 4), np.float32); patch[..., :3] = col
    cover = np.zeros((ph, pw), np.float32); cover[ys + WY - by0, xs + WX - bx0] = 1.0
    cover = np.asarray(Image.fromarray((cover * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32)
    sub = arr[by0:by1, bx0:bx1].astype(int)
    other = ~is_skin(sub) & ~(np.asarray(Image.fromarray(((cover > 0) * 255).astype(np.uint8), "L")) > 0)
    cover[other] = 0
    patch[..., 3] = cover
    img = Image.fromarray(patch.astype(np.uint8), "RGBA")
    d = ImageDraw.Draw(img)
    sx0, sx1, syy = pad + w * 0.16, pad + w * 0.84, pad + h * 0.30
    d.line([(sx0 + (sx1 - sx0) * k / 20, syy + 4.5 * np.sin(np.pi * k / 20)) for k in range(21)], fill=(112, 50, 40, 255), width=5, joint="curve")
    img.save(f"{OUT}/v4_{name}_closed.png")
    return [bx0, by0], col, (x0, y0, x1, y1)
# the mouth: the largest reddish region under the eyes
eyes2 = find_eyes(p2, (380, 250, 800, 520))
red = (p2[..., 0].astype(int) > 150) & (p2[..., 1].astype(int) < 150) & (p2[..., 0].astype(int) - p2[..., 1].astype(int) > 45) & (p2[..., 3] > 200)
ey = int(max(e[1] + e[3] / 2 for e in eyes2)); exl, exr = int(eyes2[0][0]), int(eyes2[1][0])
red[:ey + 8] = False; red[ey + 140:] = False; red[:, :exl - 10] = False; red[:, exr + 10:] = False
mouth = max(components(red, 8), key=len)
closed2, skin2c, mbox2 = closed_patch(p2, (float(mouth[:, 1].mean()), float(mouth[:, 0].mean())), "sit_p2")
# panel mask: panel surface inside each quad (shrunk to stay off the drawn border), minus finger and outline
r2, g2, b2 = p2[..., 0].astype(int), p2[..., 1].astype(int), p2[..., 2].astype(int)
surface = (lum2 > 150) & ~((r2 - b2 > 28) & (r2 > 170)) & (p2[..., 3] > 200)
full = np.zeros((H2, W2), bool)
for qd in (qa, qb):
    qq = np.array(qd, float); cc = qq.mean(axis=0)
    m = Image.new("L", (W2, H2), 0); ImageDraw.Draw(m).polygon([tuple(cc + (p - cc) * 0.965) for p in qq], fill=255)
    full |= (np.asarray(m) > 0) & surface
mimg = Image.fromarray((full * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.8))
MX0, MY0, MX1, MY1 = 100, 500, 520, 960
crop = mimg.crop((MX0, MY0, MX1, MY1))
Image.merge("RGBA", (Image.new("L", crop.size, 255),) * 3 + (crop,)).save(f"{OUT}/v4_sit_p2_panelmask.png", optimize=True)
meta["p2"] = {"eyes": eyes2, "closed": closed2, "skin": skin2c, "a": qa, "b": qb, "tip": tip, "mask": [MX0, MY0]}
# head alignment of ② onto ①: offset that puts the eye midpoints together
e1 = np.mean([[e[0], e[1]] for e in meta["p1"]["eyes"]], axis=0); e2 = np.mean([[e[0], e[1]] for e in eyes2], axis=0)
meta["p2"]["off"] = [round(float(e1[0] - e2[0]), 1), round(float(e1[1] - e2[1]), 1)]
meta["p1"]["off"] = [0, 0]
print("p1", meta["p1"]); print("p2", meta["p2"], "mouth box", mbox2)


# ------------------------------------------------------------------ citizen sheets
def key_cell(sheet, box, seeds=("top", "left", "right"), drop=400, loose=False):
    """Cut a cell off the cream paper. Paper = near the paper colour, or any light neutral (the dashed guide lines and
    the ground shadow count as paper). The soft rim between ink and paper becomes ink at partial opacity."""
    a = np.asarray(sheet.crop(box)).astype(np.float32)
    H, W, _ = a.shape
    paper = np.median(np.concatenate([a[0:3].reshape(-1, 3), a[:, 0:3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)]), axis=0)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    sat = a.max(axis=2) - a.min(axis=2)
    bgl = (np.sqrt(((a - paper) ** 2).sum(axis=2)) < 28) | ((lum > 188) & (sat < 20))
    if loose:         # standing figures: the warm grey ground shadow under the slippers is paper too
        bgl |= (lum > 170) & (sat < 34)
    seen = np.zeros((H, W), bool); q = deque()
    def seed(y, x):
        if bgl[y, x] and not seen[y, x]:
            seen[y, x] = True; q.append((y, x))
    if "top" in seeds:
        for x in range(W): seed(0, x)
    if "bottom" in seeds:
        for x in range(W): seed(H - 1, x)
    if "left" in seeds:
        for y in range(H): seed(y, 0)
    if "right" in seeds:
        for y in range(H): seed(y, W - 1)
    while q:
        y, x = q.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < H and 0 <= nx < W and not seen[ny, nx] and bgl[ny, nx]:
                seen[ny, nx] = True; q.append((ny, nx))
    if loose:         # paper enclosed by the figure (between the legs) — large, paper-coloured, no white props here
        pd = np.sqrt(((a - paper) ** 2).sum(axis=2))
        for c in components(bgl & ~seen, 800):
            if pd[c[:, 0], c[:, 1]].mean() < 14:
                seen[c[:, 0], c[:, 1]] = True
    fg = ~seen
    # drop loose marks (speech lines, panel numbers, sparkles); keep every sizeable part (a hand entering the panel)
    keep = np.zeros_like(fg)
    for c in components(fg, drop):
        keep[c[:, 0], c[:, 1]] = True
    alpha = keep.astype(np.float32)
    near = np.asarray(Image.fromarray(((~keep) * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(5))) > 0
    edge = near & keep
    lp, li = float(paper @ np.array([0.299, 0.587, 0.114])), 40.0
    ramp = np.clip((lp - lum) / (lp - li), 0.0, 1.0)
    alpha[edge] = np.maximum(ramp[edge], 0.0)
    rgb = a.copy(); rgb[edge] = INK
    return np.dstack([rgb, alpha * 255]).astype(np.uint8)


def upscale(arr):
    """3x: premultiplied bicubic colour, a smoothed then re-tightened silhouette, ink on the rim, light unsharp inside."""
    h, w = arr.shape[:2]
    size = (w * K, h * K)
    a = arr[..., 3].astype(np.float32) / 255.0
    fr = lambda ch: np.asarray(Image.fromarray(ch.astype(np.float32), "F").resize(size, Image.BICUBIC))
    pre = [fr(arr[..., c].astype(np.float32) * a) for c in range(3)]
    ab = np.clip(fr(a), 0, 1)
    rgb = np.dstack([p / np.maximum(ab, 1e-3) for p in pre])
    sil = np.asarray(Image.fromarray((ab * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.3))).astype(np.float32) / 255.0
    sil = np.clip((sil - 0.22) / (0.78 - 0.22), 0, 1)
    rgb[sil < 0.985] = INK
    rgb = np.clip(rgb, 0, 255)
    sharp = np.asarray(Image.fromarray(rgb.astype(np.uint8), "RGB").filter(ImageFilter.UnsharpMask(radius=2.2, percent=65, threshold=2))).astype(np.float32)
    inner = sil >= 0.999
    rgb[inner] = sharp[inner]
    return np.dstack([rgb, sil * 255]).astype(np.uint8)


def align(A, B, region, rng=8):
    """Translation (dx, dy) that moves B onto A, by brute force over the region (y0, y1, x0, x1) at 1x."""
    g = lambda arr: (arr[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114])) * (arr[..., 3] / 255.0)
    GA, GB = g(A), g(B)
    y0, y1, x0, x1 = region
    best = None
    for dy in range(-rng, rng + 1):
        for dx in range(-rng, rng + 1):
            e = np.abs(GA[y0:y1, x0:x1] - np.roll(np.roll(GB, dy, 0), dx, 1)[y0:y1, x0:x1]).mean()
            if best is None or e < best[0]:
                best = (e, dx, dy)
    return best[1], best[2]


expr = Image.open(f"{SRC}/citizen_expr.png").convert("RGB")
turn = Image.open(f"{SRC}/citizen_turnaround.png").convert("RGB")
poses = Image.open(f"{SRC}/citizen_poses.png").convert("RGB")
# expression cells (inside the dashed lines); busts are cut by the cell's bottom line, so no seeds there
COLS = {"front": (194, 646), "34": (655, 1066), "side": (1075, 1520)}
ROWS = {"neutral": (59, 333), "talk": (342, 616), "smile": (623, 905)}      # neutral and talk cells the same height (they are blended)
pieces = {}
for (cn, (cx0, cx1)) in COLS.items():
    for (rn, (ry0, ry1)) in ROWS.items():
        pieces[f"{cn}_{rn}"] = key_cell(expr, (cx0, ry0, cx1, ry1))
# the side view talks (CUT 5): the talking cell is aligned onto the neutral one and only a feathered area around the mouth
# is taken from it (premultiplied blend), so swapping the two whole images moves nothing but the mouth — even on the profile edge
N, T = pieces["side_neutral"], pieces["side_talk"]
dx, dy = align(N, T, (20, 200, 60, N.shape[1] - 60))
T = np.roll(np.roll(T, dy, 0), dx, 1)
red = (T[..., 0].astype(int) > 150) & (T[..., 1].astype(int) < 150) & (T[..., 0].astype(int) - T[..., 1].astype(int) > 45) & (T[..., 3] > 200)
mc = max(components(red, 8), key=len)
my, mxx = mc[:, 0].mean(), mc[:, 1].mean()
m = Image.new("L", (N.shape[1], N.shape[0]), 0)
ImageDraw.Draw(m).ellipse([mxx - 30, my - 22, mxx + 30, my + 24], fill=255)
m = np.asarray(m.filter(ImageFilter.GaussianBlur(4))).astype(np.float32)[..., None] / 255
na, ta = N[..., 3:4].astype(np.float32) / 255, T[..., 3:4].astype(np.float32) / 255
pa = na * (1 - m) + ta * m
prgb = (N[..., :3] * na * (1 - m) + T[..., :3] * ta * m) / np.maximum(pa, 1e-3)
talk = np.dstack([prgb, pa * 255]).astype(np.uint8)
print("side talk→neutral shift", (dx, dy), "mouth at", (round(mxx), round(my)))
# the 3/4 busts are mirrored so he faces right, toward the official beside him
SAVE = {"cz_side_neutral": N, "cz_side_talk": talk, "cz_34_smile": pieces["34_smile"][:, ::-1].copy(), "cz_34_neutral": pieces["34_neutral"][:, ::-1].copy(),
        "cz_front_smile": pieces["front_smile"], "cz_front_neutral": pieces["front_neutral"]}
# full figures from the turnaround (the ground shadow and guide lines go with the paper)
SAVE["cz_front"] = key_cell(turn, (222, 72, 492, 700), seeds=("top", "left", "right", "bottom"), loose=True)
SAVE["cz_back"] = key_cell(turn, (1278, 72, 1532, 700), seeds=("top", "left", "right", "bottom"), loose=True)
# seated cup panels (inside the panel border): 5 holds the cup, 6 offers it, 7 = his hand has taken it
SAVE["cz_cup"] = key_cell(poses, (18, 387, 529, 668), seeds=("top", "left", "right"))
SAVE["cz_offer"] = key_cell(poses, (551, 387, 1102, 668), seeds=("top", "left", "right"))
SAVE["cz_given"] = key_cell(poses, (1124, 387, 1657, 668), seeds=("top", "left"))
for name, arr in SAVE.items():
    up = upscale(arr)
    Image.fromarray(up, "RGBA").save(f"{OUT}/v4_{name}.png", optimize=True)
    h, w = up.shape[:2]
    face = (0, 0, w, int(h * (0.55 if name in ("cz_front", "cz_back") else 0.8)))
    eyes = find_eyes(up, face) if name != "cz_back" else []
    skin = None
    if eyes:      # eyelid colour: the skin between the eye and the brow
        ex, ey_, ew, eh = eyes[0]
        skin = skin_near(up, (int(ex - 18), int(ey_ - eh / 2 - 26), int(ex + 18), int(ey_ - eh / 2 - 6)), pad=0)
    meta[name] = {"size": [w, h], "eyes": eyes, "skin": skin}
    print(name, (w, h), "eyes", eyes, "skin", skin)
# the back view is an out-of-focus foreground shoulder in CUT 3: blur it once here (premultiplied, so no dark fringe)
back = np.asarray(Image.open(f"{OUT}/v4_cz_back.png").convert("RGBA")).astype(np.float32)
ab = back[..., 3:4] / 255
blur = lambda ch: np.asarray(Image.fromarray(np.clip(ch, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(7))).astype(np.float32)
pre = np.dstack([blur(back[..., c] * ab[..., 0]) for c in range(3)])
bal = blur(ab[..., 0] * 255)[..., None] / 255
Image.fromarray(np.dstack([pre / np.maximum(bal, 1e-3), bal * 255]).clip(0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/v4_cz_back_blur.png", optimize=True)
json.dump(meta, open(f"{OUT}/v4_meta.json", "w"), indent=1)
print("ok")
