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
from utils import MeshBuilder, get_collection, heading_vec, rot2, smoothstep


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
    mb.to_object("C_집_문창", col, [M.get("gate_jade", roughness=0.45), M.get("window_dark", roughness=0.3)])   # v2: 옥색 문

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
    for name in ("cup_citizen", "cup_main"):
        mb = MeshBuilder()
        mb.cylinder(0.034, 0.042, 0.0, 0.075, segments=12, mat=0)
        mb.cylinder(0.036, 0.036, 0.055, 0.058, segments=12, mat=1)
        ob = mb.to_object("C_찻잔_" + ("시민" if name == "cup_citizen" else "주인공"), col,
                          [M.get("cup", roughness=0.4), M.get("tea", roughness=0.2)])
        L.props[name] = ob

    # 안내 자료(큰 태블릿): 왼쪽 = ① 분납 안내, 오른쪽 = ② 복지서비스 연계. 글자 없이 색·모양으로 구분.
    #   ① 차가운 파랑 + 네모난 아이콘: 달력(3칸 표시 = 달마다 나눠 냄) + 세 토막 막대, 위쪽 점 1개
    #   ② 따뜻한 산호색 + 둥근 아이콘: 손잡은 사람 둘 + 하트 + 이어진 점 셋(기관 연결), 위쪽 점 2개
    # 로컬 +Y = 두 사람 쪽(화면에서 위), 로컬 +X = 주인공 쪽(화면 오른쪽)
    mb = MeshBuilder()
    tw, td = config.TABLET_SIZE
    mb.box((tw, td, 0.014), center=(0, 0, 0.007), mat=0)
    mb.box((tw - 0.024, td - 0.024, 0.002), center=(0, 0, 0.0145), mat=1)
    pw, ph = tw * 0.5 - 0.03, td - 0.05
    for sx, pm in ((-1, 2), (1, 3)):
        mb.box((pw, ph, 0.003), center=(sx * tw * 0.25, 0, 0.0165), mat=pm)
    z1, z2 = 0.0195, 0.0225                    # 아이콘 판 높이 (겹침 방지용 층)
    cxl, cxr = -tw * 0.25, tw * 0.25
    # ① 분납: 달력
    mb.box((0.14, 0.13, 0.003), center=(cxl, 0.02, z1), mat=4)
    mb.box((0.14, 0.03, 0.003), center=(cxl, 0.07, z2), mat=5)
    for rx in (-0.038, 0.038):
        mb.box((0.012, 0.026, 0.004), center=(cxl + rx, 0.088, z2 + 0.001), mat=5)
    for col_ in range(3):
        for row in range(2):
            hot = row == 0
            mb.box((0.03, 0.026, 0.003), center=(cxl - 0.042 + col_ * 0.042, 0.022 - row * 0.036, z2), mat=5 if hot else 6)
    for k in range(3):                         # 세 토막 막대 (나눠 내기)
        mb.box((0.046, 0.024, 0.003), center=(cxl - 0.052 + k * 0.052, -0.085, z1), mat=5)
    mb.cylinder(0.011, 0.011, z1 - 0.0015, z1 + 0.0015, center_xy=(cxl - pw * 0.5 + 0.025, ph * 0.5 - 0.022),
                segments=10, mat=4)                # 위쪽 점 1개 (①)
    # ② 복지 연계: 사람 둘(머리+몸) + 맞잡은 손 + 하트 + 연결된 점 셋
    for sx in (-1, 1):
        x = cxr + sx * 0.052
        mb.cylinder(0.021, 0.021, z1 - 0.0015, z1 + 0.0015, center_xy=(x, 0.052), segments=14, mat=4)
        mb.cylinder(0.034, 0.034, z1 - 0.0015, z1 + 0.0015, center_xy=(x, -0.004), segments=14, mat=4)
        mb.box((0.068, 0.034, 0.003), center=(x, -0.021, z1), mat=4)
    mb.box((0.05, 0.012, 0.003), center=(cxr, -0.004, z2), mat=4)
    for sx in (-1, 1):                         # 하트 (원 두 개 + 45° 네모)
        mb.cylinder(0.013, 0.013, z2 - 0.0015, z2 + 0.0015, center_xy=(cxr + sx * 0.0095, 0.066), segments=12, mat=7)
    mb.box((0.024, 0.024, 0.003), center=(cxr, 0.057, z2), rot_z=math.radians(45), mat=7)
    for k in (-1, 0, 1):
        mb.cylinder(0.012, 0.012, z1 - 0.0015, z1 + 0.0015, center_xy=(cxr + k * 0.055, -0.085), segments=12, mat=4)
    mb.box((0.11, 0.006, 0.003), center=(cxr, -0.085, z1 - 0.0005), mat=4)
    for k in (0, 1):                           # 위쪽 점 2개 (②)
        mb.cylinder(0.011, 0.011, z1 - 0.0015, z1 + 0.0015,
                    center_xy=(cxr - pw * 0.5 + 0.025 + k * 0.03, ph * 0.5 - 0.022), segments=10, mat=4)
    tab = mb.to_object("C_안내태블릿", col, [M.get("tablet_body", roughness=0.4), M.get("screen_base", emission=0.25),
                                               M.get("panel_installment", emission=0.35),
                                               M.get("panel_welfare", emission=0.35), M.get("icon_white", emission=0.5),
                                               M.get("icon_navy", emission=0.3), M.get("icon_cell", emission=0.4),
                                               M.get("icon_heart", emission=0.45)])
    L.props["tablet"] = tab
    mb = MeshBuilder()   # 받침대 (태블릿 뒤쪽 = 두 사람 쪽 가장자리를 들어 올림)
    stand_h = td * math.sin(math.radians(config.TABLET_TILT)) - 0.012
    mb.box((tw * 0.8, 0.03, stand_h), center=(0, 0.0, stand_h * 0.5), mat=0)
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

    def ridge(x, y):
        """v2: 윗동네 테라스를 가운데가 솟은 언덕 모양으로 (CUT8 마을 실루엣이 평평한 탁자처럼 보이지 않게)."""
        return config.HILL_RIDGE_HEIGHT * math.exp(-((y - 14.0) / 42.0) ** 2) * smoothstep((x - 18.0) / 30.0)

    def segmented(a, b, zz, zbase, mat):
        """테라스를 길이 방향으로 잘라 높이를 조금씩 달리함 (일직선 옹벽 느낌 줄이기)."""
        yy = y0
        while yy < y1:
            ln = rng.uniform(14.0, 30.0)
            dz = rng.uniform(-0.35, 0.35)
            ye = min(y1, yy + ln)
            ys = yy
            while ys < ye - 1e-6:                   # 언덕 높이를 따라가도록 8m 이하로 나눠 세움
                yn = min(ye, ys + 8.0)
                mb.prism([(a, ys), (b, ys), (b, yn), (a, yn)], zbase, zz + dz + ridge((a + b) * 0.5, (ys + yn) * 0.5), mat=mat)
                ys = yn
            yy += ln
    for (a, b, zz) in terraces:
        segmented(a, b, zz, -2.0, 0)
    mb.prism([(quay_x0, y0 + 4), (quay_x1, y0 + 4), (quay_x1, y1 - 10), (quay_x0, y1 - 10)], -2.0, 1.5, mat=1)
    for (a, b, zz) in up_terraces:
        segmented(a, b, zz, zu - 1.0, 2)
    last = up_terraces[-1]
    yy = y0
    while yy < y1:                                  # 마을 뒤 언덕 (가운데가 솟은 능선)
        yn = min(y1, yy + 8.0)
        mb.prism([(last[1], yy), (last[1] + 60.0, yy), (last[1] + 60.0, yn), (last[1], yn)], zu,
                 last[2] + 3.0 + ridge(last[1] + 6.0, (yy + yn) * 0.5), mat=3)
        yy = yn
    # v2: 대문·마당 북쪽으로 계단처럼 올라가는 윗동네 (CUT1 계단 너머로 겹겹이 쌓인 집, CUT8 실루엣 보강)
    north_rows = []
    for k, (ya_, yb_) in enumerate(((11.0, 18.0), (18.0, 25.0), (25.0, 32.0), (32.0, 46.0), (46.0, 84.0))):
        zz = zu + 2.3 * (k + 1)
        north_rows.append((ya_, yb_, zz))
        mb.prism([(-0.6, ya_), (11.8, ya_), (11.8, yb_), (-0.6, yb_)], zu - 1.0, zz, mat=0)
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
    tanks = MeshBuilder()
    rng3 = random.Random(config.RANDOM_SEED + 2)     # v2 추가 요소용 (기존 배치 난수 순서는 그대로)
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
                zz0 = zz
                zz = zz0 + (ridge(x, y) if kind == "up" else 0.0)
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
                    if roof == "flat" and rng3.random() < 0.45:   # v2: 옥상 파란 물탱크
                        tanks.cylinder(0.42, 0.42, zz + h + 0.18, zz + h + 1.0, center_xy=(x + w * 0.2, y - d * 0.15),
                                       segments=10, mat=0)
                zz = zz0
            y += d + rng.uniform(1.4, 3.6)
    for (ya_, yb_, zz) in north_rows:               # v2: 윗동네 집 (서쪽 창 = CUT8, 남쪽 창 = CUT1)
        yc = ya_
        while yc + 6.5 <= yb_ + 1e-6:
            x = -0.2 + rng3.uniform(0.0, 1.2)
            while x + 3.4 < 11.6:                    # 윗동네 테라스(x -0.6 ~ 11.8) 안에서만
                w, d = min(rng3.uniform(3.4, 5.0), 11.6 - x), rng3.uniform(3.4, 5.0)
                h = 5.0 if rng3.random() < 0.15 else rng3.uniform(2.4, 3.2)
                cx, cy = x + w * 0.5, yc + 3.5 + rng3.uniform(-0.6, 0.6)
                rot = math.radians(rng3.uniform(-7.0, 7.0))
                roof = "gable" if rng3.random() < 0.6 else "flat"
                _house(walls, cx, cy, zz, w, d, h, rot=rot, roof="none", mat_wall=rng3.randrange(len(WALL_MATS)))
                _roof_only(roofs, cx, cy, zz, w, d, h, roof, rng3.randrange(len(ROOF_MATS)), rot)
                if roof == "flat" and rng3.random() < 0.5:
                    tanks.cylinder(0.42, 0.42, zz + h + 0.18, zz + h + 1.0, center_xy=(cx - w * 0.2, cy), segments=10, mat=0)
                m_rot = Matrix.Translation((cx, cy, 0)) @ Matrix.Rotation(rot, 4, 'Z') @ Matrix.Translation((-cx, -cy, 0))
                wz = zz + (1.45 if h > 4.5 else h * 0.55)
                p = m_rot @ Vector((cx - w * 0.5 - 0.03, cy, wz))
                wins.box((0.05, 0.85, 0.8), center=p, rot_z=rot, mat=0)
                lit_candidates.append((p, rot))
                ps = m_rot @ Vector((cx, cy - d * 0.5 - 0.03, wz))
                wins.box((0.85, 0.05, 0.8), center=ps, rot_z=rot, mat=0)
                x += w + rng3.uniform(0.8, 2.2)
            yc += 7.0
    walls.to_object("D_주택_벽", col, [M.get(n) for n in WALL_MATS])
    roofs.to_object("D_주택_지붕", col, [M.get(n) for n in ROOF_MATS])
    wins.to_object("D_창문_꺼짐", col, [M.get("window_dark", roughness=0.35)])
    for k in range(9):                               # v2: 능선 위 나무
        tx, ty = last[1] + rng3.uniform(2.0, 14.0), -30.0 + k * 11.0 + rng3.uniform(-3.0, 3.0)
        tz = last[2] + 3.0 + ridge(last[1] + 6.0, ty)
        trees.cylinder(0.15, 0.12, tz, tz + 2.0, center_xy=(tx, ty), segments=6, mat=0)
        trees.sphere((2.0, 2.0, 1.7), center=(tx, ty, tz + 2.9), segments=8, rings=6, mat=1)
    trees.to_object("D_나무", col, [M.get("wood_dark"), M.get("leaf")])
    tanks.to_object("D_옥상물탱크", col, [M.get("water_tank")])

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
        ob = mb.to_object("D_창문불_%02d" % (i + 1), lcol, [M.get("window_lit", emission=config.WINDOW_LIGHT_EMISSION)],
                          location=p + Vector((-0.02, 0, 0)))
        ob.rotation_euler = (0.0, 0.0, rot)
        L.window_lights.append(ob)

    # --- 항구: 방파제, 배, 창고 ---
    mb = MeshBuilder()
    mb.box_between(Vector((quay_x0 - 4, -24, 0.9)), Vector((quay_x0 - 50, 20, 0.9)), 6.0, 2.6, mat=0)
    mb.box_between(Vector((quay_x0 - 2, 40, 0.9)), Vector((quay_x0 - 40, 48, 0.9)), 5.0, 2.6, mat=0)
    mb.to_object("D_방파제", col, [M.get("quay")])
    mb = MeshBuilder()   # v2: 선체 + 이물 + 조타실 + 돛대 모양의 어선
    for k, (bx, by, rot) in enumerate([(-14, -6, 8), (-15, 3, -5), (-18, 12, 12), (-13, 20, 0), (-20, -14, -10),
                                       (-12, 30, 4), (-17, -22, -6)]):
        _boat(mb, quay_x0 + bx, by, 180.0 + rot, 7.5, hull=(0, 2, 3)[k % 3], cabin=1, mast=4)
    mb.to_object("D_배", col, [M.get("boat_hull"), M.get("boat_hull"), M.get("boat_blue"), M.get("boat_red"),
                              M.get("rail")])
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
    L.quay_x0 = quay_x0
    L.terraces = terraces
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


