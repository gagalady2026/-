"""
animation.py — 컷별 블로킹: setup_cut_01() ~ setup_cut_08()

각 컷은 "프레임 → 두 인물·소품의 전체 포즈" 함수로 작성하고, 컷 구간을 매 프레임 키로 굽습니다.
  · 컷 경계에서 포즈가 새지 않고(다음 컷 첫 프레임에 정확히 전환), 결과가 항상 같게 재현됩니다.
  · 행동 타이밍은 config.BEATS(컷 길이 대비 비율), 크기·속도는 config 값을 씁니다.
계단 보행은 발 디딤 계획(FootTrack) + 다리 IK 로 발이 디딤판에 실제로 닿게 만듭니다.
"""
import math

from mathutils import Euler, Matrix, Vector

import cameras
import config
from utils import (bump, clamp, heading_vec, key_visible, rot2, smootherstep, smoothstep, window,
                   yaw_facing)


# =============================================================================
# 컨텍스트
# =============================================================================
class PrevisContext:
    def __init__(self, layout, main, citizen, cams):
        self.L = layout
        self.main = main
        self.cit = citizen
        self.cams = cams
        self.house_spot = Vector((9.3, 1.0, layout.z_up))   # 화면 밖 대기 위치(집 안)

    def key_chars(self, f):
        self.main.key(f)
        self.cit.key(f)


def _t(f, n):
    f0, f1 = config.cut_range(n)
    return (f - f0) / max(1, f1 - f0)


def _frames(n):
    f0, f1 = config.cut_range(n)
    return range(f0, f1 + 1)


def _key_obj(obj, f, loc=None, rot=None):
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert("location", frame=f)
    if rot is not None:
        obj.rotation_euler = rot
        obj.keyframe_insert("rotation_euler", frame=f)


def _hide_citizen(ctx):
    """시민을 화면 밖(집 안)에 세워 둠."""
    ctx.cit.stand(ctx.house_spot, Vector((-1, 0, 0)))


def _gate(ctx, f, deg):
    _key_obj(ctx.L.gate_leaf, f, rot=(0.0, 0.0, math.radians(deg)))


# =============================================================================
# 보행: 발 디딤 계획 + 골반 높이(도달 가능 높이의 최소값을 부드럽게) + 다리 IK
# =============================================================================
class FootTrack:
    """한 발의 디딤 계획. move() 로 (시작·끝 프레임, 도착 발목 위치, 발 방향)을 쌓아 둠.
    ground(p) 가 주어지면 공중에 뜬 발의 발바닥(뒤꿈치~발끝)이 계단 면 아래로 파고들지 않게 올려 줌."""

    def __init__(self, pos, yaw, ground=None, ankle_h=0.08, foot=(0.06, 0.20)):
        self.p0 = Vector(pos)
        self.y0 = yaw
        self.moves = []
        self.ground = ground
        self.ankle_h = ankle_h
        self.heel, self.toe = foot

    def last(self):
        if self.moves:
            m = self.moves[-1]
            return m[3], m[5]
        return self.p0, self.y0

    def move(self, f0, f1, p1, yaw1=None, lift=0.07, mode="flat"):
        pa, ya = self.last()
        self.moves.append((f0, f1, pa, Vector(p1), ya, ya if yaw1 is None else yaw1, lift, mode))

    def _clear(self, pos, yaw):
        if self.ground is None:
            return pos
        fwd = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
        top = -1e9
        for k in range(6):
            q = pos + fwd * (-self.heel + (self.heel + self.toe) * k / 5.0)
            top = max(top, self.ground(q))
        if pos.z < top + self.ankle_h + 0.012:
            pos.z = top + self.ankle_h + 0.012
        return pos

    def at(self, f):
        p, y = self.p0, self.y0
        for (a, b, pa, pb, ya, yb, lift, mode) in self.moves:
            if f >= b:
                p, y = pb, yb
                continue
            if f <= a:
                break
            s = (f - a) / (b - a)
            e = smootherstep(s)
            pos = pa.lerp(pb, e)
            dz = pb.z - pa.z
            if mode == "up":        # 오를 때: 앞 계단 모서리를 넘도록 초반에 발을 먼저 들어 올림
                z = pa.z + dz * smoothstep(s / 0.5) + lift * math.sin(math.pi * s)
            elif mode == "down":    # 내려갈 때: 앞으로 먼저 내밀고 늦게 내려 디딤
                z = pa.z + dz * smoothstep((s - 0.45) / 0.55) + lift * math.sin(math.pi * min(1.0, s / 0.85))
            else:
                z = pa.z + dz * e + lift * math.sin(math.pi * s)
            pos.z = z
            yaw = ya + (yb - ya) * e
            if s < 0.97:
                pos = self._clear(pos, yaw)
            return pos, yaw, True
        return p, y, False


