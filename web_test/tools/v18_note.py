"""CUT 5: the user's picture of the official listening and taking notes (standing, the tablet in his left hand, a stylus in
his right, turned a little to his left), prepared for a short shot in which he writes while the citizen tells his story.

  - the writing arm — forearm from the sleeve, hand and stylus — is lifted off as its own layer, so it can turn a little
    about the sleeve (as the tablet arm of CUT 6 does) and the stylus make small strokes over the tablet; the place it leaves
    is filled from the colours around it (shirt, strap, lanyard), which only ever shows as a sliver beside the moving arm
  - measured for the page: his two eyes (the lids are lowered over them, looking down at what he writes), the skin colour
    of the lids, and the ID card (its white face and teal band, for the 동해시 / 체납관리단 lettering the page writes on it)
  - his smile (the user asked for a serious face while the citizen tells of his illness): the curved line is taken out
    (filled from the skin around it) and a short, level closed mouth of the same colour and weight is drawn in its place
Nothing else is redrawn: the picture is the user's, split into two layers.

usage: python3 -I tools/v18_note.py NOTE.png assets_v18
  → assets_v18/v18_note_base.png (without the writing hand), v18_note_hand.png (the hand alone, same size) and v18_meta.json
"""
import json, os, sys
from collections import deque
import numpy as np
from PIL import Image

HAND_BOX = (355, 425, 638, 600)    # x0, y0, x1, y1: the writing forearm, hand and stylus (picture px); the tablet hand is right of it
STYLUS = ((536, 444), (613, 507), 11)   # the stylus: from its cap to its tip, and half its width with the outline
CARD_BOX = (515, 560, 625, 660)    # the ID card on the lanyard
MOUTH_BOX = (612, 291, 664, 316)   # the smile (a reddish-brown curve, x 619-656, rising to the right)
MOUTH = ((629.0, 305.2), (647.5, 303.6), 3.0)   # the serious mouth: a short level line (ends, thickness), the face's slight tilt
FACE_BOX = (560, 200, 720, 320)    # where the eyes are


def components(mask):
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32); n = 0; sizes = {}
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not lab[y, x]:
                n += 1; lab[y, x] = n; q = deque([(y, x)]); c = 0
                while q:
                    cy, cx = q.popleft(); c += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = n; q.append((ny, nx))
                sizes[n] = c
    return lab, sizes


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dy * dy + dx * dx <= r * r:
                out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out