# =============================================================================
# E. 묵호·논골담길 로컬리티 (v2) — 단순 프록시만
#   골목(CUT1·7): 벽화, 계단 화분, 전봇대·전선, 골목을 가로지르는 빨래, 벽 설비(계량기·실외기·방범창·파란 문)
#   마당(CUT3~6): 부표, 그물 더미, 스티로폼 상자 텃밭, 빨간 고무대야, 오징어 덕장
#   엔딩(CUT7·8): 등대 곶 옆 방파제 + 빨간 등대, 어선, 가로등(컷8에 켜짐)
# =============================================================================
def _frame(origin, ax_u, ax_n):
    """벽면 로컬 좌표계: u = 벽을 따라, n = 벽에서 바깥(보는 쪽), z = 위."""
    u = Vector((ax_u[0], ax_u[1], 0.0)).normalized()
    n = Vector((ax_n[0], ax_n[1], 0.0)).normalized()
    m = Matrix.Identity(4)
    for i in range(3):
        m[i][0], m[i][1], m[i][2], m[i][3] = u[i], n[i], (0.0, 0.0, 1.0)[i], origin[i]
    return m


def _wall_disc(mb, fr, u, z, r, layer, mat, segments=14):
    """벽면(fr)에 붙는 원판. layer = 벽에서 띄우는 거리(겹침 방지)."""
    m = fr @ Matrix.Translation((u, layer, z)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    mb.cylinder(r, r, -0.004, 0.004, segments=segments, mat=mat, matrix=m)


def _wall_rect(mb, fr, u0, u1, z0, z1, layer, mat, rot=0.0):
    mb.box((u1 - u0, 0.008, z1 - z0), center=((u0 + u1) * 0.5, layer, (z0 + z1) * 0.5), mat=mat,
           matrix=fr @ Matrix.Translation(((u0 + u1) * 0.5, 0, (z0 + z1) * 0.5)) @ Matrix.Rotation(rot, 4, 'Y')
           @ Matrix.Translation((-(u0 + u1) * 0.5, 0, -(z0 + z1) * 0.5)))


MURAL_MATS = ["mural_sky", "mural_sea", "icon_white", "mural_sun", "mural_fish", "mural_dark", "lighthouse",
              "mural_red", "mural_yellow", "mural_green", "roof_slate"]


def _mural_sea(mb, fr, u0, u1, z0, z1):
    """바다 벽화: 하늘 · 물결(반원 파도 + 물결선) · 해 · 큰 물고기 · 작은 등대 · 갈매기 (묵호 바다 풍경)."""
    w, h = u1 - u0, z1 - z0
    _wall_rect(mb, fr, u0, u1, z0, z1, 0.010, 0)                              # 하늘
    _wall_rect(mb, fr, u0, u1, z0, z0 + h * 0.42, 0.020, 1)                   # 바다 (파도 원판 아래 절반을 가림)
    k = 0
    while u0 + 0.10 + k * 0.20 < u1 - 0.05:                                   # 파도 마루: 반원이 이어진 물결
        _wall_disc(mb, fr, u0 + 0.10 + k * 0.20, z0 + h * 0.42, 0.10, 0.015, 2)
        k += 1
    for row, zz in enumerate((0.30, 0.17)):                                   # 바다 속 물결선
        k = 0
        while u0 + 0.12 + k * 0.42 + row * 0.2 < u1 - 0.3:
            uu = u0 + 0.12 + k * 0.42 + row * 0.2
            _wall_rect(mb, fr, uu, uu + 0.24, z0 + h * zz, z0 + h * zz + 0.035, 0.026, 2)
            k += 1
    _wall_disc(mb, fr, u1 - w * 0.18, z0 + h * 0.78, h * 0.12, 0.014, 3)       # 해
    fu, fz = u0 + w * 0.52, z0 + h * 0.64                                     # 물고기
    mb.sphere((w * 0.16, 0.012, h * 0.11), center=(fu, 0.026, fz), segments=14, rings=6, mat=4, matrix=fr)
    _wall_rect(mb, fr, fu + w * 0.13, fu + w * 0.22, fz - h * 0.07, fz + h * 0.07, 0.024, 4, rot=math.radians(45))
    _wall_disc(mb, fr, fu - w * 0.09, fz + h * 0.02, h * 0.022, 0.040, 5)
    lu = u0 + w * 0.13                                                        # 등대
    _wall_rect(mb, fr, lu - 0.09, lu + 0.09, z0 + h * 0.40, z0 + h * 0.80, 0.030, 6)
    _wall_rect(mb, fr, lu - 0.11, lu + 0.11, z0 + h * 0.80, z0 + h * 0.90, 0.032, 7)
    for gu, gz in ((0.30, 0.86), (0.36, 0.80)):                               # 갈매기
        _wall_rect(mb, fr, u0 + w * gu - 0.07, u0 + w * gu, z0 + h * gz, z0 + h * gz + 0.025, 0.030, 5, rot=math.radians(25))
        _wall_rect(mb, fr, u0 + w * gu, u0 + w * gu + 0.07, z0 + h * gz, z0 + h * gz + 0.025, 0.030, 5, rot=math.radians(-25))


def _mural_houses(mb, fr, u0, u1, z0, z1):
    """언덕 마을 벽화: 노란 바탕 + 계단처럼 올라가는 박공지붕 집들 + 파란 물결 띠 + 해."""
    w, h = u1 - u0, z1 - z0
    _wall_rect(mb, fr, u0, u1, z0, z1, 0.010, 8)
    _wall_rect(mb, fr, u0, u1, z0, z0 + h * 0.16, 0.018, 1)
    walls_ = [7, 9, 0, 4, 1, 7]
    roofs_ = [10, 5, 7, 10, 5, 10]
    n = 6
    for k in range(n):
        cu = u0 + w * (k + 0.5) / n
        base = z0 + h * (0.20 + 0.085 * k)
        hw = w / n * 0.36
        top = base + h * 0.20
        a = 1.1 * hw * math.sqrt(2.0)                                         # 45° 돌린 정사각형의 윗 절반 = 박공지붕
        _wall_rect(mb, fr, cu - a * 0.5, cu + a * 0.5, top - a * 0.5, top + a * 0.5, 0.016, roofs_[k], rot=math.radians(45))
        _wall_rect(mb, fr, cu - hw, cu + hw, base, top, 0.020, walls_[k])
        _wall_rect(mb, fr, cu - hw * 0.62, cu - hw * 0.12, base + h * 0.09, base + h * 0.15, 0.026, 2)
        _wall_rect(mb, fr, cu + hw * 0.18, cu + hw * 0.55, base, base + h * 0.11, 0.026, 5)
    _wall_disc(mb, fr, u1 - w * 0.10, z1 - h * 0.16, h * 0.09, 0.020, 3)


def _utility_pole(mb, x, y, z, h):
    mb.cylinder(0.13, 0.10, z, z + h, center_xy=(x, y), segments=8, mat=0)
    mb.box((1.3, 0.10, 0.10), center=(x, y, z + h - 0.35), mat=0)
    mb.box((0.9, 0.10, 0.10), center=(x, y, z + h - 0.9), mat=0)
    mb.cylinder(0.16, 0.16, z + h - 1.7, z + h - 1.2, center_xy=(x + 0.25, y), segments=8, mat=0)   # 변압기
    return Vector((x, y, z + h - 0.3))


def _wire(mb, p0, p1, sag, mat=1, segs=10, r=0.018):
    pts = []
    for i in range(segs + 1):
        t = i / segs
        p = p0.lerp(p1, t)
        p.z -= sag * 4.0 * t * (1.0 - t)
        pts.append(p)
    for a, b in zip(pts, pts[1:]):
        mb.box_between(a, b, r, r, mat=mat)


def _laundry(col, pa, pb, items, name, cloths):
    mb = MeshBuilder()
    mb.box_between(pa, pb, 0.012, 0.012, mat=0)
    mb.to_object(name + "_줄", col, [M.get("rail")])
    for k, (t, w, h, cm) in enumerate(items):
        p = pa.lerp(pb, t)
        mb = MeshBuilder()
        mb.box((0.012, w, h), center=(0, 0, -h * 0.5), mat=0)
        ob = mb.to_object("%s_%d" % (name, k + 1), col, [M.get(cm)], location=p)
        ob.rotation_euler = (0, 0, math.atan2(pb.y - pa.y, pb.x - pa.x) - math.pi * 0.5)
        cloths.append(ob)


def _float(mb, x, y, z, r, mat):
    mb.sphere((r, r, r * 0.92), center=(x, y, z), segments=10, rings=7, mat=mat)


def _styro_box(mb, x, y, z, rot=0.0):
    """스티로폼 생선 상자에 심은 상추·파 (바닷마을 텃밭)."""
    m = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(rot, 4, 'Z')
    mb.box((0.62, 0.42, 0.30), center=(0, 0, z + 0.15), mat=0, matrix=m)
    for k in range(3):
        mb.sphere((0.13, 0.11, 0.09), center=(-0.19 + k * 0.19, 0, z + 0.32), segments=8, rings=5, mat=1, matrix=m)


def _boat(mb, x, y, heading, length, hull, cabin, mast):
    """어선: 선체 + 뾰족한 이물 + 조타실 + 돛대·깃발."""
    m = Matrix.Translation((x, y, 0.0)) @ Matrix.Rotation(math.radians(90.0 - heading), 4, 'Z')
    L_, W_ = length, length * 0.30
    mb.box((L_ * 0.8, W_, 0.9), center=(-L_ * 0.1, 0, 0.35), mat=hull, matrix=m)
    mb.box((L_ * 0.28, W_ * 0.72, 0.9), center=(L_ * 0.38, 0, 0.42), rot_z=math.radians(45), mat=hull, matrix=m)
    mb.box((L_ * 0.22, W_ * 0.72, 1.1), center=(-L_ * 0.24, 0, 1.3), mat=cabin, matrix=m)
    mb.cylinder(0.07, 0.05, 0.8, 0.8 + L_ * 0.42, center_xy=(L_ * 0.05, 0), segments=6, mat=mast, matrix=m)
    mb.box((0.6, 0.04, 0.35), center=(L_ * 0.05 - 0.3, 0, 0.8 + L_ * 0.40), mat=cabin, matrix=m)


def build_locality_set(layout, parent):
    col = get_collection("SET_E_묵호_로컬리티", parent)
    L = layout
    zl, zu = L.z_low, L.z_up
    x_west = config.LOWER_STREET_WEST_X
    br, tr = L.terrace_edge[2], L.terrace_edge[1]
    cloths = L.props.setdefault("laundry", [])

    # --- A. 골목 벽화 (CUT1 오른쪽 벽) ---
    mb = MeshBuilder()
    face = Vector((br.x - 0.035, 0.0, 0.0))                     # 아랫골목 동쪽 벽(서쪽을 봄)
    fr = _frame(face, (0.0, -1.0), (-1.0, 0.0))                # u = 남쪽(-Y)으로, n = 서쪽(-X)
    y_end = br.y - 0.55                                          # CUT1 화면에 보이는 벽 구간: y ≈ -12.7 ~ -9.5
    _mural_sea(mb, fr, -y_end, -y_end + 2.9, zl + 0.45, zl + 2.30)
    # 윗단 남쪽 담벼락 벽화 (CUT7 에서 계단 왼쪽, CUT2 배경) — 북쪽을 보는 벽
    wall_y = -9.05
    mb2 = MeshBuilder()
    mb2.box((4.4, 0.22, 2.25), center=(-2.25, wall_y - 0.11, zu + 1.125), mat=0)
    mb2.to_object("E_윗단_담벼락", col, [M.get("wall_white")])
    fr2 = _frame(Vector((0.0, wall_y, 0.0)), (1.0, 0.0), (0.0, 1.0))
    _mural_houses(mb, fr2, -4.35, -2.15, zu + 0.35, zu + 2.05)
    mb.to_object("E_벽화", col, [M.get(n) for n in MURAL_MATS])

    # --- 벽 설비: 방범창 창문·파란 문·가스계량기·배관·에어컨 실외기 (CUT1 오른쪽 벽) ---
    mb = MeshBuilder()
    fx = br.x - 0.03
    mb.box((0.18, 0.26, 0.34), center=(fx - 0.09, y_end + 0.3, zl + 1.15), mat=3)             # 가스계량기
    mb.cylinder(0.025, 0.025, zl + 0.2, zl + 2.85, center_xy=(fx - 0.06, y_end + 0.12), segments=6, mat=3)
    mb.box((0.30, 0.75, 0.52), center=(fx - 0.15, y_end - 1.2, zl + 2.62), mat=3)             # 에어컨 실외기
    m = Matrix.Translation((fx - 0.31, y_end - 1.2, zl + 2.62)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
    mb.cylinder(0.19, 0.19, -0.005, 0.005, segments=14, mat=1, matrix=m)
    mb.box((0.72, 0.07, 1.95), center=(-1.59, wall_y + 0.035, zu + 0.975), mat=2)                 # 윗단 담벼락 파란 문
    mb.box((0.8, 0.06, 0.55), center=(-0.55, wall_y + 0.03, zu + 1.55), mat=0)                   # 방범창 창
    for k in range(4):
        mb.box((0.025, 0.03, 0.55), center=(-0.85 + k * 0.2, wall_y + 0.075, zu + 1.55), mat=1)
    mb.to_object("E_벽_설비", col, [M.get("window_dark", roughness=0.3), M.get("rail"), M.get("door_blue"),
                                    M.get("meter_grey")])

    # --- 화분: 계단 가장자리(벽 쪽)·계단 아래·담장 위, 스티로폼 텃밭 ---
    mb = MeshBuilder()
    for i, (r, fl) in zip((2, 5, 8, 11, 14), ((0.13, True), (0.11, False), (0.12, True), (0.10, True), (0.12, False))):
        p = L.stair_point((i + 0.5) * L.st_run, -(L.st_w * 0.5 - 0.17))
        _pot(mb, p.x, p.y, p.z, r=r, h=r * 1.9, flower=fl)
    for (dx, dy, r, fl) in ((-0.5, -0.45, 0.17, True), (-0.9, -0.2, 0.13, False), (-0.35, -1.25, 0.15, True)):
        _pot(mb, br.x + dx, br.y + dy, zl, r=r, h=r * 1.8, flower=fl)
    for k in range(6):                                          # 벽화 벽 아래 화분 줄
        _pot(mb, br.x - 0.3, y_end - 0.5 - k * 0.62, zl, r=0.11 + 0.03 * (k % 2), h=0.24, flower=k % 3 != 1)
    for t in (0.25, 0.55, 0.8):                                 # 계단 옆 담장 위
        p = br.lerp(tr, t)
        _pot(mb, p.x + 0.12, p.y - 0.09, zu + 0.9, r=0.1, h=0.18, flower=True)
    mb.to_object("E_골목화분", col, _pot_mats())
    mb = MeshBuilder()
    bl = L.terrace_edge[3]
    _styro_box(mb, bl.x - 0.55, bl.y - 0.75, zl, rot=math.radians(35))
    _styro_box(mb, x_west + 0.45, config.CAM_CUT01["start_xy"][1] + 9.0, zl, rot=math.radians(90))
    _styro_box(mb, 1.5, -4.6, zu)
    _styro_box(mb, 2.25, -4.6, zu, rot=math.radians(4))
    _styro_box(mb, 0.75, 2.75, zu, rot=math.radians(90))
    mb.to_object("E_스티로폼텃밭", col, [M.get("styrofoam"), M.get("leaf")])

    # --- 전봇대와 전선 (골목 하늘을 가로지름) ---
    mb = MeshBuilder()
    pa = _utility_pole(mb, x_west + 0.3, br.y - 0.2, zl, 7.6)
    pb = _utility_pole(mb, tr.x - 0.85, tr.y + 2.8, zu, 6.4)
    pc = _utility_pole(mb, x_west + 0.3, 7.0, zl, 7.6)
    for dz in (0.0, -0.55, -1.1):
        _wire(mb, pa + Vector((0, 0, dz)), pb + Vector((0, 0, dz)), 0.45 + 0.05 * dz, mat=1)
        _wire(mb, pa + Vector((0, 0, dz)), pc + Vector((0, 0, dz)), 0.9, mat=1)
    _wire(mb, pa + Vector((0, 0, -1.4)), Vector((br.x - 0.1, br.y - 3.0, zl + 3.0)), 0.3, mat=1)
    mb.to_object("E_전봇대_전선", col, [M.get("pole_grey"), M.get("wire")])

    # --- 골목을 가로지르는 빨랫줄 (CUT1: 계단 왼쪽 너머) ---
    _laundry(col, Vector((x_west + 0.3, 1.2, zl + 2.7)), Vector((L.terrace_edge[0].x - 0.05, 1.9, zl + 2.55)),
             [(0.15, 0.45, 0.6, "cloth_2"), (0.33, 0.38, 0.5, "cloth_3"), (0.52, 0.5, 0.7, "cloth_1"),
              (0.70, 0.36, 0.45, "mural_red"), (0.86, 0.42, 0.55, "cloth_2")], "E_골목빨래", cloths)

    # --- B. 마당: 오징어 덕장, 부표, 그물 더미, 빨간 고무대야 ---
    mb = MeshBuilder()
    ya, yb = -3.95, -2.05
    for yy in (ya, yb):
        mb.cylinder(0.035, 0.035, zu, zu + 1.6, center_xy=(0.62, yy), segments=6, mat=0)
    mb.box_between(Vector((0.62, ya, zu + 1.55)), Vector((0.62, yb, zu + 1.55)), 0.035, 0.035, mat=0)
    n_sq = 6
    for k in range(n_sq):                                       # 반쯤 말린 오징어 (몸통 + 지느러미 + 다리)
        yy = ya + (k + 0.5) * (yb - ya) / n_sq
        mb.box((0.012, 0.13, 0.26), center=(0.62, yy, zu + 1.36), mat=1)
        mb.box((0.012, 0.09, 0.09), center=(0.62, yy, zu + 1.50), rot_z=0.0, mat=1,
               matrix=Matrix.Translation((0.62, yy, zu + 1.50)) @ Matrix.Rotation(math.radians(45), 4, 'X')
               @ Matrix.Translation((-0.62, -yy, -(zu + 1.50))))
        for j in (-1, 0, 1):
            mb.box((0.01, 0.014, 0.17), center=(0.62, yy + j * 0.035, zu + 1.14), mat=1)
    mb.to_object("E_오징어덕장", col, [M.get("wood_dark"), M.get("squid")])
    mb = MeshBuilder()
    for k, (x, y, z, r) in enumerate([(5.66, 3.55, zu + 1.10, 0.11), (5.66, 3.55, zu + 0.88, 0.10),
                                      (6.30, 4.70, zu + 1.30, 0.13), (1.55, 6.88, zu + 0.78, 0.15),
                                      (1.95, 6.88, zu + 0.80, 0.14), (2.35, 6.88, zu + 0.78, 0.15),
                                      (6.05, 5.00, zu + 0.14, 0.14), (6.35, 5.25, zu + 0.14, 0.15),
                                      (6.20, 5.12, zu + 0.38, 0.13), (0.62, -2.18, zu + 1.30, 0.12)]):
        _float(mb, x, y, z, r, k % 2)
    for (x, y, sx, sy, sz) in ((2.55, 6.35, 0.55, 0.38, 0.28), (3.05, 6.45, 0.45, 0.32, 0.22), (2.85, 6.1, 0.4, 0.3, 0.2)):
        mb.sphere((sx, sy, sz), center=(x, y, zu + sz * 0.6), segments=10, rings=6, mat=2)
    for (x, y) in ((2.7, 6.0), (3.2, 6.25)):
        _float(mb, x, y, zu + 0.32, 0.11, 0)
    mb.cylinder(0.34, 0.37, zu, zu + 0.26, center_xy=(4.75, -4.3), segments=16, mat=3)
    mb.cylinder(0.30, 0.30, zu + 0.2, zu + 0.24, center_xy=(4.75, -4.3), segments=16, mat=4)
    mb.to_object("E_부표_그물더미_대야", col, [M.get("float_orange"), M.get("float_white"), M.get("net"),
                                              M.get("basin_red"), M.get("sea_deep")])

    # --- C. 항구: 방파제 끝 빨간·흰 등대, 등대 곶 옆 방파제(CUT7 끝 화면), 어선, 가로등 ---
    qx = L.quay_x0
    lx, ly = config.LIGHTHOUSE_XY
    mb = MeshBuilder()
    bw0, bw1 = Vector((lx - 13.0, ly + 18.0, 0.9)), Vector((lx - 30.0, ly + 31.0, 0.9))
    mb.box_between(bw0, bw1, 4.5, 2.6, mat=0)
    mb.to_object("E_곶방파제", col, [M.get("quay")])
    mb = MeshBuilder()
    for (x, y, red) in ((bw1.x, bw1.y, True), (qx - 50.0, 20.0, False), (qx - 40.0, 48.0, True)):
        mb.cylinder(1.0, 0.8, 2.2, 8.2, center_xy=(x, y), segments=12, mat=0 if red else 1)
        mb.cylinder(0.85, 0.85, 5.2, 5.9, center_xy=(x, y), segments=12, mat=1 if red else 0)
        mb.cylinder(0.6, 0.6, 8.2, 9.2, center_xy=(x, y), segments=10, mat=2)
        mb.cylinder(0.8, 0.1, 9.2, 9.9, center_xy=(x, y), segments=10, mat=0 if red else 1)
    mb.to_object("E_방파제등대", col, [M.get("harbor_red"), M.get("lighthouse"), M.get("lantern")])
    mb = MeshBuilder()
    for k, (dx, dy, hd) in enumerate(((-14.0, 21.0, 215.0), (-19.0, 26.0, 230.0), (-10.0, 27.0, 200.0))):
        _boat(mb, lx + dx, ly + dy, hd, 6.8, hull=(3, 0, 2)[k], cabin=1, mast=4)
    mb.to_object("E_곶어선", col, [M.get("boat_hull"), M.get("boat_hull"), M.get("boat_blue"), M.get("boat_red"),
                                  M.get("rail")])

    # 가로등: 기둥은 늘 보이고, 따뜻한 전구는 CUT8 에 하나씩 켜짐 (animation.setup_cut_08)
    spots = [(x_west + 0.3, yy, zl) for yy in (-38.0, -26.0, 16.0, 28.0)]
    spots += [(qx + 1.2, yy, 1.5) for yy in (-30.0, -14.0, 2.0, 18.0, 34.0)]
    for (x0, x1, zz) in L.terraces[:3]:
        spots += [(x1 - 0.5, yy, zz) for yy in (-22.0, 8.0)]
    mb = MeshBuilder()
    lcol = get_collection("E_가로등_전구", col)
    L.street_lamps = []
    for i, (x, y, z) in enumerate(spots):
        mb.cylinder(0.07, 0.06, z, z + 4.2, center_xy=(x, y), segments=6, mat=0)
        mb.box((0.5, 0.08, 0.08), center=(x + 0.2, y, z + 4.2), mat=0)
        b = MeshBuilder()
        b.sphere((0.28, 0.28, 0.24), segments=10, rings=6, mat=0)
        L.street_lamps.append(b.to_object("E_가로등불_%02d" % (i + 1), lcol,
                                          [M.get("lamp_warm", emission=config.STREET_LAMP_EMISSION)],
                                          location=(x + 0.42, y, z + 4.05)))
    mb.to_object("E_가로등_기둥", col, [M.get("pole_grey")])
    return col
