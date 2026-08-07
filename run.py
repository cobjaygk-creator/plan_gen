"""Entry point: request.xlsx 하나를 넣으면 실제 .pptx가 나온다.

사용법:
    .venv\\Scripts\\python.exe run.py samples/202605_request.xlsx
    .venv\\Scripts\\python.exe run.py samples/202605_request.xlsx --out out/custom.pptx

내부적으로 하는 일 (design doc 파이프라인 그대로):
    고정 필드 파싱 -> 특별보상 원문 추출 -> AI 분류(Haiku/Sonnet) -> 위치 기반
    이미지 매칭 -> 블록 엔진 레이아웃 -> .pptx 렌더링
AI 분류 단계에서 실제 Anthropic API 호출이 발생한다 (.env의 ANTHROPIC_API_KEY 필요).
"""
import argparse
import os
import re
import sys
from datetime import datetime

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from tools.parse_fixed_fields import parse_fixed_fields
from tools.pipeline import process_month, summarize
from tools.render_pptx import render_pptx
from tools.render_from_template import render_from_template
from tools.classify_month import NeedsHumanReview

TEMPLATE_PATH = "samples/template.pptx"


def _guess_month(request_path: str) -> str:
    basename = os.path.basename(request_path)
    m = re.match(r"(\d{6})", basename)
    return m.group(1) if m else "output"


def main():
    parser = argparse.ArgumentParser(description="request.xlsx -> 배틀패스 SB .pptx 자동 생성")
    parser.add_argument("request_path", help="request.xlsx 경로")
    parser.add_argument("--out", help="출력 .pptx 경로 (기본: out/<월>/gen_<날짜>_<시분>.pptx)")
    parser.add_argument("--images", help="이미지 저장 폴더 (기본: out/<월>/images)")
    parser.add_argument("--template", default=TEMPLATE_PATH, help=f"기준 template.pptx 경로 (기본: {TEMPLATE_PATH})")
    parser.add_argument("--no-template", action="store_true",
                         help="template.pptx 없이 처음부터 슬라이드 생성 (구 방식)")
    args = parser.parse_args()

    if not os.path.exists(args.request_path):
        print(f"파일을 찾을 수 없습니다: {args.request_path}")
        sys.exit(1)

    month = _guess_month(args.request_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_path = args.out or f"out/{month}/gen_{timestamp}.pptx"
    image_dir = args.images or f"out/{month}/images"

    print(f"[1/4] 고정 필드 파싱 중... ({args.request_path})")
    fixed = parse_fixed_fields(args.request_path)
    print(f"      제목: {' / '.join(fixed['title_lines'])}")
    print(f"      기간: {fixed['period']}")

    print("[2/4] AI 분류 + 이미지 매칭 중... (Anthropic API 호출 발생)")
    try:
        result = process_month(month, args.request_path, image_out_dir=image_dir)
    except NeedsHumanReview as e:
        print(f"\n[중단] AI가 이 요청서를 확신 있게 분류하지 못했습니다: {e.reason}")
        print("사람이 원문을 직접 확인해야 합니다. .pptx는 생성되지 않았습니다.")
        sys.exit(2)

    if result.needs_human_review:
        print(f"\n[중단] {result.needs_human_review}")
        print(".pptx는 생성되지 않았습니다.")
        sys.exit(2)

    print("[3/4] 결과 요약:")
    for line in summarize(result).splitlines():
        print("      " + line)

    use_template = not args.no_template and os.path.exists(args.template)
    print(f"[4/4] .pptx 렌더링 중... -> {out_path}"
          + (f" (template.pptx 마커 기반: {args.template})" if use_template else " (템플릿 없이 새로 생성)"))
    if use_template:
        render_from_template(fixed, result, args.template, out_path)
    else:
        render_pptx(fixed, result, out_path)

    print(f"\n완료: {out_path}")


if __name__ == "__main__":
    main()
