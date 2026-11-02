# CUT 6 웹 애니 시험 (three.js)

Blender 프리비즈 v2의 CUT 6(17.0~21.0초, F409~F504)을 **이미지·영상 생성 없이 three.js 코드만으로** 다시 그린 4초 시험 컷입니다.
"Seedance 없이 코드만으로 애니를 만들 수 있나"를 판단하기 위한 샘플입니다.

| 파일 | 내용 |
|---|---|
| `cut06_threejs.html` | 브라우저에서 바로 재생되는 장면 (재생·일시정지·프레임 이동, 안내 화면 글자 켜기/끄기) |
| `cut06_threejs_1080p.mp4` | 같은 HTML 을 헤드리스 크롬으로 프레임 단위 렌더한 1920×1080, 24fps, 96프레임(4.000초) 영상 |
| `capture.mjs` | MP4 프레임 추출 스크립트 |

- 인물·세트·안내 화면·동작이 모두 코드입니다: 툰 셰이딩 + 외곽선, 관절 계층 인형 + 팔 IK(손끝이 화면 아이콘에 정확히 닿도록 계산),
  눈 깜빡임·표정(미소)·정수리 한 가닥의 흔들림, 안내 화면의 강조 테두리·톡톡 물결·번호 배지.
- 동작 타이밍은 프리비즈 v2의 `config.BEATS[6]` 과 같습니다(① 분납 짚기 → 시민 얼굴 확인 → ② 복지 연계 → 끄덕임 → 자세 풀림).
- 주인공 헤어는 v2 프리비즈의 버섯형 캡·앞머리·한 가닥 모양을 그대로 옮겼습니다.
- 안내 화면 글자는 이 시험에서만 넣었습니다(코드로는 글자가 깨지지 않는다는 것을 보이려고). 페이지에서 끌 수 있습니다.

## MP4 다시 뽑기

```bash
npm i playwright-core@1.57.0 three@0.160.0          # 이 폴더나 임시 폴더에서
node capture.mjs cut06_threejs.html frames all      # frames/f0000.png … f0095.png (1920×1080)
ffmpeg -framerate 24 -i frames/f%04d.png -c:v libx264 -crf 16 -pix_fmt yuv420p cut06_threejs_1080p.mp4
```

`capture.mjs` 는 페이지를 `?capture` 로 열어 1920×1080 으로 고정하고, `window.__renderAt(프레임)` 으로 한 프레임씩 그려 저장합니다.
three.js 는 CDN 대신 `node_modules/three` 의 같은 버전(0.160.0)을 읽어 쓰고, 크롬 실행 파일 경로(`executablePath`)는 환경에 맞게 바꿔 주세요.
