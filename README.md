# 「똑똑, 괜찮으세요?」 — 30초 3D 프리비즈 (Blender / bpy)

동해시 지방세입 체납관리단 30초 홍보영상의 **프리비즈(애니매틱)** 프로젝트입니다.

> **이 프로젝트는 최종 렌더용이 아닙니다.**
> Blender는 여기서 "움직이는 설계도"로만 씁니다. 검증 대상은 ① 30초 컷 길이·리듬 ② 컷별 카메라 위치·이동
> ③ 인물 위치·동선·행동 ④ GPT 이미지 생성에 쓸 구도, 이 네 가지입니다.
> 인물·세트는 로우폴리 프록시이고, 얼굴·실제 묵호 지형·자막·CI는 이후 단계
> (GPT 이미지 → Seedance/Kling I2V → 편집)에서 만듭니다.

---

## 1. Blender 버전

- **기준: Blender 4.0.2** (Python `bpy`)
- 4.0의 `BLENDER_EEVEE`와 4.2 이후의 `BLENDER_EEVEE_NEXT`를 모두 처리하도록 작성했습니다.
  개발 중 검증은 PyPI `bpy` 4.2 모듈로 헤드리스 실행했습니다(4.0.2 모듈은 배포되지 않음).
  4.0.2에서 처음 실행할 때 콘솔에 오류가 없는지 한 번 확인해 주세요.

## 2. 실행 순서 · 3. 먼저 실행할 파일

**`main.py` 를 먼저 실행합니다.** 나머지 파일은 `main.py` 가 불러옵니다.

### A. Blender 화면에서

1. Blender 4.0.2 실행 → **새 파일**(General)
   > `main.py` 는 현재 파일의 오브젝트·재질·카메라·조명을 모두 지우고 다시 만듭니다.
2. `Scripting` 탭 → `Open` → 이 폴더의 `main.py` → `Run Script`
3. 타임라인에서 재생(Space). 카메라 뷰(Numpad 0)로 보면 마커마다 CAM_CUT01~08 로 자동 전환됩니다.
   - 시간대 조명까지 보려면 뷰포트 셰이딩을 `Rendered`(또는 Material Preview + Scene Lights/World)로 바꾸세요.
4. `config.py` 를 고친 뒤 `main.py` 를 다시 Run 하면 전체가 새로 만들어집니다.

### B. 명령줄에서 (이 폴더에서 실행)

```bash
blender -b -P main.py                    # 씬 생성 → build/donghae_previs.blend 저장
blender -b -P main.py -- --render        # 씬 생성 + 저장 + 30초 MP4 렌더
blender -b -P render_preview.py          # (씬 생성 포함) 30초 MP4만 렌더
```

실행하면 콘솔에 **컷 표 + 자동 점검 결과**가 찍힙니다.

```
 CUT_01  0.00~ 3.50   F001~F084   3.5초  CAM_CUT01  바닷가 마을로 들어서다
 ...
 전체 720프레임 = 30.00초 @24fps  ·  점검: 통과
 구도 점검 (머리 x,y = 화면 좌하단 0 ~ 우상단 1 / 부위 = 화면 안에서 가려지지 않은 머리·몸통·손·발 수)
  CUT_01 F047  CAM_CUT01 | 주인공 머리(0.59,0.64) 부위 7/7
  CUT_05 F332  CAM_CUT05 | 주인공 머리(0.94,0.52) 부위 1/1  |  시민 머리(0.35,0.59) 부위 1/1
```

- `점검`: 1~720 프레임, 24fps, 마커 8개 위치, **모든 프레임에서 카메라가 올바른 컷 카메라인지** 확인
- `구도 점검`: 컷마다 시작 이후·중간·끝·'이미지용 한 순간' 프레임에서 등장인물의 머리·몸통·손·발이 화면 안에 있는지,
  **세트에 가려지지 않았는지(레이캐스트)** 확인. 머리 좌표는 '이미지용 한 순간' 프레임 기준입니다.
