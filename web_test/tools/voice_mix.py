"""Put the user's recorded lines (their CapCut edit) back on the current cut, unchanged.

The voices exist only inside the user's CapCut export, mixed over the 36-second MP4 they edited (commit 50ed47b). This
takes them out of it and lays them on the current film:

  1. their export minus the soundtrack they edited over — that MP4's own decoded audio, so its AAC stage cancels too —
     scaled by their volume over time (they lowered the music, and lowered it more under each line), read every 10 ms
     from 5-12 kHz where the voices have little energy;
  2. a spectral mask guided by that soundtrack for what the second (CapCut) encode leaves behind;
  3. the middle of the stereo pair only (the voices are centred: L/R correlation 0.99), gated to the lines;
  4. each line moved to where it now belongs: the gate line to just after the knocks (2.40 s, ending before the latch),
     "요즘은 좀 어떠세요?" to where his mouth starts (6.37 s), every line from the citizen's first one on exactly 1 s
     later than in their edit (the cut grew by a second before it). Their words, their voices and the spacing between
     lines are kept;
  5. the lines evened out (asked for after the first voiced cut): in the export the official's lines sat 3.6 LU under
     the citizen's on average, 6.7 LU between the loudest and the quietest. Each line's loudness (BS.1770, gated) is
     moved 80% of the way to -20 LUFS, at most about 3 dB either way, which leaves them within ~1.3 LU of each other;
  6. the soundtrack (already mastered) 2 dB lower throughout and 6.5 dB lower under each line, as in their edit
     (10 dB under the two guidance lines, so the 분납 / 복지 lines read over the music), then the voices on top.

usage: python3 -I tools/voice_mix.py USER_EXPORT.mov EDITED_BASE.mp4 SOUNDTRACK_MASTER.wav OUT_MIX.wav OUT_VOICE.flac
  The mix is then levelled to -16 LUFS with a limiter (README); the voice stem is the gated mono voice track on the
  current timeline (48 kHz), kept so the film can be re-rendered without going back to the export.
"""
import subprocess, sys
import numpy as np

SR = 48000
DUR = 39.5
# each line: the stretches of voice in the user's export (s), and where its first word now starts (s)
LINES = [
    ("계세요? 동해시청에서 나왔어요.", [(2.48, 2.86), (3.14, 4.30)], 2.50),   # 0.4 s after the second knock (2.083 s)
    ("요즘은 좀 어떠세요?", [(5.98, 7.06)], 6.37),
    ("몸이 안 좋아서 한동안 일을 못 했어요…", [(10.20, 10.94), (11.68, 12.84)], 11.20),
    ("많이 힘드셨겠어요.", [(13.32, 14.74)], 14.32),
    ("그러다 보니 세금도 밀렸네요…", [(14.94, 16.30)], 15.94),
    ("같이 방법을 찾아볼게요.", [(17.06, 18.54)], 18.06),
    ("나눠서 내는 방법도 상담해 드릴게요.", [(18.80, 21.28)], 19.80),
    ("필요하시면 복지서비스도 연계해 드릴게요.", [(23.04, 25.50)], 24.04),
    ("고마워요, 마음이 좀 놓이네요.", [(26.26, 27.10), (27.58, 28.82)], 27.26),
]
GUIDANCE = {6, 7}                       # the 분납 / 복지 lines: the music goes a little further down under them
PRE, POST, FADE = 0.08, 0.18, 0.015     # kept around each stretch of voice (breath in, the tail of the last word)
DUCK, DUCK_GUIDE, BASE = -6.5, -10.0, -2.0
ATTACK, RELEASE = 0.12, 0.25
LEVEL_TARGET, LEVEL_SHARE = -20.0, 0.8  # each line's loudness moved this share of the way to the target (LUFS)


