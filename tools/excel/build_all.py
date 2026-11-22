"""templates/ 폴더의 엑셀 파일을 한 번에 다시 만들어요.

- 시뮬레이터 입력 샘플·양식 (make_input → app/sim/xlsx.py 작성기, 웹앱 내보내기와 같은 열)
- 조사 양식: 일일 기록·정기 설문 (make_survey), 파트별 업무·실적 집계 (make_freq)
업무 목록(업무구분)은 시뮬레이터 입력 파일 안에만 있어요 (업무사전 별도 파일은 2026-11-21에 없앴어요).

사용법:  python tools/excel/build_all.py [출력 폴더]   (기본: templates/)
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:2]
for name in ["make_input", "make_survey", "make_freq"]:
    print(f"== {name}")
    subprocess.run([sys.executable, os.path.join(HERE, f"{name}.py"), *args], check=True)
