"""
environments.py — 블록아웃 세트 (A 언덕 골목 / B 대문 / C 마당 / D 엔딩 마을)

네 세트를 따로 떼지 않고 '하나의 언덕 마을' 안에 이어 붙였습니다.
  아랫골목(해발 Z_LOW) → 북동쪽으로 오르는 계단(CUT1·7) → 윗골목 → 시민 집 대문(CUT2·3·7)
  → 마당·평상(CUT4~6) … 서쪽 아래로 계단식 지붕·항구·바다, 남서쪽 곶 위에 등대(CUT7·8)
그래서 CUT1(아래에서 계단을 올려다봄)과 CUT7(대문에서 같은 계단을 내려다봄)이 공간적으로 대응합니다.
실제 묵호 지형·건물은 모델링하지 않습니다(GPT 이미지 단계에서 실제 사진 레퍼런스 사용).
"""
import math
import random

from mathutils import Matrix, Vector

import config
import materials as M
from utils import MeshBuilder, get_collection, heading_vec, rot2


class Layout:
    """세트 기준점 모음 (카메라·애니메이션이 이 값을 참조)."""

    def __init__(self):
        c = config
        self.z_up = c.GATE_LEVEL_Z
        self.z_low = c.GATE_LEVEL_Z - c.STAIR_COUNT * c.STAIR_RISE
        # --- 계단 좌표계: u = 오르는 방향, v = 왼쪽 ---
        self.st_dir = heading_vec(c.STAIR_HEADING)
        self.st_left = rot2(self.st_dir, 90.0)
        self.st_rise, self.st_run, self.st_n, self.st_w = c.STAIR_RISE, c.STAIR_RUN, c.STAIR_COUNT, c.STAIR_WIDTH
        self.st_len = (self.st_n - 1) * self.st_run          # 첫 챌판 ~ 윗골목(맨 윗단) 까지
        top = Vector((c.STAIR_TOP_XY[0], c.STAIR_TOP_XY[1], 0.0))
        self.st_origin = top - self.st_dir * self.st_len     # 첫 챌판 중심 (아랫골목 바닥)
        self.st_origin.z = self.z_low
        # --- 대문 ---
        self.gate = Vector((0.0, 0.0, self.z_up))
        self.gate_leaf = None
        # --- 평상 좌표계 ---
        cx, cy = c.PYEONGSANG_CENTER_XY
        front = heading_vec(c.PYEONGSANG_FRONT_HEADING)       # 로컬 -Y
        self.pl_y = -front
        self.pl_x = rot2(self.pl_y, -90.0)                    # 로컬 +X (주인공 쪽)
        self.pl_center = Vector((cx, cy, self.z_up))
        self.pl_top = self.z_up + c.PYEONGSANG_HEIGHT
        self.props = {}
        self.window_lights = []

    # 계단 위 한 점 (u, v) 의 디딤판 높이 포함 월드 좌표
    def stair_height(self, u):
        if u < 0.0:
            return self.z_low
        i = min(int(u // self.st_run), self.st_n - 1)
        return self.z_low + (i + 1) * self.st_rise

    def surface_height(self, p):
        """점 p 아래 바닥 높이 (계단 폭 안에서만 정확, 밖은 무시)."""
        rel = Vector((p[0], p[1], 0.0)) - Vector((self.st_origin.x, self.st_origin.y, 0.0))
        u, v = rel.dot(self.st_dir), rel.dot(self.st_left)
        if abs(v) > self.st_w * 0.5 + 0.3:
            return -1e9
        if u < 0.0:
            return self.z_low
        return self.stair_height(u)

    def stair_point(self, u, v=0.0, dz=0.0, on_surface=True):
        p = self.st_origin + self.st_dir * u + self.st_left * v
        p.z = (self.stair_height(u) if on_surface else self.z_low) + dz
        return p

    def plat(self, x, y, z=0.0):
        """평상 로컬(x, y) + 마당 바닥 기준 높이 z → 월드."""
        return self.pl_center + self.pl_x * x + self.pl_y * y + Vector((0, 0, z))

    def plat_dir(self, x, y):
        return (self.pl_x * x + self.pl_y * y).normalized()

    def plat_rot_z(self):
        return math.atan2(self.pl_x.y, self.pl_x.x)


# =============================================================================
# 공통 소품
# =============================================================================
def _pot(mb, x, y, z, r=0.16, h=0.30, flower=False):
    mb.cylinder(r * 0.8, r, z, z + h, center_xy=(x, y), segments=10, mat=0)
    mb.sphere((r * 1.05, r * 1.05, r * 0.85), center=(x, y, z + h + r * 0.55), segments=8, rings=6, mat=1)
    if flower:
        for k in range(3):
            a = k * 2.1
            mb.sphere((0.045, 0.045, 0.045), center=(x + math.cos(a) * r * 0.6, y + math.sin(a) * r * 0.6,
                                                      z + h + r * 1.1), segments=6, rings=4, mat=2)


def _pot_mats():
    return [M.get("pot"), M.get("leaf"), M.get("flower_red")]


def _railing(mb, p0, p1, height=0.95, post_step=1.3, r=0.022, mat=0):
    """두 점을 잇는 파이프 난간(계단 기울기도 따라감)."""
    p0, p1 = Vector(p0), Vector(p1)
    n = max(2, int((p1 - p0).length / post_step) + 1)
    for i in range(n):
        p = p0.lerp(p1, i / (n - 1))
        mb.cylinder(r, r, p.z, p.z + height, center_xy=(p.x, p.y), segments=6, mat=mat)
    top0, top1 = p0 + Vector((0, 0, height)), p1 + Vector((0, 0, height))
    mb.box_between(top0, top1, r * 2.2, r * 2.2, mat=mat)
    mid = height * 0.5
    mb.box_between(p0 + Vector((0, 0, mid)), p1 + Vector((0, 0, mid)), r * 1.6, r * 1.6, mat=mat)


def _house(mb, cx, cy, z_base, w, d, h, rot=0.0, roof="gable", mat_wall=0, mat_roof=1, bury=1.5):
    """박스형 주택 + 지붕. w = X폭, d = Y깊이 (rot 적용 전)."""
    rz = Matrix.Rotation(rot, 4, 'Z')
    m = Matrix.Translation((cx, cy, 0.0)) @ rz
    mb.box((w, d, h + bury), center=(0, 0, z_base + (h - bury) * 0.5), mat=mat_wall, matrix=m)
    if roof == "none":
        return
    if roof == "gable":   # 박공: 용마루는 Y 방향
        ov = 0.25
        for sx in (-1, 1):
            p0 = Vector((sx * (w * 0.5 + ov), 0, z_base + h - 0.12))
            p1 = Vector((0, 0, z_base + h + min(w, 6.0) * 0.18))
            mid = (p0 + p1) * 0.5
            slope = (p1 - p0)
            ang = math.atan2(slope.z, abs(slope.x))
            mm = m @ Matrix.Translation(mid) @ Matrix.Rotation(-sx * ang, 4, 'Y')
            mb.box(((p1 - p0).length + 0.05, d + ov * 2, 0.12), mat=mat_roof, matrix=mm)
    else:                 # 평지붕 슬래브
        mb.box((w + 0.3, d + 0.3, 0.16), center=(0, 0, z_base + h + 0.08), mat=mat_roof, matrix=m)


# =============================================================================
# A. 언덕 골목 + 계단
# =============================================================================
def build_stairs_set(layout, parent):
    col = get_collection("SET_A_언덕골목_계단", parent)
    L = layout
    zl, zu = L.z_low, L.z_up
    x_west = config.LOWER_STREET_WEST_X

    # 아랫골목 바닥 (윗단 테라스 아래까지 넓게 깔아 둠)
    mb = MeshBuilder()
    mb.prism([(x_west, -75.0), (46.0, -75.0), (46.0, 85.0), (x_west, 85.0)], zl - 3.5, zl, mat=0)
    mb.to_object("A_아랫골목_바닥", col, [M.get("ground_concrete")])

    # 윗단 테라스(윗골목·대문·마당이 올라앉는 땅). 계단 오른쪽 옹벽이 이 테라스의 벽면.
    bl = L.st_origin + L.st_left * (L.st_w * 0.5)
    br = L.st_origin - L.st_left * (L.st_w * 0.5)
    top = L.st_origin + L.st_dir * L.st_len
    tl = top + L.st_left * (L.st_w * 0.5)
    tr = top - L.st_left * (L.st_w * 0.5)
    poly = [(br.x, -75.0), (46.0, -75.0), (46.0, 85.0), (tl.x, 85.0), (tl.x, tl.y), (tr.x, tr.y), (br.x, br.y)]
    mb = MeshBuilder()
    mb.prism(poly, zl - 0.2, zu, mat=0)
    mb.to_object("A_윗단_테라스", col, [M.get("retaining")])
    L.terrace_edge = (tl, tr, br, bl)

    # 계단 (한 칸씩 박스, 아래로 채움)
    mb = MeshBuilder()
    rz = math.atan2(L.st_dir.y, L.st_dir.x) - math.pi * 0.5
    for i in range(L.st_n):
        u0 = i * L.st_run
        depth = L.st_run if i < L.st_n - 1 else L.st_run + 0.4
        c = L.st_origin + L.st_dir * (u0 + depth * 0.5)
        ztop = zl + (i + 1) * L.st_rise
        mb.box((L.st_w, depth, ztop - (zl - 0.5)), center=(c.x, c.y, (ztop + zl - 0.5) * 0.5), rot_z=rz, mat=0)
    L.props["stairs"] = mb.to_object("A_계단", col, [M.get("stair")])

    # 계단 왼쪽(열린 쪽) 파이프 난간 — 모션 시트의 계단 난간처럼 발이 가려지지 않음
    mb = MeshBuilder()
    rail_v = L.st_w * 0.5 - 0.06
    p0 = L.stair_point(0.15, rail_v)
    p1 = L.stair_point(L.st_len - 0.1, rail_v)
    _railing(mb, p0, p1, height=0.9, post_step=1.45)
    # 아랫골목 서쪽 가장자리 파이프 난간 (바다 쪽이 트여 보이도록)
    cy = config.CAM_CUT01["start_xy"][1]            # 컷1 카메라 시작점 기준으로 전경 소품 배치
    _railing(mb, (x_west + 0.08, cy + 3.15, zl), (x_west + 0.08, 30.0, zl), height=0.95, post_step=2.2)
    _railing(mb, (x_west + 0.08, -60.0, zl), (x_west + 0.08, cy + 1.55, zl), height=0.95, post_step=2.2)
    mb.to_object("A_난간", col, [M.get("rail", roughness=0.4)])

    # 계단 오른쪽 옹벽 위 담장 (계단에서 보면 '담장 너머 집')
    mb = MeshBuilder()
    wall_h = 0.9
    edge0 = br - L.st_left * 0.12
    edge1 = tr - L.st_left * 0.12
    mb.box_between(Vector((edge0.x, edge0.y, zu + wall_h * 0.5)), Vector((edge1.x, edge1.y, zu + wall_h * 0.5)),
                   0.2, wall_h, mat=0, up=(0, 0, 1))
    # 아랫골목 동쪽 옹벽 위 담장
    mb.box((0.2, 60.0, wall_h), center=(br.x + 0.1, br.y - 30.2, zu + wall_h * 0.5), mat=0)
    mb.to_object("A_담장", col, [M.get("wall_white")])

    # 아랫골목 동쪽 옹벽에 붙은 집 입면 (문·창·차양) — CUT1 오른쪽이 '마을 골목'으로 읽히게
    mb = MeshBuilder()
    face_x = br.x - 0.02
    y = -44.0
    k = 0
    while True:
        wdt = 3.2 + (k % 3) * 0.7
        if y + wdt > br.y - 0.6:          # 계단 입구를 가리지 않도록 계단 앞에서 멈춤
            break
        mb.box((0.08, 0.9, 1.95), center=(face_x - 0.03, y + wdt * 0.3, zl + 0.975), mat=0)       # 문
        mb.box((0.06, 1.0, 0.8), center=(face_x - 0.03, y + wdt * 0.72, zl + 1.55), mat=1)        # 창
        mb.box((0.6, wdt * 0.9, 0.06), center=(face_x - 0.3, y + wdt * 0.5, zl + 2.25), mat=2)    # 차양
        mb.box((0.04, wdt - 0.15, 2.6), center=(face_x - 0.005, y + wdt * 0.5, zl + 1.3), mat=3 + (k % 3))
        y += wdt + 0.25
        k += 1
    mb.to_object("A_골목_집입면", col, [M.get("wood_dark"), M.get("window_dark", roughness=0.3), M.get("roof_slate"),
                                      M.get("wall_white"), M.get("wall_cream"), M.get("wall_peach")])

    # CUT1 전경: 짧은 담장 + 화분, 빨랫줄과 빨래
    mb = MeshBuilder()
    mb.box((0.28, 1.5, 0.78), center=(x_west + 0.14, cy + 2.35, zl + 0.39), mat=0)
    mb.to_object("A_전경담장", col, [M.get("wall_cream")])
    mb = MeshBuilder()
    _pot(mb, x_west + 0.16, cy + 2.55, zl + 0.78, r=0.15, h=0.26, flower=True)
    _pot(mb, x_west + 0.16, cy + 1.95, zl + 0.78, r=0.12, h=0.22, flower=False)
    _pot(mb, x_west + 0.45, cy + 7.0, zl, r=0.2, h=0.36, flower=True)
    _pot(mb, br.x - 0.35, br.y - 0.8, zl, r=0.18, h=0.32, flower=False)
    mb.to_object("A_화분", col, _pot_mats())

    mb = MeshBuilder()
    pa, pb = Vector((x_west + 0.35, cy + 3.3, zl)), Vector((x_west + 0.5, cy + 7.6, zl))
    for p in (pa, pb):
        mb.cylinder(0.03, 0.03, p.z, p.z + 2.05, center_xy=(p.x, p.y), segments=6, mat=0)
    mb.box_between(pa + Vector((0, 0, 1.95)), pb + Vector((0, 0, 1.95)), 0.012, 0.012, mat=0)
    mb.to_object("A_빨랫줄", col, [M.get("rail")])
    cloths = []
    for k, (t, w, h, cm) in enumerate([(0.18, 0.42, 0.55, "cloth_1"), (0.38, 0.36, 0.48, "cloth_2"),
                                       (0.58, 0.46, 0.62, "cloth_3"), (0.80, 0.34, 0.42, "cloth_1")]):
        p = pa.lerp(pb, t) + Vector((0, 0, 1.95))
        mb = MeshBuilder()
        mb.box((0.012, w, h), center=(0, 0, -h * 0.5), mat=0)
        ob = mb.to_object("A_빨래_%d" % (k + 1), col, [M.get(cm)], location=p)
        ob.rotation_euler = (0, 0, math.atan2(pb.y - pa.y, pb.x - pa.x) - math.pi * 0.5)
        cloths.append(ob)
    L.props["laundry"] = cloths
    return col


# =============================================================================
# B. 시민 집 대문 (옥색 철대문, 흰 담장, 문 옆 화분, 여닫는 구조)
# =============================================================================
def build_gate_set(layout, parent):
    col = get_collection("SET_B_대문", parent)
    L = layout
    zu = L.z_up
    gw, gh = config.GATE_WIDTH, config.GATE_HEIGHT
    half = gw * 0.5
    post = 0.28
    yh = config.YARD_WALL_HEIGHT
    tall = config.GATE_WALL_HEIGHT

    mb = MeshBuilder()
    # 대문 기둥 + 작은 지붕
    for sy in (1, -1):
        mb.box((post, post, gh + 0.2), center=(0.1, sy * (half + post * 0.5), zu + (gh + 0.2) * 0.5), mat=0)
    # 대문 옆 높은 담장(대문 좌우 1.2m) + 낮은 마당 담장
    for sy in (1, -1):
        y0 = sy * (half + post)
        mb.box((0.2, 1.2, tall), center=(0.1, y0 + sy * 0.6, zu + tall * 0.5), mat=1)
    mb.box((0.2, 7.0 - (half + post + 1.2), yh), center=(0.1, (7.0 + half + post + 1.2) * 0.5, zu + yh * 0.5), mat=1)
    mb.box((0.2, 5.0 - (half + post + 1.2), yh), center=(0.1, -(5.0 + half + post + 1.2) * 0.5, zu + yh * 0.5), mat=1)
    mb.to_object("B_대문기둥_담장", col, [M.get("gate_post"), M.get("wall_white")])

    mb = MeshBuilder()
    mb.box((0.62, gw + post * 2 + 0.5, 0.1), center=(0.1, 0, zu + gh + 0.26), mat=0)
    mb.box((0.5, gw + post * 2 + 0.3, 0.12), center=(0.1, 0, zu + gh + 0.16), mat=1)
    mb.to_object("B_대문지붕", col, [M.get("roof_slate"), M.get("wall_white")])

    # 빈 문패 (글자 없음)
    mb = MeshBuilder()
    mb.box((0.03, 0.2, 0.09), center=(-0.03, half + post * 0.5, zu + 1.5), mat=0)
    mb.to_object("B_빈문패", col, [M.get("wood")])

    # 철대문 한 짝: 원점 = 북쪽 경첩, +Z 회전 = 마당 안쪽(동쪽)으로 열림
    mb = MeshBuilder()
    mb.box((0.05, gw, gh - 0.1), center=(0.0, -half, (gh - 0.1) * 0.5), mat=0)
    for k in range(5):  # 세로 살 (노크하는 면의 결)
        yy = -0.12 - k * (gw - 0.24) / 4.0
        mb.box((0.07, 0.035, gh - 0.3), center=(-0.012, yy, (gh - 0.1) * 0.5), mat=0)
    mb.box((0.07, gw, 0.06), center=(-0.012, -half, gh - 0.2), mat=0)
    mb.box((0.07, gw, 0.06), center=(-0.012, -half, 0.2), mat=0)
    for sx in (-1, 1):  # 손잡이 (자유단 쪽)
        mb.box((0.04, 0.05, 0.14), center=(sx * 0.05, -gw + 0.1, 1.05), mat=1)
    leaf = mb.to_object("B_철대문", col, [M.get("gate_jade", roughness=0.45), M.get("lantern")],
                        location=(0.06, half, zu + 0.06))
    L.gate_leaf = leaf
    L.props["gate_leaf"] = leaf

    # 문 옆 화분 (제라늄·고추) — CUT2 에서 카메라가 스쳐 지나감
    mb = MeshBuilder()
    _pot(mb, -0.28, 1.12, zu, r=0.17, h=0.30, flower=True)
    _pot(mb, -0.30, 1.62, zu, r=0.14, h=0.26, flower=True)
    _pot(mb, -0.26, -1.10, zu, r=0.15, h=0.28, flower=False)
    _pot(mb, 0.10, 2.30, zu + config.YARD_WALL_HEIGHT, r=0.13, h=0.22, flower=True)   # 담장 위 (CUT2 전경)
    _pot(mb, 0.10, 2.75, zu + config.YARD_WALL_HEIGHT, r=0.11, h=0.20, flower=False)
    mb.to_object("B_대문화분", col, _pot_mats())

    # 윗골목 바닥 표시 (살짝 다른 색)
    mb = MeshBuilder()
    tl = L.terrace_edge[0]
    tr = L.terrace_edge[1]
    edge = (tr - tl).normalized()
    y_at_gate = tr.y + edge.y / edge.x * (0.0 - tr.x)          # 계단 윗단 선을 대문 선(x=0)까지 연장
    mb.prism([(tl.x, tl.y), (tr.x, tr.y), (0.0, y_at_gate), (0.0, 22.0), (tl.x, 22.0)], zu, zu + 0.01, mat=0)
    mb.to_object("B_윗골목", col, [M.get("ground_concrete")])
    return col


# =============================================================================
# C. 마당 (평상, 화분, 그물, 담장, 집)
# =============================================================================
def build_yard_set(layout, parent):
    col = get_collection("SET_C_마당", parent)
    L = layout
    zu = L.z_up
    yh = config.YARD_WALL_HEIGHT
    house_x0, house_x1, house_y0, house_y1 = 7.2, 11.4, -3.6, 5.6

    mb = MeshBuilder()
    mb.prism([(0.2, -5.0), (house_x0, -5.0), (house_x0, 7.0), (0.2, 7.0)], zu, zu + 0.012, mat=0)
    mb.to_object("C_마당바닥", col, [M.get("ground_yard")])

    mb = MeshBuilder()   # 남·북 담장 (낮게: 마당에서 바다가 보이도록)
    mb.box((house_x1 - 0.2, 0.2, yh), center=((house_x1 + 0.2) * 0.5, -5.1, zu + yh * 0.5), mat=0)
    mb.box((house_x1 - 0.2, 0.2, yh), center=((house_x1 + 0.2) * 0.5, 7.1, zu + yh * 0.5), mat=0)
    mb.to_object("C_마당담장", col, [M.get("wall_white")])

    # 집 (하얀 회벽 + 파란 슬레이트 지붕, 마당 쪽 처마)
    mb = MeshBuilder()
    w, d, h = house_x1 - house_x0, house_y1 - house_y0, 2.9
    cx, cy = (house_x0 + house_x1) * 0.5, (house_y0 + house_y1) * 0.5
    mb.box((w, d, h + 1.0), center=(cx, cy, zu + (h - 1.0) * 0.5), mat=0)
    mb.to_object("C_집", col, [M.get("wall_white")])
    mb = MeshBuilder()
    ov = 0.7
    for sx in (-1, 1):
        p0 = Vector((cx + sx * (w * 0.5 + ov), cy, zu + h - 0.15))
        p1 = Vector((cx, cy, zu + h + 1.0))
        mid = (p0 + p1) * 0.5
        ang = math.atan2(p1.z - p0.z, abs(p1.x - p0.x))
        mb.box(((p1 - p0).length + 0.05, d + 0.6, 0.12), mat=0,
               matrix=Matrix.Translation(mid) @ Matrix.Rotation(-sx * ang, 4, 'Y'))
    mb.to_object("C_집지붕", col, [M.get("roof_slate")])
    mb = MeshBuilder()   # 마당 쪽 문·창
    mb.box((0.06, 0.95, 2.0), center=(house_x0 - 0.02, 1.2, zu + 1.0), mat=0)
    for yy in (-1.8, 3.8):
        mb.box((0.06, 1.3, 1.0), center=(house_x0 - 0.02, yy, zu + 1.45), mat=1)
    mb.to_object("C_집_문창", col, [M.get("wood_dark"), M.get("window_dark", roughness=0.3)])

    # 평상 (나무판 6장 + 다리) — 나무판 결 = 평상 로컬 X 방향
    sx_, sy_ = config.PYEONGSANG_SIZE
    ph = config.PYEONGSANG_HEIGHT
    mb = MeshBuilder()
    rz = L.plat_rot_z()
    n_planks = 6
    for k in range(n_planks):
        y = -sy_ * 0.5 + (k + 0.5) * sy_ / n_planks
        c = L.plat(0.0, y, ph - 0.03)
        mb.box((sx_, sy_ / n_planks - 0.012, 0.06), center=c, rot_z=rz, mat=0)
    for fx in (-1, 1):
        for fy in (-1, 1):
            c = L.plat(fx * (sx_ * 0.5 - 0.08), fy * (sy_ * 0.5 - 0.08), (ph - 0.06) * 0.5)
            mb.box((0.08, 0.08, ph - 0.06), center=c, rot_z=rz, mat=1)
    c = L.plat(0.0, 0.0, ph - 0.09)
    mb.box((sx_ - 0.1, sy_ - 0.1, 0.05), center=c, rot_z=rz, mat=1)
    L.props["pyeongsang"] = mb.to_object("C_평상", col, [M.get("wood"), M.get("wood_dark")])

    # 화분들
    mb = MeshBuilder()
    for (x, y, r, fl) in [(0.7, 6.3, 0.2, True), (1.3, 6.4, 0.16, False), (6.4, -4.3, 0.2, True),
                          (5.8, -4.4, 0.15, False), (0.7, -4.3, 0.18, True), (6.6, 6.3, 0.15, True)]:
        _pot(mb, x, y, zu, r=r, h=r * 1.8, flower=fl)
    mb.to_object("C_마당화분", col, _pot_mats())

    # 말리는 그물 (CUT4 전경, CUT3 대문 너머) — 거치대 + 그물(와이어프레임)
    mb = MeshBuilder()
    rack_a, rack_b = Vector((5.72, 3.62, zu)), Vector((6.28, 4.62, zu))
    for p in (rack_a, rack_b):
        mb.cylinder(0.035, 0.035, zu, zu + 1.85, center_xy=(p.x, p.y), segments=6, mat=0)
    mb.box_between(rack_a + Vector((0, 0, 1.8)), rack_b + Vector((0, 0, 1.8)), 0.04, 0.04, mat=0)
    mb.to_object("C_그물거치대", col, [M.get("wood_dark")])
    net = _net_mesh(rack_a + Vector((0, 0, 1.78)), rack_b + Vector((0, 0, 1.78)), drop=1.15, col=col, cols=10, rows=8)
    L.props["net"] = net
    # 대문 너머로 보이는 두 번째 그물 (마당 안쪽 벽)
    net2 = _net_mesh(Vector((2.4, 6.85, zu + 1.55)), Vector((4.6, 6.85, zu + 1.55)), drop=1.1, col=col, name="C_그물_2")
    L.props["net2"] = net2

    _build_yard_props(L, col)
    return col


def _net_mesh(p0, p1, drop, col, name="C_그물", cols=16, rows=10):
    import bmesh
    mb = MeshBuilder()
    bm = mb.bm
    verts = []
    for r in range(rows + 1):
        row = []
        for c in range(cols + 1):
            t = c / cols
            p = p0.lerp(p1, t)
            sag = math.sin(t * math.pi) * 0.18 * (r / rows)
            p = p + Vector((0, 0, -drop * r / rows - sag))
            p += Vector((0.06 * math.sin(r * 1.3 + c * 0.7), 0.0, 0.0))
            row.append(bm.verts.new(p))
        verts.append(row)
    for r in range(rows):
        for c in range(cols):
            bm.faces.new((verts[r][c], verts[r][c + 1], verts[r + 1][c + 1], verts[r + 1][c]))
    ob = mb.to_object(name, col, [M.net_material()])
    mod = ob.modifiers.new("net_wire", 'WIREFRAME')
    mod.thickness = 0.018
    return ob


def _build_yard_props(L, col):
    """찻잔 2개, 태블릿(분납/복지 두 영역), 평상 위 클리어파일."""
    top = L.pl_top
    for name in ("cup_citizen", "cup_main"):
        mb = MeshBuilder()
        mb.cylinder(0.034, 0.042, 0.0, 0.075, segments=12, mat=0)
        mb.cylinder(0.036, 0.036, 0.055, 0.058, segments=12, mat=1)
        ob = mb.to_object("C_찻잔_" + ("시민" if name == "cup_citizen" else "주인공"), col,
                          [M.get("cup", roughness=0.4), M.get("tea", roughness=0.2)])
        L.props[name] = ob

    # 안내 자료 태블릿: 왼쪽 = 분납 안내(단계 막대 아이콘), 오른쪽 = 복지서비스 연계(하트 아이콘). 글자 없음.
    mb = MeshBuilder()
    tw, td = 0.36, 0.25
    mb.box((tw, td, 0.012), center=(0, 0, 0.006), mat=0)
    mb.box((tw - 0.02, td - 0.02, 0.002), center=(0, 0, 0.0125), mat=1)
    mb.box((tw * 0.5 - 0.025, td - 0.045, 0.003), center=(-tw * 0.25 + 0.002, 0, 0.0145), mat=2)
    mb.box((tw * 0.5 - 0.025, td - 0.045, 0.003), center=(tw * 0.25 - 0.002, 0, 0.0145), mat=3)
    for k in range(3):   # 분납: 점점 높아지는 막대 3개 (나눠서 내기)
        hh = 0.035 + k * 0.026
        mb.box((0.026, hh, 0.004), center=(-tw * 0.25 - 0.042 + k * 0.042, -0.04 + hh * 0.5, 0.0165), mat=4)
    for sx in (-1, 1):   # 복지: 하트
        mb.cylinder(0.026, 0.026, 0.015, 0.019, center_xy=(tw * 0.25 + sx * 0.022, 0.014), segments=12, mat=4)
    mb.box((0.05, 0.05, 0.004), center=(tw * 0.25, -0.007, 0.017), rot_z=math.radians(45), mat=4)
    tab = mb.to_object("C_안내태블릿", col, [M.get("tablet_body", roughness=0.4), M.get("screen_base", emission=0.25),
                                               M.get("panel_installment", emission=0.35),
                                               M.get("panel_welfare", emission=0.35), M.get("icon_white", emission=0.5)])
    L.props["tablet"] = tab
    mb = MeshBuilder()   # 받침대 (태블릿 뒤쪽을 들어 올림)
    mb.box((0.30, 0.03, 0.10), center=(0, 0.0, 0.05), mat=0)
    L.props["tablet_stand"] = mb.to_object("C_태블릿받침", col, [M.get("tablet_body")])

    mb = MeshBuilder()
    mb.box((0.235, 0.31, 0.012), center=(0, 0, 0.006), mat=0)
    L.props["plat_file"] = mb.to_object("C_평상위_클리어파일", col, [M.get("file_blue", roughness=0.35)])
    mb = MeshBuilder()
    mb.box((0.012, 0.14, 0.012), center=(0, 0, 0.006), mat=0)
    L.props["pen"] = mb.to_object("C_펜", col, [M.get("pen")])


# =============================================================================
# D. 엔딩용 언덕 마을 (계단식 테라스 + 박스 주택 + 창문 + 항구 + 바다 + 등대 곶)
# =============================================================================
WALL_MATS = ["wall_white", "wall_cream", "wall_sage", "wall_bluegrey", "wall_peach"]
ROOF_MATS = ["roof_slate", "roof_sage", "roof_terracotta", "roof_grey"]


def build_village_set(layout, parent):
    col = get_collection("SET_D_마을_바다_등대", parent)
    L = layout
    rng = random.Random(config.RANDOM_SEED)
    zl, zu = L.z_low, L.z_up
    x_west = config.LOWER_STREET_WEST_X

    # --- 서쪽 아래 계단식 테라스 (아랫골목 → 항구) ---
    terraces = []   # (x0, x1, z)
    z = zl - 3.4
    x1 = x_west
    while z > 2.0:
        x0 = x1 - 6.8
        terraces.append((x0, x1, z))
        x1 = x0
        z -= 2.35
    quay_x0, quay_x1 = x1 - 7.0, x1
    # --- 동쪽 위 테라스 (마을 윗동네) ---
    up_terraces = []
    z = zu + 2.5
    x0 = 11.8
    while z < 44.0:
        up_terraces.append((x0, x0 + 7.5, z))
        x0 += 7.5
        z += 2.6

    mb = MeshBuilder()
    y0, y1 = -54.0, 84.0

    def segmented(a, b, zz, zbase, mat):
        """테라스를 길이 방향으로 잘라 높이를 조금씩 달리함 (일직선 옹벽 느낌 줄이기)."""
        yy = y0
        while yy < y1:
            ln = rng.uniform(14.0, 30.0)
            dz = rng.uniform(-0.35, 0.35)
            mb.prism([(a, yy), (b, yy), (b, min(y1, yy + ln)), (a, min(y1, yy + ln))], zbase, zz + dz, mat=mat)
            yy += ln
    for (a, b, zz) in terraces:
        segmented(a, b, zz, -2.0, 0)
    mb.prism([(quay_x0, y0 + 4), (quay_x1, y0 + 4), (quay_x1, y1 - 10), (quay_x0, y1 - 10)], -2.0, 1.5, mat=1)
    for (a, b, zz) in up_terraces:
        segmented(a, b, zz, zu - 1.0, 2)
    last = up_terraces[-1]
    mb.prism([(last[1], y0), (last[1] + 60.0, y0), (last[1] + 60.0, y1), (last[1], y1)], zu, last[2] + 3.0, mat=3)
    mb.to_object("D_지형_테라스", col, [M.get("retaining"), M.get("quay"), M.get("retaining"), M.get("hill_grass")])

    # --- 주택 배치 (세트 주변·등대 시야선은 비워 둠) ---
    lx, ly = config.LIGHTHOUSE_XY

    def blocked(x, y, r):
        if L.terrace_edge[3].x - 1.0 - r < x < 12.2 + r and L.terrace_edge[2].y - r < y < 9.5 + r:
            return True                      # 계단·윗골목·대문·마당 세트
        if x_west - r < x < L.terrace_edge[2].x + r and -70 < y < 70:
            return True                      # 아랫골목 길
        t = max(0.0, min(1.0, (x * lx + y * ly) / (lx * lx + ly * ly)))   # 대문 → 등대 시야선 (CUT7)
        if 0.03 < t and math.hypot(x - lx * t, y - ly * t) < 3.0 + r and y < -3:
            return True
        return False

    walls = MeshBuilder()
    roofs = MeshBuilder()
    wins = MeshBuilder()
    trees = MeshBuilder()
    lit_candidates = []
    all_rows = [(a, b, zz, "down") for (a, b, zz) in terraces] + [(a, b, zz, "up") for (a, b, zz) in up_terraces]
    all_rows.append((L.terrace_edge[2].x + 0.6, -0.4, zu, "mid"))   # 윗단(대문 레벨)의 계단 남쪽 집들 — CUT1 오른쪽 위
    for (a, b, zz, kind) in all_rows:
        y = y0 + 3.0 + rng.uniform(0, 4)
        while y < y1 - 4.0:
            w = rng.uniform(3.8, 6.0)
            d = rng.uniform(3.6, 6.2)
            h = rng.uniform(2.4, 3.4)
            if kind != "mid" and rng.random() < 0.12:
                h = 5.2                       # 2층집
            if kind == "mid":
                w, h = min(w, 4.4), 2.5
            x = (a + b) * 0.5 + rng.uniform(-0.9, 0.7)
            rot = math.radians(rng.uniform(-9.0, 9.0))
            skip = rng.random() < 0.10
            if not skip and not blocked(x, y, max(w, d) * 0.5):
                if kind != "mid" and rng.random() < 0.09:     # 나무 한 그루
                    trees.cylinder(0.12, 0.10, zz, zz + 1.6, center_xy=(x, y), segments=6, mat=0)
                    trees.sphere((1.5, 1.5, 1.3), center=(x, y, zz + 2.4), segments=8, rings=6, mat=1)
                else:
                    wm = rng.randrange(len(WALL_MATS))
                    rm = rng.randrange(len(ROOF_MATS))
                    roof = "gable" if rng.random() < 0.65 else "flat"
                    m_rot = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(rot, 4, 'Z') @ Matrix.Translation((-x, -y, 0))
                    _house(walls, x, y, zz, w, d, h, rot=rot, roof="none", mat_wall=wm)
                    _roof_only(roofs, x, y, zz, w, d, h, roof, rm, rot)
                    # 서쪽(바다·CUT8 카메라 쪽) 창문
                    n_win = 2 if d > 4.8 else 1
                    floors = 2 if h > 4.5 else 1
                    for fl in range(floors):
                        for k in range(n_win):
                            wy = y + (k - (n_win - 1) * 0.5) * d * 0.42
                            wz = zz + (1.45 + fl * 2.5 if floors > 1 else h * 0.55)
                            wx = x - w * 0.5 - 0.03
                            p = m_rot @ Vector((wx, wy, wz))
                            wins.box((0.05, 0.85, 0.8), center=p, rot_z=rot, mat=0)
                            lit_candidates.append((p, rot))
            y += d + rng.uniform(1.4, 3.6)
    walls.to_object("D_주택_벽", col, [M.get(n) for n in WALL_MATS])
    roofs.to_object("D_주택_지붕", col, [M.get(n) for n in ROOF_MATS])
    wins.to_object("D_창문_꺼짐", col, [M.get("window_dark", roughness=0.35)])
    trees.to_object("D_나무", col, [M.get("wood_dark"), M.get("leaf")])

    # --- 켜지는 창문 (Emission 판을 하나씩 보이게) ---
    rng2 = random.Random(config.RANDOM_SEED + 1)
    # CUT8 카메라에서 잘 보이는 창(아래쪽 테라스·중간) 위주로 고름
    # CUT8 화면 가운데(마을 중턱)에 고르게 퍼지도록 후보를 고름
    lit_candidates.sort(key=lambda pr: (abs(pr[0].y - 10.0) * 0.6 + abs(pr[0].z - 16.0) * 1.2))
    pick = lit_candidates[:max(config.WINDOW_LIGHTS_AT_END * 2, 30)]
    rng2.shuffle(pick)
    lcol = get_collection("D_켜지는창문", col)
    for i, (p, rot) in enumerate(pick[:config.WINDOW_LIGHTS_AT_END]):
        mb = MeshBuilder()
        mb.box((0.04, 0.82, 0.77), mat=0)
        ob = mb.to_object("D_창문불_%02d" % (i + 1), lcol, [M.get("window_lit", emission=6.0)],
                          location=p + Vector((-0.02, 0, 0)))
        ob.rotation_euler = (0.0, 0.0, rot)
        L.window_lights.append(ob)

    # --- 항구: 방파제, 배, 창고 ---
    mb = MeshBuilder()
    mb.box_between(Vector((quay_x0 - 4, -24, 0.9)), Vector((quay_x0 - 50, 20, 0.9)), 6.0, 2.6, mat=0)
    mb.box_between(Vector((quay_x0 - 2, 40, 0.9)), Vector((quay_x0 - 40, 48, 0.9)), 5.0, 2.6, mat=0)
    mb.to_object("D_방파제", col, [M.get("quay")])
    mb = MeshBuilder()
    for (bx, by, rot) in [(-14, -6, 8), (-15, 3, -5), (-18, 12, 12), (-13, 20, 0), (-20, -14, -10)]:
        bxw = quay_x0 + bx
        m = Matrix.Translation((bxw, by, 0.35)) @ Matrix.Rotation(math.radians(rot + 90), 4, 'Z')
        mb.box((7.5, 2.3, 1.2), mat=0, matrix=m)
        mb.box((2.2, 1.8, 1.4), center=(0.8, 0, 1.2), mat=1, matrix=m)
    mb.to_object("D_배", col, [M.get("boat_hull"), M.get("boat_blue")])
    mb = MeshBuilder()
    for k, yy in enumerate((-36, -20, 30, 50)):
        _house(mb, quay_x0 + 3.2, yy, 1.5, 5.5, 11.0, 4.2, roof="flat", mat_wall=0, mat_roof=1)
    mb.to_object("D_항구창고", col, [M.get("wall_bluegrey"), M.get("roof_grey")])

    # --- 등대 곶 + 등대 ---
    lx, ly = config.LIGHTHOUSE_XY
    mb = MeshBuilder()
    zt = config.LIGHTHOUSE_BASE_Z
    mb.cylinder(22.0, 12.0, -2.0, zt - 4.0, center_xy=(lx, ly), segments=18, mat=0)
    mb.cylinder(12.0, 8.5, zt - 4.0, zt, center_xy=(lx, ly), segments=18, mat=1)
    for k in range(5):
        a = k * 1.3
        mb.sphere((2.2, 2.2, 1.6), center=(lx + math.cos(a) * 7.0, ly + math.sin(a) * 7.0, zt + 0.6), segments=8, rings=5, mat=2)
    mb.to_object("D_등대곶", col, [M.get("hill_rock"), M.get("hill_grass"), M.get("leaf")])
    hl = config.LIGHTHOUSE_HEIGHT
    mb = MeshBuilder()
    mb.cylinder(2.5, 1.8, zt, zt + hl, center_xy=(lx, ly), segments=16, mat=0)
    mb.cylinder(2.3, 2.3, zt + hl, zt + hl + 0.35, center_xy=(lx, ly), segments=16, mat=0)
    mb.cylinder(1.35, 1.35, zt + hl + 0.35, zt + hl + 2.4, center_xy=(lx, ly), segments=12, mat=1)
    mb.cylinder(1.6, 0.2, zt + hl + 2.4, zt + hl + 3.6, center_xy=(lx, ly), segments=12, mat=2)
    mb.to_object("D_등대", col, [M.get("lighthouse"), M.get("lantern", roughness=0.25), M.get("roof_grey")])

    # --- 바다 ---
    mb = MeshBuilder()
    mb.box((3000.0, 3000.0, 0.1), center=(-400.0, 0.0, config.SEA_LEVEL_Z - 0.05), mat=0)
    L.props["sea"] = mb.to_object("D_바다", col, [M.sea_material()])
    L.quay_x = quay_x1
    return col


def _roof_only(mb, x, y, zz, w, d, h, roof, rm, rot=0.0):
    m = Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(rot, 4, 'Z')
    if roof == "gable":
        ov = 0.3
        for sx in (-1, 1):
            p0 = Vector((sx * (w * 0.5 + ov), 0, zz + h - 0.12))
            p1 = Vector((0, 0, zz + h + w * 0.2))
            mid = (p0 + p1) * 0.5
            ang = math.atan2(p1.z - p0.z, abs(p1.x - p0.x))
            mb.box(((p1 - p0).length + 0.05, d + ov * 2, 0.14), mat=rm,
                   matrix=m @ Matrix.Translation(mid) @ Matrix.Rotation(-sx * ang, 4, 'Y'))
        mb.box((w * 0.9, d * 0.96, w * 0.14), center=(0, 0, zz + h + w * 0.07), mat=rm, matrix=m)
    else:
        mb.box((w + 0.3, d + 0.3, 0.18), center=(0, 0, zz + h + 0.09), mat=rm, matrix=m)
