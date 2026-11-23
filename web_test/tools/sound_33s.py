"""Original soundtrack for the 33-second animatic (animatic_33s.html): music, sound effects and ambience, all synthesized in
this file from sine waves and noise. No samples, no third-party audio, nothing to license. There are no voices: the lines
stay as subtitles, and README.md has a timing sheet for recording them.

usage: python3 tools/sound_33s.py OUT.f32 [CUES.json]
  OUT.f32    48 kHz stereo float32 (raw, interleaved), exactly 33.0 s, peak -3 dBFS; loudness-normalised and encoded with
             ffmpeg (see README)
  CUES.json  every sound event with its time, for checking against the picture

Timing follows the page's shot list (24 fps): knocks on the frames where 똑! appears, the hinge creak with 끼익, taps on the
tablet presses, chimes as the ① / ② labels appear, the evening ambience from 28.0 s, the end-card bell with the message.

Music: D major, 60 bpm, a chord every two seconds, following the story. A soft pad from the start; piano when the gate opens;
thinner and lower while he tells his trouble; rising into the guidance; arriving on D in the sunset; a G -> D close.
"""
import json, sys
import numpy as np

SR = 48000
DUR = 33.0
N = int(round(SR * DUR))
TAIL = 4 * SR
rng = np.random.default_rng(20261123)          # fixed seed: every run writes the same file
CUES = []


def S(sec):
    return int(round(sec * SR))


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def tvec(sec):
    return np.arange(S(sec)) / SR


def cue(t, what):
    CUES.append({"t": round(float(t), 3), "sound": what})


# ---------------------------------------------------------------- filters (zero-phase, frequency domain) and convolution
def nfft_for(n):
    return 1 << int(np.ceil(np.log2(max(2, n))))


def ffilt(x, mag):
    n = x.shape[-1]
    m = nfft_for(n)
    f = np.fft.rfftfreq(m, 1 / SR)
    return np.fft.irfft(np.fft.rfft(x, m) * mag(f), m)[..., :n]


def lp(fc, o=2):
    return lambda f: 1 / np.sqrt(1 + (f / fc) ** (2 * o))


def hp(fc, o=2):
    return lambda f: 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * o))


def bp(lo, hi, o=2):
    return lambda f: lp(hi, o)(f) * hp(lo, o)(f)


def conv(x, ir):
    n = x.shape[-1] + ir.shape[-1] - 1
    m = nfft_for(n)
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[..., :n]


def reverb_ir(rt60, length, predelay, bright, seed):
    """Stereo impulse response: decorrelated noise decaying to -60 dB at rt60, darker as it decays, a few early reflections."""
    r = np.random.default_rng(seed)
    n = S(length)
    t = np.arange(n) / SR
    noise = r.standard_normal((2, n)) * np.exp(-6.91 * t / rt60)
    early_w = np.exp(-t / (rt60 * 0.25))
    ir = ffilt(noise, lp(bright, 1)) * early_w + ffilt(noise, lp(bright * 0.3, 1)) * (1 - early_w)
    ir *= 1 - np.exp(-t / 0.01)
    pd = S(predelay)
    ir = np.concatenate([np.zeros((2, pd)), ir], axis=1)[:, :n]
    for d, g in ((0.009, 0.45), (0.014, 0.33), (0.021, 0.28), (0.029, 0.2), (0.038, 0.15)):
        ir[0, pd + S(d)] += g * 3
        ir[1, pd + S(d * 1.09)] += g * 3
    return ir / np.sqrt((ir ** 2).sum() / 2)


class Bus:
    """A stereo track; add() places a mono (equal-power pan) or stereo sound at a time."""
    def __init__(self):
        self.x = np.zeros((2, N + TAIL))

    def add(self, sig, t0, gain=1.0, pan=0.0):
        sig = np.asarray(sig, float) * gain
        if sig.ndim == 1:
            a = (np.clip(pan, -1, 1) + 1) * np.pi / 4
            sig = np.vstack([np.cos(a) * sig, np.sin(a) * sig]) * np.sqrt(2)
        i = S(t0)
        if i < 0:
            sig, i = sig[:, -i:], 0
        n = min(sig.shape[1], self.x.shape[1] - i)
        if n > 0:
            self.x[:, i:i + n] += sig[:, :n]