def bake_locomotion(p, frames, feet, body_fn, extra_fn=None, lean=0.0, arm_amp=10.0, margin=0.975):
    """feet = {'L': FootTrack, 'R': FootTrack}, body_fn(f) → (몸 중심 xy Vector, yaw rad)."""
    d = p.dims
    leg = d["thigh"] + d["shin"]
    frames = list(frames)
    raw = []
    for f in frames:
        xy, yaw = body_fn(f)
        rz = Matrix.Rotation(yaw, 3, 'Z')
        h = 1e9
        for side, sx in (("L", 1.0), ("R", -1.0)):
            ank, _yaw, swinging = feet[side].at(f)
            if swinging:
                continue                      # 골반 높이는 디딘 발 기준 (흔드는 발은 IK 가 따라감)
            hip = Vector((xy.x, xy.y, 0.0)) + rz @ Vector((sx * d["hip_w"], 0.0, 0.0))
            dxy = math.hypot(ank.x - hip.x, ank.y - hip.y)
            h = min(h, ank.z + math.sqrt(max((leg * margin) ** 2 - dxy * dxy, 0.0)))
        if h > 1e8:                           # 두 발이 모두 공중이면(없어야 함) 직전 값 유지
            h = raw[-1] if raw else d["hip_z"]
        raw.append(h)
    n, w = len(raw), 4
    ero = [min(raw[max(0, i - w):i + w + 1]) for i in range(n)]
    smooth = []
    for i in range(n):
        seg = ero[max(0, i - w):i + w + 1]
        smooth.append(min(sum(seg) / len(seg), raw[i]))

    for i, f in enumerate(frames):
        xy, yaw = body_fn(f)
        p.reset_pose()
        p.root.location = (xy.x, xy.y, smooth[i] - d["hip_z"])
        p.root.rotation_euler = (0.0, 0.0, yaw)
        facing = p.facing()
        p.set_rot("torso", lean, 0.0, 0.0)
        fwd_off = {}
        for side in ("L", "R"):
            ank, fyaw, _ = feet[side].at(f)
            p.leg_ik(side, ank, knee_dir=facing + Vector((0, 0, 0.1)), foot_yaw=fyaw)
            fwd_off[side] = (ank - p.joint_pos("thigh_" + side)).dot(facing)
        swing = clamp((fwd_off["L"] - fwd_off["R"]) / 0.45, -1.0, 1.0)
        p.set_rot("upper_arm_R", -arm_amp * swing, 5.0, 0.0)
        p.set_rot("upper_arm_L", arm_amp * 0.5 * swing, -5.0, 0.0)
        p.set_rot("forearm_R", -10.0 - 6.0 * max(0.0, swing), 0.0, 0.0)
        p.set_rot("forearm_L", -12.0, 0.0, 0.0)
        p.set_rot("torso", lean, 0.0, -2.5 * swing)
        if extra_fn is not None:
            extra_fn(p, f)
        p.key(f)


def stairs_ascent(L, p, first_lift, n_steps, frames_per_step, lead_tread, swing=0.72):
    """한 발에 한 칸씩 오르기. 앞발(L)이 lead_tread, 뒷발(R)이 그 아래 칸에서 시작."""
    ah = p.dims["ankle_h"]

    def ank(tread, side):
        return L.stair_point(tread * L.st_run + 0.08, 0.095 if side == "L" else -0.095, dz=ah)
    yaw = yaw_facing(L.st_dir)
    kw = dict(ground=L.surface_height, ankle_h=ah, foot=(0.06 * p.dims["scale"], 0.20 * p.dims["scale"]))
    feet = {"L": FootTrack(ank(lead_tread, "L"), yaw, **kw), "R": FootTrack(ank(lead_tread - 1, "R"), yaw, **kw)}
    tread = {"L": lead_tread, "R": lead_tread - 1}
    s = max(2, round(frames_per_step * swing))
    trail = "R"
    for i in range(n_steps):
        fl = first_lift + i * frames_per_step
        tread[trail] += 2
        feet[trail].move(fl, fl + s, ank(tread[trail], trail), lift=0.075, mode="up")
        trail = "L" if trail == "R" else "R"
    u0 = lead_tread * L.st_run + 0.08 - 0.10

    def body(f):
        u = u0 + (f - first_lift) * L.st_run / frames_per_step
        return L.stair_point(u, 0.0), yaw
    return feet, body


def flat_walk(p, start, heading, first_lift, n_steps, frames_per_step, step_len, swing=0.62):
    fv = heading_vec(heading)
    left = rot2(fv, 90.0)
    yaw = yaw_facing(fv)
    base = Vector(start)
    ah = p.dims["ankle_h"]

    def ank(s, side):
        return base + fv * s + left * (0.09 if side == "L" else -0.09) + Vector((0, 0, ah))
    pos = {"L": step_len * 0.5, "R": -step_len * 0.5}
    feet = {k: FootTrack(ank(v, k), yaw) for k, v in pos.items()}
    sw = max(2, round(frames_per_step * swing))
    trail = "R"
    for i in range(n_steps):
        fl = first_lift + i * frames_per_step
        pos[trail] += 2 * step_len
        feet[trail].move(fl, fl + sw, ank(pos[trail], trail), lift=0.05)
        trail = "L" if trail == "R" else "R"

    def body(f):
        return base + fv * (0.3 * step_len + (f - first_lift) * step_len / frames_per_step), yaw
    return feet, body


