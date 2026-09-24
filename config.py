"""
config.py — 「똑똑, 괜찮으세요?」 30초 프리비즈 설정값

이 파일의 숫자만 고쳐도 컷 길이·카메라·동선·크기를 조정할 수 있도록 모아 두었습니다.
수정 후 main.py 를 다시 실행하면 씬 전체가 새로 만들어집니다.

단위     : 길이 m, 각도 도(deg), 시간 frame (24fps)
좌표계   : X = 동, Y = 북, Z = 위(해발 m).  방위각(heading) 0 = 북, 90 = 동 (시계 방향)
세트 원점 : 시민 집 대문 중심 = (0, 0, GATE_LEVEL_Z).  대문은 서쪽(-X, 골목·계단 쪽)을 향함.
            바다는 서쪽 아래, 등대 곶은 남서쪽.
"""
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# =============================================================================
# 1. 타임라인  (수정 지시문 기준: 전환 3.5 / 6 / 10 / 13 / 17 / 21 / 24초)
# =============================================================================
FPS = 24
FRAME_START = 1
FRAME_END = 720                 # 30초 × 24fps
RESOLUTION_X = 1280
RESOLUTION_Y = 720

CUT_01_START, CUT_01_END = 1, 84      # 0.0 ~  3.5초  바닷가 마을로 들어서다
CUT_02_START, CUT_02_END = 85, 144    # 3.5 ~  6.0초  문 앞에서
CUT_03_START, CUT_03_END = 145, 240   # 6.0 ~ 10.0초  문이 열린다
CUT_04_START, CUT_04_END = 241, 312   # 10.0 ~ 13.0초 평상에 마주 앉다
CUT_05_START, CUT_05_END = 313, 408   # 13.0 ~ 17.0초 이야기를 듣다 (핵심 감정 컷)
CUT_06_START, CUT_06_END = 409, 504   # 17.0 ~ 21.0초 분납과 복지 연계를 안내하다
CUT_07_START, CUT_07_END = 505, 576   # 21.0 ~ 24.0초 배웅
CUT_08_START, CUT_08_END = 577, 720   # 24.0 ~ 30.0초 집집마다 불이 켜진다

CUTS = [
    # (번호, 시작, 끝, 제목)
    (1, CUT_01_START, CUT_01_END, "바닷가 마을로 들어서다"),
    (2, CUT_02_START, CUT_02_END, "문 앞에서"),
    (3, CUT_03_START, CUT_03_END, "문이 열린다"),
    (4, CUT_04_START, CUT_04_END, "평상에 마주 앉다"),
    (5, CUT_05_START, CUT_05_END, "이야기를 듣다"),
    (6, CUT_06_START, CUT_06_END, "분납과 복지 연계를 안내하다"),
    (7, CUT_07_START, CUT_07_END, "배웅"),
    (8, CUT_08_START, CUT_08_END, "집집마다 불이 켜진다"),
]


def cut_range(n):
    """컷 번호 → (시작 프레임, 끝 프레임)."""
    for num, start, end, _title in CUTS:
        if num == n:
            return start, end
    raise KeyError(n)


# 컷 안의 행동 타이밍은 "컷 길이 대비 비율(0~1)"로 적었습니다.
# 컷 길이를 바꾸면 행동도 같은 비율로 늘어나거나 줄어듭니다.
BEATS = {
    2: dict(tag_adjust=(0.10, 0.42), knock_raise=0.40, knock_1=0.62, knock_2=0.75, knock_lower=(0.86, 1.00)),
    3: dict(door_half=(0.04, 0.28), bow=(0.33, 0.58), door_full=(0.62, 0.88), turn_to_yard=(0.66, 0.92)),
    4: dict(push_cup=(0.12, 0.45), receive=(0.40, 0.75)),
    5: dict(look_away=(0.00, 0.34), look_back=(0.34, 0.52), nod=(0.58, 0.86)),
    6: dict(point_1=(0.08, 0.30), move_to_2=(0.42, 0.56), point_2_hold=(0.56, 0.78),
            citizen_nod=(0.60, 0.82), citizen_hands=(0.66, 0.90)),
    7: dict(bow=(0.00, 0.26), wave=(0.10, 0.62), turn=(0.28, 0.44), descend_start=0.44),
}

# =============================================================================
# 2. 캐릭터
# =============================================================================
MAIN_CHAR_HEIGHT = 1.70         # 주인공 키 (3.75~4등신 프록시. 머리 ≈ 0.40m)
CITIZEN_HEIGHT = 1.88           # 시민 키 (주인공보다 머리 약 반 개 큼)
CITIZEN_BUILD = 1.12            # 시민 어깨·몸통 폭 배율 (비교적 단단한 체형)
BOW_ANGLE = 13.0                # 목례 각도(몸통+고개 합계, 10~15도)
NOD_ANGLE = 11.0                # 경청 끄덕임 각도