def main(src, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    im = np.asarray(Image.open(src).convert('RGBA')).astype(np.float64)
    rgb, al = im[..., :3], im[..., 3]
    L = rgb.mean(-1); sat = rgb.max(-1) - rgb.min(-1)
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    H, W = L.shape

    # ---- the eyes: the two dark ovals in the face
    x0, y0, x1, y1 = FACE_BOX
    lab, sizes = components((L[y0:y1, x0:x1] < 70) & (al[y0:y1, x0:x1] > 200))
    eyes = []
    for i, n in sorted(sizes.items(), key=lambda kv: -kv[1]):
        if 60 <= n <= 1500:
            ys, xs = np.nonzero(lab == i)
            hgt, wid = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
            if hgt > wid * 1.1 and wid <= 30 and hgt <= 45:   # small tall ovals (the eyes), not the brows or the hair
                eyes.append([round(float(xs.mean() + x0), 1), round(float(ys.mean() + y0), 1), int(wid), int(hgt)])
        if len(eyes) == 2: break
    eyes.sort()
    # the lids' skin: the face just under the eyes
    skin_px = []
    for ex, ey, ew, eh in eyes:
        box = rgb[int(ey + eh * 0.9):int(ey + eh * 1.6), int(ex - ew):int(ex + ew)].reshape(-1, 3)
        skin_px.append(box[(box[:, 0] > 200) & (box[:, 0] > box[:, 2] + 25)])
    skin = np.median(np.concatenate(skin_px), 0).round().astype(int).tolist()

    # ---- the ID card: its white face and the teal band over it
    x0, y0, x1, y1 = CARD_BOX
    white = (L > 225) & (sat < 30) & (al > 200); white[:y0] = False; white[y1:] = False; white[:, :x0] = False; white[:, x1:] = False
    lab, sizes = components(white[y0:y1, x0:x1]); big = max(sizes, key=sizes.get)
    ys, xs = np.nonzero(lab == big); ys = ys + y0; xs = xs + x0
    top = {x: ys[xs == x].min() for x in np.unique(xs)}                 # the face's top edge, column by column
    cols = np.array(sorted(top)); tops = np.array([top[c] for c in cols])
    keep = (cols > cols.min() + 4) & (cols < cols.max() - 4)
    slope = np.polyfit(cols[keep], tops[keep], 1)[0]; rot = float(np.degrees(np.arctan(slope)))
    teal = (G > R + 40) & (B > R + 30) & (al > 200)
    tx = slice(int(xs.min()) + 4, int(xs.max()) - 4)
    band_rows = [y for y in range(int(ys.min()) - 40, int(ys.min()) + 2) if teal[y, tx].mean() > 0.5]
    band = float(len(band_rows)) if band_rows else 14.0
    card = [round(float(xs.mean()), 1), round(float(ys.mean()), 1), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1), round(rot, 2), round(band, 1)]

    # ---- the writing hand: the skin of the right hand and the stylus in it, with their outline
    x0, y0, x1, y1 = HAND_BOX
    inbox = np.zeros(L.shape, bool); inbox[y0:y1, x0:x1] = True
    skinm = (R > 190) & (R > B + 30) & (G > 140) & (al > 200) & inbox
    lab, sizes = components(skinm)
    hand = lab == max(sizes, key=sizes.get)
    (ax, ay), (bx, by), pr = STYLUS                                                    # the stylus: everything within its capsule
    yy, xx = np.mgrid[0:H, 0:W]
    vx, vy = bx - ax, by - ay; tproj = np.clip(((xx - ax) * vx + (yy - ay) * vy) / (vx * vx + vy * vy), 0, 1)
    pen = (np.hypot(xx - (ax + tproj * vx), yy - (ay + tproj * vy)) <= pr) & (al > 0)
    pen &= ~(((B > R + 25) & (B > 150)) & (tproj < 0.9))                               # not the tablet under it (but its tip)
    core = hand | pen
    blue = (B > R + 25) & (B > 150)                                                    # the tablet stays where it is
    layer = dilate(core, 3) & inbox & (al > 0) & ~(blue & ~core)
    # soft edge: the outline ring is part of the hand; anything else dark beyond 3 px stays in the base
    base = im.copy(); hole = layer.copy()
    base[hole] = 0
    known = ~hole & (al > 0)
    acc = np.where(known[..., None], im, 0.0); wsum = known.astype(np.float64)
    fill = base.copy()
    todo = hole.copy()
    for _ in range(200):                                                              # diffuse the colours around inward
        if not todo.any(): break
        s = np.zeros_like(acc); c = np.zeros_like(wsum)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s += np.roll(np.roll(acc, dy, 0), dx, 1); c += np.roll(np.roll(wsum, dy, 0), dx, 1)
        new = todo & (c > 0)
        acc[new] = s[new] / c[new][:, None]; wsum[new] = 1.0; todo &= ~new
    fill[hole] = acc[hole]; fill[hole, 3] = 255
    hand_rgba = np.zeros_like(im); hand_rgba[layer] = im[layer]
    ys, xs = np.nonzero(hand)
    left = xs.min(); pivot = [round(float(left + 4), 1), round(float(ys[xs <= left + 8].mean()), 1)]   # the sleeve end of the forearm
    tip = np.nonzero(pen); tip = [round(float(tip[1].max()), 1), round(float(tip[0][np.argmax(tip[1])]), 1)] if pen.any() else None

    # ---- a serious mouth: take out the smile, draw a short level closed mouth (4x supersampled, then down)
    x0, y0, x1, y1 = MOUTH_BOX
    reg = fill[y0:y1, x0:x1]
    line = (reg[..., :3].mean(-1) < 205) & (reg[..., 0] - reg[..., 2] > 55)
    lp = reg[line][:, :3]; dark = lp.mean(-1) <= np.percentile(lp.mean(-1), 30)
    colour = np.median(lp[dark], 0)                                                   # the line's own (inked) colour, not its soft edge
    hole = np.zeros(fill.shape[:2], bool); hole[y0:y1, x0:x1] = dilate(line, 2)
    acc = fill.copy(); todo = hole.copy(); known = ~hole
    for _ in range(60):
        if not todo.any(): break
        s4 = np.zeros_like(acc); c4 = np.zeros(acc.shape[:2])
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            s4 += np.roll(np.roll(np.where(known[..., None], acc, 0), dy, 0), dx, 1); c4 += np.roll(np.roll(known.astype(float), dy, 0), dx, 1)
        new = todo & (c4 > 0); acc[new] = s4[new] / c4[new][:, None]; known |= new; todo &= ~new
    fill = acc
    from PIL import ImageDraw
    SS = 4; (ax, ay), (bx, by), lw = MOUTH
    pw, ph = (x1 - x0) * SS, (y1 - y0) * SS
    patch = Image.new('L', (pw, ph), 0); dr = ImageDraw.Draw(patch)
    pts = [((ax - x0) * SS, (ay - y0) * SS), (((ax + bx) / 2 - x0) * SS, ((ay + by) / 2 + 0.35 - y0) * SS), ((bx - x0) * SS, (by - y0) * SS)]
    dr.line(pts, fill=255, width=round(lw * SS), joint='curve')
    r = lw * SS / 2
    for px_, py_ in (pts[0], pts[-1]): dr.ellipse((px_ - r, py_ - r, px_ + r, py_ + r), fill=255)   # round ends
    cov = np.asarray(patch.resize((x1 - x0, y1 - y0), Image.LANCZOS)).astype(np.float64)[..., None] / 255
    fill[y0:y1, x0:x1, :3] = fill[y0:y1, x0:x1, :3] * (1 - cov) + colour * cov
    Image.fromarray(np.clip(np.round(fill), 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(out_dir, 'v18_note_base.png'))
    Image.fromarray(np.clip(np.round(hand_rgba), 0, 255).astype(np.uint8), 'RGBA').save(os.path.join(out_dir, 'v18_note_hand.png'))
    fy, fx = np.nonzero(al > 30)
    meta = {'source': os.path.basename(src), 'size': [W, H], 'figure_bbox': [int(fx.min()), int(fy.min()), int(fx.max()), int(fy.max())],
            'eyes': eyes, 'skin': skin, 'card': card, 'hand_pivot': pivot, 'stylus_tip': tip,
            'hand_px': int(layer.sum()), 'hand_bbox': [int(np.nonzero(layer)[1].min()), int(np.nonzero(layer)[0].min()),
                                                       int(np.nonzero(layer)[1].max()), int(np.nonzero(layer)[0].max())]}
    json.dump(meta, open(os.path.join(out_dir, 'v18_meta.json'), 'w'), indent=1)
    print(json.dumps(meta))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