# =============================================================================
# CUT 1 — 바닷가 마을로 들어서다 (계단 오르기 + 담장 너머 집 확인)
# =============================================================================
def setup_cut_01(ctx):
    L, m = ctx.L, ctx.main
    f0, f1 = config.cut_range(1)
    F = config.WALK_FRAMES_PER_STEP
    first = f0 - 4                                   # 첫 프레임부터 이미 발이 움직이고 있음
    n_steps = (f1 - first) // F + 2
    feet, body = stairs_ascent(L, m, first, n_steps, F, lead_tread=config.CUT01_START_STEP)
    house = Vector((9.3, 1.0, L.z_up + 2.2))

    def extra(p, f):
        t = _t(f, 1)
        ahead = p.joint_pos("head") + L.st_dir * 4.0 + Vector((0, 0, 1.2))
        wgt = bump(t, 0.46, 0.98, hold=0.4)
        p.look_at(ahead.lerp(house, wgt), max_yaw=55.0)

    bake_locomotion(m, _frames(1), feet, body, extra_fn=extra, lean=6.0, arm_amp=9.0)
    for f in (f0, f1):
        _hide_citizen(ctx)
        ctx.cit.key(f)
        _gate(ctx, f, 0.0)
    cameras.camera_cut01(ctx.cams[1], L)


# =============================================================================
# CUT 2 — 문 앞에서 (명찰 정돈 → 두 번 노크)
# =============================================================================
def setup_cut_02(ctx):
    L, m = ctx.L, ctx.main
    zu = L.z_up
    b = config.BEATS[2]
    s = m.dims["scale"]
    pos = Vector((-0.44, -0.30, zu))
    facing = heading_vec(24.0)                      # 대문 남쪽 절반 앞, 몸을 카메라(북) 쪽으로 튼 자세 → 명찰이 보임
    knock_pt = Vector((-0.012, 0.06, zu + 1.16))    # 철대문 바깥면(살 표면 x≈0.013)에 주먹 끝이 닿는 점, 문짝 가운데
    knock_dir = Vector((1.0, 0.35, -0.12)).normalized()
    ready = knock_pt - knock_dir * 0.075

    for f in _frames(2):
        t = _t(f, 2)
        m.stand(pos, facing)
        m.set_rot("torso", 2.0, 0.0, 0.0)
        rest_l = m.local_point("hand_L", (0, 0, -m.dims["hand"] * 1.12))
        rest_r = m.local_point("hand_R", (0, 0, -m.dims["hand"] * 1.12))
        # 왼손: 명찰 정돈 (살짝 잡아 내렸다 놓기)
        a0, a1 = b["tag_adjust"]
        wl = bump(t, a0, a1, hold=0.4)
        tag = m.local_point("torso", (0.028 * s, -0.15 * s, 0.186 * s))
        tag.z -= 0.012 * bump(t, a0 + (a1 - a0) * 0.42, a0 + (a1 - a0) * 0.72)
        m.reach("L", rest_l.lerp(tag, wl), direction=m.to_char_space((-0.55, -0.35, 0.75)).lerp(
            m.to_char_space((0.2, -0.3, -0.9)), 1.0 - wl), elbow_dir=m.to_char_space((0.8, 0.3, -0.6)))
        # 오른손: 들어 올려 두 번 노크 → 살짝 내림
        up = window(t, b["knock_raise"] - 0.13, b["knock_raise"] + 0.05)
        tap = max(bump(t, b["knock_1"] - 0.045, b["knock_1"] + 0.045), bump(t, b["knock_2"] - 0.045, b["knock_2"] + 0.045))
        down = window(t, b["knock_lower"][0], b["knock_lower"][1]) * 0.55
        tip_r = rest_r.lerp(ready.lerp(knock_pt, tap), up * (1.0 - down))
        m.reach("R", tip_r, direction=m.to_char_space((0.0, -0.3, -1.0)).lerp(knock_dir, up),
                elbow_dir=m.to_char_space((-0.7, 0.35, -0.6)))
        m.look_at(knock_pt + Vector((0, 0.1, 0.15)), weight=0.8)
        m.key(f)
        if f in config.cut_range(2):
            _hide_citizen(ctx)
            ctx.cit.key(f)
            _gate(ctx, f, 0.0)
    cameras.camera_cut02(ctx.cams[2], L)


# =============================================================================
# CUT 3 — 문이 열린다 (반쯤 열림 → 가벼운 목례 → 더 열고 마당 쪽으로 안내)
# =============================================================================
def _gate_handle(L, deg, inner=True):
    leaf = L.gate_leaf
    r = Matrix.Rotation(math.radians(deg), 4, 'Z')
    local = Vector((0.05 if inner else -0.05, -config.GATE_WIDTH + 0.1, 1.05))
    return Vector(leaf.location) + (r @ local.to_4d()).to_3d()