def curve(points):
    """Piecewise-linear automation over the whole track: [(time, gain), ...]."""
    ts, gs = zip(*points)
    return np.interp(np.arange(N + TAIL) / SR, ts, gs)


def rms_db(x, t0, t1):
    seg = x[..., S(t0):S(t1)]
    return 20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-12)


def to_rms(x, t0, t1, target_db):
    return x * 10 ** ((target_db - rms_db(x, t0, t1)) / 20)


def to_peak(x, target_db):
    return x * 10 ** (target_db / 20) / (np.abs(x).max() + 1e-12)


# ---------------------------------------------------------------- instruments
def piano(m, dur, vel):
    """A soft felt piano: inharmonic partials, the upper ones quieter and shorter, two detuned strings, a felt thump."""
    f = hz(m)
    t = tvec(dur + 1.8)
    out = np.zeros_like(t)
    reg = (f / 261.6) ** 0.5
    for k in range(1, int(min(12, 8000 // f)) + 1):
        fk = k * f * np.sqrt(1 + 0.0004 * k * k)
        a = k ** -1.2 * np.exp(-(k - 1) * (0.42 - 0.2 * vel))
        e = 0.6 * np.exp(-t * (2.0 + 1.0 * k) * reg) + 0.4 * np.exp(-t * (0.3 + 0.15 * k) * reg)
        for c in (-0.8, 0.8):
            out += 0.5 * a * e * np.sin(2 * np.pi * fk * 2 ** (c / 1200) * t + rng.uniform(0, 2 * np.pi))
    out *= 1 - np.exp(-t / 0.003)
    nb = S(0.04)
    thump = rng.standard_normal(nb) * np.exp(-np.arange(nb) / SR / 0.007)
    out[:nb] += 0.06 * ffilt(thump, lp(min(2.5 * f, 2500), 2))
    rel = t > dur
    out[rel] *= np.exp(-(t[rel] - dur) / 0.3)
    return out * vel


def pad_chord(notes, t0, t1, level, att, rel=0.8):
    """Strings-like pad: three detuned band-limited saws per note, slow vibrato, swelling in and out. Returns stereo."""
    t = tvec(t1 - t0 + rel)
    env = np.minimum(1, t / att) ** 2 * np.where(t > t1 - t0, np.exp(-(t - (t1 - t0)) / (rel / 3)), 1)
    out = np.zeros((2, t.size))
    for m in notes:
        f = hz(m)
        for c, pan in ((-7, -0.55), (0, 0.0), (7, 0.55)):
            vib = 1 + (2 ** (4 / 1200) - 1) * np.sin(2 * np.pi * 4.6 * t + rng.uniform(0, 6.3)) * np.minimum(1, t / 0.6)
            ph = 2 * np.pi * np.cumsum(f * 2 ** (c / 1200) * vib) / SR + rng.uniform(0, 6.3)
            v = sum((1 / k) * np.exp(-(k - 1) / 2.5) * np.sin(k * ph) for k in range(1, 8) if k * f < 6000)
            a = (pan + 1) * np.pi / 4
            out[0] += np.cos(a) * v
            out[1] += np.sin(a) * v
    return out * env * level


def bass(m, dur):
    f = hz(m)
    t = tvec(dur + 0.8)
    v = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t) + 0.08 * np.sin(6 * np.pi * f * t)
    env = (1 - np.exp(-t / 0.03)) * (0.7 + 0.3 * np.exp(-t / 0.5))
    env = np.where(t > dur, env * np.exp(-(t - dur) / 0.25), env)
    return v * env


def bell(m, vel, dur=3.0):
    """A soft struck bar (celesta-like): partials 1, 2.76, 5.40, 8.93, the upper ones dying fast."""
    f = hz(m)
    t = tvec(dur)
    out = sum(a * np.exp(-t * d) * np.sin(2 * np.pi * f * r * t + rng.uniform(0, 6.3))
              for r, a, d in ((1.0, 1.0, 1.3), (2.76, 0.3, 3.2), (5.40, 0.1, 6.5), (8.93, 0.035, 10.0)) if f * r < 16000)
    return out * (1 - np.exp(-t / 0.002)) * vel


def plink(m, vel):
    """A short wooden plink (marimba-like bar: partials 1, 3.93, 9.2)."""
    f = hz(m)
    t = tvec(0.6)
    out = sum(a * np.exp(-t * d) * np.sin(2 * np.pi * f * r * t) for r, a, d in ((1.0, 1.0, 9.0), (3.93, 0.22, 24.0), (9.2, 0.05, 45.0)) if f * r < 16000)
    return out * (1 - np.exp(-t / 0.0015)) * vel


# ---------------------------------------------------------------- sound effects
def knock(seed):
    """A knuckle on the painted wooden gate: the panel's body modes, a contact click and a low thock."""
    r = np.random.default_rng(seed)
    t = tvec(0.4)
    modes = ((172, 0.085, 1.0), (251, 0.07, 0.75), (397, 0.05, 0.55), (618, 0.035, 0.38), (945, 0.025, 0.25), (1480, 0.016, 0.16), (2300, 0.01, 0.1))
    sig = sum(a * np.exp(-t / tau) * np.sin(2 * np.pi * f * (1 + r.normal(0, 0.012)) * t + r.uniform(0, 6.3)) for f, tau, a in modes)
    sig *= 1 - np.exp(-t / 0.0008)
    sig += 0.55 * np.exp(-t / 0.02) * np.sin(2 * np.pi * 96 * t)
    nc = S(0.012)
    sig[:nc] += 0.5 * ffilt(r.standard_normal(nc), bp(1500, 6500)) * np.exp(-np.arange(nc) / SR / 0.0012)
    return sig


def creak():
    """The gate's hinge: stick-slip pulses speeding up (the pitch of the squeak rising) through the gate's metal resonances."""
    dur = 0.62
    t = tvec(dur)
    rate = 105 + 230 * (t / dur) ** 0.75 + 16 * np.sin(2 * np.pi * 6.5 * t)
    ph = np.cumsum(rate) / SR
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
    pulses = np.zeros(t.size)
    pulses[idx] = 1 + rng.normal(0, 0.18, idx.size)
    flutter = ffilt(rng.standard_normal(t.size), lp(25, 2))
    flutter = 0.75 + 0.25 * flutter / (np.abs(flutter).max() + 1e-9)
    env = np.sin(np.pi * np.minimum(1, t / dur)) ** 0.6 * flutter
    tt = tvec(0.09)
    ir = sum(a * np.exp(-tt / tau) * np.sin(2 * np.pi * f * tt) for f, tau, a in ((480, 0.035, 1.0), (930, 0.03, 0.8), (1560, 0.02, 0.62), (2380, 0.014, 0.45), (3350, 0.01, 0.3), (4700, 0.006, 0.18)))
    sig = conv(pulses * env, ir)
    grit = ffilt(rng.standard_normal(sig.size), bp(1500, 5000)) * np.concatenate([env, np.zeros(sig.size - env.size)]) * 0.04
    return sig / (np.abs(sig).max() + 1e-9) + grit


def latch():
    """The metal latch lifting: a short bright clack."""
    t = tvec(0.15)
    sig = sum(a * np.exp(-t / tau) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.3)) for f, tau, a in ((1850, 0.02, 1.0), (3120, 0.012, 0.7), (5230, 0.007, 0.45)))
    sig += 0.4 * np.exp(-t / 0.012) * np.sin(2 * np.pi * 140 * t)
    return sig * (1 - np.exp(-t / 0.0005))