def loudness(x):
    """Integrated loudness of a mono clip (ITU-R BS.1770: K-weighting, 400 ms blocks, absolute and relative gates). The
    K-weighting is applied as its magnitude response in the frequency domain (loudness needs power only)."""
    f = np.fft.rfftfreq(len(x), 1 / SR)
    z = np.exp(-2j * np.pi * f / SR)
    shelf = (1.53512485958697 - 2.69169618940638 * z + 1.19839281085285 * z * z) / (1 - 1.69065929318241 * z + 0.73248077421585 * z * z)
    hp = (1 - 2 * z + z * z) / (1 - 1.99004745483398 * z + 0.99007225036621 * z * z)
    y = np.fft.irfft(np.fft.rfft(x) * np.abs(shelf * hp), len(x))
    B, H = int(0.4 * SR), int(0.1 * SR)
    p = np.array([(y[i:i + B] ** 2).mean() for i in range(0, len(y) - B + 1, H)])
    lk = -0.691 + 10 * np.log10(p + 1e-20)
    p = p[lk > -70]
    rel = -0.691 + 10 * np.log10(p.mean()) - 10
    return -0.691 + 10 * np.log10(p[-0.691 + 10 * np.log10(p + 1e-20) > rel].mean())


def load(path):
    raw = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', path, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, '<f4').astype(np.float64).reshape(-1, 2)


