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

PROMPT_VERSION = "v4"  # v4: paired_columns pair_group tagging for per-set sub-item lists
CONFIDENCE_THRESHOLD = 0.7
CACHE_DIR = "ai_results"

SYSTEM_PROMPT = """\
너는 게임 배틀패스 기획서의 "특별 보상 미리보기" 구간 원문을 읽고, 그 안의 각 하위
섹션을 아래 5개 블록타입 중 하나로 분류하고 항목을 뽑아내는 역할만 한다.

블록타입 정의:
- grid: 아이콘/이미지 여러 개 + 캡션, N열 그리드 (소형/대형 이미지 크기는 무관).
  일부 항목에 "(new)"/"(new!)" 마커나 별도의 "NEW!" 행이 붙어 있어도 grid다 —
  NEW 항목은 다른 항목과 같은 칸에 들어가고 배지만 붙을 뿐, 별도 레이아웃이 아니다.
- text_list: 이미지 없이 이름만 나열, 보통 3열
- new_highlight: grid와 렌더링은 동일하지만 "신규 항목이 있다"는 의미를 구분하고
  싶을 때 쓴다 — is_new=true 항목이 있는 grid류 섹션에 사용해도 되고, 굳이
  구분 안 되면 grid로 분류해도 무방하다 (렌더러가 동일하게 처리함)
- few_preview: 항목 1~3개, 큰 이미지 프리뷰 성격
- paired_columns: 정확히 세트 2개를 비교하는 구조. 두 가지 실제 패턴이 있다:
  (a) "···중 택 1" 각주가 붙고 세트 2개만 있는 단순한 경우
  (b) 세트 이름 2개가 "A 세트 / B 세트"처럼 한 줄에 슬래시로 나란히 적혀 있고, 그
      아래 여러 행에 걸쳐 두 열(예: B열, D열)에 각 세트의 하위 구성품이 나란히
      나열되는 경우 — "···중 택 1" 문구가 없어도 이 구조면 paired_columns다.
      이때 세트 이름 2개는 items에 pair_group=null로 넣고(이게 pair_items가 됨),
      각 하위 구성품은 어느 세트 소속인지에 따라 pair_group=0(첫 세트, 보통 왼쪽 열)
      또는 pair_group=1(둘째 세트, 보통 오른쪽 열)을 붙인다. 하위 구성품이 없으면
      pair_group은 전부 null로 둔다 (기존 단순 paired_columns와 동일하게 처리됨).
      **하위 구성품 15개를 그냥 flat하게 grid로 뽑지 마라** — 두 세트 밑에 각각
      딸린 목록이라는 구조 정보를 pair_group으로 반드시 남겨야 한다.

입력의 각 줄 끝에 "[이미지있음]"이 붙어있으면 그 행에 실제 이미지가 있다는 뜻이다
(원본 엑셀에 삽입된 그림 기준, 추측 아님). 이게 있는 섹션은 grid/few_preview/
new_highlight/paired_columns 중 하나여야 하고, 이미지가 하나도 없는 섹션만
text_list일 수 있다. "[이미지있음]" 마커 없이 이름만 나열된 걸 보고 grid로
판단하지 마라 — 이미지 유무는 반드시 이 마커로만 판단해라, 이름 느낌으로 추측하지 마라.

**"NEW!"/"이미지 추후 전달 예정" 같은 문구가 이름 옆이 아니라 완전히 독립된 한 줄로
나오면, 그건 그 줄 다음(아래)에 나오는 같은 열(B/C/D)의 항목을 가리키는 것이다 —
바로 위에 나온 항목이 아니다.** 예를 들어 "D49: NEW!" 다음에 "D50: 이미지 추후
전달 예정"이 나오고 그 다음 "CD52: 항목A | 항목B"가 나오면, D열의 항목B가 신규
항목이고 아직 이미지가 없는 것이지 그 앞에 나온 항목이 신규인 게 아니다. 헷갈리면
"이미지 추후 전달 예정"이라는 문구가 있었다는 걸 근거로 그 항목의 is_new를
true로, 그리고 confidence를 낮춰서 사람이 재확인하게 해라.

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


MALFORMED_RETRY_ATTEMPTS = 2  # observed ~2/3 per-call success rate on malformed-
                              # response cases (double-nested JSON quirk) even with
                              # an unchanged prompt/input — Sonnet doesn't support a
                              # temperature pin to reduce this, so retry the same
                              # tier before escalating/giving up, since a schema
                              # error is a formatting fluke, not a judgment call
                              # (unlike low confidence, which is never retried).


def _classify_with_retry(system_prompt, user_prompt, model, attempts=MALFORMED_RETRY_ATTEMPTS):
    last_error = None
    for _ in range(attempts):
        try:
            return classify(system_prompt, user_prompt, ClassificationOutput, model)
        except ClassificationError as e:
            last_error = e
    raise last_error


def classify_month(month: str, raw_text: str, force_refresh: bool = False) -> ClassifyResult:
    key = _cache_key(raw_text)

    if not force_refresh:
        cached = _load_cache(month, key)
        if cached is not None:
            output, model_used = cached
            return ClassifyResult(month, output, model_used, from_cache=True)

    user_prompt = _build_user_prompt(raw_text)

    try:
        output = _classify_with_retry(SYSTEM_PROMPT, user_prompt, HAIKU_MODEL)
        if _is_confident(output):
            _save_cache(month, key, output, HAIKU_MODEL)
            return ClassifyResult(month, output, HAIKU_MODEL, from_cache=False)
    except ClassificationError:
        output = None

    try:
        output = _classify_with_retry(SYSTEM_PROMPT, user_prompt, SONNET_MODEL)
        if _is_confident(output):
            _save_cache(month, key, output, SONNET_MODEL)
            return ClassifyResult(month, output, SONNET_MODEL, from_cache=False)
    except ClassificationError as e:
        raise NeedsHumanReview(month, f"Sonnet also failed schema validation: {e}", raw_text) from e

    low_conf = [s.section_title for s in output.sections if s.confidence < CONFIDENCE_THRESHOLD]
    raise NeedsHumanReview(
        month, f"Sonnet confidence still below {CONFIDENCE_THRESHOLD} for: {low_conf}", raw_text
    )
