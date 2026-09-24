"""
characters.py — 주인공 / 시민 프록시 캐릭터 ("퍼펫" 리그)

뼈대(Armature) 대신 '관절 = 부위 메시의 원점'인 계층형 오브젝트로 만들었습니다.
  ROOT(빈 오브젝트) → pelvis → torso → head / upper_arm → forearm → hand
                              → thigh → shin → foot
- 각 부위는 원점이 관절에 있으므로 Blender 에서 부위를 선택해 회전하면 바로 포즈가 됩니다.
- 로컬 축(모든 부위 공통, 차렷 자세 기준): 정면 = -Y, 캐릭터 왼쪽 = +X, 위 = +Z
    몸통/고개 X+ 회전 = 앞으로 숙임(목례·끄덕임), 고개 Z+ = 왼쪽으로 돌림
    팔/다리 X- 회전 = 앞으로 들어 올림, 팔꿈치/무릎은 IK 로 계산
- 얼굴·손가락은 만들지 않습니다(프리비즈). 대신 시선 방향을 읽을 수 있게 점 눈 두 개만 둡니다.

주인공 실루엣 기준(캐릭터 시트): 둥근 버섯 머리 + 정수리 한 가닥, 차콜 반팔 폴로(흰 단추 2개),
아이보리 와이드 팬츠, 흰 양말+빨간 선, 검정 로퍼, 네이비 명찰 줄 + 흰 가로 명찰(청록 띠),
오른쪽 어깨 → 왼쪽 엉덩이로 메는 짙은 회색 크로스백, 왼쪽 허리 옆 연하늘 A4 클리어파일.
"""
import math

import bmesh
from mathutils import Euler, Matrix, Vector

import config
import materials as M
from utils import MeshBuilder, clamp, get_collection, new_empty, yaw_facing

# 1.70m 주인공 기준 뼈대 치수 (m). 캐릭터 시트 턴어라운드(4칸 눈금)에서 측정한 비율.
BASE_DIMS = dict(
    hip_z=0.80,        # 고관절 높이
    hip_w=0.085,       # 고관절 좌우 간격(절반)
    waist=0.08,        # pelvis → torso 피벗
    torso_h=0.375,     # torso 피벗 → 목(머리 피벗)
    shoulder_w=0.195,  # 어깨 관절 좌우(절반)
    shoulder_dz=0.33,  # torso 피벗 → 어깨 관절 높이
    thigh=0.36, shin=0.36, ankle_h=0.08,
    upper_arm=0.25, forearm=0.22, hand=0.09,
)
CHAIN_PARENT = {
    "pelvis": None, "torso": "pelvis", "head": "torso",
    "upper_arm_L": "torso", "forearm_L": "upper_arm_L", "hand_L": "forearm_L",
    "upper_arm_R": "torso", "forearm_R": "upper_arm_R", "hand_R": "forearm_R",
    "thigh_L": "pelvis", "shin_L": "thigh_L", "foot_L": "shin_L",
    "thigh_R": "pelvis", "shin_R": "thigh_R", "foot_R": "shin_R",
    "finger_R": "hand_R",
}
POSED_PARTS = [n for n in CHAIN_PARENT if n != "finger_R"]


def _dims(height, build=1.0):
    s = height / 1.70
    d = {k: v * s for k, v in BASE_DIMS.items()}
    d["hip_w"] *= build
    d["shoulder_w"] *= build
    d["scale"] = s
    d["build"] = build
    return d