def footstep(seed):
    """A loafer on a stone step: heel thud, a small click, a short scuff."""
    r = np.random.default_rng(seed)
    t = tvec(0.22)
    sig = 0.8 * np.exp(-t / 0.025) * np.sin(2 * np.pi * 118 * t) + 0.4 * np.exp(-t / 0.014) * np.sin(2 * np.pi * 212 * t)
    sig *= 1 - np.exp(-t / 0.001)
    nc = S(0.008)
    sig[:nc] += 0.35 * ffilt(r.standard_normal(nc), bp(2000, 8000)) * np.exp(-np.arange(nc) / SR / 0.0015)
    scuff = ffilt(r.standard_normal(t.size), bp(500, 3000)) * np.where((t > 0.015) & (t < 0.13), np.sin(np.pi * (t - 0.015) / 0.115), 0)
    return sig + 0.12 * scuff


def tap(seed):
    """A fingertip on the tablet's glass: a dull small thud and a tiny click."""
    r = np.random.default_rng(seed)
    t = tvec(0.12)
    sig = 0.7 * np.exp(-t / 0.01) * np.sin(2 * np.pi * 260 * t) + 0.3 * np.exp(-t / 0.006) * np.sin(2 * np.pi * 540 * t)
    sig *= 1 - np.exp(-t / 0.0007)
    nc = S(0.004)
    sig[:nc] += 0.25 * ffilt(r.standard_normal(nc), lp(5000, 2)) * np.exp(-np.arange(nc) / SR / 0.001)
    return sig