# 주인공 걷기 속도
WALK_FRAMES_PER_STEP = 14       # 계단 오르기: 한 칸 = 14f (≈0.58초, 서두르지 않는 속도)
DESCEND_FRAMES_PER_STEP = 11    # 계단 내려가기(컷7): 한 칸 프레임
FLAT_WALK_FRAMES_PER_STEP = 15  # 평지 걷기(컷8 원경 보행자)
FLAT_WALK_STEP_LENGTH = 0.55    # 평지 보폭
CUT01_START_STEP = 2            # 컷1 시작 시 주인공 앞발이 딛고 있는 계단 번호(0 = 첫 단)
CUT08_TINY_WALKER = True        # 컷8에 점 크기의 주인공을 아랫골목에 둘지 여부

# =============================================================================
# 3. 세트 (블록아웃)
# =============================================================================
GATE_LEVEL_Z = 20.0             # 대문·마당·윗골목 바닥 해발
SEA_LEVEL_Z = 0.0

STAIR_COUNT = 18                # 계단 수
STAIR_RISE = 0.16               # 계단 한 칸 높이
STAIR_RUN = 0.32                # 계단 한 칸 디딤판 깊이
STAIR_WIDTH = 1.6
STAIR_HEADING = 35.0            # 계단을 올라가는 방향 (북동)
STAIR_TOP_XY = (-5.4, -4.5)     # 계단 맨 윗단(윗골목과 만나는 선) 중심 — 대문에서 약 7m

LOWER_STREET_WEST_X = -12.0     # 아랫골목 서쪽 가장자리(난간, 아래로 지붕·바다)
YARD_WALL_HEIGHT = 1.0          # 마당 담장 높이 (낮아야 마당에서 바다가 보임)
GATE_WALL_HEIGHT = 1.95         # 대문 좌우 담장 높이
GATE_WIDTH = 1.2                # 대문(철문 한 짝) 폭
GATE_HEIGHT = 1.95
GATE_OPEN_HALF = 42.0           # 컷3 반쯤 열림 각도
GATE_OPEN_FULL = 88.0           # 컷3 끝 완전 열림 각도

PYEONGSANG_SIZE = (1.8, 1.2)    # 평상 길이 × 폭
PYEONGSANG_HEIGHT = 0.40
PYEONGSANG_CENTER_XY = (3.4, 1.6)
PYEONGSANG_FRONT_HEADING = 45.0  # 두 사람이 비스듬히 함께 향하는 '앞' 방향 (컷4 카메라 쪽)
SEAT_OFFSET = 0.42              # 평상 중심에서 두 좌석까지 거리 (시민 = 왼쪽, 주인공 = 오른쪽)
SEAT_TURN = 35.0                # 정면으로 마주 보는 방향에서 '앞'으로 튼 각도 → 비스듬히 마주 앉기

LIGHTHOUSE_XY = (-42.0, -78.0)  # 등대 곶 위치 (대문에서 내려다본 계단 방향 끝, 남서쪽)
LIGHTHOUSE_BASE_Z = 20.0        # 곶 꼭대기 높이
LIGHTHOUSE_HEIGHT = 17.0
WINDOW_LIGHTS_AT_START = 3      # 컷8 시작 때 켜져 있는 창문 수
WINDOW_LIGHTS_AT_END = 17       # 컷8 끝까지 켜지는 창문 수
RANDOM_SEED = 7                 # 마을 주택 배치 난수

# =============================================================================
# 4. 카메라  (렌즈 mm · 높이 m · 이동 거리 m · ease_in/ease_out = 가속/감속 구간이 컷 길이에서 차지하는 비율)
#    xy 는 월드 좌표(대문 중심 원점), height 는 그 자리 바닥에서의 높이.
#    CUT4~6 의 *_local 은 평상 로컬 좌표: +X = 주인공 쪽, -Y = 두 사람이 함께 향한 앞쪽, Z = 마당 바닥 기준
#    CUT7 은 시민 기준: over_shoulder = (시민 뒤쪽 m, 시민 오른쪽 m), rise = 크레인 상승량, back = 뒤로 빠지는 양
#    CUT8 은 월드 좌표 그대로 (start = 시작 위치, target = 바라보는 점)
# =============================================================================
SENSOR_WIDTH = 36.0

CAM_CUT01 = dict(lens=24.0, height=0.55, start_xy=(-10.1, -19.0), heading=6.0, pitch=2.5,
                 move_dist=1.6, ease_in=0.45, ease_out=0.0)        # Low forward tracking
