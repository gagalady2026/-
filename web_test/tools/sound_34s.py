"""Original soundtrack for the 34-second animatic (animatic_34s.html): music, sound effects and ambience, all synthesized in
this file from sine waves and noise. No samples, no third-party audio, nothing to license. There are no voices: the lines
stay as subtitles, and README.md has a timing sheet for recording them.

usage: python3 tools/sound_34s.py OUT.f32 [CUES.json]
  OUT.f32    48 kHz stereo float32 (raw, interleaved), exactly 34.0 s; mastered to -16 LUFS (one gain for everything) and a limiter, then
             encoded with ffmpeg (see README); one gain for the whole mix keeps the music under the effects
  CUES.json  every sound event with its time, for checking against the picture

Timing follows the page's shot list (24 fps): knocks on the frames where 똑! appears, the hinge creak with 끼익, taps on the
tablet presses, chimes as the ① / ② labels appear, the evening ambience from 28.0 s, the end-card bell with the message.

Music: a light, everyday tune, the kind a corner shop plays — ukulele strums, a bouncy bass, finger snaps and a shaker, a
glockenspiel line. D major, 120 bpm, bars of two seconds placed so the gate opening (4.25 s), sitting down (8.25 s), "같이 방법을
찾아봐요." (16.25 s) and the sunset (28.25 s) fall on downbeats. It steps aside for the knocks and the creak, drops to soft
fingerpicking while he tells his trouble, comes back with the guidance, plays its tune in the sunset and ends with a "ding".
The music sits about 6 dB under the first (piano) version; effects and ambience keep their levels.

Mix moves (the tune itself is unchanged), so the lines — subtitles now, voices if they are recorded — sit clearly on top:
  - 6-24 s, the conversation: the music 2 dB lower, and a further 2.5 dB lower while a line is on screen (the line spans
    of the timing sheet, merged where the gaps are short so it does not pump; 0.25 s in, 0.5 s out);
  - 10-17 s, while he tells his trouble: 1.5 dB lower again (it is already only soft fingerpicking there);
  - from 28 s, the farewell: back up, 1 dB over where it was; from 30.5 s, under "체납 뒤에 사람이 있습니다.", opened a little
    more (+2.5 dB in all) so the close lingers;
  - the knocks, the latch and the creak about 2.5 dB further forward (fuller bodies under the same peaks: a soft clip before
    their level is set, since the master limiter would flatten higher peaks), the air of the gate opening 1.5 dB.
"""
import json, sys
import numpy as np

SR = 48000
DUR = 34.0
N = int(round(SR * DUR))
TAIL = 4 * SR
rng = np.random.default_rng(20261123)          # fixed seed: every run writes the same file
MUSIC_RMS = -28.0                              # music level over 18-28 s, dBFS before mastering: 6 dB under the first version
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


def dense(x, k):
    """A soft clip that fills out a sound's body under the same peak (the master limiter would flatten a higher peak)."""
    return np.tanh(k * x / (np.abs(x).max() + 1e-12)) / np.tanh(k)


# the lines as they are on screen (the README's timing sheet): the music steps back under them
LINES = [(2.0, 4.0), (5.1, 6.7), (9.6, 11.9), (12.8, 14.0), (14.1, 16.2), (16.3, 18.0), (18.4, 21.0), (22.4, 25.0), (26.2, 28.0)]


def db_curve(points):
    """Piecewise-linear automation in dB over the whole track: [(time, dB), ...] → gain."""
    ts, ds = zip(*points)
    return 10 ** (np.interp(np.arange(N + TAIL) / SR, ts, ds) / 20)


def music_moves():
    """The music's level moves under the picture (dB): the conversation, his story, each line on screen, the farewell, the close."""
    t = np.arange(N + TAIL) / SR
    section = np.interp(t, [0, 5.2, 6.0, 24.0, 25.0, 27.8, 28.6, 30.5, 31.1, 40], [0, 0, -2, -2, 0, 0, 1, 1, 2.5, 2.5])
    story = np.interp(t, [0, 9.6, 10.2, 16.8, 17.4, 40], [0, 0, -1.5, -1.5, 0, 0])
    spans = []                                                    # lines closer than 0.8 s count as one: no pumping between them
    for a, b in LINES:
        if a < 5.0:
            continue                                              # at the gate the music is out of the way already
        if spans and a - spans[-1][1] < 0.8:
            spans[-1][1] = b
        else:
            spans.append([a, b])
    duck = np.zeros_like(t)
    for a, b in spans:
        duck = np.minimum(duck, np.interp(t, [a - 0.25, a, b, b + 0.5], [0, -2.5, -2.5, 0], left=0, right=0))
    return 10 ** ((section + story + duck) / 20), spans