def whoosh(dur=0.7):
    """Air as the gate swings open."""
    t = tvec(dur)
    env = np.minimum(1, t / 0.18) ** 2 * np.exp(-np.maximum(0, t - 0.18) / 0.2)
    return ffilt(rng.standard_normal(t.size), bp(300, 2500, 1)) * env


def chirp_bird(seed):
    """A sparrow: two or three short falling cheeps."""
    r = np.random.default_rng(seed)
    out = np.zeros(S(0.5))
    t0 = 0.0
    for _ in range(r.integers(2, 4)):
        d = r.uniform(0.05, 0.08)
        t = tvec(d)
        f0, f1 = r.uniform(4800, 5600), r.uniform(3700, 4300)
        f = f0 * (f1 / f0) ** (t / d)
        ph = 2 * np.pi * np.cumsum(f) / SR
        s = np.sin(np.pi * t / d) ** 2 * (np.sin(ph) + 0.15 * np.sin(2 * ph))
        i = S(t0)
        out[i:i + s.size] += s[:out.size - i]
        t0 += d + r.uniform(0.05, 0.09)
    return out


def gull_call(seed):
    """A gull's call (a nasal rising-then-falling 'kyow'), harmonics with a formant around 2-3 kHz, a little rough."""
    r = np.random.default_rng(seed)
    d = 0.28
    t = tvec(d)
    f0 = np.interp(t, (0, 0.04, 0.22, 0.28), (820, 1180, 1080, 650)) * (1 + 0.03 * np.sin(2 * np.pi * 18 * t))
    ph = 2 * np.pi * np.cumsum(f0) / SR
    sig = sum(w * np.sin(k * ph) for k, w in enumerate((0.45, 1.0, 0.85, 0.55, 0.35, 0.2, 0.12, 0.07), start=1))
    sig *= 1 + 0.25 * np.sin(2 * np.pi * 35 * t)
    sig += 0.12 * ffilt(r.standard_normal(t.size), bp(1500, 4500)) * np.abs(sig).max()
    env = np.minimum(1, t / 0.015) * np.minimum(1, (d - t) / 0.04)
    return sig * env


def cricket(t0, t1, f, period, seed):
    """One cricket: chirps of three 14 ms pulses every period seconds."""
    r = np.random.default_rng(seed)
    out = np.zeros(S(t1 - t0) + S(0.2))
    t = t0 + r.uniform(0, period)
    pt = tvec(0.014)
    pulse = np.sin(np.pi * pt / 0.014) ** 2 * np.sin(2 * np.pi * f * pt)
    while t < t1:
        for p in range(3):
            i = S(t - t0 + p * 0.028)
            out[i:i + pulse.size] += pulse * r.uniform(0.8, 1.0)
        t += period * r.uniform(0.9, 1.1)
    return out


def waves(n):
    """The sea below the village: a low surf rumble swelling with each wave, foam hiss on the crests. Stereo."""
    t = np.arange(n) / SR
    rumble = ffilt(rng.standard_normal((2, n)), lambda f: lp(650, 2)(f) * hp(35, 2)(f) / np.maximum(f, 20) ** 0.5)
    hiss = ffilt(rng.standard_normal((2, n)), bp(1200, 7000, 1))
    env = np.zeros(n)
    tc = -2.5
    while tc < n / SR:
        env += np.where(t < tc + 1.4, np.clip((t - tc) / 1.4, 0, 1) ** 2, np.exp(-(t - tc - 1.4) / 2.0))
        tc += rng.uniform(4.2, 6.8)
    env /= env.max()
    rumble /= np.sqrt(np.mean(rumble ** 2))
    hiss /= np.sqrt(np.mean(hiss ** 2))
    return rumble * (0.35 + 0.65 * env) + 0.45 * hiss * env ** 1.6