- `카메라 경로 점검`: 모든 프레임에서 컷 카메라가 벽·지붕 같은 메시 안을 지나가지 않는지 확인
  → 카메라나 세트를 옮긴 뒤 문제가 생기면 `[경고]` 가 뜹니다.

## 4. 전체 타임라인 · 5. 컷별 프레임 범위 · 6. 카메라 이름

24fps, Frame 1 ~ 720 (30.0초), 컷 전환 7곳: 3.5 / 6 / 10 / 13 / 17 / 21 / 24초.
타임라인 마커 `CUT_01` ~ `CUT_08` 이 각 컷 시작 프레임에 있고, 마커마다 카메라가 묶여 있습니다.

| 마커 | 시간(초) | 프레임 | 길이 | 카메라 | 화면 크기 | 카메라 이동 | 행동 |
|---|---|---|---|---|---|---|---|
| CUT_01 | 0.0–3.5 | F001–F084 | 3.5초 | `CAM_CUT01` | Wide, 24mm, 무릎 높이 | Low forward tracking (천천히 출발→등속) | 계단 오르기, 중반에 담장 너머 집을 봄 |
| CUT_02 | 3.5–6.0 | F085–F144 | 2.5초 | `CAM_CUT02` | Close, 85mm, 허리 높이 | Left→right surface tracking, 대문 앞 감속 | 왼손 명찰 정돈 → 오른손 두 번 노크 |
| CUT_03 | 6.0–10.0 | F145–F240 | 4초 | `CAM_CUT03` | Eye-level Medium, 50mm, 150cm | Short oblique push-in, 문 다 열릴 즈음 정지 | 문 반쯤 열림 → 13° 목례 → 문 더 열고 마당 쪽 안내 |
| CUT_04 | 10.0–13.0 | F241–F312 | 3초 | `CAM_CUT04` | Wide, 28mm, 가슴 높이 | Dolly-out (전경 그물) | 평상에 비스듬히 마주 앉음, 찻잔 밀어 주기/두 손으로 받기 |
| CUT_05 | 13.0–17.0 | F313–F408 | 4초 | `CAM_CUT05` | MCU, 70mm, 앉은 눈높이 | Slow lateral slide 우→좌 (8컷 중 가장 느린 등속) | 시민 먼 곳 보며 이야기 → 다시 주인공 / 주인공 기울여 경청·한 번 끄덕임 |
| CUT_06 | 17.0–21.0 | F409–F504 | 4초 | `CAM_CUT06` | 3/4 Medium, 50mm, 약간 높은 눈높이 | Nearly static (미세 드리프트) | 자료 ① 분납 영역 → ② 복지 연계 영역 차례로 가리킴, 시민 끄덕임·손 모음 |
| CUT_07 | 21.0–24.0 | F505–F576 | 3초 | `CAM_CUT07` | Eye-level → wider, 50→28mm | Crane-up (시민 어깨 옆에서 솟아오름) | 돌아서 목례 → 시민 손 들어 화답 → 계단 내려감, 골목·등대 드러남 |
| CUT_08 | 24.0–30.0 | F577–F720 | 6초 | `CAM_CUT08` | Extreme wide, 24mm | Dolly-out + slight rise, 마지막 1.5초 감속 정지 | 창문 불빛 3개 → 17개로 하나씩 켜짐, 바다 일렁임 |

시간대(조명): CUT1~3 늦은 오후 → CUT4~6 조금 더 따뜻한 늦은 오후 → CUT7 해 질 무렵 → CUT8 해질녘 초입
(태양 고도 30°→24°→12°→3°, 하늘색도 한 방향으로만 변함. 컷 안에서 되돌아가지 않음)

## 7. 자주 수정할 설정 위치 — `config.py`