# =============================================================================
# Puppet: 포즈 설정 · FK · IK · 키프레임
# =============================================================================
class Puppet:
    def __init__(self, name, root, parts, dims, props=None):
        self.name = name
        self.root = root
        self.parts = parts            # 이름 → 오브젝트
        self.dims = dims
        self.props = props or {}      # 가방, 파일, 명찰 등
        self.rest = {n: Vector(o.location) for n, o in parts.items()}

    # ---------------- 포즈 ----------------
    def reset_pose(self):
        for n in POSED_PARTS:
            self.parts[n].rotation_euler = (0.0, 0.0, 0.0)
        self.point_finger(0.0)

    def set_rot(self, part, x=0.0, y=0.0, z=0.0):
        self.parts[part].rotation_euler = (math.radians(x), math.radians(y), math.radians(z))

    def add_rot(self, part, x=0.0, y=0.0, z=0.0):
        e = self.parts[part].rotation_euler
        self.parts[part].rotation_euler = (e.x + math.radians(x), e.y + math.radians(y), e.z + math.radians(z))

    def place(self, pos, facing=None, yaw=None):
        """루트 위치(발 사이 바닥점)와 방향 지정. facing = 바라볼 월드 수평 방향."""
        self.root.location = Vector(pos)
        if facing is not None:
            self.root.rotation_euler = (0.0, 0.0, yaw_facing(facing))
        elif yaw is not None:
            self.root.rotation_euler = (0.0, 0.0, yaw)

    def facing(self):
        return (self.root.matrix_basis.to_3x3() @ Vector((0, -1, 0))).normalized()

    def point_finger(self, amount):
        f = self.parts.get("finger_R")
        if f is not None:
            f.scale = (1.0, 1.0, max(0.05, amount))

    # ---------------- FK ----------------
    def root_matrix(self):
        r = self.root
        return Matrix.Translation(r.location) @ r.rotation_euler.to_matrix().to_4x4()

    def world_matrix(self, part):
        chain = []
        n = part
        while n is not None:
            chain.append(n)
            n = CHAIN_PARENT[n]
        m = self.root_matrix()
        for n in reversed(chain):
            o = self.parts[n]
            m = m @ Matrix.Translation(self.rest[n]) @ o.rotation_euler.to_matrix().to_4x4()
        return m

    def joint_pos(self, part):
        return self.world_matrix(part).to_translation()

    def local_point(self, part, co):
        """부위 로컬 좌표 co 의 월드 위치."""
        return self.world_matrix(part) @ Vector(co)

    def to_char_space(self, vec):
        """캐릭터(루트) 기준 방향 벡터 → 월드."""
        return self.root.rotation_euler.to_matrix() @ Vector(vec)

    # ---------------- IK (2본 해석해) ----------------
    def ik_chain(self, upper, lower, end, target, pole, end_world_rot=None):
        """upper(허벅지/위팔) → lower(정강이/아래팔) 을 target(발목/손목) 에 닿게.
        pole = 무릎/팔꿈치가 향할 월드 방향. end_world_rot = 발/손의 월드 회전(3x3)."""
        target = Vector(target)
        parent = CHAIN_PARENT[upper]
        m_parent = self.world_matrix(parent)
        s = (m_parent @ Matrix.Translation(self.rest[upper])).to_translation()
        l1 = self.rest[lower].length
        l2 = self.rest[end].length
        dvec = target - s
        dist = clamp(dvec.length, abs(l1 - l2) + 1e-4, l1 + l2 - 1e-4)
        u = dvec.normalized() if dvec.length > 1e-6 else Vector((0, 0, -1))
        a = (l1 * l1 - l2 * l2 + dist * dist) / (2.0 * dist)
        h = math.sqrt(max(l1 * l1 - a * a, 0.0))
        p = Vector(pole) - u * Vector(pole).dot(u)
        if p.length < 1e-6:
            p = u.orthogonal()
        p.normalize()
        elbow = s + u * a + p * h
        tip = s + u * dist

        z1 = -(elbow - s).normalized()
        y1 = -(p - z1 * p.dot(z1)).normalized()
        x1 = y1.cross(z1).normalized()
        y1 = z1.cross(x1)
        r1_w = Matrix((x1, y1, z1)).transposed()
        r_parent = m_parent.to_3x3().normalized()
        prev = self.parts[upper].rotation_euler.copy()
        self.parts[upper].rotation_euler = (r_parent.inverted() @ r1_w).to_euler('XYZ', prev)

        z2 = -(tip - elbow).normalized()
        x2 = x1
        y2 = z2.cross(x2).normalized()
        x2 = y2.cross(z2)
        r2_w = Matrix((x2, y2, z2)).transposed()
        prev = self.parts[lower].rotation_euler.copy()
        self.parts[lower].rotation_euler = (r1_w.inverted() @ r2_w).to_euler('XYZ', prev)

        if end_world_rot is not None:
            prev = self.parts[end].rotation_euler.copy()
            self.parts[end].rotation_euler = (r2_w.inverted() @ end_world_rot).to_euler('XYZ', prev)
        return elbow

    def leg_ik(self, side, ankle, knee_dir=None, foot_yaw=None, foot_pitch=0.0):
        """다리 IK. foot_yaw = 발끝 방향 Z회전(rad, None 이면 루트 방향), foot_pitch = 발끝 들기(+)/내리기(-) 도."""
        if knee_dir is None:
            knee_dir = self.facing() + Vector((0, 0, 0.05))
        yaw = self.root.rotation_euler.z if foot_yaw is None else foot_yaw
        rot = (Matrix.Rotation(yaw, 3, 'Z') @ Matrix.Rotation(math.radians(-foot_pitch), 3, 'X'))
        self.ik_chain("thigh_" + side, "shin_" + side, "foot_" + side, ankle, knee_dir, rot)

    def arm_ik(self, side, wrist, elbow_dir=None, hand_rot=None):
        if elbow_dir is None:
            out = 1.0 if side == "L" else -1.0
            elbow_dir = self.to_char_space((0.55 * out, 0.8, -0.35))
        return self.ik_chain("upper_arm_" + side, "forearm_" + side, "hand_" + side, wrist, elbow_dir, hand_rot)

    def reach(self, side, tip, direction=None, elbow_dir=None, pointing=False):
        """손끝(주먹 끝, pointing=True 면 검지 끝)을 tip 에 두기. direction = 손이 향할 월드 방향."""
        tip = Vector(tip)
        hand_len = self.dims["hand"] * 1.12 + (0.075 * self.dims["scale"] if pointing else 0.0)
        if direction is None:
            shoulder = self.joint_pos("upper_arm_" + side)
            direction = (tip - shoulder).normalized()
        direction = Vector(direction).normalized()
        wrist = tip - direction * hand_len
        # 손(로컬 -Z)이 direction 을 향하는 월드 회전
        z = -direction
        ref = self.to_char_space((1.0 if side == "L" else -1.0, 0, 0))
        x = (ref - z * ref.dot(z))
        if x.length < 1e-6:
            x = z.orthogonal()
        x.normalize()
        y = z.cross(x)
        hand_rot = Matrix((x, y, z)).transposed()
        return self.arm_ik(side, wrist, elbow_dir, hand_rot)

    def look_at(self, target, weight=1.0, extra_pitch=0.0, max_yaw=75.0, max_pitch=40.0):
        """고개를 target 쪽으로 (몸통 기준 yaw/pitch 로 제한)."""
        m_t = self.world_matrix("torso")
        eye = self.local_point("head", (0.0, -0.05, 0.19 * self.dims["scale"]))
        d = m_t.to_3x3().normalized().inverted() @ (Vector(target) - eye)
        yaw = math.degrees(math.atan2(d.x, -d.y))
        pitch = math.degrees(math.atan2(-d.z, math.hypot(d.x, d.y)))
        yaw = clamp(yaw, -max_yaw, max_yaw) * weight
        pitch = clamp(pitch, -max_pitch, max_pitch) * weight + extra_pitch
        self.set_rot("head", pitch, 0.0, yaw)

    # ---------------- 자세 프리셋 ----------------
    def stand(self, pos, facing, arm_out=6.0, elbow=8.0):
        self.reset_pose()
        self.place(pos, facing)
        self.set_rot("upper_arm_L", 0, -arm_out, 0)
        self.set_rot("upper_arm_R", 0, arm_out, 0)
        self.set_rot("forearm_L", -elbow, 0, 0)
        self.set_rot("forearm_R", -elbow, 0, 0)

    def sit_cross_legged(self, seat_pos, facing, seat_height):
        """평상 위 양반다리. seat_pos = 엉덩이 아래 바닥(평상 윗면)의 월드 XY, seat_height = 평상 윗면 높이."""
        self.reset_pose()
        d = self.dims
        z_root = seat_height + 0.07 * d["scale"] - d["hip_z"]
        self.place((seat_pos[0], seat_pos[1], z_root), facing)
        s = d["scale"]
        for side, sx in (("L", 1.0), ("R", -1.0)):
            ankle = self.to_char_space((-sx * 0.10 * s, -0.24 * s, 0.0)) + Vector((seat_pos[0], seat_pos[1], seat_height + 0.06 * s))
            if side == "R":
                ankle += self.to_char_space((0, -0.07 * s, 0.035 * s))
            knee_dir = self.to_char_space((sx * 0.95, -0.35, 0.15))
            foot_yaw = self.root.rotation_euler.z + math.radians(-sx * 70.0)
            self.leg_ik(side, ankle, knee_dir, foot_yaw=foot_yaw, foot_pitch=0.0)
        self.rest_hands_on_knees()

    def rest_hands_on_knees(self):
        s = self.dims["scale"]
        for side, sx in (("L", 1.0), ("R", -1.0)):
            knee = self.joint_pos("shin_" + side)
            tip = knee + self.to_char_space((-sx * 0.06 * s, 0.02 * s, 0.05 * s))
            self.reach(side, tip, direction=self.to_char_space((-sx * 0.25, -0.9, -0.35)),
                       elbow_dir=self.to_char_space((sx * 0.7, 0.4, -0.5)))

    # ---------------- 키프레임 ----------------
    def key(self, frame, parts=None, root=True):
        if root:
            self.root.keyframe_insert("location", frame=frame)
            self.root.keyframe_insert("rotation_euler", frame=frame)
        for n in (parts or POSED_PARTS):
            self.parts[n].keyframe_insert("rotation_euler", frame=frame)
        f = self.parts.get("finger_R")
        if f is not None and (parts is None or "finger_R" in parts or "hand_R" in parts):
            f.keyframe_insert("scale", frame=frame)

    def all_objects(self):
        return [self.root] + list(self.parts.values()) + list(self.props.values())


