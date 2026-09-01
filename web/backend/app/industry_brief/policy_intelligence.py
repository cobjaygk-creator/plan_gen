"""Fact-first policy cards derived only from official-source article text."""
from datetime import date, datetime
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Article

POLICY_TITLE_TERMS = (
    "정책", "규제", "법률", "법안", "시행령", "개정", "의무", "금지",
    "펀드", "예산", "지원사업", "지원 사업", "공모", "모집",
    "가이드라인", "제도", "협약", "인재양성", "인재 양성",
    "단속", "근절", "위반", "피해구제", "불법", "행정지도", "사후관리",
)
POLICY_SOURCES = (
    "문화체육관광부",
    "한국콘텐츠진흥원",
    "대한민국 정책브리핑",
    "게임물관리위원회",
)
TARGET_TERMS = ("대상", "기업", "사업자", "이용자", "청소년", "개발사", "게임사", "종사자", "창작자", "학생", "선수", "참가자")
ACTION_TERMS = ("시행", "지원", "확대", "개정", "의무", "금지", "조성", "투자", "도입", "개최", "운영", "추진", "체결", "공개")
DATE_PATTERN = re.compile(r"(20\d{2}년\s*\d{1,2}월(?:\s*\d{1,2}일)?(?:부터|까지)?|\d{1,2}월\s*\d{1,2}일(?:부터|까지)?|오는\s*\d{1,2}월(?:\s*\d{1,2}일)?)")


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    return [part.strip(" -·") for part in re.split(r"(?<=[.!?다])\s+|\s*[□■◆▶▷○●]\s*", normalized) if len(part.strip()) >= 12]


def _first_matching(sentences: list[str], terms: tuple[str, ...], fallback: str) -> str:
    for sentence in sentences:
        if any(term in sentence for term in terms):
            return sentence[:220]
    return fallback[:220]


def _policy_type(text: str) -> tuple[str, str]:
    if any(term in text for term in ("단속", "근절", "위반", "불법", "행정지도", "사후관리", "피해구제")):
        return "ENFORCEMENT", "단속·집행"
    if any(term in text for term in ("규제", "의무", "금지", "법률", "법안", "개정")):
        return "REGULATION", "규제 시행"
    if any(term in text for term in ("펀드", "예산", "투자", "지원사업", "지원 사업", "공모", "모집")):
        return "FUNDING", "지원사업"
    if any(term in text for term in ("인재", "교육", "아카데미", "인력")):
        return "TALENT", "인재"
    if any(term in text for term in ("해외", "수출", "글로벌", "진출")):
        return "GLOBAL", "해외 진출"
    if any(term in text for term in ("협약", "협력")):
        return "PARTNERSHIP", "협력"
    return "PROGRAM", "정책·사업"


def _implication(text: str) -> str:
    if any(term in text for term in ("단속", "근절", "위반", "불법", "행정지도", "사후관리", "피해구제")):
        return "단속 대상과 위반 유형을 확인하고 자사 서비스의 운영·표시·신고 대응 절차에 같은 위험이 없는지 점검할 필요가 있습니다."
    if any(term in text for term in ("규제", "의무", "금지", "개정")):
        return "게임사와 플랫폼은 적용 대상과 시행 시점을 확인하고 운영·표시·보호 절차의 변경 여부를 점검할 필요가 있습니다."
    if any(term in text for term in ("펀드", "예산", "투자", "지원사업", "지원 사업", "공모", "모집")):
        return "지원 대상과 신청 조건이 자사 사업에 해당하는지 확인하면 개발·유통·해외 진출 자원으로 활용할 수 있습니다."
    if any(term in text for term in ("인재", "교육", "아카데미")):
        return "관련 인력 확보와 교육 협력 기회가 확대되는지 중장기적으로 살펴볼 필요가 있습니다."
    if any(term in text for term in ("해외", "수출", "글로벌", "진출")):
        return "참여 조건과 대상 시장을 확인해 퍼블리싱·전시·현지화 계획에 활용할 수 있는지 검토할 필요가 있습니다."
    return "공식 사업의 후속 일정과 참여 조건이 구체화되는지 계속 확인할 필요가 있습니다."


