"""Facebook / Instagram cuts of the animatic: the 16:9 picture whole, across the width of a 4:5 (1080x1350, the feed) or
9:16 (1080x1920, Reels and Stories) frame, with the film's title above it and the words set large under it. Placed into a
tall frame as it is, the 16:9 film would shrink its subtitles and its phone number to about half their size; here they are
set again at full size in the space under the picture, from the page's own timing.

  1. the pictures without words:      CAPQ='&bare' node capture_q.mjs animatic_36s.html BARE "<frames with words>"
                                      (?bare: the page draws no subtitles and none of the end card's words)
  2. the timing of the words:         node states2.mjs <page with window.__dbg> STATES.json   (subtitle text/alpha per
                                      frame; the end card's message, 2027 line and sign-off alphas)
  3. the words, in the page's fonts:  python3 tools/social_cut.py spec SPEC.json ; node tools/social_text.mjs SPEC.json TEXT
  4. each cut:                        python3 -I tools/social_cut.py make 4x5|9x16 FRAMES BARE STATES.json TEXT AUDIO OUT.mp4
     FRAMES: the film's frames (f0000.png ...), BARE: the same frames without words (used where it has them), AUDIO: the
     voiced master (48 kHz WAV). The city's symbol is the official file (assets_ci/donghae_ci_symbol.png), not redrawn.

In the 9:16 cut everything sits inside the middle 4:5 (y 285-1635), which the feed and the profile grid show, and clear
of the Reels buttons along the bottom and the right edge.
"""
import json, os, subprocess, sys
import numpy as np
from PIL import Image

FPS = 24
HERE = os.path.dirname(os.path.abspath(__file__))
CI = os.path.join(HERE, '..', 'assets_ci', 'donghae_ci_symbol.png')
NOTO, GOWUN = '"Noto Sans KR"', '"Gowun Dodum"'
TITLE, ORG = '똑똑, 괜찮으세요?', '동해시 지방세입 체납관리단'
LEAD, WHEN, ASK, TEL = '2027년에도 찾아갑니다.', '상반기 중 참여자 모집 · 6개월간 근무 예정', '문의 ', '033-530-2064'
MSG = '체납 뒤에 사람이 있습니다.'
# long lines in two, at a natural pause (the film's subtitles are one line across 1920 px)
WRAP = {
    '계세요? 동해시청에서 나왔어요.': ['계세요?', '동해시청에서 나왔어요.'],
    '몸이 안 좋아서 한동안 일을 못 했어요…': ['몸이 안 좋아서', '한동안 일을 못 했어요…'],
    '나눠서 내는 방법도 상담해 드릴게요.': ['나눠서 내는 방법도', '상담해 드릴게요.'],
    '필요하시면 복지서비스도 연계해 드릴게요.': ['필요하시면 복지서비스도', '연계해 드릴게요.'],
}
SUBS = ['계세요? 동해시청에서 나왔어요.', '요즘은 좀 어떠세요?', '몸이 안 좋아서 한동안 일을 못 했어요…', '많이 힘드셨겠어요.',
        '그러다 보니 세금도 밀렸네요…', '같이 방법을 찾아볼게요.', '나눠서 내는 방법도 상담해 드릴게요.',
        '필요하시면 복지서비스도 연계해 드릴게요.', '고마워요, 마음이 좀 놓이네요.']
# y: centres of the words (px); pic: top of the 1080x608 picture
FORMATS = {
    '4x5': dict(W=1080, H=1350, pic=262, title=(118, 64), org=(196, 30), sub=(1000, 56, 76),
                msg=(1040, 58), lead=(912, 40), ci=(1022, 120), name=(1080, 56), when=(1140, 33), tel=(1218, 44, 62)),
    '9x16': dict(W=1080, H=1920, pic=560, title=(392, 72), org=(476, 34), sub=(1300, 60, 82),
                 msg=(1330, 62), lead=(1214, 44), ci=(1338, 132), name=(1402, 60), when=(1466, 36), tel=(1552, 48, 68)),
}
BG_TOP, BG_BOTTOM = (40, 33, 56), (20, 17, 28)     # the end card's dusk, deepening downward


