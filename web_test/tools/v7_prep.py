"""Pictures for the consultation rework of the 36-second animatic (assets_v7).

usage: python3 tools/v7_prep.py SRC ASSETS_V4 ASSETS_V5 OUT
  SRC        citizen_poses.png (the citizen pose sheet)
  ASSETS_V4  v4_cz_side_neutral.png (his profile, made by tools/v4_prep.py)
  ASSETS_V5  v5_climb_a.png, v5_walk_away.png (the official from behind, made by tools/v5_prep.py)
  writes
  OUT/v7_cz_seated.png         CUT 4: the citizen sitting on the bench, 3/4 toward the official (pose sheet panel 2), keyed, 3x
  OUT/v7_cz_side_sad.png       CUT 5: his profile with the mouth corner turned slightly down and the eye heavy-lidded, its
                               upper lid lowered and drooping toward the outer corner (from the neutral profile)
  OUT/v7_cz_side_sad_talk.png  the same with a small, unsmiling open mouth: he talks about falling ill, not happily
  OUT/v7_official_ots.png      CUT 5: the official's head and shoulder from behind, mirrored to face the citizen, out of focus
  OUT/v7_walk_b.png            CUT 7c: the other step of the walk away: v5_walk_away.png with only the legs mirrored (the other
                               foot planted), so the two pictures alternate as a walk instead of one stride sliding or bouncing
"""
import json, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC, V4, V5, OUT = sys.argv[1:5]
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