# ---------------------------------------------------------------- instruments
def ks_pluck(m, dur, vel, bright=0.5, t60=1.4, seed=0):
    """A plucked nylon string (Karplus-Strong): a noise burst circulating in a delay line one period long, averaged on every
    pass, so the string loses its highs as it rings; resampled afterwards to the exact pitch."""
    f = hz(m)
    L = max(2, int(SR / f - 0.5))
    n = S(dur) + 8
    r = np.random.default_rng(seed)
    exc = r.uniform(-1, 1, L)
    for _ in range(int(round(3 - 2 * bright))):
        exc = 0.5 * (exc + np.roll(exc, 1))
    exc -= exc.mean()
    g = 0.001 ** (1 / (t60 * f))
    z = np.zeros(n + 2 * L + 2)
    z[1:L + 1] = exc
    p = L + 1
    while p < n + 1:
        b = min(L, n + 1 - p)
        z[p:p + b] = g * 0.5 * (z[p - L:p - L + b] + z[p - L - 1:p - L - 1 + b])
        p += b
    y = z[1:n + 1]
    ratio = f / (SR / (L + 0.5))                     # the loop's own pitch is SR / (L + 0.5): stretch to the exact note
    y = np.interp(np.arange(S(dur)) * ratio, np.arange(y.size), y)
    fade = min(S(0.04), y.size)
    y[-fade:] *= np.linspace(1, 0, fade)
    return y * vel


def brush(vel, seed):
    """Fingers across the strings."""
    r = np.random.default_rng(seed)
    t = tvec(0.05)
    env = np.where(t < 0.035, np.sin(np.pi * t / 0.035) ** 2, 0)
    return ffilt(r.standard_normal(t.size), bp(2000, 7000, 1)) * env * vel * 0.08


def bass_pluck(m, dur, vel):
    """A round fingerstyle bass note."""
    f = hz(m)
    t = tvec(dur + 0.25)
    sig = np.sin(2 * np.pi * f * t) + 0.35 * np.exp(-t / 0.12) * np.sin(4 * np.pi * f * t) + 0.12 * np.exp(-t / 0.06) * np.sin(6 * np.pi * f * t)
    env = (1 - np.exp(-t / 0.004)) * np.exp(-t / 0.9)
    env = np.where(t > dur, env * np.exp(-(t - dur) / 0.05), env)
    return sig * env * vel


def kick():
    """A soft, round kick."""
    t = tvec(0.35)
    f = 50 + 75 * np.exp(-t / 0.03)
    sig = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12) * (1 - np.exp(-t / 0.0015))
    nc = S(0.004)
    sig[:nc] += 0.15 * ffilt(rng.standard_normal(nc), lp(3000, 2))
    return sig


def snap(seed):
    """A finger snap / light clap."""
    r = np.random.default_rng(seed)
    t = tvec(0.12)
    burst = lambda d: np.where(t >= d, np.exp(-np.maximum(0, t - d) / 0.006), 0)
    env = burst(0) + 0.7 * burst(0.007) + 0.35 * np.exp(-t / 0.035)
    return ffilt(r.standard_normal(t.size), bp(1100, 4500, 2)) * env


def shaker(seed):
    r = np.random.default_rng(seed)
    t = tvec(0.07)
    env = np.minimum(1, t / 0.006) * np.exp(-t / 0.022)
    return ffilt(r.standard_normal(t.size), hp(5500, 2)) * env


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
BPM = 120
BEAT = 60 / BPM
BAR0 = 0.25          # bars start at 0.25 + 2k s: the gate opening (4.25), sitting down (8.25), "같이 방법을 찾아봐요." (16.25) and the
                     # sunset (28.25) all land on a downbeat


def at(bar, beat=0.0):
    return BAR0 + (4 * bar + beat) * BEAT