def setup_cut_03(ctx):
    L, m, c = ctx.L, ctx.main, ctx.cit
    zu = L.z_up
    b = config.BEATS[3]
    pos_m = Vector((-0.62, 0.02, zu))
    c_start, c_peek, c_aside = Vector((0.62, -0.50, zu)), Vector((0.34, -0.40, zu)), Vector((0.50, -0.30, zu))

    for f in _frames(3):
        t = _t(f, 3)
        dh, df = b["door_half"], b["door_full"]
        ang = config.GATE_OPEN_HALF * window(t, *dh) + (config.GATE_OPEN_FULL - config.GATE_OPEN_HALF) * window(t, *df)
        _gate(ctx, f, ang)
        # 주인공: 문 앞에 선 자세 (고개는 시민 포즈 뒤에)
        m.stand(pos_m, Vector((1, 0, 0)))
        bow = bump(t, *b["bow"], hold=0.3)
        m.set_rot("torso", 1.5 + bow * config.BOW_ANGLE * 0.4, 0, 0)

        # 시민: 문을 반쯤 열고 조심스럽게 내다봄 → 문을 더 열며 옆으로 비켜서서 마당 쪽으로 안내
        peek = window(t, dh[0] + 0.08, dh[1] + 0.06)
        aside = window(t, *b["turn_to_yard"])
        cpos = c_start.lerp(c_peek, peek).lerp(c_aside, aside)
        face = rot2(Vector((-1, 0, 0)), -40.0 * aside)            # 서쪽(주인공)을 보다가 반걸음 물러서며 몸을 엶
        c.stand(cpos, face)
        c.look_at(_face(m, m.dims["scale"]), max_yaw=70.0)
        rest_r = c.local_point("hand_R", (0, 0, -c.dims["hand"] * 1.12))
        hold = window(t, 0.0, dh[0] + 0.02) * (1.0 - window(t, df[1] - 0.02, df[1] + 0.07))
        handle = _gate_handle(L, ang)
        gesture = c.local_point("torso", (-0.30, -0.26, 0.02))    # 마당 쪽을 가리키는 열린 손
        tip = rest_r.lerp(handle, hold)
        tip = tip.lerp(gesture, window(t, df[1] - 0.02, 1.0) * 0.9)
        c.reach("R", tip, elbow_dir=c.to_char_space((-0.8, 0.3, -0.5)))
        c.key(f)

        # 주인공 고개: 시민을 보며 10~15도 목례
        m.look_at(_face(c, c.dims["scale"]), max_yaw=60.0, extra_pitch=bow * config.BOW_ANGLE * 0.6)
        m.key(f)
    cameras.camera_cut03(ctx.cams[3], L)


# =============================================================================
# CUT 4~6 공통 — 평상 좌석
# =============================================================================
def _seat(ctx):
    L = ctx.L
    so, st = config.SEAT_OFFSET, math.radians(config.SEAT_TURN)
    main_face = L.plat_dir(-math.cos(st), -math.sin(st))
    cit_face = L.plat_dir(math.cos(st), -math.sin(st))
    ctx.main.sit_cross_legged(L.plat(so, 0.05), main_face, L.pl_top)
    ctx.cit.sit_cross_legged(L.plat(-so, 0.05), cit_face, L.pl_top)


def _face(p, s):
    return p.local_point("head", (0, -0.05, 0.19 * s))


def _cup_rot(L):
    return (0.0, 0.0, L.plat_rot_z())


