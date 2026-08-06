"""Step 6: Haiku→Sonnet escalation classifier + per-month result cache.

Escalation policy (design doc 3.1):
  1st try: Haiku — cheap, handles the common case
  -> schema validation failure, or any section confidence below threshold
  2nd try: Sonnet — judgment-needed cases only
  -> still failing: raise NeedsHumanReview (never silently accept a bad
     classification just to avoid escalating — design doc principle 4:
     no "느낌" acceptance, only numeric confidence gates the retry)

Caching: ai_results/<month>.json, keyed by a hash of (prompt_version +
raw_text) so editing the prompt/schema/few-shot doesn't silently serve a
stale result — only an unchanged input for an unchanged prompt is a cache
hit. ai_results/ is gitignored (regenerable, and shouldn't carry API
output into version control).
"""
import hashlib
import json
import os
from dataclasses import dataclass, asdict

from schemas.classification_schema import ClassificationOutput
from schemas.few_shot_examples import FEW_SHOT_EXAMPLES
from tools.ai_client import classify, HAIKU_MODEL, SONNET_MODEL, ClassificationError

PROMPT_VERSION = "v2"  # v2: added [이미지있음] image-presence marker (grid vs text_list fix)
CONFIDENCE_THRESHOLD = 0.7
CACHE_DIR = "ai_results"

SYSTEM_PROMPT = """\
너는 게임 배틀패스 기획서의 "특별 보상 미리보기" 구간 원문을 읽고, 그 안의 각 하위
섹션을 아래 5개 블록타입 중 하나로 분류하고 항목을 뽑아내는 역할만 한다.

블록타입 정의:
- grid: 아이콘/이미지 여러 개 + 캡션, N열 그리드 (소형/대형 이미지 크기는 무관)
- text_list: 이미지 없이 이름만 나열, 보통 3열
- new_highlight: 이름에 "(new)"/"(new!)" 마커가 붙은 항목 1~2개 + 나머지는 평범한 목록
- few_preview: 항목 1~3개, 큰 이미지 프리뷰 성격
- paired_columns: 정확히 세트 2개를 비교하고 "···중 택 1" 같은 각주가 붙는 구조

입력의 각 줄 끝에 "[이미지있음]"이 붙어있으면 그 행에 실제 이미지가 있다는 뜻이다
(원본 엑셀에 삽입된 그림 기준, 추측 아님). 이게 있는 섹션은 grid/few_preview/
new_highlight/paired_columns 중 하나여야 하고, 이미지가 하나도 없는 섹션만
text_list일 수 있다. "[이미지있음]" 마커 없이 이름만 나열된 걸 보고 grid로
판단하지 마라 — 이미지 유무는 반드시 이 마커로만 판단해라, 이름 느낌으로 추측하지 마라.

절대 원칙:
- 좌표/이미지 매칭은 네 역할이 아니다. 오직 텍스트 분류 + 항목 추출만 한다.
- 원문에 없는 항목을 지어내지 마라. 원문 이름을 그대로 옮겨라 (오타 포함).
- 하나의 입력에 여러 섹션(예: "기간제 패키지"와 "배틀패스 의상 교환권")이 섞여 있으면
  섹션별로 각각 분류해라. 섹션 구분은 볼드/헤더처럼 보이는 짧은 제목 줄로 판단한다.
- confidence는 네가 이 분류에 얼마나 확신하는지 0~1로 정직하게 적어라. 애매하면
  낮게 적어라 — 낮은 confidence는 상위 모델 재검토로 이어질 뿐, 감점이 아니다.
"""


@dataclass
class ClassifyResult:
    month: str
    output: ClassificationOutput
    model_used: str
    from_cache: bool


class NeedsHumanReview(Exception):
    def __init__(self, month: str, reason: str, raw_text: str):
        super().__init__(f"{month}: {reason}")
        self.month = month
        self.reason = reason
        self.raw_text = raw_text


def _cache_key(raw_text: str) -> str:
    return hashlib.sha256((PROMPT_VERSION + raw_text).encode("utf-8")).hexdigest()[:16]


def _cache_path(month: str) -> str:
    return os.path.join(CACHE_DIR, f"{month}.json")


def _load_cache(month: str, key: str) -> ClassificationOutput | None:
    path = _cache_path(month)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        cached = json.load(f)
    if cached.get("cache_key") != key:
        return None
    return ClassificationOutput.model_validate(cached["output"]), cached["model_used"]


def _save_cache(month: str, key: str, output: ClassificationOutput, model_used: str) -> None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_cache_path(month), "w", encoding="utf-8") as f:
        json.dump(
            {"cache_key": key, "model_used": model_used, "output": output.model_dump()},
            f, ensure_ascii=False, indent=2,
        )


def _is_confident(output: ClassificationOutput) -> bool:
    return all(s.confidence >= CONFIDENCE_THRESHOLD for s in output.sections) if output.sections else False


def _build_user_prompt(raw_text: str) -> str:
    return f"{FEW_SHOT_EXAMPLES}\n---\n이제 아래 입력을 같은 형식으로 분류해라:\n\n{raw_text}"


def classify_month(month: str, raw_text: str, force_refresh: bool = False) -> ClassifyResult:
    key = _cache_key(raw_text)

    if not force_refresh:
        cached = _load_cache(month, key)
        if cached is not None:
            output, model_used = cached
            return ClassifyResult(month, output, model_used, from_cache=True)

    user_prompt = _build_user_prompt(raw_text)

    try:
        output = classify(SYSTEM_PROMPT, user_prompt, ClassificationOutput, HAIKU_MODEL)
        if _is_confident(output):
            _save_cache(month, key, output, HAIKU_MODEL)
            return ClassifyResult(month, output, HAIKU_MODEL, from_cache=False)
    except ClassificationError:
        output = None

    try:
        output = classify(SYSTEM_PROMPT, user_prompt, ClassificationOutput, SONNET_MODEL)
        if _is_confident(output):
            _save_cache(month, key, output, SONNET_MODEL)
            return ClassifyResult(month, output, SONNET_MODEL, from_cache=False)
    except ClassificationError as e:
        raise NeedsHumanReview(month, f"Sonnet also failed schema validation: {e}", raw_text) from e

    low_conf = [s.section_title for s in output.sections if s.confidence < CONFIDENCE_THRESHOLD]
    raise NeedsHumanReview(
        month, f"Sonnet confidence still below {CONFIDENCE_THRESHOLD} for: {low_conf}", raw_text
    )
