"""Split each keyed bust into head / body layers and upscale 3x for the 1080p motion-comic test.

Edges: the silhouette is upscaled as a smoothed alpha (blur + re-tighten, no staircase), and every
anti-aliased silhouette pixel takes the ink colour — in this style every outer edge is a dark outline,
so no paper halo or resampling speckles can show against a new background.

usage: python3 mc_layers.py WORK ../assets   (after mc_cutout.py; writes mc_{listening,smile}_{head,body}.png at 3x)
"""
import json, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SP, OUT = sys.argv[1], sys.argv[2]
INSET = (3, 3)
K = 3
INK = np.array([40, 35, 33], np.float32)
al = json.load(open(f"{SP}/mc/align.json"))
bdx, bdy = al["body"]; hdx, hdy = al["head"]
HEAD_PTS = [(60, 120), (55, 60), (100, 15), (150, -5), (200, 0), (268, 50), (268, 115), (248, 150), (226, 172), (210, 188)]
HEAD_LEFT = [(130, 192), (90, 178), (58, 150)]
COLLAR_UP = [(204, 196), (197, 203), (168, 225), (150, 202), (146, 196)]
COLLAR_EXT = [(214, 200), (207, 216), (168, 242), (138, 213), (136, 198)]

def poly(name, collar):
    hx, hy = (0, 0) if name == "listening" else (-hdx, -hdy)
    bx, by = (0, 0) if name == "listening" else (-bdx, -bdy)
    pts = [(x + hx, y + hy) for x, y in HEAD_PTS] + [(x + bx, y + by) for x, y in collar] + [(x + hx, y + hy) for x, y in HEAD_LEFT]
    return [((x - INSET[0]) * K, (y - INSET[1]) * K) for x, y in pts]

def fresize(ch, size):
    return np.asarray(Image.fromarray(ch.astype(np.float32), "F").resize(size, Image.BICUBIC))

def polymask(size, pts):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    return np.asarray(m.filter(ImageFilter.GaussianBlur(2.2))).astype(np.float32) / 255.0

meta = json.load(open(f"{OUT}/mc_layers.json"))
for name in ("listening", "smile"):
    key = np.asarray(Image.open(f"{SP}/mc/key_{name}.png").convert("RGBA")).astype(np.float32)
    h, w = key.shape[:2]
    size = (w * K, h * K)
    a = key[..., 3] / 255.0
    pre = [fresize(key[..., c] * a, size) for c in range(3)]
    ab = np.clip(fresize(a, size), 0, 1)
    rgb = np.dstack([p / np.maximum(ab, 1e-3) for p in pre])
    # silhouette: smooth the 1x staircase, then tighten back to a crisp edge
    sil = np.asarray(Image.fromarray((ab * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.3))).astype(np.float32) / 255.0
    sil = np.clip((sil - 0.22) / (0.78 - 0.22), 0, 1)
    edge = sil < 0.985
    rgb[edge] = INK
    rgb = np.clip(rgb, 0, 255)
    sharp = np.asarray(Image.fromarray(rgb.astype(np.uint8), "RGB").filter(ImageFilter.UnsharpMask(radius=2.2, percent=65, threshold=2))).astype(np.float32)
    inner = sil >= 0.999
    rgb[inner] = sharp[inner]
    m_up, m_ext = polymask(size, poly(name, COLLAR_UP)), polymask(size, poly(name, COLLAR_EXT))
    # the neck carried on under the collar is painted neck-shade skin, so a small head shift never shows collar in the V
    bx, by = (0, 0) if name == "listening" else (-bdx, -bdy)
    band = [((x + bx - INSET[0]) * K, (y + by - INSET[1]) * K) for x, y in COLLAR_EXT + COLLAR_UP[::-1]]
    bm = Image.new("L", size, 0); ImageDraw.Draw(bm).polygon(band, fill=255)
    bm = np.asarray(bm.filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255.0
    sx, sy = (165 + bx - INSET[0]) * K, (212 + by - INSET[1]) * K
    neck = np.median(rgb[sy - 6:sy + 6, sx - 6:sx + 6].reshape(-1, 3), axis=0)
    rgb_head = rgb * (1 - bm[..., None]) + neck * bm[..., None]
    sil_head = sil                      # paint only where the drawing is opaque (collar), never into the paper
    for part, col, alpha in (("head", rgb_head, sil_head * m_ext), ("body", rgb, sil * (1 - m_up))):
        Image.fromarray(np.dstack([col, alpha * 255]).astype(np.uint8), "RGBA").save(f"{OUT}/mc_{name}_{part}.png", optimize=True)
    print(name, "ok", size, "neck", neck.round())