# =============================================================================
# CUT 4 — 평상에 마주 앉다 (시민이 찻잔을 밀어 주고, 주인공이 두 손으로 받음)
# =============================================================================
def setup_cut_04(ctx):
    L, m, c = ctx.L, ctx.main, ctx.cit
    b = config.BEATS[4]
    top = L.pl_top
    cup_a, cup_b = L.plat(-0.07, -0.33, 0.0), L.plat(0.13, -0.25, 0.0)
    cup_a.z = cup_b.z = top
    cup_cit = L.plat(-0.20, -0.42)
    cup_cit.z = top
    f0, f1 = config.cut_range(4)
    for f in _frames(4):
        t = _t(f, 4)
        _seat(ctx)
        m.set_rot("torso", 3.0, 0, 0)
        c.set_rot("torso", 3.0, 0, 0)
        p0, p1 = b["push_cup"]
        push = window(t, p0 + (p1 - p0) * 0.3, p1 - (p1 - p0) * 0.1)
        cup = cup_a.lerp(cup_b, push)
        # 시민 오른손: 찻잔으로 → 밀기 → 거두기
        reach_c = bump(t, p0, p1 + 0.05, hold=0.55)
        rest = c.local_point("hand_R", (0, 0, -c.dims["hand"] * 1.12))
        push_dir = (cup_b - cup_a).normalized()
        c.reach("R", rest.lerp(cup - push_dir * 0.05 + Vector((0, 0, 0.05)), reach_c),
                direction=(push_dir + Vector((0, 0, -0.6))).normalized(), elbow_dir=c.to_char_space((-0.7, 0.4, -0.6)))
        # 주인공: 두 손으로 받아 살짝 들어 올림
        r0, r1 = b["receive"]
        rc = window(t, r0, r0 + (r1 - r0) * 0.45)
        lift = window(t, r0 + (r1 - r0) * 0.5, r1)
        cup = cup + Vector((0, 0, 0.12 * lift)) + m.to_char_space((0, 0.10, 0)) * lift
        side = m.to_char_space((1, 0, 0))
        for sd, sgn in (("L", 1.0), ("R", -1.0)):
            rest = m.local_point("hand_" + sd, (0, 0, -m.dims["hand"] * 1.12))
            tip = cup + side * (sgn * 0.055) + Vector((0, 0, 0.04))
            m.reach(sd, rest.lerp(tip, rc), direction=(-side * sgn + Vector((0, 0, -0.4))).normalized().lerp(
                m.to_char_space((0, -0.5, -0.8)), 1.0 - rc), elbow_dir=m.to_char_space((sgn * 0.8, 0.3, -0.6)))
        m.look_at(_face(c, c.dims["scale"]).lerp(cup, 0.7 * bump(t, r0 - 0.08, r1 + 0.1, 0.5)))
        c.look_at(_face(m, m.dims["scale"]).lerp(cup, 0.6 * bump(t, p0, p1, 0.5)))
        ctx.key_chars(f)
        _key_obj(L.props["cup_main"], f, loc=cup, rot=_cup_rot(L))
        if f in (f0, f1):
            _key_obj(L.props["cup_citizen"], f, loc=cup_cit, rot=_cup_rot(L))
    cameras.camera_cut04(ctx.cams[4], L)


# =============================================================================
# CUT 5 — 이야기를 듣다 (시민: 먼 곳을 보며 말하다 다시 주인공을 봄 / 주인공: 몸을 기울여 천천히 한 번 끄덕임)
# =============================================================================
def setup_cut_05(ctx):
    L, m, c = ctx.L, ctx.main, ctx.cit
    b = config.BEATS[5]
    top = L.pl_top
    f0, f1 = config.cut_range(5)
    cup_main = L.plat(0.17, -0.30)
    cup_main.z = top
    for f in _frames(5):
        t = _t(f, 5)
        _seat(ctx)
        cs = c.dims["scale"]
        # 시민: 찻잔을 두 손으로 감싸 쥠
        cup = c.root.location + c.to_char_space((0.0, -0.25 * cs, 0.0))
        cup.z = top + 0.27
        side = c.to_char_space((1, 0, 0))
        for sd, sgn in (("L", 1.0), ("R", -1.0)):
            c.reach(sd, cup + side * (sgn * 0.058) + Vector((0, 0, 0.035)),
                    direction=(-side * sgn + c.to_char_space((0, -0.3, 0)) + Vector((0, 0, -0.2))).normalized(),
                    elbow_dir=c.to_char_space((sgn * 0.7, 0.3, -0.7)))
        c.set_rot("torso", 4.0, 0, 0)
        la0 = b["look_away"][0]
        away_in = 1.0 if la0 <= 0.0 else window(t, la0, la0 + 0.08)
        away = away_in * (1.0 - window(t, *b["look_back"]))
        c.look_at(_face(m, m.dims["scale"]))
        talk = 1.6 * math.sin(2.0 * math.pi * (f - f0) / 13.0) * (1.0 - window(t, 0.62, 0.8))
        h = c.parts["head"].rotation_euler
        c.parts["head"].rotation_euler = (h.x + math.radians(talk + 7.0 * away),
                                          h.y, h.z * (1.0 - away) + math.radians(-52.0) * away)
        # 주인공: 시민 쪽으로 몸을 약간 기울이고 경청, 천천히 한 번 끄덕임
        m.set_rot("torso", 5.0, 0, 7.0)
        m.look_at(_face(c, cs))
        nod = bump(t, *b["nod"], hold=0.15) * config.NOD_ANGLE
        m.add_rot("head", nod, 0, 0)
        ctx.key_chars(f)
        _key_obj(L.props["cup_citizen"], f, loc=cup, rot=(0.0, 0.0, c.root.rotation_euler.z))
        if f in (f0, f1):
            _key_obj(L.props["cup_main"], f, loc=cup_main, rot=_cup_rot(L))
    cameras.camera_cut05(ctx.cams[5], L)


# =============================================================================
# CUT 6 — 분납과 복지 연계를 안내하다 (자료의 두 영역을 순서대로 가리킴 → 시민 끄덕임·손 모음)
# =============================================================================
def _tablet_pose(L):
    tilt = 24.0
    loc = L.plat(0.03, -0.30)
    loc.z = L.pl_top + 0.125 * math.sin(math.radians(tilt)) + 0.004
    rot = Euler((math.radians(tilt), 0.0, L.plat_rot_z()), 'XYZ')
    return loc, rot