| 바꾸고 싶은 것 | `config.py` 항목 |
|---|---|
| 컷 길이·전환 시점 | `CUT_01_START` ~ `CUT_08_END` (빈틈·겹침이 있으면 실행 시 오류로 알려 줌) |
| 컷 안 행동 타이밍 | `BEATS` — 컷 길이 대비 비율(0~1). 컷 길이를 바꾸면 행동도 비율대로 늘어남 |
| 카메라 렌즈·높이·이동 거리·가감속 | `CAM_CUT01` ~ `CAM_CUT08` (`lens`, `height`, `move_dist`/`start_xy`·`end_xy`, `ease_in`/`ease_out`) |
| 주인공·시민 키, 체형 | `MAIN_CHAR_HEIGHT`, `CITIZEN_HEIGHT`, `CITIZEN_BUILD` |
| 목례·끄덕임 각도 | `BOW_ANGLE`(기본 13°), `NOD_ANGLE` |
| 걷기 속도 | `WALK_FRAMES_PER_STEP`(계단 오르기 한 칸 프레임), `DESCEND_FRAMES_PER_STEP`, `FLAT_WALK_*` |
| 계단 높이·수·폭·방향·위치 | `STAIR_RISE`, `STAIR_COUNT`, `STAIR_RUN`, `STAIR_WIDTH`, `STAIR_HEADING`, `STAIR_TOP_XY` |
| 평상 크기·위치, 앉는 간격·각도 | `PYEONGSANG_SIZE`, `PYEONGSANG_HEIGHT`, `PYEONGSANG_CENTER_XY`, `SEAT_OFFSET`, `SEAT_TURN` |
| 대문 열림 각도, 담장 높이 | `GATE_OPEN_HALF`, `GATE_OPEN_FULL`, `YARD_WALL_HEIGHT`, `GATE_WALL_HEIGHT` |
| 등대 위치·높이, 창문 불빛 개수 | `LIGHTHOUSE_XY`, `LIGHTHOUSE_HEIGHT`, `WINDOW_LIGHTS_AT_START/END` |
| 시간대 조명 | `SUN_AZIMUTH`, `LIGHTING` (컷 묶음별 태양 고도·색·세기, 하늘 지평선/천정 색) |
| 렌더 엔진·샘플·번인 | `PREVIEW_ENGINE`, `EEVEE_SAMPLES`, `BURN_IN`, `BURN_IN_NOTE` |
| 출력 폴더·파일명 | `OUTPUT_DIR`, `MOVIE_NAME`, `STILLS_DIR`, `BLEND_PATH` |
| 컷별 '이미지용 한 순간' 프레임 | `STILL_MOMENTS` (컷 길이 대비 비율) |

좌표 약속: X = 동, Y = 북, Z = 해발(m). 방위각 0 = 북, 90 = 동. **대문 중심 = (0, 0, 20m)**, 대문은 서쪽(계단 쪽)을 향함.
CUT4~6 카메라는 평상 로컬 좌표(+X = 주인공 쪽, −Y = 두 사람이 함께 향한 앞쪽)로 적습니다.

## 8. 프리뷰 렌더 방법

```bash
blender -b -P render_preview.py                            # Eevee, 1280×720, 24fps, H.264 MP4 (시간대 조명 보임)
blender -b -P render_preview.py -- --engine workbench      # 가장 빠른 Workbench(외곽선·재질색)
blender -b -P render_preview.py -- --scale 50              # 해상도 50%로 빠르게
blender -b -P render_preview.py -- --frames 409-504        # CUT 6만
blender -b -P render_preview.py -- --stills                # 컷별 '이미지용 한 순간' PNG 8장 (번인 없음)
blender -b build/donghae_previs.blend -P render_preview.py # 저장해 둔 .blend 로 렌더
```

- 기본 번인(좌상단 메모, 하단에 마커·타임코드·프레임·카메라·렌즈)이 들어갑니다. `--no-burnin` 으로 끔.
- Blender 화면에서는 `render_preview.py` 를 Run Script 해도 같은 설정으로 렌더합니다.
- 참고 속도(GPU 없는 4코어 클라우드, 소프트웨어 GL): Workbench 1280×720 전체 30초 약 8분(≈0.7초/프레임),
  Eevee 스틸 8장 약 1분. GPU가 있는 PC에서는 Eevee 전체 렌더도 몇 분 안에 끝납니다.