def spec(out):
    items = []
    for fmt, L in FORMATS.items():
        items.append(dict(id=f'{fmt}_title', text=TITLE, family=GOWUN, weight=400, size=L['title'][1], color='#FFF6EC', shadow=6))
        items.append(dict(id=f'{fmt}_org', text=ORG, family=NOTO, weight=500, size=L['org'][1], color='#CFC6DA'))
        for i, t in enumerate(SUBS):
            for j, line in enumerate(WRAP.get(t, [t])):
                items.append(dict(id=f'{fmt}_sub{i}_{j}', text=line, family=NOTO, weight=700, size=L['sub'][1], color='#FFFFFF', shadow=8))
        items.append(dict(id=f'{fmt}_msg', text=MSG, family=GOWUN, weight=400, size=L['msg'][1], color='#FFFFFF', shadow=10))
        items.append(dict(id=f'{fmt}_lead', text=LEAD, family=NOTO, weight=500, size=L['lead'][1], color='#F6E3C8', shadow=6))
        items.append(dict(id=f'{fmt}_name', text=ORG, family=NOTO, weight=700, size=L['name'][1], color='#FFF9F1', shadow=8))
        items.append(dict(id=f'{fmt}_when', text=WHEN, family=NOTO, weight=500, size=L['when'][1], color='#ECE0F2', shadow=6))
        items.append(dict(id=f'{fmt}_tel', shadow=8, parts=[dict(text=ASK, family=NOTO, weight=500, size=L['tel'][1], color='#F2E8DA'),
                                                           dict(text=TEL, family=NOTO, weight=700, size=L['tel'][2], color='#FFF9F1')]))
    json.dump(items, open(out, 'w'), ensure_ascii=False, indent=1)
    print('items', len(items))


def faded(im, a):
    if a >= 0.999: return im
    r = im.copy(); al = np.asarray(r.getchannel('A')).astype(np.float32) * max(0.0, a)
    r.putalpha(Image.fromarray(np.clip(al, 0, 255).astype(np.uint8)))
    return r


def put(canvas, im, cx, cy, a=1.0):
    if a <= 0.001: return
    canvas.alpha_composite(faded(im, a), (int(round(cx - im.width / 2)), int(round(cy - im.height / 2))))


def make(fmt, frames, bare, states, text, audio, out):
    L = FORMATS[fmt]; W, H = L['W'], L['H']
    rows = json.load(open(states))
    T = {n[:-4]: Image.open(os.path.join(text, n)).convert('RGBA') for n in os.listdir(text) if n.startswith(fmt + '_')}
    g = np.linspace(0, 1, H)[:, None, None]
    bg = (np.array(BG_TOP)[None, None, :] * (1 - g) + np.array(BG_BOTTOM)[None, None, :] * g) * np.ones((1, W, 1))
    base = Image.fromarray(np.round(bg).astype(np.uint8), 'RGB').convert('RGBA')
    put(base, T[f'{fmt}_title'], W / 2, L['title'][0]); put(base, T[f'{fmt}_org'], W / 2, L['org'][0])
    ci = Image.open(CI).convert('RGBA'); cw = L['ci'][1]; ci = ci.resize((cw, round(ci.height * cw / ci.width)), Image.LANCZOS)
    cmd = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-i', audio, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
           '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', out]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for r in rows:
        f = r['f']; name = f'f{f:04d}.png'
        src = os.path.join(bare, name) if os.path.exists(os.path.join(bare, name)) else os.path.join(frames, name)
        pic = Image.open(src).convert('RGB').resize((W, round(W * 1080 / 1920)), Image.LANCZOS)
        c = base.copy(); c.paste(pic, (0, L['pic']))
        if r['sub'] > 0.001:
            i = SUBS.index(r['text']); lines = WRAP.get(r['text'], [r['text']]); lh = L['sub'][2]
            y0 = L['sub'][0] - (len(lines) - 1) * lh / 2
            for j in range(len(lines)):
                put(c, T[f'{fmt}_sub{i}_{j}'], W / 2, y0 + j * lh, r['sub'])
        if r['k'] == 'end':
            put(c, T[f'{fmt}_msg'], W / 2, L['msg'][0], r['msg'])
            put(c, T[f'{fmt}_lead'], W / 2, L['lead'][0] + 6 * (1 - r['lead']), r['lead'])
            a, rise = r['info'], 6 * (1 - r['info'])
            put(c, ci, W / 2, L['ci'][0] - ci.height / 2 + rise, a)
            put(c, T[f'{fmt}_name'], W / 2, L['name'][0] + rise, a)
            put(c, T[f'{fmt}_when'], W / 2, L['when'][0] + rise, a)
            put(c, T[f'{fmt}_tel'], W / 2, L['tel'][0] + rise, a)
        enc.stdin.write(c.convert('RGB').tobytes())
    enc.stdin.close(); enc.wait()
    print(out, 'frames', len(rows), 'exit', enc.returncode)


if __name__ == '__main__':
    if sys.argv[1] == 'spec':
        spec(sys.argv[2])
    else:
        make(*sys.argv[2:9])
