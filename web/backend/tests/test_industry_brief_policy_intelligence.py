from datetime import datetime, timezone

from app.industry_brief.models import Article
from app.industry_brief.policy_intelligence import build_policy_updates


def test_policy_cards_use_only_relevant_official_articles(db_factory):
    db = db_factory()
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    db.add_all([
        Article(
            source="문화체육관광부", source_type="official", category="GAME",
            title="게임산업 지원 사업 시행", url="https://official.example/policy",
            published_at=now, is_relevant=True,
            summary="게임 개발사를 대상으로 2026년 9월 1일부터 해외 진출 지원 사업을 시행한다.",
        ),
        Article(
            source="일반언론", source_type="media", category="GAME",
            title="게임 규제 보도", url="https://media.example/policy",
            published_at=now, is_relevant=True, summary="관련 정책을 보도했다.",
        ),
        Article(
            source="NVIDIA", source_type="official", category="AI",
            title="AI 개발 지원 사업", url="https://official.example/ai",
            published_at=now, is_relevant=True, summary="개발자를 지원한다.",
        ),
    ])
    db.commit()
    cards = build_policy_updates(
        db,
        datetime(2026, 8, 17, tzinfo=timezone.utc),
        datetime(2026, 8, 19, tzinfo=timezone.utc),
    )
    assert len(cards) == 1
    assert cards[0]["effectiveDate"] == "2026년 9월 1일부터"
    assert cards[0]["urgencyLabel"] == "13일 후 시행"
    assert cards[0]["priorityLabel"] == "우선 확인"
    assert "게임 개발사" in cards[0]["target"]
    assert cards[0]["source"] == "문화체육관광부"
    assert "지원사업 공식 발표" in cards[0]["selectionReason"]
    assert cards[0]["evidenceSentence"] in cards[0]["target"] or "게임 개발사" in cards[0]["evidenceSentence"]


def test_regulation_card_labels_implication_as_required_review(db_factory):
    db = db_factory()
    now = datetime(2026, 8, 18)
    db.add(Article(
        source="문화체육관광부", source_type="official", category="GAME",
        title="게임사업자 표시 의무 개정", url="https://official.example/rule",
        published_at=now, is_relevant=True,
        summary="게임사업자의 확률 표시 의무를 개정하여 9월 1일부터 시행한다.",
    ))
    db.commit()
    card = build_policy_updates(
        db, datetime(2026, 8, 17), datetime(2026, 8, 19),
    )[0]
    assert card["type"] == "REGULATION"
    assert card["typeLabel"] == "규제 시행"
    assert "점검할 필요" in card["implication"]
    assert card["responseChecklist"] == [
        "적용 대상과 시행일 원문 확인",
        "표시·운영·보호 절차 변경 필요 여부 점검",
    ]


def test_enforcement_card_is_separate_from_regulation(db_factory):
    db = db_factory()
    now = datetime(2026, 8, 18)
    db.add(Article(
        source="게임물관리위원회", source_type="official", category="GAME",
        title="불법 사설서버 단속과 이용자 피해구제 시행",
        url="https://official.example/enforcement", published_at=now,
        summary="게임위는 불법 게임물 단속 대상을 확대하고 신고 절차를 운영한다.",
    ))
    db.commit()
    card = build_policy_updates(db, datetime(2026, 8, 17), datetime(2026, 8, 19))[0]
    assert card["type"] == "ENFORCEMENT"
    assert card["typeLabel"] == "단속·집행"
    assert "위반 유형" in card["responseChecklist"][0]


def test_imminent_policy_is_prioritized_above_newer_observation(db_factory):
    db = db_factory()
    db.add_all([
        Article(
            source="문화체육관광부", source_type="official", category="GAME",
            title="게임 인재양성 사업 모집", url="https://official.example/talent",
            published_at=datetime(2026, 8, 18), summary="게임 인재를 모집하고 교육한다.",
        ),
        Article(
            source="게임물관리위원회", source_type="official", category="GAME",
            title="게임사업자 표시 의무 개정", url="https://official.example/imminent",
            published_at=datetime(2026, 8, 17),
            summary="게임사업자 표시 의무를 개정하여 2026년 8월 20일부터 시행한다.",
        ),
    ])
    db.commit()
    cards = build_policy_updates(db, datetime(2026, 8, 16), datetime(2026, 8, 19))
    assert cards[0]["title"] == "게임사업자 표시 의무 개정"
    assert cards[0]["priorityLabel"] == "긴급 확인"
    assert cards[0]["urgencyLabel"] == "1일 후 시행"


def test_policy_history_marks_revision_and_stage_change(db_factory):
    db = db_factory()
    db.add_all([
        Article(
            source="게임물관리위원회", source_type="official", category="GAME",
            title="확률형 아이템 정보 공개 제도 발표", url="https://official.example/old",
            published_at=datetime(2026, 6, 1), summary="확률형 아이템 제도를 발표한다.",
        ),
        Article(
            source="게임물관리위원회", source_type="official", category="GAME",
            title="확률형 아이템 표시 의무 개정", url="https://official.example/new",
            published_at=datetime(2026, 8, 18), summary="표시 의무를 개정한다.",
        ),
    ])
    db.commit()
    card = build_policy_updates(db, datetime(2026, 8, 17), datetime(2026, 8, 19))[0]
    assert card["policyKey"] == "확률형 아이템"
    assert card["changeType"] == "REVISION"
    assert card["changeLabel"] == "기존 정책 개정"
    assert card["historyCount"] == 1
    assert card["history"][0]["stageLabel"] == "발표"


def test_policy_cards_exclude_articles_already_marked_irrelevant(db_factory):
    db = db_factory()
    db.add(Article(
        source="대한민국 정책브리핑", source_type="official", category="AI",
        title="일반 산업 정책 토론회", url="https://official.example/irrelevant",
        published_at=datetime(2026, 8, 18), summary="본문에서 AI를 단순 언급한다.",
        is_relevant=False,
    ))
    db.commit()
    assert build_policy_updates(db, datetime(2026, 8, 17), datetime(2026, 8, 19)) == []


def test_evidence_sentence_is_taken_from_official_summary(db_factory):
    db = db_factory()
    summary = "위원회는 간담회를 개최했다. 게임사업자의 확률형 아이템 표시 의무를 9월부터 시행한다."
    db.add(Article(
        source="게임물관리위원회", source_type="official", category="GAME",
        title="확률형 아이템 표시 의무 시행", url="https://official.example/evidence",
        published_at=datetime(2026, 8, 18), summary=summary,
    ))
    db.commit()
    card = build_policy_updates(db, datetime(2026, 8, 17), datetime(2026, 8, 19))[0]
    assert card["evidenceSentence"] in summary
    assert "확률형 아이템 표시 의무" in card["evidenceSentence"]


def test_policy_card_does_not_treat_event_body_mention_as_policy(db_factory):
    db = db_factory()
    now = datetime(2026, 8, 18)
    db.add(Article(
        source="문화체육관광부", source_type="official", category="GAME",
        title="전국 이스포츠 대회 결선 개최", url="https://official.example/event",
        published_at=now, is_relevant=True,
        summary="게임 진흥 정책에 따라 아마추어 선수를 지원하고 대회를 개최한다.",
    ))
    db.commit()
    assert build_policy_updates(
        db, datetime(2026, 8, 17), datetime(2026, 8, 19),
    ) == []
