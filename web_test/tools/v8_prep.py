"""Pictures for the conversation-first cut of the animatic (assets_v8).

usage: python3 tools/v8_prep.py SRC OUT
  SRC  citizen_expr.png (the citizen expression sheet, the same file tools/v4_prep.py reads)
  writes
  OUT/v8_cz_34_talk.png  CUT 6 end: his 3/4 face, mirrored to face the official, talking (“고마워요, 한시름 놓았어요.”).
                         Only a feathered area round the mouth is taken from the sheet's talking cell (aligned onto the
                         neutral cell first), and the result is mirrored and upscaled exactly as v4_cz_34_neutral.png is, so
                         swapping the two pictures moves nothing but the mouth.

The keying, alignment and upscale functions are read from tools/v4_prep.py itself, so both pictures go through the same steps.
"""
import ast, json, os, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
ns = {"np": np, "Image": Image, "ImageDraw": ImageDraw, "ImageFilter": ImageFilter, "deque": deque,
      "INK": np.array([38, 33, 31], np.float32), "K": 3}
tree = ast.parse(open(os.path.join(HERE, "v4_prep.py"), encoding="utf-8").read())
funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("components", "key_cell", "upscale", "align")]
exec(compile(ast.Module(body=funcs, type_ignores=[]), "v4_prep.py", "exec"), ns)
key_cell, upscale, align, components = ns["key_cell"], ns["upscale"], ns["align"], ns["components"]

expr = Image.open(f"{SRC}/citizen_expr.png").convert("RGB")
N = key_cell(expr, (655, 59, 1066, 333))           # the 3/4 column, neutral row (as in v4_prep.py)
T = key_cell(expr, (655, 342, 1066, 616))          # the 3/4 column, talking row (the same height)
dx, dy = align(N, T, (20, 150, 60, N.shape[1] - 60))
T = np.roll(np.roll(T, dy, 0), dx, 1)
# the open mouth: the largest red component in the talking cell
red = (T[..., 0].astype(int) > 150) & (T[..., 1].astype(int) < 150) & (T[..., 0].astype(int) - T[..., 1].astype(int) > 45) & (T[..., 3] > 200)
mc = max(components(red, 8), key=len)
my, mx = mc[:, 0].mean(), mc[:, 1].mean()
h0, h1 = mc[:, 0].min(), mc[:, 0].max()
w0, w1 = mc[:, 1].min(), mc[:, 1].max()
m = Image.new("L", (N.shape[1], N.shape[0]), 0)
ImageDraw.Draw(m).ellipse([w0 - 14, h0 - 12, w1 + 14, h1 + 14], fill=255)
m = np.asarray(m.filter(ImageFilter.GaussianBlur(4))).astype(np.float32)[..., None] / 255
na, ta = N[..., 3:4].astype(np.float32) / 255, T[..., 3:4].astype(np.float32) / 255
pa = na * (1 - m) + ta * m
prgb = (N[..., :3] * na * (1 - m) + T[..., :3] * ta * m) / np.maximum(pa, 1e-3)
talk = np.dstack([prgb, pa * 255]).astype(np.uint8)
up = upscale(talk[:, ::-1].copy())                  # mirrored: he faces right, toward the official
os.makedirs(OUT, exist_ok=True)
Image.fromarray(up, "RGBA").save(f"{OUT}/v8_cz_34_talk.png", optimize=True)
meta = {"cz_34_talk": {"size": [up.shape[1], up.shape[0]], "talk_to_neutral_shift": [int(dx), int(dy)],
                       "mouth_1x": [int(w0), int(h0), int(w1), int(h1)]}}
json.dump(meta, open(f"{OUT}/v8_meta.json", "w"), indent=1)
print("ok", meta)
