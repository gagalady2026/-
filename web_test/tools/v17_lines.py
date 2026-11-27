"""CUT 5a: the citizen's profile (v7, cut from the expression sheet and enlarged 3x) has black outlines about 7 px wide, so on
screen (drawn at 1.25) they are about 9 px against about 5 px on his 3/4 close-ups (v15) a few seconds later (11-17 s). This
thins the black outline of the profile to the 3/4 face's weight, keeping its colours and its soft (anti-aliased) edges.

How: at twice the size (premultiplied alpha), each black outline is measured (its local width), and only where it is wider
than the 3/4 face's lines (4 px of the picture, 5 px on screen) do the fills on either side (skin, hair, collar, or the
transparent background, counted as brightest) close in on it: a pixel there takes the brightest pixel within the amount
that line is too wide (half of it each side, at most 1.8 px), chosen on a slightly smoothed brightness so the edges move
together and stay clean, and keep their own soft ramps. Lines already thin are left alone. Only black, unsaturated strokes
are touched: the eye (pupil and lid line) and the mouth are left as drawn, and so are the coloured lines (wrinkles, ear,
mouth line) and the boundary between his dark and grey hair. Then back to the picture's size.

usage: python3 -I tools/v17_lines.py assets_v7/v7_cz_side_sad.png assets_v7/v7_cz_side_sad_talk.png assets_v17
  → assets_v17/v17_cz_side_sad.png, v17_cz_side_sad_talk.png (same size, same alignment) and v17_meta.json
"""
import json, os, sys
import numpy as np
from PIL import Image

UP = 2                               # work at twice the size, so the edges move by fractions of a pixel
TARGET = 4.0                         # px of the picture: the 3/4 close-ups' line weight (5 px on screen / 1.25)
THIN_MAX = 1.8                       # px of the picture taken off each side at most
CORE = 58                            # a black outline: brightness (over white) under this and nearly grey
SAT = 45
PROTECT = [(392, 325, 456, 415),     # the eye: pupil and lid line, drawn shapes (x0, y0, x1, y1, picture px)
           (350, 470, 460, 560)]     # the mouth (closed line / open mouth)


def resize(arr, size):
    return np.stack([np.asarray(Image.fromarray(arr[..., c].astype(np.float32), "F").resize(size, Image.LANCZOS)) for c in range(arr.shape[-1])], -1)


def dilate(mask, r):
    out = mask.copy()
    ri = int(np.ceil(r))
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            if dy * dy + dx * dx <= r * r:
                out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def blur(a):
    """a small Gaussian (1-4-6-4-1, twice), to choose by a brightness that does not flicker pixel to pixel"""
    for _ in range(2):
        for ax in (0, 1):
            a = (np.roll(a, -2, ax) + 4 * np.roll(a, -1, ax) + 6 * a + 4 * np.roll(a, 1, ax) + np.roll(a, 2, ax)) / 16
    return a


def depth_map(mask, n=40):
    """how far inside the mask each pixel is (4-connected erosion steps)"""
    d = np.zeros(mask.shape, np.float64); cur = mask.copy(); k = 0
    while cur.any() and k < n:
        k += 1; d[cur] = k
        e = cur.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            e &= np.roll(np.roll(cur, dy, 0), dx, 1)
        cur = e
    return d


def maxfilter(a, r):
    out = a.copy(); ri = int(np.ceil(r))
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            if dy * dy + dx * dx <= r * r:
                out = np.maximum(out, np.roll(np.roll(a, dy, 0), dx, 1))
    return out


def thin(path):
    im = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    h, w = im.shape[:2]
    pm = np.concatenate([im[..., :3] * im[..., 3:4] / 255.0, im[..., 3:4]], -1)        # premultiplied
    P = resize(pm, (w * UP, h * UP)).astype(np.float64)
    P[..., 3] = np.clip(P[..., 3], 0, 255); P[..., :3] = np.clip(P[..., :3], 0, None)
    P[..., :3] = np.minimum(P[..., :3], P[..., 3:4])
    a = P[..., 3:4] / 255.0
    over = P[..., :3] + (1 - a) * 255.0                                                   # over white: transparent = brightest
    B = over.mean(-1)
    core = (B < CORE) & (over.max(-1) - over.min(-1) < SAT)
    prot = np.zeros(core.shape, bool)
    for x0, y0, x1, y1 in PROTECT:
        prot[y0 * UP:y1 * UP, x0 * UP:x1 * UP] = True
    core &= ~prot
    # the line's half-width at each of its pixels (the deepest point across it, spread over the line), and how much of it
    # each side is too much: (width - target) / 2, at most THIN_MAX (all at twice the size)
    d = depth_map(core)
    half = maxfilter(d, 9 * UP / 2) * core
    half = maxfilter(half, 2 * UP)                                    # reach the line's soft edges too
    rmap = np.clip(half - TARGET * UP / 2, 0, THIN_MAX * UP)
    r = THIN_MAX * UP
    zone = (rmap > 0) & ~prot
    Bs = blur(B)
    best, bestP = Bs.copy(), P.copy()
    ri = int(np.ceil(r))
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            dist = (dy * dy + dx * dx) ** 0.5
            if (dy or dx) and dist <= r:
                sB = np.roll(np.roll(Bs, dy, 0), dx, 1)
                take = (sB > best) & (dist <= rmap)
                if take.any():
                    sP = np.roll(np.roll(P, dy, 0), dx, 1)
                    best = np.where(take, sB, best)
                    bestP = np.where(take[..., None], sP, bestP)
    out = np.where(zone[..., None], bestP, P)
    small = resize(out, (w, h))
    al = np.clip(small[..., 3], 0, 255)
    rgb = np.where(al[..., None] > 0, small[..., :3] * 255.0 / np.maximum(al[..., None], 1e-6), 0)
    res = np.concatenate([np.clip(rgb, 0, 255), al[..., None]], -1)
    res[im[..., 3] == 0] = 0                                                              # nothing new outside his shape
    return np.round(res).astype(np.uint8), int(zone.sum() // (UP * UP))


def main(paths, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    meta = {"target_px": TARGET, "thin_max_px_each_side": THIN_MAX, "core_brightness": CORE, "protect": PROTECT, "files": {}}
    for p in paths:
        res, n = thin(p)
        name = os.path.basename(p).replace("v7_", "v17_")
        Image.fromarray(res, "RGBA").save(os.path.join(out_dir, name))
        meta["files"][name] = {"source": os.path.basename(p), "pixels_in_zone": n}
        print(name, n)
    json.dump(meta, open(os.path.join(out_dir, "v17_meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:-1], sys.argv[-1])