UKE = {'D': [69, 62, 66, 69], 'A': [69, 61, 64, 69], 'Bm': [71, 62, 66, 71], 'G': [67, 62, 67, 71], 'Em': [67, 64, 67, 71]}   # G C E A strings
ROOT = {'D': 38, 'A': 45, 'Bm': 47, 'G': 43, 'Em': 40}
FIFTH = {'D': 45, 'A': 52, 'Bm': 54, 'G': 50, 'Em': 47}
# bar: (chord on beats 1-2, chord on beats 3-4, style). Before bar 2 (4.25 s): one soft strum and a little run while he climbs,
# then the music steps aside for the knocks, his voice at the gate and the creak.
BARS = {2: ('D', 'A', 'groove'), 3: ('Bm', 'G', 'groove'), 4: ('D', 'A', 'groove'),         # the gate opens, the greeting, the bench
        5: ('Em', 'Bm', 'soft'), 6: ('G', 'D', 'soft'), 7: ('Em', 'A', 'soft'),              # he tells his trouble
        8: ('G', 'A', 'build'),                                                              # "같이 방법을 찾아봐요."
        9: ('D', 'A', 'groove'), 10: ('Bm', 'G', 'groove'), 11: ('D', 'A', 'groove'), 12: ('Bm', 'G', 'groove'),   # ① and ②
        13: ('Em', 'A', 'light'),                                                            # "고마워요, 마음이 좀 놓이네요."
        14: ('D', 'A', 'chorus'),                                                            # the sunset
        15: ('G', 'A', 'end')}                                                               # the end card; D on the next downbeat
QUIET = (9.5, 16.25)     # from his first word to the official's answer: no drums, no strumming, soft fingerpicking
STRUM = {0: ('D', .75), 1: ('D', .55), 1.5: ('U', .45), 2.5: ('U', .45), 3: ('D', .6), 3.5: ('U', .45)}   # beat: stroke, velocity
PICK = (1, 2, 0, 3, 2, 0, 1, 3)        # fingerpicking order over the four strings, one note an eighth
MELODY = [  # (bar, beat, midi, beats, velocity): the glockenspiel tune in the sunset and the close
    (14, 0, 78, 1, .5), (14, 1, 81, .5, .45), (14, 1.5, 78, .5, .42), (14, 2, 76, 1, .48), (14, 3, 73, .5, .42), (14, 3.5, 76, .5, .42),
    (15, 0, 74, 1.5, .45), (15, 2, 76, 1.5, .42), (16, 0, 86, 2, .5)]
RUNS = [(0.25, [74, 78, 81]), (4.25, [81, 86]), (17.875, [81, 83, 85])]   # little glockenspiel runs (16ths): climbing, the gate, into ①


def score():
    """Every note and hit of the band: lists of (time, ...)."""
    strums, picks, basses, kicks, snaps, shakes, glock = [(0.25, 'D', 'D', .45)], [], [], [], [], [], []
    for b, (c1, c2, style) in sorted(BARS.items()):
        for i in range(8):
            beat = i / 2
            t = at(b, beat)
            ch = c1 if beat < 2 else c2
            quiet = QUIET[0] <= t < QUIET[1]
            st = 'soft' if quiet else style
            if st == 'soft':
                picks.append((t, UKE[ch][PICK[i]], .34 + (.06 if i % 4 == 0 else 0)))
                if beat in (0, 2) or (style != 'soft' and t == QUIET[0]):
                    basses.append((t, ROOT[ch], 2 * BEAT if beat in (0, 2) else 1.5 * BEAT, .55))
                continue
            if st == 'end':
                if beat in (0, 1, 2, 3):
                    strums.append((t, ch, 'D', (.6, .45, .58, .42)[int(beat)]))
                if beat in (0, 2):
                    basses.append((t, ROOT[ch], 2 * BEAT, .7))
                if beat == 0:
                    kicks.append((t, .8))
                if beat < 2:
                    shakes.append((t, .4 if i % 2 == 0 else .6))
                continue
            k = {'groove': 1.0, 'chorus': 1.05, 'light': .72, 'build': .85}[st]
            if beat in STRUM:
                stroke, v = STRUM[beat]
                strums.append((t, ch, stroke, v * k))
            if st == 'build':
                if beat in (0, 1, 2, 3):                     # walking up into D: G B A C#
                    basses.append((t, ROOT[ch] + (4 if beat in (1, 3) else 0), BEAT, .8))
                if beat == 3:
                    snaps.append((t, .7))
                continue
            if beat in (0, 1.5, 2, 3.5):
                note = ROOT[c1] if beat < 2 else (ROOT[c2] if beat == 2 else FIFTH[c2])
                basses.append((t, note, (BEAT if beat in (0, 2) else BEAT / 2), .65 if st == 'light' else .85))
            if st != 'light' and (beat in (0, 2) or (st == 'chorus' and beat == 2.5)):
                kicks.append((t, 1.0 if beat == 0 else .85))
            if beat in (1, 3):
                snaps.append((t, .6 if st == 'light' else .85))
            shakes.append((t, (.35 if i % 2 == 0 else .6) * (.75 if st == 'light' else 1)))
    for i in range(8):                                   # bar 8: the shaker swells in sixteenths toward the guidance
        shakes.append((at(8, 2 + i * 0.25), .25 + .07 * i))
    t_end = at(16)                                       # the last downbeat: D, a ding, a kick
    strums.append((t_end, 'D', 'D', .7))
    basses.append((t_end, ROOT['D'], 3 * BEAT, .8))
    kicks.append((t_end, .9))
    for b, beat, m, beats, v in MELODY:
        glock.append((at(b, beat), m, v))
    for t0, notes in RUNS:
        for j, m in enumerate(notes):
            glock.append((t0 + 0.125 * j, m, .38 + .04 * j))
    return strums, picks, basses, kicks, snaps, shakes, glock


