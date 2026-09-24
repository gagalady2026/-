"""
main.py — 「똑똑, 괜찮으세요?」 30초 프리비즈 씬 생성 (Blender 4.0.2 / bpy)

실행 방법
  A) Blender UI : Scripting 탭 → Open → main.py → Run Script
                  (새 파일에서 실행하세요. 현재 파일의 오브젝트·재질을 모두 지우고 다시 만듭니다.)
  B) 명령줄     : blender -b -P main.py              → 씬 생성 + build/donghae_previs.blend 저장
                  blender -b -P main.py -- --render  → 씬 생성 + 저장 + 30초 MP4 렌더
config.py 값을 고친 뒤 다시 실행하면 전체가 새로 만들어집니다.
"""
import importlib
import os
import sys

import bpy


def _project_dir():
    if "__file__" in globals():
        d = os.path.dirname(os.path.abspath(__file__))
        if os.path.exists(os.path.join(d, "config.py")):
            return d
    for t in bpy.data.texts:                       # Blender 텍스트 에디터에서 실행한 경우
        if t.filepath and os.path.basename(t.filepath) == "main.py":
            return os.path.dirname(bpy.path.abspath(t.filepath))
    return os.getcwd()


PROJECT_DIR = _project_dir()
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

_MODULES = ["config", "utils", "materials", "characters", "environments", "cameras", "animation",
            "timeline", "render_preview"]
for _name in _MODULES:                               # 다시 실행할 때 수정한 config 가 반영되도록
    if _name in sys.modules:
        importlib.reload(sys.modules[_name])

import animation      # noqa: E402
import cameras        # noqa: E402
import characters     # noqa: E402
import config         # noqa: E402
import environments   # noqa: E402
import render_preview  # noqa: E402
import timeline       # noqa: E402
from utils import get_collection  # noqa: E402


def reset_scene():
    """현재 파일의 오브젝트·메시·재질·카메라·조명·액션·마커를 모두 지움."""
    scene = bpy.context.scene
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.cameras, bpy.data.lights,
                  bpy.data.actions, bpy.data.curves):
        for item in list(block):
            block.remove(item)
    scene.timeline_markers.clear()
    scene.camera = None
    for w in list(bpy.data.worlds):
        if w != scene.world:
            bpy.data.worlds.remove(w)


def build_previs():
    reset_scene()
    scene = bpy.context.scene
    scene.name = "PREVIS_30s"
    total = timeline.validate_cuts()
    timeline.setup_scene_timing(scene)
    root = get_collection("PREVIS_똑똑괜찮으세요")

    # 세트
    layout = environments.Layout()
    env = get_collection("ENVIRONMENT", root)
    environments.build_stairs_set(layout, env)
    environments.build_gate_set(layout, env)
    environments.build_yard_set(layout, env)
    environments.build_village_set(layout, env)

    # 인물 · 카메라
    main_char = characters.build_main_character(root)
    citizen = characters.build_citizen_proxy(root)
    cams = cameras.create_cut_cameras(root)
    ctx = animation.PrevisContext(layout, main_char, citizen, cams)

    # 컷별 블로킹 + 카메라
    animation.setup_cut_01(ctx)
    animation.setup_cut_02(ctx)
    animation.setup_cut_03(ctx)
    animation.setup_cut_04(ctx)
    animation.setup_cut_05(ctx)
    animation.setup_cut_06(ctx)
    animation.setup_cut_07(ctx)
    animation.setup_cut_08(ctx)
    animation.setup_prop_states(ctx)

    # 타임라인 · 조명 · 렌더 설정
    timeline.setup_timeline_markers(scene, cams)
    timeline.setup_lighting(scene, root)
    timeline.finalize_cut_boundaries()
    render_preview.configure_preview_render(scene)
    scene.frame_set(config.FRAME_START)
    timeline.verify_timeline(scene)
    cameras.report_framing(scene, render_preview.still_frames())
    scene.frame_set(config.FRAME_START)
    print("[previs] 생성 완료: %d프레임 (%.1f초), 컷 %d개, 카메라 %d대"
          % (config.FRAME_END - config.FRAME_START + 1, total, len(config.CUTS), len(cams)))
    return ctx


def save_blend(path=None):
    path = path or config.BLEND_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    print("[previs] 저장:", path)
    return path


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build_previs()
    if bpy.app.background or "--save" in argv:
        save_blend()
    if "--render" in argv:
        render_preview.render_movie(bpy.context.scene)


if __name__ == "__main__":
    main()
