"""
render_preview.py — 30초 프리뷰 MP4 / 컷별 '이미지용 한 순간' 스틸 출력

사용법 (프로젝트 폴더에서):
  blender -b -P render_preview.py                          # 씬 생성 + Eevee 30초 MP4
  blender -b -P render_preview.py -- --engine workbench    # 가장 빠른 Workbench 프리뷰
  blender -b -P render_preview.py -- --stills              # 컷별 스틸 PNG 8장
  blender -b build/donghae_previs.blend -P render_preview.py   # 저장된 .blend 로 렌더
옵션: --engine eevee|workbench|cycles   --scale 50 (해상도 %)   --frames 241-312   --no-burnin
출력: renders/donghae_previs_30s.mp4 , renders/stills/CUT01_F0046.png ...
Blender UI 에서는 이 파일을 Run Script 하면 현재 씬을 같은 설정으로 렌더합니다.
"""
import glob
import os
import sys

import bpy

_here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
if not os.path.exists(os.path.join(_here, "config.py")):
    for _t in bpy.data.texts:
        if _t.filepath and os.path.basename(_t.filepath) == "render_preview.py":
            _here = os.path.dirname(bpy.path.abspath(_t.filepath))
if _here not in sys.path:
    sys.path.insert(0, _here)

import config  # noqa: E402


def _set_engine(scene, engine):
    engine = (engine or config.PREVIEW_ENGINE).upper()
    if engine == "EEVEE":
        for ident in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):   # 4.0 = BLENDER_EEVEE, 4.2+ = _NEXT
            try:
                scene.render.engine = ident
                break
            except TypeError:
                continue
    elif engine == "WORKBENCH":
        scene.render.engine = 'BLENDER_WORKBENCH'
    elif engine == "CYCLES":
        scene.render.engine = 'CYCLES'
    else:
        raise ValueError("알 수 없는 엔진: %s" % engine)
    return scene.render.engine


def _setattr_safe(obj, name, value):
    if hasattr(obj, name):
        try:
            setattr(obj, name, value)
        except (TypeError, AttributeError, ValueError):
            pass


def configure_preview_render(scene, engine=None, scale=100, burn_in=None):
    """빠른 프리뷰용 렌더 설정 (1280×720, 24fps, H.264 MP4)."""
    eng = _set_engine(scene, engine)
    r = scene.render
    r.resolution_x, r.resolution_y = config.RESOLUTION_X, config.RESOLUTION_Y
    r.resolution_percentage = int(scale)
    r.fps, r.fps_base = config.FPS, 1.0
    r.use_motion_blur = False
    _setattr_safe(r, "film_transparent", False)
    # 색: 팔레트가 그대로 보이도록 Standard
    try:
        scene.view_settings.view_transform = 'Standard'
        scene.view_settings.look = 'None'
    except TypeError:
        pass
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    if eng.startswith("BLENDER_EEVEE"):
        ee = scene.eevee
        _setattr_safe(ee, "taa_render_samples", config.EEVEE_SAMPLES)
        _setattr_safe(ee, "taa_samples", 4)
        _setattr_safe(ee, "use_gtao", True)
        _setattr_safe(ee, "gtao_distance", 0.6)
        _setattr_safe(ee, "use_soft_shadows", True)
        _setattr_safe(ee, "shadow_cascade_size", '2048')
        _setattr_safe(ee, "shadow_cube_size", '512')
        _setattr_safe(ee, "use_bloom", False)
        _setattr_safe(ee, "use_ssr", False)
        _setattr_safe(ee, "use_shadows", True)
    elif eng == 'BLENDER_WORKBENCH':
        sh = scene.display.shading
        sh.light = 'STUDIO'
        sh.color_type = 'MATERIAL'
        sh.show_shadows = True
        sh.shadow_intensity = 0.35
        sh.show_cavity = True
        sh.cavity_type = 'WORLD'
        sh.show_object_outline = True          # 외곽선 → 만화풍 레퍼런스 느낌
        sh.object_outline_color = (0.08, 0.08, 0.09)
        _setattr_safe(sh, "show_specular_highlight", False)
        _setattr_safe(scene.display, "render_aa", '8')
    elif eng == 'CYCLES':
        scene.cycles.samples = 16
        _setattr_safe(scene.cycles, "use_denoising", True)
        scene.cycles.max_bounces = 3

    burn = config.BURN_IN if burn_in is None else burn_in
    r.use_stamp = burn
    for name, val in (("use_stamp_date", False), ("use_stamp_time", True), ("use_stamp_render_time", False),
                      ("use_stamp_frame", True), ("use_stamp_frame_range", False), ("use_stamp_memory", False),
                      ("use_stamp_hostname", False), ("use_stamp_camera", True), ("use_stamp_lens", True),
                      ("use_stamp_scene", False), ("use_stamp_marker", True), ("use_stamp_filename", False),
                      ("use_stamp_sequencer_strip", False), ("use_stamp_note", True), ("use_stamp_labels", True)):
        _setattr_safe(r, name, val)
    _setattr_safe(r, "stamp_note_text", config.BURN_IN_NOTE)
    _setattr_safe(r, "stamp_font_size", 18)
    _setattr_safe(r, "stamp_background", (0.0, 0.0, 0.0, 0.55))

    # 동영상 출력: MP4 / H.264 (속도 우선)
    r.image_settings.file_format = 'FFMPEG'
    ff = r.ffmpeg
    ff.format = 'MPEG4'
    ff.codec = 'H264'
    _setattr_safe(ff, "constant_rate_factor", 'MEDIUM')
    _setattr_safe(ff, "ffmpeg_preset", 'REALTIME')
    ff.gopsize = config.FPS
    _setattr_safe(ff, "audio_codec", 'NONE')
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    r.filepath = os.path.join(config.OUTPUT_DIR, config.MOVIE_NAME + "_")
    r.use_file_extension = True
    return eng


