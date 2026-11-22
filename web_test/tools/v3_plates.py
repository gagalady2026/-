"""Background plates for the 36-second animatic (assets_v3).

usage: python3 tools/v3_plates.py SRC OUT
  SRC/bg_yard.png   the yard background made with GPT (1672x941)
  writes
  OUT/v3_plate_far.jpg   sea, red lighthouse and the hillside village over the wall (CUT 0 opening)
  OUT/v3_plate_gate.jpg  the jade gate seen from inside the yard, kept sharp (CUT 2 knock)

Both are 1.06x the 1920x1080 frame (2035x1144), so the page's camera can drift and push in without showing an edge.
The v2 plates (assets_v2/v2_bg_*.jpg) are the same picture blurred for depth of field behind a character;
these two are the subject of their shot, so they stay sharp (Lanczos up-scale + a light unsharp mask).
"""
import sys
from PIL import Image, ImageFilter

SRC, OUT = sys.argv[1], sys.argv[2]
bg = Image.open(f"{SRC}/bg_yard.png").convert("RGB")
W, H = 2035, 1144
BOXES = {
    "far": (600, 0, 1672, 603),       # top-right of the picture: sky, sea, lighthouse, village, the tree
    "gate": (531, 212, 1549, 784),    # the same box as the v2 gate plate
}
for key, box in BOXES.items():
    crop = bg.crop(box).resize((W, H), Image.LANCZOS)
    crop = crop.filter(ImageFilter.UnsharpMask(radius=2.2, percent=60, threshold=2))
    crop.save(f"{OUT}/v3_plate_{key}.jpg", quality=90, optimize=True)
    print(key, box, "->", (W, H))
