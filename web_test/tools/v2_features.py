"""Find eyes and mouth on each GPT character image (flat cel style: black oval eyes, small mouth).

usage: python3 v2_features.py SRC_DIR   (st_*.png / sit_*.png as named in v2_prep.py; writes SRC_DIR/features.json + debug crops)
"""
import json, sys
from collections import deque
import numpy as np
from PIL import Image, ImageDraw
D = sys.argv[1]
def components(mask, min_area=20):
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    out = []
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]: continue
        q = deque([(y0, x0)]); seen[y0, x0] = True; pts = []
        while q:
            y, x = q.popleft(); pts.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; q.append((ny, nx))
        if len(pts) >= min_area:
            p = np.array(pts); out.append({"n": len(pts), "y0": int(p[:, 0].min()), "y1": int(p[:, 0].max()), "x0": int(p[:, 1].min()), "x1": int(p[:, 1].max()),
                                           "cy": float(p[:, 0].mean()), "cx": float(p[:, 1].mean())})
    return out
res = {}
for n, face in (("st_neutral", (380, 120, 700, 360)), ("st_talk", (380, 120, 700, 360)), ("st_listen", (380, 120, 700, 360)), ("st_smile", (380, 120, 700, 360)),
                ("sit_point1", (300, 220, 720, 520)), ("sit_point2", (300, 250, 720, 540))):
    a = np.asarray(Image.open(f"{D}/{n}.png").convert("RGBA")).astype(int)
    x0, y0, x1, y1 = face
    sub = a[y0:y1, x0:x1]
    r, g, b, al = sub[..., 0], sub[..., 1], sub[..., 2], sub[..., 3]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    # eyes: very dark, enclosed by skin (dark hair is excluded by requiring skin above and below within 25 px)
    dark = (lum < 60) & (al > 200)
    skin = (r > 200) & (g > 150) & (b > 120) & (r - b > 25)
    comps = [c for c in components(dark, 60) if 8 <= c["x1"] - c["x0"] <= 40 and 14 <= c["y1"] - c["y0"] <= 50]
    eyes = []
    for c in comps:
        cy, cx = int(c["cy"]), int(c["cx"])
        up = skin[max(0, c["y0"] - 12):c["y0"] - 2, cx].any() if c["y0"] > 14 else False
        dn = skin[c["y1"] + 2:c["y1"] + 14, cx].any()
        side = skin[cy, max(0, c["x0"] - 12):c["x0"]].any() and skin[cy, c["x1"] + 1:c["x1"] + 13].any()
        if dn and side: eyes.append(c)
    eyes = sorted(eyes, key=lambda c: -c["n"])[:2]
    eyes = sorted(eyes, key=lambda c: c["cx"])
    # mouth: reddish / dark-red pixels below the eyes, between them
    ey = max(e["y1"] for e in eyes) if eyes else 80
    exl, exr = (eyes[0]["cx"], eyes[-1]["cx"]) if eyes else (60, 200)
    red = (r > 150) & (g < 150) & (b < 140) & (r - g > 45) & (al > 200)
    red[:ey + 10, :] = False
    red[:, :int(exl) - 10] = False; red[:, int(exr) + 10:] = False
    mc = sorted(components(red, 8), key=lambda c: -c["n"])
    mouth = mc[0] if mc else None
    out = {"eyes": [{"x": round(e["cx"] + x0, 1), "y": round(e["cy"] + y0, 1), "w": e["x1"] - e["x0"] + 1, "h": e["y1"] - e["y0"] + 1} for e in eyes]}
    if mouth: out["mouth"] = {"x": round(mouth["cx"] + x0, 1), "y": round(mouth["cy"] + y0, 1), "w": mouth["x1"] - mouth["x0"] + 1, "h": mouth["y1"] - mouth["y0"] + 1}
    res[n] = out
    print(n, out)
    im = Image.open(f"{D}/{n}.png").convert("RGBA"); bg = Image.new("RGBA", im.size, (235, 232, 225, 255)); bg.alpha_composite(im)
    d = ImageDraw.Draw(bg)
    for e in out["eyes"]: d.rectangle([e["x"] - e["w"] / 2, e["y"] - e["h"] / 2, e["x"] + e["w"] / 2, e["y"] + e["h"] / 2], outline=(255, 0, 0, 255), width=2)
    if "mouth" in out: m = out["mouth"]; d.rectangle([m["x"] - m["w"] / 2, m["y"] - m["h"] / 2, m["x"] + m["w"] / 2, m["y"] + m["h"] / 2], outline=(0, 160, 0, 255), width=2)
    bg.crop((face[0] - 40, face[1] - 40, face[2] + 40, face[3] + 40)).convert("RGB").save(f"{D}/feat_{n}.png")
json.dump(res, open(f"{D}/features.json", "w"), indent=1)