def tablet_point(L, which, lift=0.018):
    """태블릿 두 영역의 중심 (1 = 왼쪽 분납, 2 = 오른쪽 복지)."""
    loc, rot = _tablet_pose(L)
    mtx = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
    x = -0.09 if which == 1 else 0.09
    return mtx @ Vector((x, 0.005, lift))


def setup_cut_06(ctx):
    L, m, c = ctx.L, ctx.main, ctx.cit
    b = config.BEATS[6]
    top = L.pl_top
    f0, f1 = config.cut_range(6)
    tloc, trot = _tablet_pose(L)
    p1, p2 = tablet_point(L, 1), tablet_point(L, 2)
    screen = (p1 + p2) * 0.5
    for f in _frames(6):
        t = _t(f, 6)
        _seat(ctx)
        # 주인공: 태블릿 쪽으로 몸을 기울이고 오른손 검지로 ① 분납 → ② 복지 영역을 차례로 가리킴
        m.set_rot("torso", 11.0, 0, 6.0)
        rest = m.local_point("hand_R", (0, 0, -m.dims["hand"] * 1.12))
        a0, a1 = b["point_1"]
        reach_w = window(t, a0, a1) * (1.0 - window(t, 0.86, 1.0) * 0.75)
        move = window(t, *b["move_to_2"])
        tip = p1.lerp(p2, move) + Vector((0, 0, 0.02 * bump(t, b["move_to_2"][0], b["move_to_2"][1])))
        tap = 0.012 * (bump(t, a1 - 0.04, a1 + 0.06) + bump(t, b["point_2_hold"][0], b["point_2_hold"][0] + 0.1))
        tip = rest.lerp(tip - Vector((0, 0, tap)), reach_w)
        m.point_finger(window(t, a0 - 0.05, a0 + 0.06) * (1.0 - window(t, 0.88, 0.98)))
        m.reach("R", tip, direction=(tip - m.joint_pos("upper_arm_R") + Vector((0, 0, -0.35))).normalized(),
                elbow_dir=m.to_char_space((-0.6, 0.5, -0.6)), pointing=True)
        glance = bump(t, 0.80, 0.98, hold=0.3)
        m.look_at(screen.lerp(_face(c, c.dims["scale"]), glance))
        # 시민: 자료 쪽으로 몸을 기울여 함께 보고, 두 번째 영역에서 끄덕이며 손을 가볍게 모음
        c.set_rot("torso", 9.0, 0, -5.0)
        c.look_at(screen)
        nod = (bump(t, b["citizen_nod"][0], b["citizen_nod"][0] + 0.11) +
               bump(t, b["citizen_nod"][0] + 0.11, b["citizen_nod"][1])) * 8.0
        c.add_rot("head", nod, 0, 0)
        hands = window(t, *b["citizen_hands"])
        cs = c.dims["scale"]
        clasp = c.root.location + c.to_char_space((0.0, -0.20 * cs, 0.0))
        clasp.z = top + 0.24
        for sd, sgn in (("L", 1.0), ("R", -1.0)):
            rest = c.local_point("hand_" + sd, (0, 0, -c.dims["hand"] * 1.12))
            c.reach(sd, rest.lerp(clasp + c.to_char_space((sgn * 0.035, 0, 0)), hands),
                    direction=c.to_char_space((-sgn * 0.8, -0.3, -0.3)).normalized().lerp(
                        c.to_char_space((-sgn * 0.25, -0.9, -0.35)), 1.0 - hands),
                    elbow_dir=c.to_char_space((sgn * 0.8, 0.3, -0.6)))
        ctx.key_chars(f)
        if f in (f0, f1):
            _key_obj(L.props["tablet"], f, loc=tloc, rot=trot)
            st = tloc + (trot.to_matrix() @ Vector((0, 0.10, 0)))
            st.z = top
            _key_obj(L.props["tablet_stand"], f, loc=st, rot=(0, 0, L.plat_rot_z()))
            cm, cc, pen = L.plat(0.36, -0.40), L.plat(-0.34, -0.42), L.plat(0.20, -0.46)
            for v in (cm, cc, pen):
                v.z = top
            _key_obj(L.props["cup_main"], f, loc=cm, rot=_cup_rot(L))
            _key_obj(L.props["cup_citizen"], f, loc=cc, rot=_cup_rot(L))
            _key_obj(L.props["pen"], f, loc=pen, rot=(0, 0, L.plat_rot_z() + 0.4))
    cameras.camera_cut06(ctx.cams[6], L)