def main(out_path, cues_path=None):
    strums, picks, basses, kicks, snaps, shakes, glock = score()
    uke, bass_b, kick_b, snap_b, shk_b, glock_b, bell_b = Bus(), Bus(), Bus(), Bus(), Bus(), Bus(), Bus()
    seeds = iter(range(1000, 10 ** 6))
    strums.sort()
    for j, (t0, ch, stroke, v) in enumerate(strums):
        nxt = strums[j + 1][0] if j + 1 < len(strums) else DUR
        ring = min(1.6, max(0.12, nxt - t0 + 0.03))       # a new strum damps the strings it replays
        notes = UKE[ch] if stroke == 'D' else UKE[ch][::-1]
        for i, m in enumerate(notes):
            uke.add(ks_pluck(m, ring, v * (0.9 + 0.1 * rng.random()), bright=.55 if stroke == 'D' else .45, seed=next(seeds)),
                    t0 + i * (0.011 if stroke == 'D' else 0.008), pan=-0.25 + 0.15 * i)
        uke.add(brush(v, next(seeds)), t0)
    for t0, m, v in picks:
        uke.add(ks_pluck(m, 1.1, v, bright=.4, seed=next(seeds)), t0, pan=-0.2 + 0.4 * ((m - 60) / 12))
    for t0, m, d, v in basses:
        bass_b.add(bass_pluck(m, d, v), t0)
    for t0, v in kicks:
        kick_b.add(kick() * v, t0)
    for t0, v in snaps:
        snap_b.add(snap(next(seeds)) * v, t0, pan=0.15)
    for t0, v in shakes:
        shk_b.add(shaker(next(seeds)) * v, t0, pan=0.35)
    for t0, m, v in glock:
        glock_b.add(bell(m, v, 1.6), t0, pan=0.2)
    uke_x = ffilt(uke.x, lambda f: lp(5500, 1)(f) * hp(140, 1)(f))
    music_dry = (to_rms(uke_x, 18.25, 26.25, -30) + to_rms(bass_b.x, 18.25, 26.25, -33) + to_rms(kick_b.x, 18.25, 26.25, -37)
                 + to_rms(snap_b.x, 18.25, 26.25, -40) + to_rms(shk_b.x, 18.25, 26.25, -44) + to_peak(glock_b.x, -20))
    send = music_dry.mean(axis=0) * 0.6
    music = music_dry + 0.22 * conv(send, reverb_ir(1.1, 1.6, 0.012, 6000, 4))[:, :N + TAIL]
    music = to_rms(music, 18, 28, MUSIC_RMS)
    moves, spans = music_moves()
    music *= moves * curve([(0, 1), (33.5, 1), (34.0, 0), (40, 0)])
    for a, b in spans:
        cue(a, f"music steps back under the lines ({a:.1f}-{b:.1f} s)")
    cue(0.25, "music: a strum and a little run")
    cue(4.25, "music: the band comes in (the gate opens)")
    cue(9.5, "music: soft fingerpicking (he tells his trouble)")
    cue(16.25, "music: strums again, the shaker swells")
    cue(18.25, "music: full groove (the guidance)")
    cue(28.25, "music: the glockenspiel tune (sunset)")
    cue(32.25, "music: the last D, a ding")

    # chimes (effects, not music: they keep their level): the ① / ② labels, the bars filling / links lighting, the end card
    for t0, notes in ((18.32, [74, 78, 81]), (22.32, [79, 83, 86])):
        for j, m in enumerate(notes):
            bell_b.add(bell(m, .5 - .08 * j, 1.6), t0 + 0.06 * j, pan=-0.3)
        cue(t0, "chime: label " + ("①" if t0 < 20 else "②"))
    for t0, notes in ((18.64, [78, 81, 86]), (22.64, [79, 83, 86])):
        for j, m in enumerate(notes):
            bell_b.add(plink(m, .4), t0 + 0.14 * j, pan=-0.35)
        cue(t0, "plinks: " + ("bars fill" if t0 < 20 else "links light"))
    bell_b.add(bell(86, .55, 3.0), 30.78)
    cue(30.78, "bell: end-card message")
    # the sign-off (CI place, name, number) appears on the music's last downbeat (32.25 s): the band's final D and 'ding' mark it
    bell_x = to_peak(bell_b.x, -17)
    bells = (bell_x + 0.3 * conv(bell_x.mean(axis=0), reverb_ir(1.6, 2.4, 0.02, 5500, 1))[:, :N + TAIL]) * curve([(0, 1), (33.4, 1), (34.0, 0), (40, 0)])

    # ---------------------------------------------------------------- effects
    fx = Bus()
    for i, t0 in enumerate((0.255, 0.681)):                                   # CUT 1: footfalls (steps land at (n + 0.6) / 2.35 s)
        fx.add(to_peak(footstep(10 + i), -18), t0 - 0.004, pan=(-0.08, 0.08)[i])
        cue(t0, "footstep")
    for i, t0 in enumerate((1.3208, 1.7379)):                                 # CUT 2: 똑! 똑! (u = 0.10, 0.23 of the gate shot)
        fx.add(to_peak(dense(knock(20 + i), 1.3), -7.0 + 0.5 * i), t0, pan=(0.22, 0.4)[i])   # the title's 똑똑: the loudest effect,
                                                                                               # fuller under the same peak (forward)
        cue(t0, "knock")
    fx.add(to_peak(dense(latch(), 1.2), -19), 3.62, pan=0.3)                # the gate's sounds ~2.5 dB further forward
    cue(3.62, "latch")
    fx.add(to_peak(dense(creak(), 1.0), -12.5), 3.70, pan=0.32)             # 끼익 shows at 3.76
    cue(3.70, "hinge creak")
    fx.add(to_peak(whoosh(), -25.5), 4.12, pan=0.1)
    cue(4.12, "air, gate open")
    for i, t0 in enumerate((18.23, 18.59, 22.23, 22.59)):                    # CUT 6: the two presses on each panel
        fx.add(to_peak(tap(30 + i), -21), t0, pan=-0.4)
        cue(t0, "tablet tap")
    fx_send = fx.x.mean(axis=0)
    fx_x = fx.x + 0.22 * conv(fx_send, reverb_ir(0.7, 1.2, 0.008, 6000, 2))[:, :N + TAIL]

    # ---------------------------------------------------------------- ambience
    n = N + TAIL
    amb = to_rms(waves(n), 0, 30, -30) * curve([(0, 1), (0.97, 1), (1.03, .4), (9.45, .4), (9.55, .3), (28.0, .3), (28.5, .65),
                                                (31.0, .65), (33.7, 0), (40, 0)])
    amb += to_rms(wind(n), 0, 30, -43) * curve([(0, .8), (0.97, .8), (1.03, .5), (28.0, .5), (28.5, .6), (31.0, .6), (33.7, 0), (40, 0)])
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
        crick.add(cricket(28.0, 34.0, f, period, 60 + j), 28.0, pan=pan)
    cue(28.0, "crickets (evening)")
    crick_x = to_peak(crick.x, -31) * curve([(0, 0), (28.0, 0), (28.5, 1), (31.0, 1), (33.7, 0), (40, 0)])
    air_x = air.x + crick_x
    air_x = air_x + 0.35 * conv(air_x.mean(axis=0), reverb_ir(1.5, 2.0, 0.03, 5000, 3))[:, :n]
    amb += air_x
    amb *= curve([(0, 0), (0.2, 1), (40, 1)])

    mix = (music + bells + fx_x + amb)[:, :N] * 10 ** (0.43 / 20)    # the first version's normalisation gain, kept fixed so
                                                                        # effects and ambience stay where they were
    mix.T.astype("<f4").tofile(out_path)
    stems = {"music": music[:, :N], "chimes": bells[:, :N], "effects": fx_x[:, :N], "ambience": amb[:, :N]}
    report = {k: {"rms_dbfs": round(rms_db(v, 0, DUR), 1), "peak_dbfs": round(20 * np.log10(np.abs(v).max() + 1e-12), 1)} for k, v in stems.items()}
    print(json.dumps(report))
    if cues_path:
        json.dump(sorted(CUES, key=lambda c: c["t"]), open(cues_path, "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
