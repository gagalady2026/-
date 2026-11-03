"""Cut the 3/4 busts (listening / gentle smile) out of the expression sheet for the motion-comic test.

usage: python3 mc_cutout.py WORK WORK/mc   (WORK/sheets/img_01_fb30c814e8_from_transcript.jpg = the expression sheet; writes WORK/mc/key_*.png + align.json)
"""
import json, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SP = sys.argv[1]
OUT = sys.argv[2]
sheet = Image.open(f"{SP}/sheets/img_01_fb30c814e8_from_transcript.jpg").convert("RGB")
CELLS = {"listening": (615, 371, 984, 686), "smile": (615, 693, 984, 1008)}   # 3/4 column, inside the dashed cell lines

def key(img):
    a = np.asarray(img).astype(np.float32)
    H, W, _ = a.shape
    border = np.concatenate([a[0:3, :].reshape(-1, 3), a[:, 0:3].reshape(-1, 3), a[:, -3:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((a - bg) ** 2).sum(axis=2))
    tol = 26.0
    seen = np.zeros((H, W), bool)
    q = deque()
    for x in range(W):
        for y in (0,):                      # not the bottom row: the bust is cut there (the white ID tag touches it)
            if dist[y, x] < tol and not seen[y, x]: seen[y, x] = True; q.append((y, x))
    for y in range(H):
        for x in (0, W - 1):
            if dist[y, x] < tol and not seen[y, x]: seen[y, x] = True; q.append((y, x))
    while q:
        y, x = q.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < H and 0 <= nx < W and not seen[ny, nx] and dist[ny, nx] < tol:
                seen[ny, nx] = True; q.append((ny, nx))
    alpha = (~seen).astype(np.float32)
    # soft edge = the anti-aliased ramp between the ink outline and the paper (within 2 px of the paper):
    # colour-to-alpha against the ink, so the ramp becomes ink at partial opacity (no grey or paper halo)
    near = np.zeros_like(seen)
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            near |= np.roll(np.roll(seen, dy, 0), dx, 1)
    edge = near & ~seen
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    lp, li = float(bg @ np.array([0.299, 0.587, 0.114])), 34.0
    ramp = np.clip((lp - lum) / (lp - li), 0.0, 1.0)
    alpha[edge] = ramp[edge]
    rgb = a.copy()
    rgb[edge] = (40, 35, 33)
    return np.dstack([rgb, alpha * 255]).astype(np.uint8), bg

rgba = {}
for name, box in CELLS.items():
    arr, bg = key(sheet.crop(box))
    rgba[name] = arr
    Image.fromarray(arr).save(f"{SP}/mc/key_{name}.png")
    print(name, "paper", bg.round(1), "size", arr.shape)

# align the smile bust onto the listening bust (body and head separately) by brute-force translation
def gray(arr):
    return (arr[..., :3].astype(np.float32) @ np.array([0.299, 0.587, 0.114])) * (arr[..., 3] / 255.0)
A, B = gray(rgba["listening"]), gray(rgba["smile"])
def best(region):
    y0, y1, x0, x1 = region
    best_ = None
    for dy in range(-14, 15):
        for dx in range(-14, 15):
            b = np.roll(np.roll(B, dy, 0), dx, 1)
            e = np.abs(A[y0:y1, x0:x1] - b[y0:y1, x0:x1]).mean()
            if best_ is None or e < best_[0]: best_ = (e, dx, dy)
    return best_
body = best((236, 310, 40, 330))
head = best((10, 125, 50, 270))
print("body shift (err,dx,dy)", body, "head shift", head)
json.dump({"body": body[1:], "head": head[1:]}, open(f"{SP}/mc/align.json", "w"))
