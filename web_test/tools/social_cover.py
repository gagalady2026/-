"""The cover (대표 썸네일) for the 4:5 feed post on Instagram and Facebook: a 1080x1350 still, in two options, each made of a
frame of the film without words, the film's own fonts and colours, and the city's symbol (the official file, only scaled).

  A  the bench two-shot (CUT 4, frame 212): the official listening to the elder, side by side. The film's dusk around the
     picture, as in the feed cut, so the cover and the post that plays after it look like one thing.
  B  the elder's relieved smile (CUT 6, frame 684), full bleed, the words under it on the dusk.

Words: "똑똑, 괜찮으세요?" (the film's title) small over the headline "체납 뒤에 / 사람이 있습니다" (the film's message), then the
city's symbol and "동해시 지방세입 체납관리단". All of them sit inside the 3:4 middle (x 60-1020), which is what Instagram's
profile grid shows of a 4:5 post.

usage:
  python3 tools/social_cover.py spec COVER_SPEC.json
  node social_text.mjs COVER_SPEC.json TEXT_DIR                      (as for the feed cut)
  python3 tools/social_cover.py make FRAME_212.png FRAME_684.png TEXT_DIR OUT_DIR
     (the two frames rendered with ?capture&bare: no subtitles)
  → OUT_DIR/cover_4x5_A_bench.png, cover_4x5_B_smile.png
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
CI = os.path.join(HERE, '..', 'assets_ci', 'donghae_ci_symbol.png')
NOTO, GOWUN = '"Noto Sans KR"', '"Gowun Dodum"'
W, H = 1080, 1350
BG_TOP, BG_BOTTOM = (40, 33, 56), (20, 17, 28)       # the end card's dusk (as the feed cut)
KICKER, HEAD, ORG = '똑똑, 괜찮으세요?', ('체납 뒤에', '사람이 있습니다'), '동해시 지방세입 체납관리단'


def spec(out):
    items = [dict(id='cv_kicker', text=KICKER, family=GOWUN, weight=400, size=48, color='#F6E3C8', shadow=8),
             dict(id='cv_head0', text=HEAD[0], family=GOWUN, weight=400, size=106, color='#FFF6EC', shadow=12),
             dict(id='cv_head1', text=HEAD[1], family=GOWUN, weight=400, size=106, color='#FFF6EC', shadow=12),
             dict(id='cv_org', text=ORG, family=NOTO, weight=700, size=40, color='#FFF9F1', shadow=8)]
    json.dump(items, open(out, 'w'), ensure_ascii=False, indent=1)


def put(c, im, cx, cy):
    c.alpha_composite(im, (round(cx - im.width / 2), round(cy - im.height / 2)))


def dusk():
    g = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array(BG_TOP)[None, None, :] * (1 - g) + np.array(BG_BOTTOM)[None, None, :] * g) * np.ones((1, W, 1))
    return Image.fromarray(np.round(bg).astype(np.uint8), 'RGB').convert('RGBA')


def signature(c, T, M, cy):
    """the city's symbol and the name side by side, centred as one group on the line cy"""
    ci = Image.open(CI).convert('RGBA'); ch = 62
    ci = ci.resize((round(ci.width * ch / ci.height), ch), Image.LANCZOS)
    org = T['cv_org']; pad = M['cv_org']['pad']                   # the name's PNG has room for its shadow each side
    gap = 20; wsum = ci.width + gap + org.width - 2 * pad
    x0 = W / 2 - wsum / 2
    c.alpha_composite(ci, (round(x0), round(cy - ch / 2 - 2)))
    put(c, org, x0 + ci.width + gap - pad + org.width / 2, cy)


def option_a(frame, T, M):
    c = dusk()
    put(c, T['cv_kicker'], W / 2, 96)
    put(c, T['cv_head0'], W / 2, 200)
    put(c, T['cv_head1'], W / 2, 318)
    # the picture: a 1066x860 window on the bench (x 387-1453, y 50-910 of the 1920x1080 frame), as a rounded card
    x0, y0, x1, y1 = 44, 404, 1036, 1204
    src = Image.open(frame).convert('RGBA')
    sw = 860 * (x1 - x0) / (y1 - y0); sx = 920 - sw / 2
    pic = src.resize((x1 - x0, y1 - y0), Image.LANCZOS, box=(sx, 50, sx + sw, 910))
    m = Image.new('L', ((x1 - x0) * 4, (y1 - y0) * 4), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1), radius=30 * 4, fill=255)
    m = m.resize(pic.size, Image.LANCZOS)
    sh = Image.new('L', (W, H), 0); sh.paste(m, (x0, y0 + 10)); sh = sh.filter(ImageFilter.GaussianBlur(18))
    c.alpha_composite(Image.merge('RGBA', (*[Image.new('L', (W, H), 0)] * 3, sh.point(lambda v: v * 0.55))))
    pic.putalpha(m); c.alpha_composite(pic, (x0, y0))
    signature(c, T, M, 1280)
    return c.convert('RGB')


def option_b(frame, T, M):
    c = dusk()
    # the picture: the frame at 0.9 (1728x972), the window x 230-1310 of it, so his face sits left of the middle with room
    # in front of it (he looks to the right, at the official); it fades into the dusk from y 690 down to its foot (972)
    src = Image.open(frame).convert('RGBA')
    k = 0.9; pw, ph = round(1920 * k), round(1080 * k); ox = 230
    pic = src.resize((pw, ph), Image.LANCZOS).crop((ox, 0, ox + W, ph))
    a = np.ones((ph, W)); y = np.arange(ph)
    f = np.clip((y - 690) / (ph - 690), 0, 1); a *= (1 - f * f * (3 - 2 * f))[:, None]
    pic.putalpha(Image.fromarray(np.round(a * 255).astype(np.uint8), 'L'))
    c.alpha_composite(pic, (0, 0))
    put(c, T['cv_kicker'], W / 2, 902)
    put(c, T['cv_head0'], W / 2, 1004)
    put(c, T['cv_head1'], W / 2, 1122)
    signature(c, T, M, 1266)
    return c.convert('RGB')


def make(fa, fb, text, out):
    T = {n[:-4]: Image.open(os.path.join(text, n)).convert('RGBA') for n in os.listdir(text) if n.startswith('cv_')}
    M = json.load(open(os.path.join(text, 'metrics.json')))
    os.makedirs(out, exist_ok=True)
    option_a(fa, T, M).save(os.path.join(out, 'cover_4x5_A_bench.png'))
    option_b(fb, T, M).save(os.path.join(out, 'cover_4x5_B_smile.png'))


if __name__ == '__main__':
    if sys.argv[1] == 'spec': spec(sys.argv[2])
    else: make(*sys.argv[2:6])