def wind(n):
    t = np.arange(n) / SR
    w = ffilt(rng.standard_normal((2, n)), bp(120, 900, 1))
    w /= np.sqrt(np.mean(w ** 2))
    return w * (0.65 + 0.2 * np.sin(2 * np.pi * 0.11 * t) + 0.15 * np.sin(2 * np.pi * 0.27 * t + 1.0))


# ================================================================ the score
CHORDS = [  # (start, end, pad notes, level): D major, a chord about every two seconds, placed on the story's beats
    (0.0, 2.0, [50, 57, 62, 64, 66], .35),       # Dadd9      climbing the stairs
    (2.0, 4.25, [50, 55, 59, 62, 69], .3),       # G(add9)/D  knocking at the gate
    (4.25, 6.0, [50, 57, 62, 66, 69], .45),      # D          the gate opens: "요즘 지내시기 괜찮으세요?"
    (6.0, 8.0, [49, 57, 61, 64, 69], .45),       # A/C#
    (8.0, 10.0, [47, 54, 59, 62, 66], .4),       # Bm         on the bench
    (10.0, 12.0, [52, 59, 62, 67], .28),         # Em7        "몸이 안 좋아서 한동안 일을 못 했어요…"
    (12.0, 14.0, [43, 55, 59, 62, 67], .34),     # G          "많이 힘드셨겠어요."
    (14.0, 16.0, [47, 54, 59, 62], .28),         # Bm         "그러다 보니 세금도 밀렸네요…"
    (16.0, 17.0, [43, 55, 59, 62, 66], .4),      # Gmaj7      "같이 방법을 찾아봐요."
    (17.0, 17.5, [45, 57, 62, 64, 69], .45),     # Asus4
    (17.5, 18.0, [45, 57, 61, 64, 69], .5),      # A
    (18.0, 20.0, [50, 57, 62, 66, 69], .5),      # D          ① 분납 상담
    (20.0, 22.0, [49, 57, 61, 64, 69], .5),      # A/C#       he nods
    (22.0, 24.0, [43, 55, 59, 62, 67], .55),     # G          ② 복지서비스 연계
    (24.0, 26.0, [42, 57, 62, 66, 69], .55),     # D/F#       relief
    (26.0, 27.0, [52, 59, 62, 67], .55),         # Em7        "고마워요, 마음이 좀 놓이네요."
    (27.0, 28.0, [45, 57, 61, 64, 69], .62),     # A
    (28.0, 30.5, [50, 57, 62, 66, 69, 74], .85), # D          the sunset: they nod to each other
    (30.5, 31.5, [43, 55, 59, 62, 69], .62),     # Gadd9      the end card: the message
    (31.5, 33.0, [50, 57, 62, 66, 69], .55),     # D          the name and number
]


def arp(t0, notes, vels=(.4, .33, .33, .3), dur=.9):
    return [(t0 + 0.5 * i, m, dur, v) for i, (m, v) in enumerate(zip(notes, vels))]


def roll(t0, notes, vels, dur, gap=0.05):
    return [(t0 + gap * i, m, dur - gap * i, v) for i, (m, v) in enumerate(zip(notes, vels))]