def key_panel(sheet, box):
    """Cut a pose-sheet panel off the cream paper (flood fill from the top and sides; the warm grey ground shadow is paper
    too), drop loose marks (the panel number), ink-coloured soft rim. Same method as tools/v4_prep.py."""
    a = np.asarray(sheet.crop(box)).astype(np.float32)
    H, W, _ = a.shape
    paper = np.median(np.concatenate([a[0:3].reshape(-1, 3), a[:, 0:3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)]), axis=0)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    sat = a.max(axis=2) - a.min(axis=2)
    bgl = (np.sqrt(((a - paper) ** 2).sum(axis=2)) < 28) | ((lum > 188) & (sat < 20)) | ((lum > 170) & (sat < 34))
    seen = np.zeros((H, W), bool); q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if bgl[y, x] and not seen[y, x]: seen[y, x] = True; q.append((y, x))
    for y in range(H):
        for x in (0, W - 1):
            if bgl[y, x] and not seen[y, x]: seen[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < H and 0 <= nx < W and not seen[ny, nx] and bgl[ny, nx]:
                seen[ny, nx] = True; q.append((ny, nx))
    pd = np.sqrt(((a - paper) ** 2).sum(axis=2))
    for c in components(bgl & ~seen, 800):          # paper enclosed by the figure (between the legs and the bench)
        if pd[c[:, 0], c[:, 1]].mean() < 14:
            seen[c[:, 0], c[:, 1]] = True
    keep = np.zeros_like(seen)
    for c in components(~seen, 400):
        keep[c[:, 0], c[:, 1]] = True
    alpha = keep.astype(np.float32)
    near = np.asarray(Image.fromarray(((~keep) * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(5))) > 0
    edge = near & keep
    lp, li = float(paper @ np.array([0.299, 0.587, 0.114])), 40.0
    alpha[edge] = np.clip((lp - lum) / (lp - li), 0.0, 1.0)[edge]
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


def harmonic_fill(arr, mask, ring_skin):
    """Fill the masked pixels by diffusing the colours around them inward (no seam), keeping non-skin neighbours out."""
    F = arr[..., :3].astype(np.float32).copy()
    around = np.asarray(Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(9))) > 0
    fillm = mask | (around & ~is_skin(arr[..., :3].astype(int)))     # stray rim pixels are filled too, never pinned
    F[fillm] = ring_skin
    for _ in range(800):
        avg = (np.roll(F, 1, 0) + np.roll(F, -1, 0) + np.roll(F, 1, 1) + np.roll(F, -1, 1)) / 4
        F[fillm] = avg[fillm]
    soft = np.asarray(Image.fromarray((fillm * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)[..., None] / 255
    out = arr.copy()
    out[..., :3] = np.clip(arr[..., :3] * (1 - soft) + F * soft, 0, 255).astype(np.uint8)
    return out


# ---------------------------------------------------------------- CUT 4: sitting on the bench, turned toward the official
poses = Image.open(f"{SRC}/citizen_poses.png").convert("RGB")
seated = upscale(key_panel(poses, (437, 18, 826, 366)))
Image.fromarray(seated, "RGBA").save(f"{OUT}/v7_cz_seated.png", optimize=True)
ys, xs = np.nonzero(seated[..., 3] > 128)
meta["cz_seated"] = {"size": [seated.shape[1], seated.shape[0]], "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]}

# ---------------------------------------------------------------- CUT 5: a sad profile
side = np.asarray(Image.open(f"{V4}/v4_cz_side_neutral.png").convert("RGBA")).copy()
X0, Y0, X1, Y1 = 360, 490, 440, 530                       # the short mouth line at the front of the face (3x pixels)
win = side[Y0:Y1, X0:X1].astype(int)
r, g, b = win[..., 0], win[..., 1], win[..., 2]
line = (win[..., 3] > 200) & (r - g > 45) & (g < 170) & ((0.299 * r + 0.587 * g + 0.114 * b) < 175)
# the mouth stroke: start on the widest flat reddish piece (not the cheek wrinkle beside it) and take every non-skin pixel
# connected to it, so its dark core and soft rim go too
best = max(components(line, 10), key=lambda c: (c[:, 1].max() - c[:, 1].min()) - 2 * (c[:, 0].max() - c[:, 0].min()))
sy, sx = int(best[:, 0].mean()), int(best[:, 1].mean())
notskin = ~is_skin(win[..., :3]) & (win[..., 3] > 200)
blob = np.zeros_like(notskin); q = deque([(sy, sx)]); blob[sy, sx] = True
while q:
    y, x = q.popleft()
    for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
        if 0 <= ny < blob.shape[0] and 0 <= nx < blob.shape[1] and notskin[ny, nx] and not blob[ny, nx]:
            blob[ny, nx] = True; q.append((ny, nx))
ys, xs = np.nonzero(blob)
mx0, mx1, my0, my1 = xs.min() + X0, xs.max() + X0, ys.min() + Y0, ys.max() + Y0
mask = np.zeros(side.shape[:2], bool)
# grown past the pale halo the 3x sharpening left around every dark line, so the fill takes real skin from its edge
mask[Y0:Y1, X0:X1] = np.asarray(Image.fromarray((blob * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(13))) > 0
ring = side[my0 - 14:my1 + 14, mx0 - 14:mx1 + 14, :3].reshape(-1, 3).astype(int)
skin = np.median(ring[is_skin(ring)], axis=0)
sad = harmonic_fill(side, mask, skin)
# the eye, heavy-lidded. The upscale's sharpening left a light halo round the pupil, which a lid drawn over it at run time
# shows at its edge, so the lid is put into the picture: the halo and the top of the pupil are filled with the skin around
# them (diffused inward), the lower part of the pupil keeps a soft edge, and a lid line runs along the cut, higher at the
# front of the eye and lower at its outer corner (he faces left, so the outer corner is on the right)
EX, EY = 422.7, 371.1                                      # the eye as the page measures it (CZ.side.eyes)
ex0, ey0 = int(EX - 40), int(EY - 60)
win = sad[ey0:ey0 + 120, ex0:ex0 + 80].astype(np.float32)
lum = win[..., :3].sum(-1)
core = lum < 330
ys, xs = np.nonzero(core)
ptop, pbot, pl, pr = ys.min(), ys.max(), xs.min(), xs.max()
near = np.asarray(Image.fromarray((core * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(17))) > 0
xx = np.arange(win.shape[1])[None, :]; yy = np.arange(win.shape[0])[:, None]
lid_at = lambda x: ptop + (0.34 + 0.12 * np.clip((x - pl) / max(1, pr - pl), 0, 1)) * (pbot - ptop)
F = win[..., :3].copy()
F[near] = skin
for _ in range(600):
    avg = (np.roll(F, 1, 0) + np.roll(F, -1, 0) + np.roll(F, 1, 1) + np.roll(F, -1, 1)) / 4
    F[near] = avg[near]
wgt = np.clip((620 - lum) / 470, 0, 1)                     # how much of each pixel is pupil (its antialiased edge partly)
wgt[~near | (yy < lid_at(xx))] = 0
wgt = wgt[..., None]
pupil = np.where(core[..., None], win[..., :3], np.array([22, 16, 16], np.float32))
sad[ey0:ey0 + 120, ex0:ex0 + 80, :3] = np.clip(wgt * pupil + (1 - wgt) * F, 0, 255).astype(np.uint8)
lid_line = [(ex0 + x, ey0 + lid_at(x) - 2.0 * np.sin(np.pi * (x - pl + 3) / (pr - pl + 6)))
            for x in np.linspace(pl - 3, pr + 3, 14)]
meta["side_eye"] = {"pupil": [int(ex0 + pl), int(ey0 + ptop), int(ex0 + pr), int(ey0 + pbot)],
                    "lid": [[round(float(x), 1), round(float(y), 1)] for x, y in (lid_line[0], lid_line[-1])]}
# the line again, its back corner now a little lower than its front (in profile: the mouth corner turns down)
im = Image.fromarray(sad, "RGBA"); d = ImageDraw.Draw(im)
fx, fy = mx0 + 2, (my0 + my1) / 2 - 3                      # front end (toward the lips)
bx, by = mx1 - 2, (my0 + my1) / 2 + 5                      # back end (the corner)
d.line([(fx + (bx - fx) * k / 12, fy + (by - fy) * k / 12 - 1.5 * np.sin(np.pi * k / 12)) for k in range(13)], fill=(150, 70, 56, 255), width=6, joint="curve")
d.line(lid_line, fill=(36, 28, 26, 255), width=5, joint="curve")
im.save(f"{OUT}/v7_cz_side_sad.png", optimize=True)
# talking: a small, unsmiling open mouth at the same place
talk = im.copy(); d = ImageDraw.Draw(talk)
cx, cy = (fx + bx) / 2 - 2, (fy + by) / 2 + 2
d.ellipse([cx - 11, cy - 6, cx + 9, cy + 7], fill=(132, 58, 52, 255), outline=(70, 38, 34, 255), width=3)
talk.save(f"{OUT}/v7_cz_side_sad_talk.png", optimize=True)
meta["side_mouth"] = {"line": [int(mx0), int(my0), int(mx1), int(my1)], "skin": [int(v) for v in skin]}

# ---------------------------------------------------------------- CUT 5: the official from behind, over his shoulder
climb = Image.open(f"{V5}/v5_climb_a.png").convert("RGBA").transpose(Image.FLIP_LEFT_RIGHT)
part = np.asarray(climb.crop((200, 0, 900, 760))).astype(np.float32)     # head, shoulders, upper back
a = part[..., 3:4] / 255
blur = lambda ch: np.asarray(Image.fromarray(np.clip(ch, 0, 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(9))).astype(np.float32)
pre = np.dstack([blur(part[..., c] * a[..., 0]) for c in range(3)])
al = blur(a[..., 0] * 255)[..., None] / 255
Image.fromarray(np.dstack([pre / np.maximum(al, 1e-3), al * 255]).clip(0, 255).astype(np.uint8), "RGBA").save(f"{OUT}/v7_official_ots.png", optimize=True)
meta["official_ots"] = {"from": "v5_climb_a.png mirrored, crop (200, 0, 900, 760), blur 9"}

# ---------------------------------------------------------------- CUT 7c: the other step
# Below the hips only the legs are in the picture (bag, tablet and hands end above y 890). Mirror that part about the middle of the
# legs (x 569.5: the two legs together span 443..696 there, so the outline matches) and cross-fade into it over y 915..960, across
# the seat of the trousers where both versions are one shape.
walk = np.asarray(Image.open(f"{V5}/v5_walk_away.png").convert("RGBA")).astype(np.float32)
Hw, Ww = walk.shape[:2]
AX2 = 1139                                          # 2 x 569.5
src = AX2 - np.arange(Ww)
ok = (src >= 0) & (src < Ww)
mir = np.zeros_like(walk); mir[:, ok] = walk[:, src[ok]]
t = np.clip((np.arange(Hw) - 915) / 45, 0, 1); t = (t * t * (3 - 2 * t))[:, None, None]
pm = lambda im: np.dstack([im[..., :3] * im[..., 3:4] / 255, im[..., 3:4]])
mixed = pm(walk) * (1 - t) + pm(mir) * t
rgb = mixed[..., :3] / np.maximum(mixed[..., 3:4], 1e-3) * 255
out = np.dstack([rgb, mixed[..., 3:4]]).clip(0, 255).astype(np.uint8)
out[out[..., 3] == 0] = 0
Image.fromarray(out, "RGBA").save(f"{OUT}/v7_walk_b.png", optimize=True)
meta["walk_b"] = {"from": "v5_walk_away.png, legs below y 915..960 mirrored about x 569.5", "anchor": [569.5, 1383]}
json.dump(meta, open(f"{OUT}/v7_meta.json", "w"), indent=1)
print("ok", meta)
