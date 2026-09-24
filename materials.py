"""
materials.py — 프리비즈 팔레트와 단순 재질

캐릭터 색은 첨부 캐릭터 시트의 팔레트(복숭아 피부, 차콜 폴로, 아이보리 바지, 흰 양말+빨간 선,
검정 로퍼, 네이비 명찰 줄, 회색 가방, 연하늘 파일)를 그대로 옮겼고,
환경 색은 설계안의 '채도 낮은 세이지그린·청회색·크림·연한 복숭아' 톤으로 잡았습니다.
Eevee/Cycles 는 노드 재질을, Workbench/Solid 뷰는 diffuse_color 를 씁니다.
"""
import bpy

import config
from utils import hex_rgb

PALETTE = {
    # --- 주인공 (캐릭터 시트 팔레트) ---
    "skin": "#FBDAC6",
    "hair": "#1E1E21",
    "polo": "#2D2D32",
    "collar": "#232327",
    "button": "#F4F4F2",
    "pants_ivory": "#F1ECDF",
    "belt": "#1F1F22",
    "sock": "#FAFAF8",
    "sock_red": "#D2474F",
    "loafer": "#232325",
    "lanyard": "#153E78",
    "tag_white": "#FFFFFF",
    "tag_teal": "#3DB5AD",
    "bag": "#4A4A50",
    "strap": "#5E5F64",
    "file_blue": "#8FC1EE",
    "eye": "#141416",
    # --- 시민 ---
    "cit_skin": "#E4B28C",
    "cit_hair": "#222226",
    "jumper_olive": "#767B45",
    "tshirt_grey": "#9D9D9A",
    "cit_pants": "#2D2E33",
    "slipper": "#51535B",
    # --- 환경 ---
    "ground_concrete": "#CFC8BA",
    "ground_yard": "#D6CCB7",
    "stair": "#DCD5C8",
    "wall_white": "#F2EFE7",
    "wall_cream": "#ECE3D1",
    "wall_sage": "#C9D3BF",
    "wall_bluegrey": "#BFCAD2",
    "wall_peach": "#EBCFBC",
    "retaining": "#C8C1B3",
    "gate_jade": "#78C2AE",
    "gate_post": "#EDE8DC",
    "roof_slate": "#6D8DAB",
    "roof_sage": "#8FA58B",
    "roof_terracotta": "#B98A74",
    "roof_grey": "#8C9098",
    "wood": "#B38B61",
    "wood_dark": "#8E6B48",
    "pot": "#BF7C58",
    "leaf": "#6E9A5C",
    "flower_red": "#D65A55",
    "net": "#3E6B67",
    "rail": "#8E969C",
    "cloth_1": "#F3EFE6",
    "cloth_2": "#A9C6DB",
    "cloth_3": "#E8C9B3",
    "cup": "#F4EEE2",
    "tea": "#B0783E",
    "tablet_body": "#3B3C42",
    "screen_base": "#F6F3EA",
    "panel_installment": "#8CC8B6",
    "panel_welfare": "#F2B48E",
    "icon_white": "#FFFFFF",
    "paper": "#FBFAF6",
    "pen": "#2F4E7A",
    "window_dark": "#4C5563",
    "window_lit": "#FFC56E",
    "lighthouse": "#F4F2EC",
    "lantern": "#4A4F58",
    "hill_grass": "#A9B38C",
    "hill_rock": "#9C9A8E",
    "quay": "#BDB8AC",
    "boat_hull": "#E9E6DE",
    "boat_blue": "#5F87A8",
    "sea_deep": "#2F8A92",
    "sea_light": "#62B3B0",
}

_CACHE = {}


def _principled(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = nt.nodes.get("Material Output") or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    return bsdf


def _set_input(node, names, value):
    for n in names:
        if n in node.inputs:
            node.inputs[n].default_value = value
            return True
    return False


def get(name, roughness=0.85, emission=0.0, specular=0.25):
    """팔레트 이름으로 재질을 만들거나 캐시에서 가져옵니다."""
    key = (name, roughness, emission, specular)
    if key in _CACHE:
        return _CACHE[key]
    rgb = hex_rgb(PALETTE[name])
    mat_name = "M_" + name if emission == 0.0 else "M_%s_emit" % name
    mat = bpy.data.materials.new(mat_name)
    mat.diffuse_color = (rgb[0], rgb[1], rgb[2], 1.0)   # Workbench / Solid 뷰 색
    mat.roughness = roughness
    bsdf = _principled(mat)
    bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    _set_input(bsdf, ("Specular IOR Level", "Specular"), specular)
    if emission > 0.0:
        _set_input(bsdf, ("Emission Color", "Emission"), (rgb[0], rgb[1], rgb[2], 1.0))
        _set_input(bsdf, ("Emission Strength",), emission)
    _CACHE[key] = mat
    return mat


def sea_material():
    """느리게 일렁이는 바다 (노이즈 W 값을 전체 길이에 걸쳐 선형 키프레임)."""
    if "sea" in _CACHE:
        return _CACHE["sea"]
    mat = bpy.data.materials.new("M_sea")
    deep, light = hex_rgb(PALETTE["sea_deep"]), hex_rgb(PALETTE["sea_light"])
    mat.diffuse_color = (*light, 1.0)
    bsdf = _principled(mat)
    nt = mat.node_tree
    coord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.06, 0.18, 0.06)
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.noise_dimensions = '4D'
    noise.inputs["Scale"].default_value = 3.0
    noise.inputs["Detail"].default_value = 3.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[0].color = (*deep, 1.0)
    ramp.color_ramp.elements[1].position = 0.66
    ramp.color_ramp.elements[1].color = (*light, 1.0)
    nt.links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    nt.links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.32
    _set_input(bsdf, ("Specular IOR Level", "Specular"), 0.5)
    w = noise.inputs["W"]
    w.default_value = 0.0
    w.keyframe_insert("default_value", frame=config.FRAME_START)
    w.default_value = 5.0
    w.keyframe_insert("default_value", frame=config.FRAME_END)
    for fc in mat.node_tree.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    _CACHE["sea"] = mat
    return mat


def net_material():
    if "net" in _CACHE:
        return _CACHE["net"]
    mat = get("net", roughness=0.9)
    _CACHE["net"] = mat
    return mat
