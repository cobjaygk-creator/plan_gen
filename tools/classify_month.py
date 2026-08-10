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

from schemas.classification_schema import ClassificationOutput, Section
from schemas.few_shot_examples import FEW_SHOT_EXAMPLES
from tools.ai_client import classify, HAIKU_MODEL, SONNET_MODEL, ClassificationError

PROMPT_VERSION = "v7"  # v7: icon_only block type for images with no item names at all
CONFIDENCE_THRESHOLD = 0.7
CACHE_DIR = "ai_results"

SYSTEM_PROMPT = """\
너는 게임 배틀패스 기획서의 "특별 보상 미리보기" 구간 원문을 읽고, 그 안의 각 하위
섹션을 아래 6개 블록타입 중 하나로 분류하고 항목을 뽑아내는 역할만 한다.

블록타입 정의:
- grid: 아이콘/이미지 여러 개 + 캡션, N열 그리드 (소형/대형 이미지 크기는 무관).
  일부 항목에 "(new)"/"(new!)" 마커나 별도의 "NEW!" 행이 붙어 있어도 grid다 —
  NEW 항목은 다른 항목과 같은 칸에 들어가고 배지만 붙을 뿐, 별도 레이아웃이 아니다.
- text_list: 이미지 없이 이름만 나열, 보통 3열
- new_highlight: grid와 렌더링은 동일하지만 "신규 항목이 있다"는 의미를 구분하고
  싶을 때 쓴다 — is_new=true 항목이 있는 grid류 섹션에 사용해도 되고, 굳이
  구분 안 되면 grid로 분류해도 무방하다 (렌더러가 동일하게 처리함)
- few_preview: 항목 1~3개, 큰 이미지 프리뷰 성격
- paired_columns: 핵심은 정확히 2개의 **최상위 선택지**가 있고, 그 외 항목은 전부 그 2개
  중 하나에 속하는 하위 구성 요소라는 것이다. 이걸 판단할 때 **표면적 형식(슬래시로
  병기됐는지, 한 줄에 몇 열인지 등)에 얽매이지 말고 의미로 판단해라** — 최상위 선택지
  2개가 어떻게 적혀 있는지는 매번 다를 수 있다:
    · 한 셀에 "A 세트 / B 세트"처럼 슬래시로 병기된 경우도 있고,
    · 다른 하위 구성품 행들과 똑같이 생긴 2열 행(예: "CD28: 의상 세트 l | 의상 세트 ll")에
      적혀 있는 경우도 있다 — 이때 다른 행들과 형식이 같다고 전부 같은 레벨로 취급하지 마라.
  판단 근거: 각주나 안내문에 "···중 택 1"/"···중 하나" 같은 문구가 있으면, 그 문구가
  가리키는 명사(예: "패션 세트", "의상 세트")와 이름이 일치하거나 그 명사를 포함하는
  항목이 최상위 선택지다. 나머지 항목(예: 모자/상의/바지/신발처럼 구성품 하나하나를
  가리키는 이름)은 그 선택지 중 어느 쪽에 속하는지 보고 하위 구성품으로 분류한다.
  최상위 선택지 2개를 찾으면 items에 pair_group=null로 넣고(이게 pair_items가 됨), 각
  하위 구성품은 소속에 따라 pair_group=0(첫 번째) 또는 pair_group=1(두 번째)을 붙인다.
  하위 구성품이 전혀 없는 단순 비교(세트 2개만 있고 "···중 택 1" 각주만 붙은 경우)라면
  pair_group은 전부 null로 둔다. **하위 구성품을 그냥 flat하게 grid로 뽑거나, 최상위
  선택지 자체를 하위 구성품과 같은 레벨로 섞어 넣지 마라** — 세트별 목록이라는 구조
  정보를 pair_group으로 반드시 남겨야 한다.
  **최상위 선택지가 정확히 2개인지 스스로 확인해라.** 아무리 찾아도 정확히 2개가 안
  나오면(0개, 1개, 3개 이상) 이 섹션의 confidence를 반드시 낮게 적어서 사람이
  재검토하게 해라 — 애매한 채로 pair_group을 억지로 채우지 마라.
- icon_only: 제목/각주 뒤에 항목 이름이 하나도 없이, "42:  [이미지있음]"처럼 **행 번호와
  마커만 있고 그 앞에 텍스트가 전혀 없는 줄**이 이어지는 경우다. 이건 이름표 없이
  이미지만으로 고르는 선택지 그룹이라는 뜻이다 (예: 아이콘 여러 개를 합쳐놓은 그림 하나로
  보여주는 경우). 이때 items는 반드시 빈 배열 []로 둬라 — 지어낼 이름이 없다. 좌표/이미지
  배치는 코드가 알아서 하니 너는 "이 섹션엔 이름 없는 이미지만 있다"는 것만 표시하면 된다.

입력의 각 줄 끝에 "[이미지있음]"이 붙어있으면 그 행에 실제 이미지가 있다는 뜻이다
(원본 엑셀에 삽입된 그림 기준, 추측 아님). 이게 있는 섹션은 grid/few_preview/
new_highlight/paired_columns/icon_only 중 하나여야 하고, 이미지가 하나도 없는 섹션만
text_list일 수 있다. "[이미지있음]" 마커 없이 이름만 나열된 걸 보고 grid로
판단하지 마라 — 이미지 유무는 반드시 이 마커로만 판단해라, 이름 느낌으로 추측하지 마라.
grid 등 다른 타입과 icon_only의 차이는 "항목 이름이 있는지"다 — 이름 있는 항목들이
이미지와 함께 나열되면 grid, 이름 자체가 아예 없으면 icon_only다.

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
- **같은 이름이 서로 다른 행에 여러 번 나오면, 그건 실수로 중복 입력된 게 아니라
  같은 이름을 쓰는 별개의 항목(수량/파츠가 다름)일 가능성이 높다 — 임의로 하나로
  합치지 말고 원문에 나온 행 개수 그대로 items에 각각 넣어라.** 판단 근거가 되는
  각주(예: "OOO은 착용 파츠가 다른 N종이 지급됩니다")가 있으면 그게 명확한 신호다.
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


def _is_structurally_valid(section: Section) -> bool:
    """paired_columns_block hard-requires exactly 2 pair_group=None items
    (see tools/blocks/paired_columns.py) — if the model's pair_group
    tagging doesn't produce exactly 2, the section is guaranteed to blow
    up at render time and get silently dropped from the final .pptx
    (render_error sections are skipped, not fatal). Catch that here so it
    counts as "not confident" and escalates/asks for human review instead
    of quietly shipping a deck with missing content (real case: 202503
    "버니버니 의상 선택권" came back with 0 pair_group=None items)."""
    if section.block_type != "paired_columns":
        return True
    return sum(1 for i in section.items if i.pair_group is None) == 2


def _is_confident(output: ClassificationOutput) -> bool:
    if not output.sections:
        return False
    return all(
        s.confidence >= CONFIDENCE_THRESHOLD and _is_structurally_valid(s)
        for s in output.sections
    )


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
    structurally_bad = [s.section_title for s in output.sections if not _is_structurally_valid(s)]
    reasons = []
    if low_conf:
        reasons.append(f"confidence still below {CONFIDENCE_THRESHOLD} for: {low_conf}")
    if structurally_bad:
        reasons.append(f"paired_columns didn't resolve to exactly 2 top-level items for: {structurally_bad}")
    raise NeedsHumanReview(month, f"Sonnet also not usable — {'; '.join(reasons)}", raw_text)