PIANO = (
    # the gate opens: a rolled D and the greeting motif
    roll(4.25, [50, 57, 62], [.5, .42, .4], 1.7, 0.06)
    + [(4.25, 69, .75, .55), (5.0, 74, .5, .5), (5.5, 76, .5, .5), (6.0, 78, 1.5, .58), (7.5, 76, .5, .45),
       (8.0, 74, 1.0, .5), (9.0, 73, .5, .4), (9.5, 71, 1.5, .35)]
    + roll(6.0, [49, 57], [.42, .36], 1.8, 0.06) + roll(8.0, [47, 54], [.42, .36], 1.8, 0.06)
    # he tells his trouble: sparse, low and soft
    + [(10.0, 52, 2.0, .34), (10.3, 59, 1.7, .28), (12.0, 43, 2.0, .34), (12.3, 62, 1.7, .28), (12.6, 71, 1.4, .26),
       (14.0, 47, 2.0, .3), (14.3, 54, 1.7, .26), (15.2, 62, .8, .22)]
    # "같이 방법을 찾아봐요.": rising toward the guidance
    + [(16.0, 43, 1.9, .38), (16.25, 62, 1.2, .32), (16.5, 66, 1.2, .33), (16.75, 71, 1.2, .36),
       (17.0, 45, 1.0, .38), (17.25, 64, .7, .33), (17.5, 69, .6, .36), (17.75, 73, .5, .4)]
    # the guidance: eighth-note arpeggios and a hopeful line
    + arp(18.0, [50, 57, 62, 57]) + arp(20.0, [49, 57, 64, 57]) + arp(22.0, [43, 50, 59, 50]) + arp(24.0, [42, 57, 62, 57])
    + arp(26.0, [52, 59, 45, 64])
    + [(18.0, 78, 1.5, .55), (19.5, 76, .5, .45), (20.0, 76, 1.0, .5), (21.0, 73, 1.0, .45), (22.0, 74, 1.5, .55),
       (23.5, 71, .5, .45), (24.0, 69, 1.0, .5), (25.0, 74, 1.0, .55), (26.0, 71, 1.0, .45), (27.0, 73, .75, .5), (27.75, 76, .25, .45)]
    # the sunset: arriving on D
    + roll(28.0, [38, 45, 50, 57, 62], [.55, .5, .45, .42, .4], 2.4) + [(28.0, 78, 1.0, .6), (29.0, 76, .5, .5), (29.5, 74, 1.0, .5)]
    # the end card: G -> D
    + roll(30.5, [43, 50, 59, 69], [.5, .45, .4, .38], 1.1) + [(30.75, 71, .75, .45)]
    + roll(31.5, [38, 45, 50, 54, 57, 62], [.5, .46, .44, .4, .38, .36], 1.6) + [(31.5, 69, .5, .45), (32.0, 74, 1.0, .5)]
)
BASS = [(18.0, 38, 2.0), (20.0, 37, 2.0), (22.0, 43, 2.0), (24.0, 42, 2.0), (26.0, 40, 1.0), (27.0, 45, 1.0),
        (28.0, 38, 2.5), (30.5, 43, 1.0), (31.5, 38, 1.5)]