- 렌더한 MP4의 컷 전환 검수: `python check_cuts.py renders/donghae_previs_30s.mp4`
  (프레임 간 변화가 가장 큰 7곳이 컷 시작 프레임과 일치하는지 확인. ffmpeg·numpy 필요.
  나중에 Seedance/Kling 컷을 이어 붙인 편집본에도 같은 방법으로 쓸 수 있습니다.)

## 9. 출력 파일 위치

| 결과물 | 위치 |
|---|---|
| 30초 프리뷰 MP4 | `renders/donghae_previs_30s.mp4` (구간 렌더는 `…_F0409-0504.mp4`) |
| 컷별 스틸 PNG | `renders/stills/CUT01_F0047.png` … `CUT08_F0666.png` |
| 저장된 씬 | `build/donghae_previs.blend` |
| 이 저장소에 첨부한 샘플 결과 | `preview/donghae_previs_30s_workbench.mp4`, `preview/stills/*.jpg`(Eevee 스틸 8장), `preview/storyboard_8cuts.jpg` |

`renders/`, `build/` 는 `.gitignore` 에 들어 있습니다.

## 10. 프리비즈 범위와 한계

- **최종 렌더용이 아닙니다.** 프록시 인물(얼굴 없음, 점 눈만 — 시선 방향 확인용), 블록아웃 세트, 단순 조명입니다.
- 명찰·안내 자료에는 글자를 만들지 않았습니다(설계안대로 후반 합성). 안내 태블릿은 왼쪽 = 분납(단계 막대 아이콘, 세이지색),
  오른쪽 = 복지서비스 연계(하트 아이콘, 살구색) 두 영역만 보이게 했습니다.
- 실제 묵호 지형·논골담길·묵호등대는 비슷한 배치만 흉내 낸 가상 언덕 마을입니다(바다 = 서쪽, 등대 곶 = 남서쪽).

---

## 검증 결과 (이 저장소 코드 기준)

지시문 26번 완료 기준을 아래 방법으로 확인했습니다. (헤드리스 `bpy` 4.2 모듈 + 소프트웨어 GL)

| 완료 기준 | 결과 | 확인 방법 |
|---|---|---|
| Frame 1~720 정상 재생, 30초 이하 | 통과 | `verify_timeline` + MP4 720프레임·30.000초·24fps·1280×720·H.264 (ffprobe) |
| 8개 컷이 정확한 시간에 전환 / 카메라 8개 정상 전환 | 통과 | 1~720 모든 프레임의 활성 카메라 점검 + `check_cuts.py`: 검출 전환 85·145·241·313·409·505·577 = 기대값 |
| CUT1 계단 오르기 | 통과 | 모든 프레임에서 한 발은 디딤판에 정확히 닿음(틈 0mm), 발바닥 파고듦 없음, 몸 7/7 부위 보임 |
| CUT2 노크 / CUT3 목례 | 통과 | 노크 2회(주먹이 문 표면까지), 목례 13°(몸통 40%+고개 60%) |
| CUT4 같은 높이로 앉음 | 통과 | 두 사람 모두 평상 위 양반다리 (서 있는 사람 없음) |
| CUT5 경청 구도 | 통과 | 시민 머리 화면 왼쪽 약 0.35, 주인공 오른쪽 전경, 한 번 끄덕임 |
| CUT6 분납 → 복지 연계 구분 | 통과 | 손가락이 ① 영역(막대) → ② 영역(하트)으로 이동, 시민 끄덕임·손 모음 |
| CUT7 배웅 흐름 | 통과 | 목례 → 손 들어 화답 → 돌아서기 → 계단 내려가기, 크레인 경로가 세트 안을 지나가지 않음 |
| CUT8 뒤로 빠지며 엔딩 구도 안착 | 통과 | 마지막 1.5초 감속 정지, 마지막 프레임 하늘 약 34%(상단 1/3 자막 여백) |
| 프리뷰 MP4 출력 | 통과 | `preview/donghae_previs_30s_workbench.mp4` |

## 파일 구조