def render_movie(scene, frames=None):
    """MP4 렌더 후 파일 이름을 renders/<MOVIE_NAME>.mp4 로 정리."""
    f0, f1 = frames or (config.FRAME_START, config.FRAME_END)
    scene.frame_start, scene.frame_end = f0, f1
    before = set(glob.glob(os.path.join(config.OUTPUT_DIR, config.MOVIE_NAME + "_*")))
    bpy.ops.render.render(animation=True)
    scene.frame_start, scene.frame_end = config.FRAME_START, config.FRAME_END
    after = sorted(set(glob.glob(os.path.join(config.OUTPUT_DIR, config.MOVIE_NAME + "_*"))) - before,
                   key=os.path.getmtime)
    if not after:
        after = sorted(glob.glob(os.path.join(config.OUTPUT_DIR, config.MOVIE_NAME + "_*")), key=os.path.getmtime)
    if not after:
        print("[render_preview] 출력 파일을 찾지 못했습니다:", config.OUTPUT_DIR)
        return None
    src = after[-1]
    suffix = "" if (f0, f1) == (config.FRAME_START, config.FRAME_END) else "_F%04d-%04d" % (f0, f1)
    dst = os.path.join(config.OUTPUT_DIR, config.MOVIE_NAME + suffix + os.path.splitext(src)[1])
    if os.path.abspath(src) != os.path.abspath(dst):
        if os.path.exists(dst):
            os.remove(dst)
        os.replace(src, dst)
    print("[render_preview] 완료:", dst)
    return dst


def still_frames():
    out = {}
    for n, f0, f1, _title in config.CUTS:
        out[n] = int(round(f0 + (f1 - f0) * config.STILL_MOMENTS.get(n, 0.5)))
    return out


def render_stills(scene):
    """컷별 '이미지용 한 순간' PNG (번인 없음) — GPT 이미지 구도 레퍼런스용."""
    os.makedirs(config.STILLS_DIR, exist_ok=True)
    r = scene.render
    keep = (r.image_settings.file_format, r.use_stamp, r.filepath)
    r.image_settings.file_format = 'PNG'
    r.use_stamp = False
    paths = []
    for n, f in still_frames().items():
        scene.frame_set(f)
        r.filepath = os.path.join(config.STILLS_DIR, "CUT%02d_F%04d.png" % (n, f))
        bpy.ops.render.render(write_still=True)
        paths.append(r.filepath)
    r.image_settings.file_format, r.use_stamp, r.filepath = keep
    if keep[0] == 'FFMPEG':
        r.image_settings.file_format = 'FFMPEG'
    print("[render_preview] 스틸 %d장:" % len(paths), config.STILLS_DIR)
    return paths


def _parse_args(argv):
    import argparse
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    ap = argparse.ArgumentParser(prog="render_preview.py")
    ap.add_argument("--engine", default=None, help="eevee | workbench | cycles")
    ap.add_argument("--scale", type=int, default=100, help="해상도 %% (빠른 확인: 50)")
    ap.add_argument("--frames", default=None, help="예: 241-312 (일부 구간만)")
    ap.add_argument("--stills", action="store_true", help="컷별 스틸 PNG 만 렌더")
    ap.add_argument("--no-burnin", action="store_true", help="프레임·컷 번인 끄기")
    ap.add_argument("--rebuild", action="store_true", help="열린 .blend 가 있어도 씬을 새로 생성")
    return ap.parse_args(args)


def main():
    opts = _parse_args(sys.argv)
    scene = bpy.context.scene
    if opts.rebuild or bpy.data.objects.get("CAM_CUT01") is None:
        import main as previs_main
        previs_main.build_previs()
        scene = bpy.context.scene
    configure_preview_render(scene, opts.engine, opts.scale, False if opts.no_burnin else None)
    if opts.stills:
        render_stills(scene)
        return
    frames = None
    if opts.frames:
        a, b = opts.frames.split("-")
        frames = (int(a), int(b))
    render_movie(scene, frames)


if __name__ == "__main__":
    main()
