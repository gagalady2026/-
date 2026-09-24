"""
cameras.py — 컷별 카메라 8대 (CAM_CUT01 ~ CAM_CUT08)

각 카메라는 자기 컷 구간에서만 프레임마다 위치·방향(·렌즈)을 키로 굽습니다(bake).
이동은 utils.ease_profile(가속/등속/감속) 로 만들고, 수치는 config.CAM_CUTxx 에 있습니다.

컷별 이동감 (서로 겹치지 않게)
  1 Low forward tracking   2 Left→right surface tracking   3 Short oblique push-in   4 Dolly-out
  5 Slow lateral slide(등속) 6 Nearly static(미세 드리프트)   7 Crane-up               8 Dolly-out+rise+감속
"""
import math

import bpy
from mathutils import Vector

import config
from utils import ease_profile, get_collection, heading_vec, rot2, vlerp

CAM_NAMES = {n: "CAM_CUT%02d" % n for n in range(1, 9)}


def create_cut_cameras(parent):
    col = get_collection("CAMERAS", parent)
    cams = {}
    for n in range(1, 9):
        data = bpy.data.cameras.new(CAM_NAMES[n])
        data.sensor_fit = 'HORIZONTAL'
        data.sensor_width = config.SENSOR_WIDTH
        data.clip_start = 0.03
        data.clip_end = 4000.0
        data.show_composition_thirds = True   # 뷰포트 카메라 뷰에 3분할선 (CUT8 상단 1/3 자막 여백 확인용)
        data.passepartout_alpha = 0.9
        ob = bpy.data.objects.new(CAM_NAMES[n], data)
        col.objects.link(ob)
        cams[n] = ob
    return cams


def bake_camera(cam, f0, f1, pos_fn, target_fn, lens_fn):
    """f0~f1 을 0~1 로 두고 매 프레임 위치·회전·렌즈를 키."""
    prev = None
    for f in range(f0, f1 + 1):
        t = (f - f0) / max(1, f1 - f0)
        p = Vector(pos_fn(t))
        q = (Vector(target_fn(t)) - p).to_track_quat('-Z', 'Y')
        e = q.to_euler('XYZ', prev) if prev is not None else q.to_euler('XYZ')
        prev = e
        cam.location = p
        cam.rotation_euler = e
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
        cam.data.lens = lens_fn(t)
        cam.data.keyframe_insert("lens", frame=f)
    for idb in (cam, cam.data):
        for fc in idb.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


# -----------------------------------------------------------------------------
# 컷별 카메라
# -----------------------------------------------------------------------------
def camera_cut01(cam, L):
    """골목 아래 무릎 높이, 24mm. 천천히 출발 → 중반부터 등속으로 낮게 전진, 왼쪽 전경 화분·빨래를 스침."""
    c = config.CAM_CUT01
    f0, f1 = config.cut_range(1)
    start = Vector((c["start_xy"][0], c["start_xy"][1], L.z_low + c["height"]))
    fwd = heading_vec(c["heading"])
    pitch = math.radians(c["pitch"])
    look = Vector((fwd.x * math.cos(pitch), fwd.y * math.cos(pitch), math.sin(pitch)))

    def pos(t):
        return start + fwd * (c["move_dist"] * ease_profile(t, c["ease_in"], c["ease_out"]))
    bake_camera(cam, f0, f1, pos, lambda t: pos(t) + look * 10.0, lambda t: c["lens"])


def camera_cut02(cam, L):
    """허리 높이, 담장에 붙어 85mm. 담장·화분을 스치며 왼→오른쪽으로 트랙, 대문에 가까워지며 감속."""
    c = config.CAM_CUT02
    f0, f1 = config.cut_range(2)
    zu = L.z_up
    a = Vector((c["start_xy"][0], c["start_xy"][1], zu + c["height"]))
    b = Vector((c["end_xy"][0], c["end_xy"][1], zu + c["height"]))
    tgt = Vector(c["target"]) + Vector((0, 0, zu))
    bake_camera(cam, f0, f1, lambda t: a.lerp(b, ease_profile(t, c["ease_in"], c["ease_out"])),
                lambda t: tgt, lambda t: c["lens"])