def main(out_path, cues_path=None):
    piano_b, pad_b, bass_b, bell_b = Bus(), Bus(), Bus(), Bus()
    for t0, m, d, v in PIANO:
        piano_b.add(piano(m, d, v), t0, pan=np.clip((m - 60) / 30, -0.5, 0.5))
    for i, (t0, t1, notes, lvl) in enumerate(CHORDS):
        pad_b.add(pad_chord(notes, t0, t1, lvl, att=1.6 if i == 0 else 0.35), t0)
    for t0, m, d in BASS:
        bass_b.add(bass(m, d), t0)
    # chimes: the ① / ② labels, the bars filling / the links lighting, the end card's message and sign-off
    for t0, notes in ((18.32, [74, 78, 81]), (22.32, [79, 83, 86])):
        for j, m in enumerate(notes):
            bell_b.add(bell(m, .5 - .08 * j, 1.6), t0 + 0.06 * j, pan=-0.3)
        cue(t0, "chime: label " + ("①" if t0 < 20 else "②"))
    for t0, notes in ((18.64, [78, 81, 86]), (22.64, [79, 83, 86])):
        for j, m in enumerate(notes):
            bell_b.add(plink(m, .4), t0 + 0.14 * j, pan=-0.35)
        cue(t0, "plinks: " + ("bars fill" if t0 < 20 else "links light"))
    bell_b.add(bell(86, .55, 3.0), 30.78)
    bell_b.add(bell(81, .35, 2.5), 31.32)
    cue(30.78, "bell: end-card message")
    cue(31.32, "bell: CI place and name")

    piano_x = to_rms(piano_b.x, 18, 28, -24)
    pad_x = to_rms(pad_b.x, 18, 28, -28)
    bass_x = to_rms(bass_b.x, 18, 28, -31)
    bell_x = to_peak(bell_b.x, -17)
    music_dry = piano_x + pad_x + bass_x + bell_x
    send = (0.35 * piano_x + 0.5 * pad_x + 0.6 * bell_x).mean(axis=0)
    music = music_dry + 0.32 * conv(send, reverb_ir(2.2, 3.0, 0.02, 5500, 1))[:, :N + TAIL]
    music *= curve([(0, 0), (0.3, 1), (1.15, 1), (1.25, 0.72), (4.2, 0.72), (4.3, 1), (32.35, 1), (33.0, 0), (40, 0)])

    # ---------------------------------------------------------------- effects
    fx = Bus()
    for i, t0 in enumerate((0.255, 0.681)):                                   # CUT 1: footfalls (steps land at (n + 0.6) / 2.35 s)
        fx.add(to_peak(footstep(10 + i), -18), t0 - 0.004, pan=(-0.08, 0.08)[i])
        cue(t0, "footstep")
    for i, t0 in enumerate((1.3208, 1.7379)):                                 # CUT 2: 똑! 똑! (u = 0.10, 0.23 of the gate shot)
        fx.add(to_peak(knock(20 + i), -7.0 + 0.5 * i), t0, pan=(0.22, 0.4)[i])            # the title's 똑똑: clearly the loudest effect
        cue(t0, "knock")
    fx.add(to_peak(latch(), -19), 3.62, pan=0.3)
    cue(3.62, "latch")
    fx.add(to_peak(creak(), -12.5), 3.70, pan=0.32)                          # 끼익 shows at 3.76
    cue(3.70, "hinge creak")
    fx.add(to_peak(whoosh(), -27), 4.12, pan=0.1)
    cue(4.12, "air, gate open")
    for i, t0 in enumerate((18.23, 18.59, 22.23, 22.59)):                    # CUT 6: the two presses on each panel
        fx.add(to_peak(tap(30 + i), -21), t0, pan=-0.4)
        cue(t0, "tablet tap")
    fx_send = fx.x.mean(axis=0)
    fx_x = fx.x + 0.22 * conv(fx_send, reverb_ir(0.7, 1.2, 0.008, 6000, 2))[:, :N + TAIL]

    # ---------------------------------------------------------------- ambience
    n = N + TAIL
    amb = to_rms(waves(n), 0, 30, -30) * curve([(0, 1), (0.97, 1), (1.03, .4), (9.45, .4), (9.55, .3), (28.0, .3), (28.5, .65),
                                                (30.5, .65), (32.6, 0), (40, 0)])
    amb += to_rms(wind(n), 0, 30, -43) * curve([(0, .8), (0.97, .8), (1.03, .5), (28.0, .5), (28.5, .6), (30.5, .6), (32.6, 0), (40, 0)])
    air = Bus()
    for i, t0 in enumerate((0.12, 0.40)):                                    # CUT 1: gulls over the harbour, far off
        air.add(to_peak(ffilt(gull_call(40 + i), lp(3800, 2)), -27 - 2 * i), t0, pan=-0.45)
    air.add(to_peak(ffilt(gull_call(42), lp(3000, 2)), -33), 28.75, pan=-0.5)
    cue(0.12, "gulls, far")
    cue(28.75, "gull, very far")
    for i, t0 in enumerate((2.75, 7.4, 8.85, 19.35, 23.55, 25.6)):           # day: a sparrow now and then (not while he tells his trouble)
        air.add(to_peak(chirp_bird(50 + i), -29), t0, pan=(0.55, -0.5, 0.4, 0.6, -0.55, 0.45)[i])
        cue(t0, "sparrow")
    crick = Bus()
    for j, (f, period, pan) in enumerate(((4300, 0.52, -0.6), (4650, 0.47, 0.55), (4480, 0.6, 0.1))):
        crick.add(cricket(28.0, 33.0, f, period, 60 + j), 28.0, pan=pan)
    cue(28.0, "crickets (evening)")
    crick_x = to_peak(crick.x, -31) * curve([(0, 0), (28.0, 0), (28.5, 1), (30.5, 1), (32.6, 0), (40, 0)])
    air_x = air.x + crick_x
    air_x = air_x + 0.35 * conv(air_x.mean(axis=0), reverb_ir(1.5, 2.0, 0.03, 5000, 3))[:, :n]
    amb += air_x
    amb *= curve([(0, 0), (0.2, 1), (40, 1)])

    mix = (music + fx_x + amb)[:, :N]
    mix = to_peak(mix, -3.0)
    mix.T.astype("<f4").tofile(out_path)
    stems = {"music": music[:, :N], "effects": fx_x[:, :N], "ambience": amb[:, :N]}
    report = {k: {"rms_dbfs": round(rms_db(v, 0, DUR), 1), "peak_dbfs": round(20 * np.log10(np.abs(v).max() + 1e-12), 1)} for k, v in stems.items()}
    print(json.dumps(report))
    if cues_path:
        json.dump(sorted(CUES, key=lambda c: c["t"]), open(cues_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