# =============================================================================
# 부위 메시
# =============================================================================
def _part(name, collection, mats, build_fn, parent, location):
    mb = MeshBuilder()
    build_fn(mb)
    return mb.to_object(name, collection, mats, parent=parent, location=location, smooth=True)


def _build_puppet(prefix, height, build, style, collection):
    d = _dims(height, build)
    s = d["scale"]
    w = build
    is_main = style == "main"
    if is_main:
        skin, hair, top, top2, pants, shoe = "skin", "hair", "polo", "collar", "pants_ivory", "loafer"
    else:
        skin, hair, top, top2, pants, shoe = "cit_skin", "cit_hair", "jumper_olive", "tshirt_grey", "cit_pants", "slipper"

    root = new_empty(prefix + "ROOT", collection, size=0.35 * s, display='CIRCLE')
    root.empty_display_type = 'CIRCLE'
    parts = {}

    # --- pelvis (고관절 중심) ---
    def pelvis(mb):
        mb.box((0.30 * s * w, 0.20 * s * w, 0.17 * s), center=(0, 0.005 * s, 0.02 * s), mat=0)
        if is_main:
            mb.box((0.305 * s * w, 0.205 * s * w, 0.035 * s), center=(0, 0.005 * s, 0.085 * s), mat=1)
    parts["pelvis"] = _part(prefix + "pelvis", collection, [M.get(pants), M.get("belt")], pelvis, root, (0, 0, d["hip_z"]))

    # --- torso (허리 피벗) ---
    def torso(mb):
        th = d["torso_h"]
        mb.frustum((0.30 * s * w, 0.19 * s * w), (0.37 * s * w, 0.21 * s * w), -0.03 * s, th - 0.02 * s, mat=0)
        mb.box((0.17 * s * w, 0.12 * s, 0.05 * s), center=(0, -0.015 * s, th - 0.015 * s), mat=1)   # 칼라 / 라운드티
        if is_main:
            for bz in (0.30, 0.25):  # 흰 단추 두 개
                mb.sphere((0.011 * s, 0.006 * s, 0.011 * s), center=(0, -0.106 * s, bz * s), segments=6, rings=4, mat=2)
            # 네이비 명찰 줄 + 흰 가로 명찰(상단 청록 띠)
            mb.box_between((0.055 * s, -0.098 * s, 0.345 * s), (0.012 * s, -0.117 * s, 0.215 * s), 0.012 * s, 0.004 * s, mat=3)
            mb.box_between((-0.055 * s, -0.098 * s, 0.345 * s), (-0.012 * s, -0.117 * s, 0.215 * s), 0.012 * s, 0.004 * s, mat=3)
            mb.box((0.088 * s, 0.008 * s, 0.058 * s), center=(0, -0.121 * s, 0.184 * s), mat=4)
            mb.box((0.090 * s, 0.009 * s, 0.015 * s), center=(0, -0.122 * s, 0.206 * s), mat=5)
            # 크로스백 끈: 오른쪽 어깨(-X) → 왼쪽 엉덩이(+X), 앞뒤
            mb.box_between((-0.13 * s, -0.10 * s, 0.37 * s), (0.17 * s, -0.112 * s, -0.06 * s), 0.042 * s, 0.012 * s, mat=6)
            mb.box_between((-0.13 * s, 0.10 * s, 0.37 * s), (0.17 * s, 0.108 * s, -0.06 * s), 0.042 * s, 0.012 * s, mat=6)
            mb.box_between((-0.13 * s, -0.10 * s, 0.37 * s), (-0.13 * s, 0.10 * s, 0.37 * s), 0.042 * s, 0.012 * s, mat=6)
        else:
            mb.box((0.10 * s, 0.01 * s, 0.26 * s), center=(0, -0.104 * s, 0.20 * s), mat=1)   # 점퍼 앞섶 사이 회색 티
    torso_mats = [M.get(top), M.get(top2), M.get("button"), M.get("lanyard"), M.get("tag_white"), M.get("tag_teal"), M.get("strap")]
    parts["torso"] = _part(prefix + "torso", collection, torso_mats, torso, parts["pelvis"], (0, 0, d["waist"]))

    # --- head (목 피벗) ---
    def head(mb):
        mb.cylinder(0.045 * s, 0.045 * s, -0.03 * s, 0.07 * s, segments=8, mat=0)
        mb.sphere((0.158 * s, 0.148 * s, 0.158 * s), center=(0, -0.012 * s, 0.182 * s), segments=14, rings=10, mat=0)
        for ex in (1, -1):
            mb.sphere((0.034 * s, 0.022 * s, 0.040 * s), center=(ex * 0.156 * s, 0.01 * s, 0.17 * s), segments=6, rings=4, mat=0)
            mb.sphere((0.016 * s, 0.008 * s, 0.024 * s), center=(ex * 0.056 * s, -0.152 * s, 0.182 * s), segments=6, rings=4, mat=2)
        if is_main:   # 둥근 버섯형 + 이마를 덮는 앞머리
            hv = mb.sphere((0.218 * s, 0.207 * s, 0.190 * s), center=(0, 0.014 * s, 0.262 * s), segments=16, rings=12, mat=1)
            cut = lambda co: co.z < 0.162 * s - 0.37 * co.y
        else:         # 짧은 머리
            hv = mb.sphere((0.170 * s, 0.170 * s, 0.150 * s), center=(0, 0.02 * s, 0.232 * s), segments=14, rings=10, mat=1)
            cut = lambda co: co.z < 0.215 * s - 0.42 * co.y
        bmesh.ops.delete(mb.bm, geom=[v for v in hv if cut(v.co)], context='VERTS')
        if is_main:   # 정수리 삐죽 한 가닥
            m = Matrix.Translation((0.0, 0.03 * s, 0.445 * s)) @ Matrix.Rotation(math.radians(-38), 4, 'X')
            mb.cylinder(0.02 * s, 0.003 * s, 0.0, 0.10 * s, segments=6, mat=1, matrix=m)
    parts["head"] = _part(prefix + "head", collection, [M.get(skin), M.get(hair), M.get("eye")], head, parts["torso"], (0, 0, d["torso_h"]))

    # --- 팔 ---
    arm_top = top
    for side, sx in (("L", 1.0), ("R", -1.0)):
        def upper(mb, long_sleeve=not is_main):
            mb.cylinder(0.063 * s * w, 0.056 * s * w, 0.035 * s, -0.135 * s, segments=10, mat=0)
            if long_sleeve:
                mb.cylinder(0.052 * s * w, 0.048 * s * w, -0.12 * s, -d["upper_arm"] - 0.01 * s, segments=8, mat=0)
            else:
                mb.cylinder(0.041 * s, 0.039 * s, -0.10 * s, -d["upper_arm"] - 0.01 * s, segments=8, mat=1)
        parts["upper_arm_" + side] = _part(prefix + "upper_arm_" + side, collection, [M.get(arm_top), M.get(skin)], upper,
                                           parts["torso"], (sx * d["shoulder_w"], 0, d["shoulder_dz"]))

        def fore(mb, long_sleeve=not is_main):
            if long_sleeve:
                mb.cylinder(0.048 * s * w, 0.043 * s * w, 0.01 * s, -d["forearm"] + 0.03 * s, segments=8, mat=0)
                mb.cylinder(0.036 * s, 0.034 * s, -d["forearm"] + 0.04 * s, -d["forearm"], segments=8, mat=1)
            else:
                mb.cylinder(0.038 * s, 0.034 * s, 0.01 * s, -d["forearm"], segments=8, mat=1)
        parts["forearm_" + side] = _part(prefix + "forearm_" + side, collection, [M.get(arm_top), M.get(skin)], fore,
                                         parts["upper_arm_" + side], (0, 0, -d["upper_arm"]))

        def hand(mb):
            mb.box((0.068 * s, 0.036 * s, d["hand"]), center=(0, 0, -d["hand"] * 0.5), mat=0)
            mb.sphere((0.034 * s, 0.024 * s, 0.03 * s), center=(0, 0, -d["hand"] * 0.95), segments=8, rings=5, mat=0)
        parts["hand_" + side] = _part(prefix + "hand_" + side, collection, [M.get(skin)], hand,
                                      parts["forearm_" + side], (0, 0, -d["forearm"]))

    def finger(mb):   # 오른손 검지 (가리킬 때만 scale.z=1 로 펼침)
        mb.box((0.02 * s, 0.02 * s, 0.075 * s), center=(0, 0, -0.0375 * s), mat=0)
    parts["finger_R"] = _part(prefix + "finger_R", collection, [M.get(skin)], finger, parts["hand_R"],
                              (0, -0.006 * s, -d["hand"] * 1.05))

    # --- 다리 ---
    for side, sx in (("L", 1.0), ("R", -1.0)):
        def thigh(mb):
            mb.cylinder(0.086 * s * w, 0.090 * s * w, 0.03 * s, -d["thigh"] - 0.02 * s, segments=10, mat=0)
        parts["thigh_" + side] = _part(prefix + "thigh_" + side, collection, [M.get(pants)], thigh,
                                       parts["pelvis"], (sx * d["hip_w"], 0, 0))

        def shin(mb):
            if is_main:
                mb.cylinder(0.092 * s, 0.094 * s, 0.01 * s, -d["shin"] + 0.075 * s, segments=10, mat=0)   # 와이드 팬츠
                mb.cylinder(0.042 * s, 0.042 * s, -d["shin"] + 0.08 * s, -d["shin"] + 0.005 * s, segments=8, mat=1)  # 흰 양말
                mb.cylinder(0.0435 * s, 0.0435 * s, -d["shin"] + 0.046 * s, -d["shin"] + 0.036 * s, segments=8, mat=2)  # 빨간 선
            else:
                mb.cylinder(0.078 * s * w, 0.074 * s * w, 0.01 * s, -d["shin"] + 0.05 * s, segments=10, mat=0)
                mb.cylinder(0.04 * s, 0.04 * s, -d["shin"] + 0.06 * s, -d["shin"] + 0.005 * s, segments=8, mat=3)
        parts["shin_" + side] = _part(prefix + "shin_" + side, collection,
                                      [M.get(pants), M.get("sock"), M.get("sock_red"), M.get(skin)], shin,
                                      parts["thigh_" + side], (0, 0, -d["thigh"]))

        def foot(mb):
            if is_main:   # 검정 로퍼
                mb.box((0.10 * s, 0.26 * s, 0.075 * s), center=(0, -0.07 * s, -d["ankle_h"] + 0.0375 * s), mat=0)
            else:         # 슬리퍼
                mb.box((0.105 * s, 0.27 * s, 0.035 * s), center=(0, -0.07 * s, -d["ankle_h"] + 0.0175 * s), mat=0)
                mb.box((0.10 * s, 0.07 * s, 0.03 * s), center=(0, -0.13 * s, -d["ankle_h"] + 0.045 * s), mat=0)
        parts["foot_" + side] = _part(prefix + "foot_" + side, collection, [M.get(shoe)], foot,
                                      parts["shin_" + side], (0, 0, -d["shin"]))

    props = {}
    if is_main:
        mb = MeshBuilder()   # 짙은 회색 크로스백 (왼쪽 엉덩이)
        mb.box((0.075 * s, 0.23 * s, 0.17 * s), mat=0)
        mb.box((0.078 * s, 0.232 * s, 0.05 * s), center=(0, 0, 0.06 * s), mat=0)
        props["bag"] = mb.to_object(prefix + "bag", collection, [M.get("bag")], parent=parts["pelvis"],
                                    location=(0.205 * s, 0.0, -0.05 * s))
        mb = MeshBuilder()   # 연하늘 A4 클리어파일 (가방 바깥쪽에 세워 들고 다님)
        mb.box((0.014 * s, 0.235 * s, 0.31 * s), mat=0)
        props["file"] = mb.to_object(prefix + "file", collection, [M.get("file_blue", roughness=0.35)],
                                     parent=parts["pelvis"], location=(0.258 * s, -0.035 * s, -0.12 * s))
        props["file"].rotation_euler = (0.0, math.radians(-4), math.radians(4))

    puppet = Puppet(prefix.rstrip("_"), root, parts, d, props)
    puppet.reset_pose()
    return puppet


def build_main_character(parent_collection=None):
    col = get_collection("CHAR_MAIN_관리단원", get_collection("CHARACTERS", parent_collection))
    return _build_puppet("MAIN_", config.MAIN_CHAR_HEIGHT, 1.0, "main", col)


def build_citizen_proxy(parent_collection=None):
    col = get_collection("CHAR_CITIZEN_시민", get_collection("CHARACTERS", parent_collection))
    return _build_puppet("CITIZEN_", config.CITIZEN_HEIGHT, config.CITIZEN_BUILD, "citizen", col)