def camera_cut03(cam, L):
    """주인공 어깨 뒤 눈높이 150cm, 50mm. 시민 쪽으로 짧게 비스듬히 push-in, 문이 다 열릴 즈음 멈춤."""
    c = config.CAM_CUT03
    f0, f1 = config.cut_range(3)
    zu = L.z_up
    a = Vector((c["start_xy"][0], c["start_xy"][1], zu + c["height"]))
    tgt = Vector(c["target"]) + Vector((0, 0, zu))
    d = tgt - a
    d.z = 0.0
    d = rot2(d.normalized(), c["move_angle"])
    b = a + d * c["move_dist"]
    stop = c["stop_at"]

    def pos(t):
        return a.lerp(b, ease_profile(min(1.0, t / stop), c["ease_in"], c["ease_out"]))
    bake_camera(cam, f0, f1, pos, lambda t: tgt, lambda t: c["lens"])


def camera_cut04(cam, L):
    """마당 모퉁이 가슴 높이, 28mm. 전경 그물에서 천천히 뒤로 빠지는 dolly-out."""
    c = config.CAM_CUT04
    f0, f1 = config.cut_range(4)
    zu = L.z_up
    a = Vector((c["start_xy"][0], c["start_xy"][1], zu + c["height"]))
    b = Vector((c["end_xy"][0], c["end_xy"][1], zu + c["height"]))
    tgt = L.plat(*c["target_local"])
    bake_camera(cam, f0, f1, lambda t: a.lerp(b, ease_profile(t, c["ease_in"], c["ease_out"])),
                lambda t: tgt, lambda t: c["lens"])


def camera_cut05(cam, L):
    """앉은 눈높이, 70mm. 오른쪽→왼쪽 아주 느린 등속 측면 이동 (8컷 중 가장 느림)."""
    c = config.CAM_CUT05
    f0, f1 = config.cut_range(5)
    a = L.plat(c["pos_local"][0], c["pos_local"][1], c["height"])
    tgt = L.plat(*c["target_local"])
    view = (tgt - a)
    view.z = 0.0
    left = rot2(view.normalized(), 90.0)
    b = a + left * c["move_dist"]
    bake_camera(cam, f0, f1, lambda t: a.lerp(b, ease_profile(t, c["ease_in"], c["ease_out"])),
                lambda t: tgt + left * (c["move_dist"] * 0.35 * t), lambda t: c["lens"])


def camera_cut06(cam, L):
    """앉은 눈높이보다 약간 높은 시선, 55mm. 두 사람을 함께 담는 3/4 미디엄샷, 거의 정적."""
    c = config.CAM_CUT06
    f0, f1 = config.cut_range(6)
    a = L.plat(c["pos_local"][0], c["pos_local"][1], c["height"])
    tgt = L.plat(*c["target_local"])
    dx, dy, dz = c["drift"]
    b = L.plat(c["pos_local"][0] + dx, c["pos_local"][1] + dy, c["height"] + dz)
    bake_camera(cam, f0, f1, lambda t: a.lerp(b, ease_profile(t, c["ease_in"], c["ease_out"])),
                lambda t: tgt, lambda t: c["lens"])


def camera_cut07(cam, L, cam0, cam1, start_target, end_target):
    """시민 옆 눈높이에서 시작해 부드럽게 솟아오르는 crane-up. 50mm → 약간 광각, 골목·등대가 열림."""
    c = config.CAM_CUT07
    f0, f1 = config.cut_range(7)

    def pos(t):
        return cam0.lerp(cam1, ease_profile(t, c["ease_in"], c["ease_out"]))

    def tgt(t):
        return vlerp(start_target, end_target, ease_profile(t, c["ease_in"] * 0.8, c["ease_out"]))

    def lens(t):
        return c["lens_start"] + (c["lens_end"] - c["lens_start"]) * ease_profile(t, c["ease_in"], c["ease_out"])
    bake_camera(cam, f0, f1, pos, tgt, lens)


