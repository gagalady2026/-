"""
check_cuts.py — 완성본(또는 프리뷰) MP4 의 컷 전환 검출

설계안 '완성본 검수: 8컷·전환 7곳' 을 숫자로 확인합니다.
프레임마다 앞 프레임과의 밝기 차(가운데 76% 영역, 번인·자막 띠 제외)를 구해
가장 큰 변화 7곳이 config.py 의 컷 시작 프레임과 일치하는지 봅니다.

사용: python check_cuts.py renders/donghae_previs_30s.mp4
      (ffmpeg 가 PATH 에 있어야 하고 numpy 필요. Blender 의 파이썬으로도 실행 가능:
       blender -b -P check_cuts.py -- renders/donghae_previs_30s.mp4)
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402


def frame_diffs(path, w=160, h=90):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", "scale=%d:%d,format=gray" % (w, h),
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    core = frames[:, int(h * 0.12):int(h * 0.88), :]
    return len(frames), np.abs(np.diff(core, axis=0)).mean(axis=(1, 2))


def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    path = args[0] if args else os.path.join(config.OUTPUT_DIR, config.MOVIE_NAME + ".mp4")
    n, diff = frame_diffs(path)
    expected = [f0 for (_n, f0, _f1, _t) in config.CUTS][1:]
    k = len(expected)
    order = np.argsort(diff)[::-1]
    detected = sorted(int(i) + 2 for i in order[:k])          # 변화 직후 프레임 번호(1부터)
    ok = detected == expected and n == config.FRAME_END - config.FRAME_START + 1
    print("파일        :", path)
    print("프레임 수   : %d (기대 %d, %.2f초 @%dfps)" % (n, config.FRAME_END - config.FRAME_START + 1,
                                                    n / config.FPS, config.FPS))
    print("검출된 전환 :", detected)
    print("기대 전환   :", expected)
    print("여유(컷 %d번째 변화 / 컷 아닌 가장 큰 변화) = %.1f / %.1f" % (k, diff[order[k - 1]], diff[order[k]]))
    print("결과        :", "통과" if ok else "불일치 — 컷 사이 튀는 프레임이나 길이를 확인하세요")
    return 0 if ok else 1


if __name__ == "__main__":
    code = main()
    if "bpy" not in sys.modules:
        sys.exit(code)