def band(x, lo, hi):
    F = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    F[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(F, len(x), axis=0)


def extract(user, base):
    """The voices in the user's export, in its own timing (stereo)."""
    n = min(len(user), len(base))
    u, m = user[:n], base[:n]
    uh, mh = band(u, 5000, 12000), band(m, 5000, 12000)
    hop, W = int(0.01 * SR), int(0.1 * SR)
    cs_um, cs_mm = np.cumsum(np.r_[0, (uh * mh).sum(1)]), np.cumsum(np.r_[0, (mh * mh).sum(1)])
    cb_um, cb_mm = np.cumsum(np.r_[0, (u * m).sum(1)]), np.cumsum(np.r_[0, (m * m).sum(1)])
    centers = np.arange(0, n, hop)
    g = np.zeros(len(centers))
    for i, c in enumerate(centers):
        a, b = max(0, c - W // 2), min(n, c + W // 2)
        mm = cs_mm[b] - cs_mm[a]
        if mm > 1e-7 * (b - a):
            g[i] = (cs_um[b] - cs_um[a]) / mm
        else:
            mb = cb_mm[b] - cb_mm[a]
            g[i] = (cb_um[b] - cb_um[a]) / mb if mb > 1e-12 else 0
    k = 5
    gs = np.convolve(np.r_[np.full(k, g[0]), g, np.full(k, g[-1])], np.ones(2 * k + 1) / (2 * k + 1), mode='same')[k:-k]
    ref = np.interp(np.arange(n), centers, gs)[:, None] * m
    r = u - ref
    NF, HOP = 2048, 512
    win = np.hanning(NF + 1)[:-1]

    def stft(x):
        pad = np.r_[np.zeros(NF), x, np.zeros(NF)]
        return np.fft.rfft(np.lib.stride_tricks.sliding_window_view(pad, NF)[::HOP] * win, axis=1)

    def istft(X, length):
        fr = np.fft.irfft(X, NF, axis=1) * win
        out, ws = np.zeros(NF + HOP * (len(fr) - 1)), np.zeros(NF + HOP * (len(fr) - 1))
        for i, f in enumerate(fr):
            out[i * HOP:i * HOP + NF] += f
            ws[i * HOP:i * HOP + NF] += win ** 2
        return (out / np.maximum(ws, 1e-8))[NF:NF + length]

    stretches = [s for _, ss, _ in LINES for s in ss]
    out = np.zeros_like(r)
    for ch in range(2):
        R, M = stft(r[:, ch]), stft(ref[:, ch])
        t = (np.arange(len(R)) * HOP - NF / 2) / SR
        voiced = np.zeros(len(R), bool)
        for a, b in stretches:
            voiced |= (t > a - 0.1) & (t < b + 0.2)
        quiet = (~voiced) & (t > 0.3) & (t < 35.8)
        beta = np.clip(np.median(np.abs(R[quiet]) / (np.abs(M[quiet]) + 1e-9), axis=0), 0.02, 1.0)   # what the encode left, per bin
        mask = np.sqrt(np.clip(1 - (1.6 * beta * np.abs(M)) ** 2 / np.maximum(np.abs(R) ** 2, 1e-14), 0.05, 1.0))
        out[:, ch] = istft(R * mask, n)
    return out


def gate(n, stretches):
    """1 over each stretch of voice (with a little before and after), raised-cosine edges, 0 elsewhere."""
    t = np.arange(n) / SR
    g = np.zeros(n)
    for a, b in stretches:
        a, b = a - PRE, b + POST
        up = np.clip((t - a) / FADE, 0, 1)
        down = np.clip((b - t) / FADE, 0, 1)
        g = np.maximum(g, (0.5 - 0.5 * np.cos(np.pi * np.minimum(up, down))))
    return g


def main(export, base, master, out_mix, out_voice):
    v = extract(load(export), load(base))
    mid = v.mean(1)                                       # the voices are centred; the sides are what is left of the music
    # each line's gain (dB), as a smooth envelope over the export's timeline (adjacent lines meet half way between them)
    pts = []
    for text, ss, _ in LINES:
        L = loudness(mid[int(ss[0][0] * SR):int(ss[-1][1] * SR)])
        gdb = LEVEL_SHARE * (LEVEL_TARGET - L)
        print(f'{L:6.1f} LUFS -> {L + gdb:6.1f} ({gdb:+.1f} dB)  {text}')
        pts.append([ss[0][0] - PRE, ss[-1][1] + POST, gdb])
    for i in range(len(pts) - 1):
        if pts[i][1] > pts[i + 1][0] - 0.03:
            mid_t = (pts[i][1] + pts[i + 1][0]) / 2
            pts[i][1], pts[i + 1][0] = mid_t - 0.015, mid_t + 0.015
    xs = [x for a, b, _ in pts for x in (a, b)]
    gs = [g for _, _, g in pts for _ in (0, 1)]
    mid = mid * 10 ** (np.interp(np.arange(len(mid)) / SR, xs, gs) / 20)
    n = int(round(DUR * SR))
    voice = np.zeros(n)
    t_new = np.arange(n) / SR
    by_shift = {}
    for i, (_, ss, onset) in enumerate(LINES):
        by_shift.setdefault(round(onset - ss[0][0], 4), []).extend(ss)
    for shift, ss in by_shift.items():                    # lines moved by the same amount are gated together (no doubling)
        src_t = t_new - shift
        ok = (src_t >= 0) & (src_t < len(mid) / SR - 1e-6)
        g_old = gate(len(mid), ss)
        voice[ok] += np.interp(src_t[ok], np.arange(len(mid)) / SR, mid * g_old)
    # the soundtrack under the lines
    duck = np.full(n, BASE)
    for i, (_, ss, onset) in enumerate(LINES):
        shift = onset - ss[0][0]
        a, b = ss[0][0] + shift, ss[-1][1] + shift
        depth = DUCK_GUIDE if i in GUIDANCE else DUCK
        env = np.interp(t_new, [a - ATTACK, a, b, b + RELEASE], [BASE, depth, depth, BASE], left=BASE, right=BASE)
        duck = np.minimum(duck, env)
    music = load(master)[:n]
    if len(music) < n:
        music = np.r_[music, np.zeros((n - len(music), 2))]
    mix = music * (10 ** (duck / 20))[:, None] + voice[:, None]
    mix.astype('<f4').tofile(out_mix + '.f32')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', out_mix + '.f32',
                    '-c:a', 'pcm_f32le', out_mix], check=True)
    voice.astype('<f4').tofile(out_voice + '.f32')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', out_voice + '.f32',
                    '-sample_fmt', 's16', out_voice], check=True)
    db = lambda x: 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-12)
    for i, (text, ss, onset) in enumerate(LINES):
        shift = onset - ss[0][0]
        a, b = int((ss[0][0] + shift) * SR), int((ss[-1][1] + shift) * SR)
        print(f'{onset:6.2f}-{ss[-1][1] + shift:6.2f} s  voice {db(voice[a:b]):6.1f} dB  music under it {db((music * (10 ** (duck / 20))[:, None])[a:b]):6.1f} dB  {text}')


if __name__ == '__main__':
    main(*sys.argv[1:6])
