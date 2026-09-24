"""
timeline.py — 씬 시간 설정, 컷 마커(카메라 전환), 컷별 시간대 조명, 컷 경계 정리

- 마커 CUT_01 ~ CUT_08 을 각 컷 시작 프레임에 만들고 카메라를 묶어 둡니다.
  → 타임라인 재생·렌더 시 마커 위치에서 CAM_CUT01~08 로 자동 전환.
- 조명: 태양(Sun) 1개 + 월드(지평선/천정 2색). 컷 시작마다 값이 바뀌고 시간은 되돌아가지 않습니다.
"""
import math

import bpy
from mathutils import Vector

import config
from utils import get_collection, hex_rgb, iter_fcurves


def validate_cuts():
    """컷 표가 1~720 을 빈틈·겹침 없이 채우는지 확인."""
    prev_end = config.FRAME_START - 1
    for n, f0, f1, _title in config.CUTS:
        if f0 != prev_end + 1:
            raise ValueError("CUT_%02d 시작(%d)이 앞 컷 끝(%d) 바로 다음이 아닙니다." % (n, f0, prev_end))
        if f1 < f0:
            raise ValueError("CUT_%02d 끝 프레임이 시작보다 앞섭니다." % n)
        prev_end = f1
    if prev_end != config.FRAME_END:
        raise ValueError("마지막 컷 끝(%d)이 FRAME_END(%d)와 다릅니다." % (prev_end, config.FRAME_END))
    total_sec = (config.FRAME_END - config.FRAME_START + 1) / config.FPS
    if total_sec > 30.0 + 1e-6:
        raise ValueError("전체 길이 %.2f초 > 30초" % total_sec)
    return total_sec


def setup_scene_timing(scene):
    r = scene.render
    r.fps = config.FPS
    r.fps_base = 1.0
    r.resolution_x = config.RESOLUTION_X
    r.resolution_y = config.RESOLUTION_Y
    r.resolution_percentage = 100
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    scene.frame_start = config.FRAME_START
    scene.frame_end = config.FRAME_END
    scene.frame_current = config.FRAME_START
    if hasattr(scene, "sync_mode"):
        scene.sync_mode = 'AUDIO_SYNC'      # 뷰포트 재생을 실제 24fps 시간에 맞춤 (느리면 프레임 드롭)


def setup_timeline_markers(scene, cams):
    scene.timeline_markers.clear()
    for n, f0, _f1, _title in config.CUTS:
        mk = scene.timeline_markers.new("CUT_%02d" % n, frame=f0)
        mk.camera = cams[n]
    scene.camera = cams[1]


# -----------------------------------------------------------------------------
# 조명
# -----------------------------------------------------------------------------
def _sun_rotation(elev_deg, azim_deg):
    e, a = math.radians(elev_deg), math.radians(azim_deg)
    to_sun = Vector((math.cos(e) * math.sin(a), math.cos(e) * math.cos(a), math.sin(e)))
    return (-to_sun).to_track_quat('-Z', 'Y').to_euler('XYZ')


