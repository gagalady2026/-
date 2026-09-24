"""
utils.py — 공용 도우미 (이징 곡선, 방향 계산, 로우폴리 메시 생성, 컬렉션, 키프레임)
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector


# -----------------------------------------------------------------------------
# 수학 / 이징
# -----------------------------------------------------------------------------
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def lerp(a, b, t):
    return a + (b - a) * t


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


def smoothstep(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def smootherstep(t):
    t = clamp(t)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def ease_profile(t, ease_in=0.25, ease_out=0.25):
    """0~1 시간 → 0~1 이동량.

    속도가 ease_in 구간 동안 0 → 최고 속도로 부드럽게 오르고, 가운데는 등속,
    ease_out 구간 동안 최고 속도 → 0 으로 부드럽게 내려갑니다(S-커브 가감속).
    (0, 0) 이면 완전 등속, ease_out 만 크면 '감속하며 멈춤'.
    """
    t = clamp(t)
    a, b = max(0.0, ease_in), max(0.0, ease_out)
    if a + b > 1.0:
        s = 1.0 / (a + b)
        a, b = a * s, b * s
    v = 1.0 / (1.0 - 0.5 * (a + b))

    def ramp(x):  # ∫0..x smoothstep = x^3 - x^4/2
        return x ** 3 - 0.5 * x ** 4

    if a > 0.0 and t < a:
        return v * a * ramp(t / a)
    if b > 0.0 and t > 1.0 - b:
        return 1.0 - v * b * ramp((1.0 - t) / b)
    return v * (t - 0.5 * a)


def frac_frame(start, end, frac):
    """컷 (start, end) 안에서 비율 frac(0~1)에 해당하는 정수 프레임."""
    return int(round(start + (end - start) * frac))


def window(t, t0, t1):
    """t 가 [t0, t1] 을 지나며 0→1 로 부드럽게 변하는 값."""
    if t1 <= t0:
        return 1.0 if t >= t1 else 0.0
    return smootherstep((t - t0) / (t1 - t0))


def bump(t, t0, t1, hold=0.0):
    """[t0, t1] 동안 0→1→0 으로 올라갔다 내려오는 값 (가운데 hold 비율만큼 유지)."""
    if t <= t0 or t >= t1:
        return 0.0
    u = (t - t0) / (t1 - t0)
    h = clamp(hold, 0.0, 0.9)
    rise = (1.0 - h) * 0.5
    if u < rise:
        return smootherstep(u / rise)
    if u > 1.0 - rise:
        return smootherstep((1.0 - u) / rise)
    return 1.0


# -----------------------------------------------------------------------------
# 방향
# -----------------------------------------------------------------------------
def heading_vec(deg):
    """방위각(0=북, 90=동) → 수평 단위 벡터."""
    r = math.radians(deg)
    return Vector((math.sin(r), math.cos(r), 0.0))


def heading_of(v):
    return math.degrees(math.atan2(v[0], v[1])) % 360.0


def rot2(v, deg):
    """수평 벡터를 반시계(위에서 볼 때) deg 만큼 회전."""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return Vector((v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2] if len(v) > 2 else 0.0))


def yaw_facing(direction):
    """캐릭터(로컬 정면 = -Y)가 월드 방향 direction 을 보게 하는 Z 회전(rad)."""
    return math.atan2(direction[0], -direction[1])


def look_rotation(pos, target, roll_deg=0.0):
    """카메라(-Z 가 시선, +Y 가 위)가 target 을 보게 하는 Euler."""
    d = Vector(target) - Vector(pos)
    q = d.to_track_quat('-Z', 'Y')
    if roll_deg:
        q = q @ Quaternion((0.0, 0.0, 1.0), math.radians(roll_deg))
    return q.to_euler('XYZ')


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(hex_str, linear=True):
    h = hex_str.lstrip('#')
    rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    if linear:
        rgb = [srgb_to_linear(c) for c in rgb]
    return rgb


# -----------------------------------------------------------------------------
# 컬렉션
# -----------------------------------------------------------------------------
def get_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    parent_col = parent if parent is not None else bpy.context.scene.collection
    if col.name not in parent_col.children:
        parent_col.children.link(col)
    return col


def new_empty(name, collection, location=(0, 0, 0), size=0.2, display='PLAIN_AXES', parent=None):
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = display
    obj.empty_display_size = size
    obj.location = location
    collection.objects.link(obj)
    if parent is not None:
        obj.parent = parent
    return obj


# -----------------------------------------------------------------------------
# 로우폴리 메시 빌더 (bmesh). 면마다 material index 를 지정할 수 있음.
# -----------------------------------------------------------------------------
class MeshBuilder:
    def __init__(self):
        self.bm = bmesh.new()

    def _tag(self, verts, mat):
        faces = set()
        for v in verts:
            faces.update(v.link_faces)
        for f in faces:
            f.material_index = mat
        return verts

    def box(self, size, center=(0, 0, 0), rot_z=0.0, mat=0, matrix=None):
        m = (Matrix.Translation(Vector(center)) @ Matrix.Rotation(rot_z, 4, 'Z')
             @ Matrix.Diagonal((size[0], size[1], size[2], 1.0)))
        if matrix is not None:
            m = matrix @ m
        res = bmesh.ops.create_cube(self.bm, size=1.0, matrix=m)
        return self._tag(res['verts'], mat)

    def box_between(self, p0, p1, width, thickness, mat=0, up=(0, 0, 1)):
        """p0→p1 을 잇는 가늘고 긴 상자 (끈·난간·빨랫줄 등)."""
        p0, p1 = Vector(p0), Vector(p1)
        axis = p1 - p0
        length = axis.length
        if length < 1e-6:
            return []
        z = axis.normalized()
        up = Vector(up)
        x = up.cross(z)
        if x.length < 1e-6:
            x = Vector((1, 0, 0)).cross(z)
        x.normalize()
        y = z.cross(x)
        rot = Matrix((x, y, z)).transposed().to_4x4()
        m = Matrix.Translation((p0 + p1) * 0.5) @ rot
        return self.box((width, thickness, length), matrix=m, mat=mat)

    def frustum(self, bottom, top, z0, z1, center_xy=(0, 0), mat=0, y_off_top=0.0):
        """아래 (bx, by) / 위 (tx, ty) 크기가 다른 각뿔대 (몸통용)."""
        cx, cy = center_xy
        bx, by = bottom[0] * 0.5, bottom[1] * 0.5
        tx, ty = top[0] * 0.5, top[1] * 0.5
        bm = self.bm
        vb = [bm.verts.new((cx + sx * bx, cy + sy * by, z0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        vt = [bm.verts.new((cx + sx * tx, cy + sy * ty + y_off_top, z1)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        faces = [bm.faces.new(list(reversed(vb))), bm.faces.new(vt)]
        for i in range(4):
            j = (i + 1) % 4
            faces.append(bm.faces.new((vb[i], vb[j], vt[j], vt[i])))
        for f in faces:
            f.material_index = mat
        return vb + vt

    def cylinder(self, r0, r1, z0, z1, center_xy=(0, 0), segments=10, mat=0, matrix=None):
        depth = abs(z1 - z0)
        m = Matrix.Translation((center_xy[0], center_xy[1], (z0 + z1) * 0.5))
        if z1 < z0:
            m = m @ Matrix.Rotation(math.pi, 4, 'X')
        if matrix is not None:
            m = matrix @ m
        res = bmesh.ops.create_cone(self.bm, cap_ends=True, cap_tris=False, segments=segments,
                                    radius1=r0, radius2=r1, depth=depth, matrix=m)
        return self._tag(res['verts'], mat)

    def sphere(self, radii, center=(0, 0, 0), segments=12, rings=8, mat=0, matrix=None):
        m = Matrix.Translation(Vector(center)) @ Matrix.Diagonal((radii[0], radii[1], radii[2], 1.0))
        if matrix is not None:
            m = matrix @ m
        res = bmesh.ops.create_uvsphere(self.bm, u_segments=segments, v_segments=rings, radius=1.0, matrix=m)
        return self._tag(res['verts'], mat)

    def prism(self, pts, z0, z1, mat=0):
        """평면 다각형(반시계 순서) pts 를 z0~z1 로 세운 기둥 (지형 테라스 등)."""
        bm = self.bm
        vb = [bm.verts.new((x, y, z0)) for x, y in pts]
        vt = [bm.verts.new((x, y, z1)) for x, y in pts]
        n = len(pts)
        faces = [bm.faces.new(list(reversed(vb))), bm.faces.new(vt)]
        for i in range(n):
            j = (i + 1) % n
            faces.append(bm.faces.new((vb[i], vb[j], vt[j], vt[i])))
        for f in faces:
            f.material_index = mat
        return vb + vt

    def quad(self, pts, mat=0):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = mat
        return vs

    def delete_verts(self, predicate):
        bmesh.ops.delete(self.bm, geom=[v for v in self.bm.verts if predicate(v.co)], context='VERTS')

    def to_object(self, name, collection, materials, parent=None, location=None, smooth=False,
                  recalc_normals=True):
        me = bpy.data.meshes.new(name)
        if recalc_normals and len(self.bm.faces):
            bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        self.bm.to_mesh(me)
        self.bm.free()
        for m in materials:
            me.materials.append(m)
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        obj = bpy.data.objects.new(name, me)
        collection.objects.link(obj)
        if parent is not None:
            obj.parent = parent
        if location is not None:
            obj.location = location
        return obj


# -----------------------------------------------------------------------------
# 키프레임
# -----------------------------------------------------------------------------
def key_visible(obj, frame, visible):
    """오브젝트를 해당 프레임부터 보이게/숨기게 (뷰포트+렌더)."""
    obj.hide_viewport = not visible
    obj.hide_render = not visible
    obj.keyframe_insert('hide_viewport', frame=frame)
    obj.keyframe_insert('hide_render', frame=frame)


def key_transform(obj, frame, loc=None, rot=None, scale=None):
    if loc is not None:
        obj.location = loc
        obj.keyframe_insert('location', frame=frame)
    if rot is not None:
        obj.rotation_euler = rot
        obj.keyframe_insert('rotation_euler', frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert('scale', frame=frame)


def iter_fcurves(id_data):
    ad = getattr(id_data, "animation_data", None)
    if ad is None or ad.action is None:
        return []
    return list(ad.action.fcurves)