def _response_checklist(kind: str) -> list[str]:
    """Return review prompts, not unsupported claims about the company."""
    if kind == "ENFORCEMENT":
        return ["단속·조사 대상과 위반 유형 확인", "운영 기록과 신고·이용자 대응 절차 점검"]
    if kind == "REGULATION":
        return ["적용 대상과 시행일 원문 확인", "표시·운영·보호 절차 변경 필요 여부 점검"]
    if kind == "FUNDING":
        return ["신청 자격·마감·제출 조건 확인", "개발·유통·해외 진출 활용 가능성 검토"]
    if kind == "TALENT":
        return ["참여 대상과 교육 일정 확인", "채용·재교육 계획 연계 가능성 검토"]
    if kind == "GLOBAL":
        return ["대상 국가와 참가 조건 확인", "현지화·퍼블리싱 일정 연계 가능성 검토"]
    if kind == "PARTNERSHIP":
        return ["협력 범위와 후속 사업 확인", "자사 참여 가능 접점 검토"]
    return ["적용 대상과 후속 일정 확인", "자사 업무 영향 여부 검토"]


def _effective_date(value: str | None, published: datetime | None) -> date | None:
    if not value:
        return None
    full = re.search(r"(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일", value)
    if full:
        try:
            return date(*(int(part) for part in full.groups()))
        except ValueError:
            return None
    partial = re.search(r"(\d{1,2})월\s*(\d{1,2})일", value)
    if partial and published:
        try:
            return date(published.year, *(int(part) for part in partial.groups()))
        except ValueError:
            return None
    return None


def _priority(kind: str, effective: date | None, published: datetime | None, reference: date) -> tuple[int, str, str]:
    score = {
        "ENFORCEMENT": 45, "REGULATION": 40, "FUNDING": 25,
        "GLOBAL": 20, "TALENT": 18, "PARTNERSHIP": 15, "PROGRAM": 10,
    }.get(kind, 10)
    urgency = "일정 확인"
    if effective:
        days = (effective - reference).days
        if days == 0:
            score += 50
            urgency = "오늘 시행"
        elif 0 < days <= 7:
            score += 50
            urgency = f"{days}일 후 시행"
        elif 7 < days <= 30:
            score += 30
            urgency = f"{days}일 후 시행"
        elif days < 0:
            score += 15
            urgency = "시행됨"
        else:
            urgency = f"{days}일 후 시행"
    if published and abs((reference - published.date()).days) <= 7:
        score += 10
    label = "긴급 확인" if score >= 80 else "우선 확인" if score >= 50 else "관찰"
    return score, label, urgency


POLICY_TOPICS = (
    ("확률형 아이템", ("확률형",)),
    ("불법 게임물", ("불법게임", "불법 게임", "사설서버", "사행성 게임")),
    ("등급분류", ("등급분류", "등급 분류")),
    ("이용자 피해구제", ("피해구제", "피해 구제")),
    ("게임 지원사업", ("지원사업", "지원 사업")),
    ("게임 인재양성", ("인재양성", "인재 양성")),
)
STAGE_LABELS = {
    "ANNOUNCED": "발표",
    "APPLICATION": "모집·공모",
    "REVISION": "개정",
    "EFFECTIVE": "시행",
    "ENFORCEMENT": "단속·집행",
    "UPDATE": "후속 발표",
}


def _policy_key(title: str) -> str:
    compact = re.sub(r"\s+", "", title.lower())
    for label, terms in POLICY_TOPICS:
        if any(term.replace(" ", "") in compact for term in terms):
            return label
    core = re.sub(
        r"게임물관리위원회|게임위|문화체육관광부|문체부|한국콘텐츠진흥원|"
        r"20\d{2}년도?|발표|추진|시행|개정|확대|강화|개최|체결|모집|공모|관련|위한",
        " ", title,
    )
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", core.lower())[:80] or compact[:80]


def _policy_stage(text: str) -> str:
    if "개정" in text:
        return "REVISION"
    if any(term in text for term in ("단속", "근절", "위반", "행정지도", "점검")):
        return "ENFORCEMENT"
    if any(term in text for term in ("시행", "시행령", "가동", "적용")):
        return "EFFECTIVE"
    if any(term in text for term in ("모집", "공모", "신청")):
        return "APPLICATION"
    if any(term in text for term in ("발표", "계획", "추진")):
        return "ANNOUNCED"
    return "UPDATE"