CAM_CUT02 = dict(lens=85.0, height=0.95, start_xy=(-0.10, 3.40), end_xy=(-0.46, 2.80),
                 target=(-0.27, -0.10, 0.96), ease_in=0.10, ease_out=0.65)  # 좌→우 표면 트랙, 감속
CAM_CUT03 = dict(lens=50.0, height=1.50, start_xy=(-2.05, -0.92), move_dist=0.36, move_angle=10.0,
                 target=(0.18, -0.26, 1.40), stop_at=0.88, ease_in=0.10, ease_out=0.55)  # 짧은 사선 push-in
CAM_CUT04 = dict(lens=28.0, height=1.40, start_xy=(6.05, 5.55), end_xy=(6.75, 6.45),
                 target_local=(0.0, 0.0, 1.15), ease_in=0.25, ease_out=0.30)  # dolly-out
CAM_CUT05 = dict(lens=70.0, height=1.12, pos_local=(1.40, -1.33), target_local=(-0.18, 0.02, 1.10),
                 move_dist=0.14, ease_in=0.0, ease_out=0.0)          # 가장 느린 등속 측면 이동(우→좌)
CAM_CUT06 = dict(lens=50.0, height=1.32, pos_local=(0.95, -2.75), target_local=(-0.03, -0.12, 0.86),
                 drift=(0.05, 0.0, -0.02), ease_in=0.5, ease_out=0.5)   # 거의 정적(아주 미세한 드리프트)
CAM_CUT07 = dict(lens_start=50.0, lens_end=28.0, height=1.47, over_shoulder=(1.30, 0.50), rise=2.2,
                 back=0.6, ease_in=0.45, ease_out=0.20)              # 눈높이(시민 어깨 옆) → crane-up
CAM_CUT08 = dict(lens=24.0, start=(-135.0, -8.0, 34.0), target=(-12.0, -24.0, 22.0),
                 move_back=24.0, rise=4.0, ease_in=0.10, decel_sec=1.5)   # dolly-out + 상승 + 감속

# =============================================================================
# 5. 조명 (시간은 한 방향: 늦은 오후 → 해질녘 초입)
#    sun_elev = 태양 고도, sun_color/strength, sky = (지평선 색, 천정 색, 세기)
# =============================================================================
SUN_AZIMUTH = 250.0             # 태양이 있는 방위 (서남서, 바다 쪽 상공)
LIGHTING = {
    "late_afternoon":   dict(cuts=(1, 2, 3), sun_elev=30.0, sun_color="#FFF1DE", sun_strength=2.7,
                             sky=("#E9E4D8", "#9DB8D6", 0.85)),
    "late_afternoon_2": dict(cuts=(4, 5, 6), sun_elev=24.0, sun_color="#FFE3C2", sun_strength=2.5,
                             sky=("#F0DFC8", "#A7B9D0", 0.80)),
    "golden":           dict(cuts=(7,), sun_elev=12.0, sun_color="#FFC98F", sun_strength=2.2,
                             sky=("#F7C9A4", "#A3AFCB", 0.70)),
    "dusk":             dict(cuts=(8,), sun_elev=3.0, sun_color="#FFB08A", sun_strength=1.1,
                             sky=("#F2B89C", "#8C87B2", 0.50),
                             end_sun_strength=0.55, end_sky=("#E6A792", "#6F6C9C", 0.34)),
}

# =============================================================================
# 6. 렌더 / 출력
# =============================================================================
OUTPUT_DIR = os.path.join(PROJECT_DIR, "renders")          # 렌더 출력 폴더
MOVIE_NAME = "donghae_previs_30s"                           # → renders/donghae_previs_30s.mp4
STILLS_DIR = os.path.join(OUTPUT_DIR, "stills")            # 컷별 '이미지용 한 순간' PNG
BLEND_PATH = os.path.join(PROJECT_DIR, "build", "donghae_previs.blend")
PREVIEW_ENGINE = "EEVEE"        # "EEVEE"(시간대 조명 보임) | "WORKBENCH"(가장 빠름) | "CYCLES"
EEVEE_SAMPLES = 8
BURN_IN = True                  # 프레임·컷(마커)·카메라·렌즈 번인
BURN_IN_NOTE = "DONGHAE PREVIS v1 - not for final"

# 컷별 '이미지용 한 순간' (설계안의 GPT 이미지용 구도 추출 프레임, 컷 길이 대비 비율)
STILL_MOMENTS = {1: 0.55, 2: 0.60, 3: 0.24, 4: 0.30, 5: 0.20, 6: 0.25, 7: 0.14, 8: 0.62}