def camera_cut08(cam, L):
    """마을 위 낮은 고도 광각. 뒤로 빠지며 살짝 상승, 마지막 약 1.5초 감속해 엔딩 구도에 안착."""
    c = config.CAM_CUT08
    f0, f1 = config.cut_range(8)
    a = Vector(c["start"])
    tgt = Vector(c["target"])
    back = a - tgt
    back.z = 0.0
    back.normalize()
    b = a + back * c["move_back"] + Vector((0, 0, c["rise"]))
    dur = (f1 - f0 + 1) / config.FPS
    decel = min(0.6, c["decel_sec"] / dur)
    bake_camera(cam, f0, f1, lambda t: a.lerp(b, ease_profile(t, c["ease_in"], decel)),
                lambda t: tgt, lambda t: c["lens"])


# -----------------------------------------------------------------------------
# 구도 점검 (콘솔 리포트)
#  · 컷마다 시작·중간·끝·'이미지용 한 순간' 프레임에서 인물 부위(머리·몸통·손·발)가
#    화면 안에 있는지, 세트에 가려지지 않았는지 레이캐스트로 확인
# -----------------------------------------------------------------------------
_BODY = ("head", "torso", "pelvis", "hand_L", "hand_R", "foot_L", "foot_R")
_ON_STAGE = {"MAIN_": (1, 2, 3, 4, 5, 6, 7), "CITIZEN_": (3, 4, 5, 6, 7)}   # 컷별 등장 인물


def _body_visibility(scene, dg, cam, prefix):
    from bpy_extras.object_utils import world_to_camera_view
    origin = cam.matrix_world.translation
    in_frame, visible, blocker = 0, 0, None
    for part in _BODY:
        ob = bpy.data.objects.get(prefix + part)
        if ob is None:
            continue
        p = ob.matrix_world.translation
        v = world_to_camera_view(scene, cam, p)
        if not (v.z > 0 and 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0):
            continue
        in_frame += 1
        d = p - origin
        hit, _loc, _n, _i, hob, _m = scene.ray_cast(dg, origin, d.normalized(), distance=max(0.0, d.length - 0.03))
        if hit and hob is not None and not hob.name.startswith(("MAIN_", "CITIZEN_")):
            blocker = hob.name
        else:
            visible += 1
    return in_frame, visible, blocker


def report_framing(scene, frames):
    from bpy_extras.object_utils import world_to_camera_view
    warnings = []
    print(" 구도 점검 (머리 x,y = 화면 좌하단 0 ~ 우상단 1 / 부위 = 화면 안에서 가려지지 않은 머리·몸통·손·발 수)")
    for n, f_still in sorted(frames.items()):
        if n == 8:
            print("  CUT_08 F%03d  CAM_CUT08  | 원경(인물 없음 또는 점 크기)" % f_still)
            continue
        f0, f1 = config.cut_range(n)
        checks = sorted({(f0 + f1) // 2, f1, f_still})       # 첫 프레임은 제외 (CUT3 은 문이 열리기 전)
        cols = []
        for label, prefix in (("주인공", "MAIN_"), ("시민", "CITIZEN_")):
            if n not in _ON_STAGE[prefix]:
                continue
            worst = None
            for f in checks:
                scene.frame_set(f)
                dg = bpy.context.evaluated_depsgraph_get()
                inf, vis, blk = _body_visibility(scene, dg, scene.camera, prefix)
                if inf and (worst is None or vis / inf < worst[1] / max(1, worst[0])):
                    worst = (inf, vis, blk, f)
            if worst is None:
                cols.append("%s 화면 밖" % label)
                continue
            scene.frame_set(f_still)
            face = bpy.data.objects[prefix + "head"].matrix_world @ Vector((0.0, -0.03, 0.19))
            head = world_to_camera_view(scene, scene.camera, face)
            inf, vis, blk, fw = worst
            state = "%d/%d" % (vis, inf) + ("" if vis == inf else " (F%d, %s)" % (fw, blk))
            cols.append("%s 머리(%.2f,%.2f) 부위 %s" % (label, head.x, head.y, state))
            if vis < 0.6 * inf:
                warnings.append("CUT_%02d F%d %s 가 %s 에 많이 가려짐 (%d/%d)" % (n, fw, label, blk, vis, inf))
        print("  CUT_%02d F%03d  CAM_CUT%02d | %s" % (n, f_still, n, "  |  ".join(cols)))
    for w in warnings:
        print("  [경고]", w)
    return warnings