def _build_world(scene):
    world = scene.world
    if world is None:
        world = bpy.data.worlds.new("WORLD_시간대")
        scene.world = world
    world.name = "WORLD_시간대"
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    rng = nt.nodes.new("ShaderNodeMapRange")
    rng.inputs["From Min"].default_value = -0.02
    rng.inputs["From Max"].default_value = 0.55
    bg_h = nt.nodes.new("ShaderNodeBackground")
    bg_h.name = "SKY_HORIZON"
    bg_z = nt.nodes.new("ShaderNodeBackground")
    bg_z.name = "SKY_ZENITH"
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], rng.inputs["Value"])
    nt.links.new(rng.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(bg_h.outputs[0], mix.inputs[1])
    nt.links.new(bg_z.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return world, bg_h, bg_z


def _preset_for_cut(n):
    for name, p in config.LIGHTING.items():
        if n in p["cuts"]:
            return p
    raise KeyError("LIGHTING 에 CUT %d 설정이 없습니다." % n)


# 컷별 태양 그림자 범위(m): 근접 컷은 좁게(선명), 원경 컷은 넓게
SHADOW_DISTANCE = {1: 70.0, 2: 15.0, 3: 20.0, 4: 25.0, 5: 12.0, 6: 12.0, 7: 180.0, 8: 700.0}


def setup_lighting(scene, parent):
    col = get_collection("LIGHTS", parent)
    sun_data = bpy.data.lights.new("SUN_시간대", 'SUN')
    sun_data.angle = math.radians(2.0)
    if hasattr(sun_data, "shadow_cascade_count"):
        sun_data.shadow_cascade_count = 4
    sun = bpy.data.objects.new("SUN_시간대", sun_data)
    col.objects.link(sun)
    world, bg_h, bg_z = _build_world(scene)

    def apply(p, f, end=False):
        elev = p["sun_elev"]
        strength = p.get("end_sun_strength", p["sun_strength"]) if end else p["sun_strength"]
        sky = p.get("end_sky", p["sky"]) if end else p["sky"]
        sun.rotation_euler = _sun_rotation(elev - (1.5 if end and "end_sky" in p else 0.0), config.SUN_AZIMUTH)
        sun.keyframe_insert("rotation_euler", frame=f)
        sun_data.color = hex_rgb(p["sun_color"])
        sun_data.energy = strength
        sun_data.keyframe_insert("color", frame=f)
        sun_data.keyframe_insert("energy", frame=f)
        hz, zn, sk = hex_rgb(sky[0]), hex_rgb(sky[1]), sky[2]
        bg_h.inputs["Color"].default_value = (*hz, 1.0)
        bg_z.inputs["Color"].default_value = (*zn, 1.0)
        bg_h.inputs["Strength"].default_value = sk
        bg_z.inputs["Strength"].default_value = sk
        for node in (bg_h, bg_z):
            node.inputs["Color"].keyframe_insert("default_value", frame=f)
            node.inputs["Strength"].keyframe_insert("default_value", frame=f)
        world.color = [c * 0.9 + 0.1 for c in hz]        # Workbench 배경색
        world.keyframe_insert("color", frame=f)

    for n, f0, f1, _title in config.CUTS:
        p = _preset_for_cut(n)
        apply(p, f0)
        apply(p, f1, end=True)
        if hasattr(sun_data, "shadow_cascade_max_distance"):
            for f in (f0, f1):
                sun_data.shadow_cascade_max_distance = SHADOW_DISTANCE.get(n, 100.0)
                sun_data.keyframe_insert("shadow_cascade_max_distance", frame=f)
    return sun, world


# -----------------------------------------------------------------------------
# 컷 경계 정리: 컷 끝 프레임 키는 CONSTANT → 다음 컷 첫 프레임에서 정확히 바뀜
# -----------------------------------------------------------------------------
def _all_animated_ids():
    ids = list(bpy.data.objects) + list(bpy.data.lights) + list(bpy.data.cameras) + list(bpy.data.worlds)
    for w in bpy.data.worlds:
        if w.node_tree is not None:
            ids.append(w.node_tree)
    return ids


def finalize_cut_boundaries():
    starts = {f0 for (_n, f0, _f1, _t) in config.CUTS if f0 > config.FRAME_START}
    for id_data in _all_animated_ids():
        for fc in iter_fcurves(id_data):
            kps = fc.keyframe_points
            for i in range(len(kps) - 1):
                a, b = kps[i], kps[i + 1]
                if int(round(b.co.x)) in starts and b.co.x - a.co.x <= 1.01:
                    a.interpolation = 'CONSTANT'
                    a.handle_left_type = 'VECTOR'
                    b.handle_left_type = 'VECTOR'
                    b.handle_right_type = 'VECTOR'
            fc.update()


def camera_at(scene, frame):
    """마커 규칙대로 해당 프레임의 활성 카메라 이름 (검증용)."""
    cam = None
    for mk in sorted(scene.timeline_markers, key=lambda m: m.frame):
        if mk.frame <= frame and mk.camera is not None:
            cam = mk.camera
    return cam.name if cam else None


def verify_timeline(scene, verbose=True):
    """완료 기준 자동 점검: 1~720 프레임, 24fps, 마커 8개 위치, 프레임별 카메라 전환."""
    problems = []
    if (scene.frame_start, scene.frame_end) != (config.FRAME_START, config.FRAME_END):
        problems.append("프레임 범위 %d~%d" % (scene.frame_start, scene.frame_end))
    if scene.render.fps != config.FPS or abs(scene.render.fps_base - 1.0) > 1e-6:
        problems.append("fps %s/%s" % (scene.render.fps, scene.render.fps_base))
    marks = {m.name: m for m in scene.timeline_markers}
    for n, f0, f1, title in config.CUTS:
        mk = marks.get("CUT_%02d" % n)
        cam_name = "CAM_CUT%02d" % n
        if mk is None or mk.frame != f0 or mk.camera is None or mk.camera.name != cam_name:
            problems.append("마커 CUT_%02d 오류" % n)
        for f in range(f0, f1 + 1):
            if camera_at(scene, f) != cam_name:
                problems.append("F%d 카메라 %s (기대 %s)" % (f, camera_at(scene, f), cam_name))
                break
    if verbose:
        print("-" * 64)
        print(" 컷     시간(초)        프레임        길이   카메라      제목")
        for n, f0, f1, title in config.CUTS:
            print(" CUT_%02d %5.2f~%5.2f   F%03d~F%03d   %.1f초  CAM_CUT%02d  %s"
                  % (n, (f0 - 1) / config.FPS, f1 / config.FPS, f0, f1, (f1 - f0 + 1) / config.FPS, n, title))
        print(" 전체 %d프레임 = %.2f초 @%dfps  ·  점검: %s" % (
            config.FRAME_END - config.FRAME_START + 1, (config.FRAME_END - config.FRAME_START + 1) / config.FPS,
            config.FPS, "통과" if not problems else "문제 %d건 %s" % (len(problems), problems[:3])))
        print("-" * 64)
    return problems