# =============================================================================
# CUT 7 — 배웅 (돌아서 목례 → 시민이 손을 조금 들어 화답 → 계단을 내려감)
# =============================================================================
def setup_cut_07(ctx):
    L, m, c = ctx.L, ctx.main, ctx.cit
    b = config.BEATS[7]
    zu = L.z_up
    f0, f1 = config.cut_range(7)
    n = f1 - f0
    ah = m.dims["ankle_h"]
    c_pos = Vector((-1.00, -0.75, zu))                 # 대문 밖으로 한 걸음 나와 배웅
    body0 = L.stair_point(L.st_len + 0.30, 0.0)        # 계단 맨 윗단 바로 위
    to_cit = (c_pos - body0)
    to_cit.z = 0.0
    h0 = yaw_facing(to_cit.normalized())
    h1 = yaw_facing(-L.st_dir)
    dh = (h1 - h0) % (2.0 * math.pi)                   # 시민 쪽 → 계단 아래쪽으로 도는 각도
    if dh > math.pi:
        dh -= 2.0 * math.pi

    def foot_at(yaw, side, center=body0):
        fwd = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
        left = rot2(fwd, 90.0)
        p = center + left * (0.095 if side == "L" else -0.095)
        p.z = zu + ah
        return p

    kw = dict(ground=L.surface_height, ankle_h=ah, foot=(0.06 * m.dims["scale"], 0.20 * m.dims["scale"]))
    feet = {"L": FootTrack(foot_at(h0, "L"), h0, **kw), "R": FootTrack(foot_at(h0, "R"), h0, **kw)}
    tr0 = f0 + int(n * b["turn"][0])
    tr1 = f0 + int(n * b["turn"][1])
    third = max(2, (tr1 - tr0) // 3)
    hm = h0 + dh * 0.5
    feet["R"].move(tr0, tr0 + third + 1, foot_at(hm, "R"), yaw1=hm, lift=0.05)
    feet["L"].move(tr0 + third, tr0 + 2 * third + 1, foot_at(h0 + dh, "L"), yaw1=h0 + dh, lift=0.05)
    feet["R"].move(tr0 + 2 * third, tr1, foot_at(h0 + dh, "R"), yaw1=h0 + dh, lift=0.05)
    # 계단 내려가기: 첫 걸음(오른발)은 윗골목 → 한 칸 아래, 그 뒤로는 각 발이 두 칸씩
    F = config.DESCEND_FRAMES_PER_STEP
    sw = max(2, round(F * 0.72))
    fd = f0 + int(n * b["descend_start"])
    tread = {"R": L.st_n - 1, "L": L.st_n - 1}
    side, drop, fl = "R", 1, fd
    while fl < f1 + F:
        tread[side] -= drop
        u = (tread[side] + 1) * L.st_run - 0.125         # 발끝이 디딤판 모서리에 오도록 (뒤꿈치 여유 6cm)
        v = -0.095 if side == "L" else 0.095           # 내려가는 방향을 보면 캐릭터 왼쪽 = 계단 오른쪽
        feet[side].move(fl, fl + sw, L.stair_point(u, v, dz=ah), yaw1=h0 + dh, lift=0.06, mode="down")
        side, drop, fl = ("L" if side == "R" else "R"), 2, fl + F
    u_start = L.st_len + 0.30

    def body(f):
        if f < tr0:
            return body0, h0
        if f < fd:
            return body0, h0 + dh * smootherstep((f - tr0) / max(1, tr1 - tr0))
        return L.stair_point(u_start - (f - fd) * L.st_run / F, 0.0), h0 + dh

    c.stand(c_pos, -to_cit)
    face_c = _face(c, c.dims["scale"])

    def extra(p, f):
        t = (f - f0) / max(1, n)
        bow = bump(t, *b["bow"], hold=0.3)
        p.set_rot("torso", 2.0 + bow * config.BOW_ANGLE * 0.4 + 3.0 * window(t, b["descend_start"], 1.0), 0, 0)
        if f < tr0 + 3:
            p.look_at(face_c, extra_pitch=bow * config.BOW_ANGLE * 0.6)
        else:
            p.look_at(L.stair_point(max(0.0, L.st_len - 2.4), 0.0), weight=0.85)

    bake_locomotion(m, _frames(7), feet, body, extra_fn=extra, lean=2.0, arm_amp=8.0)
    for f in _frames(7):
        t = _t(f, 7)
        c.stand(c_pos, -to_cit)
        wave = bump(t, *b["wave"], hold=0.45)
        rest = c.local_point("hand_R", (0, 0, -c.dims["hand"] * 1.12))
        raise_pt = c.local_point("torso", (-0.23, -0.20, 0.50 + 0.015 * math.sin(f * 0.45)))
        c.reach("R", rest.lerp(raise_pt, wave), direction=c.to_char_space((0.05, -0.25, 1.0)).lerp(
            c.to_char_space((0.2, -0.3, -0.9)), 1.0 - wave), elbow_dir=c.to_char_space((-0.9, 0.2, -0.4)))
        c.set_rot("torso", 2.0 * wave, 0, 0)
        c.look_at(_cut7_main_head(m, f))
        c.add_rot("head", 5.0 * wave, 0, 0)
        c.key(f)
        if f in (f0, f1):
            _gate(ctx, f, config.GATE_OPEN_FULL)

    # 카메라: 시민 오른쪽 어깨 뒤 눈높이 → crane-up. 끝 구도는 '작아진 주인공 + 골목 + 등대'
    cc = config.CAM_CUT07
    fwd = (body0 - c_pos)
    fwd.z = 0.0
    fwd.normalize()
    right = rot2(fwd, -90.0)
    cam0 = c_pos - fwd * cc["over_shoulder"][0] + right * cc["over_shoulder"][1]
    cam0.z = zu + cc["height"]
    start_t = body0 + Vector((0, 0, 1.05)) + rot2(fwd, 90.0) * 0.35
    end_main = _cut7_main_head(m, f1) - Vector((0, 0, 0.5))
    lx, ly = config.LIGHTHOUSE_XY
    lh = Vector((lx, ly, config.LIGHTHOUSE_BASE_Z + config.LIGHTHOUSE_HEIGHT * 0.45))
    cam1 = cam0 + heading_vec(cc["back_heading"]) * cc["back"] + Vector((0, 0, cc["rise"]))
    d_main = (end_main - cam1).normalized()
    d_lh = (lh - cam1).normalized()
    end_t = cam1 + (d_main * 0.45 + d_lh * 0.55).normalized() * 10.0
    cameras.camera_cut07(ctx.cams[7], L, cam0, cam1, start_t, end_t)


def _cut7_main_head(m, f):
    """이미 구운 주인공 애니메이션에서 f 프레임의 머리 위치를 읽음."""
    ad = m.root.animation_data
    loc = Vector([ad.action.fcurves.find("location", index=i).evaluate(f) for i in range(3)])
    return loc + Vector((0, 0, m.dims["hip_z"] + 0.55))


# =============================================================================
# CUT 8 — 집집마다 불이 켜진다 (원경. 점 크기 보행자, 창문 불빛 하나씩)
# =============================================================================
def setup_cut_08(ctx):
    L, m, c = ctx.L, ctx.main, ctx.cit
    f0, f1 = config.cut_range(8)
    if config.CUT08_TINY_WALKER:
        start = L.stair_point(-1.2, 0.0)
        F = config.FLAT_WALK_FRAMES_PER_STEP
        feet, body = flat_walk(m, (start.x - 0.3, start.y - 1.0, L.z_low), 188.0, f0 - 3, (f1 - f0) // F + 3, F,
                               config.FLAT_WALK_STEP_LENGTH)
        bake_locomotion(m, _frames(8), feet, body, lean=2.0, arm_amp=14.0)
    else:
        for f in (f0, f1):
            m.stand(ctx.house_spot + Vector((0.8, 0, 0)), Vector((-1, 0, 0)))
            m.key(f)
    for f in (f0, f1):
        _hide_citizen(ctx)
        c.key(f)
        _gate(ctx, f, 0.0)
    # 창문: 몇 개만 켜진 채 시작 → 하나씩 늘어남 → 마지막 1.5초는 그대로
    lights = L.window_lights
    n0 = min(config.WINDOW_LIGHTS_AT_START, len(lights))
    last_on = f1 - int(config.FPS * 1.6)
    for i, ob in enumerate(lights):
        key_visible(ob, config.FRAME_START, False)
        if i < n0:
            key_visible(ob, f0, True)
        else:
            k = (i - n0 + 1) / max(1, len(lights) - n0)
            on = int(f0 + 10 + (last_on - f0 - 10) * (k ** 0.9))
            key_visible(ob, on, True)
    cameras.camera_cut08(ctx.cams[8], L)


# =============================================================================
# 컷 공통 소품 상태 (보이기/숨기기, 대문 등)
# =============================================================================
def setup_prop_states(ctx):
    L, m = ctx.L, ctx.main
    cuts = {n: config.cut_range(n) for n in range(1, 9)}
    file_ob = m.props.get("file")
    for n, (f0, f1) in cuts.items():
        seated = n in (4, 5, 6)
        if file_ob is not None:
            key_visible(file_ob, f0, not seated)
        key_visible(L.props["plat_file"], f0, seated)
        for name in ("tablet", "tablet_stand", "pen"):
            key_visible(L.props[name], f0, n == 6)
    pf = L.plat(0.40, -0.44)
    pf.z = L.pl_top
    _key_obj(L.props["plat_file"], config.FRAME_START, loc=pf, rot=(0, 0, L.plat_rot_z() + 0.25))
    # 빨래는 잔잔하게 흔들림 (F-Curve 노이즈 모디파이어)
    for ob in L.props.get("laundry", []):
        _add_sway(ob, strength=0.12, scale=18.0, axis=1)


def _add_sway(ob, strength, scale, axis):
    ob.keyframe_insert("rotation_euler", frame=config.FRAME_START, index=axis)
    fc = ob.animation_data.action.fcurves.find("rotation_euler", index=axis)
    mod = fc.modifiers.new('NOISE')
    mod.strength = strength
    mod.scale = scale
    mod.phase = sum(map(ord, ob.name)) % 97        # 실행할 때마다 같은 흔들림