def _naive(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min
    return value.replace(tzinfo=None) if value.tzinfo else value


def _history_change(stage: str, prior: list[Article]) -> tuple[str, str]:
    if not prior:
        return "NEW", "신규 정책"
    if stage == "REVISION":
        return "REVISION", "기존 정책 개정"
    previous_stage = _policy_stage(prior[0].title)
    if stage != previous_stage and stage in ("EFFECTIVE", "ENFORCEMENT", "APPLICATION"):
        return "STAGE_CHANGE", "시행 단계 변화"
    return "FOLLOW_UP", "후속 발표"


def _evidence_sentence(title: str, summary: str) -> str:
    sentences = _sentences(summary)
    if not sentences:
        return "공식 본문이 첨부파일 또는 이미지로 제공되어 원문에서 확인해야 합니다."
    title_terms = {
        token for token in re.findall(r"[0-9a-zA-Z가-힣]+", title.lower())
        if len(token) >= 2 and token not in ("게임위", "관련", "위한", "추진")
    }
    def score(sentence: str) -> tuple[int, int]:
        matches = sum(1 for term in title_terms if term in sentence.lower())
        policy_matches = sum(1 for term in POLICY_TITLE_TERMS + ACTION_TERMS if term in sentence)
        return matches * 3 + policy_matches, -len(sentence)
    return max(sentences, key=score)[:280]


def _selection_reason(kind_label: str, change_label: str, urgency_label: str, history_count: int) -> str:
    parts = [f"{kind_label} 공식 발표"]
    if urgency_label != "일정 확인":
        parts.append(urgency_label)
    if change_label != "신규 정책":
        parts.append(change_label)
    if history_count:
        parts.append(f"이전 발표 {history_count}건과 연결")
    return " · ".join(parts)


def build_policy_updates(db: Session, period_start: datetime, period_end: datetime, limit: int = 6) -> list[dict]:
    article_time = func.coalesce(Article.published_at, Article.collected_at)
    history_articles = db.execute(
        select(Article).where(
            Article.source.in_(POLICY_SOURCES),
            Article.is_relevant.is_not(False),
            article_time < period_end,
        ).order_by(article_time.desc(), Article.id.desc()).limit(500)
    ).scalars().all()
    history_by_key: dict[str, list[Article]] = {}
    for historical in history_articles:
        if any(term in historical.title for term in POLICY_TITLE_TERMS):
            history_by_key.setdefault(_policy_key(historical.title), []).append(historical)
    # 후보군을 recency 30건으로 먼저 잘라낸 뒤 POLICY_TITLE_TERMS로 걸러내고
    # 있었다 — 고빈도로 올라오는 "대한민국 정책브리핑" 글이 최근 30건을
    # 채워버리면, period_start를 아무리 넓혀도(예: 올해 기준) 그보다 오래된
    # 게임위 발표는 매칭 검사를 받기도 전에 후보군에서 잘려나갔다. 실제
    # 전체 데이터량(수십~백여 건 수준)에 맞춰 넉넉하게 올린다.
    articles = db.execute(
        select(Article).where(
            Article.source.in_(POLICY_SOURCES),
            Article.is_relevant.is_not(False),
            article_time >= period_start,
            article_time < period_end,
        ).order_by(article_time.desc(), Article.id.desc()).limit(300)
    ).scalars().all()
    cards = []
    for article in articles:
        text = f"{article.title}. {article.summary or ''}"
        if not any(term in article.title for term in POLICY_TITLE_TERMS):
            continue
        sentences = _sentences(article.summary or "")
        kind, kind_label = _policy_type(text)
        date_match = DATE_PATTERN.search(article.summary or "")
        published = article.published_at or article.collected_at
        effective_text = date_match.group(0) if date_match else None
        score, priority_label, urgency_label = _priority(
            kind, _effective_date(effective_text, published), published, period_end.date()
        )
        key = _policy_key(article.title)
        prior = [
            item for item in history_by_key.get(key, [])
            if item.id != article.id and _naive(item.published_at or item.collected_at) < _naive(published)
        ]
        change_type, change_label = _history_change(_policy_stage(article.title), prior)
        cards.append({
            "id": str(article.id), "type": kind, "typeLabel": kind_label,
            "title": article.title, "source": article.source, "url": article.url,
            "publishedDate": published.strftime("%Y.%m.%d") if published else "날짜 미상",
            "effectiveDate": effective_text,
            "target": _first_matching(sentences, TARGET_TERMS, "원문에서 구체적인 적용 대상을 추가 확인해야 합니다."),
            "action": _first_matching(sentences, ACTION_TERMS, article.title),
            "implication": _implication(text),
            "responseChecklist": _response_checklist(kind),
            "priorityScore": score,
            "priorityLabel": priority_label,
            "urgencyLabel": urgency_label,
            "policyKey": key,
            "changeType": change_type,
            "changeLabel": change_label,
            "historyCount": len(prior),
            "history": [{
                "title": item.title,
                "url": item.url,
                "publishedDate": (item.published_at or item.collected_at).strftime("%Y.%m.%d"),
                "stageLabel": STAGE_LABELS[_policy_stage(item.title)],
            } for item in prior[:3]],
            "selectionReason": _selection_reason(
                kind_label, change_label, urgency_label, len(prior)
            ),
            "evidenceSentence": _evidence_sentence(article.title, article.summary or ""),
        })
    cards.sort(key=lambda card: (card["priorityScore"], card["publishedDate"]), reverse=True)
    return cards[:limit]