```
main.py            씬 전체 생성 (reset_scene → 세트 → 인물 → 카메라 → 컷별 연기 → 마커·조명 → 점검)
config.py          모든 조정값 (타임라인, 크기, 카메라, 조명, 출력)
materials.py       팔레트(캐릭터 시트 색 그대로)·재질, 일렁이는 바다
characters.py      build_main_character(), build_citizen_proxy() — 관절 = 부위 원점인 퍼펫 리그 + FK/IK
environments.py    build_stairs_set(), build_gate_set(), build_yard_set(), build_village_set()
cameras.py         CAM_CUT01~08 생성, 컷별 이동(가감속 곡선), 구도 점검 리포트
animation.py       setup_cut_01() ~ setup_cut_08() — 컷별 블로킹, 계단 보행(발 디딤 + IK)
timeline.py        setup_timeline_markers(), setup_lighting(), 컷 경계 정리, 타임라인 점검
render_preview.py  configure_preview_render(), MP4/스틸 렌더 (명령줄 옵션)
utils.py           공용 도우미 (이징 곡선, 방향 계산, 로우폴리 메시, 키프레임)
check_cuts.py      렌더한 MP4 의 컷 전환 검출 (검수용, Blender 없이 실행 가능)
preview/           이 코드로 렌더한 샘플: 30초 Workbench MP4, 컷별 Eevee 스틸 8장, 8컷 스토리보드
```

### 구현 메모

- **하나의 언덕 마을**: 아랫골목 → 북동쪽 계단(18단, 단높이 16cm) → 윗골목 → 대문 → 마당·평상이 이어져 있어,
  CUT1(아래에서 올려다본 계단)과 CUT7(대문 앞에서 내려다본 같은 계단)이 공간적으로 대응합니다.
  CUT8은 같은 마을을 바다 쪽 상공에서 봅니다.
- **계단 보행**: 발 디딤 계획(한 발에 한 칸) → 디딘 발 기준으로 골반 높이 계산 → 다리 2본 IK.
  공중의 발은 발바닥(뒤꿈치~발끝)이 계단 면 아래로 내려가지 않게 보정합니다.
  검증 결과: CUT1·7·8 모든 프레임에서 한 발은 항상 디딤판에 정확히 닿아 있고(틈 0mm), 파고듦 없음.
- **컷 단위 굽기**: 인물·소품은 컷 구간마다 "프레임 → 포즈" 함수로 매 프레임 키를 굽고,
  컷 끝 키는 CONSTANT 로 둬서 다음 컷 첫 프레임에서 정확히 바뀝니다(포즈가 컷 사이로 새지 않음).
  카메라는 자기 컷 구간에서만 키가 있습니다.
- **같은 눈높이**: CUT4~6은 두 사람 모두 평상 위 양반다리(시민이 약간 큼). 서 있는 사람과 앉은 사람이 섞이는 구도는 없습니다.
- 주인공 치수는 캐릭터 시트 턴어라운드(4칸 눈금)에서 측정: 키 1.70m, 머리(머리카락 포함) ≈ 0.40m, 다리가 긴 약 4등신.

### 검토 포인트 (설계안 대비 판단이 필요한 곳)

- **CUT2 → CUT3 화면 방향**: 지시대로 CUT2는 주인공이 화면 오른쪽(명찰이 보이게 카메라 쪽으로 몸을 튼 자세),
  CUT3은 주인공 어깨가 화면 왼쪽입니다. 대문을 사이에 둔 역방향 컷이라 시선 방향이 한 번 뒤집힙니다.
  편집에서 튀면 `CAM_CUT03` 을 주인공 왼쪽 어깨 뒤로 옮기는 안을 검토하세요.
- **CUT7 3초**: 목례(0~0.8초) → 화답(0.3~1.9초, 겹침) → 돌아서기(0.8~1.3초) → 내려가기(1.3초~)로 압축했습니다.
  더 여유가 필요하면 `BEATS[7]` 과 `DESCEND_FRAMES_PER_STEP` 을 조정하세요.
- **CUT7 등대 크기**: 끝 구도에서 등대가 화면 위쪽 약 1/3을 차지하도록 `lens_end=28`로 넓혔습니다(설계안: 표준→약간 광각).
