from types import SimpleNamespace

from app.industry_brief.editorial_ranking import (
    editorial_score,
    has_strong_ai_technical_signal,
    is_core_summary_candidate,
)


def _issue(title: str, summary: str, category: str = "GAME"):
    return SimpleNamespace(category=category, title=title, summary=summary, importance_score=100.0)


def _article(title: str):
    return SimpleNamespace(title=title, entities="[]")


def test_celebrity_gameplay_video_is_not_core_summary_candidate():
    issue = _issue(
        "컴투스 신작 배우 게임 플레이 공개",
        "배우 박지현이 판도라 역할로 게임 플레이 비하인드 영상을 공개했습니다.",
    )
    members = [_article("배우 박지현 게임 플레이 비하인드 공개")]

    assert is_core_summary_candidate(issue, members) is False
    assert editorial_score(issue, members) == 20.0


def test_launch_announcement_remains_core_even_when_actor_is_mentioned():
    issue = _issue(
        "신작 MMORPG 8월 26일 정식 출시",
        "배우가 참여한 홍보 영상과 함께 정식 출시일을 발표했습니다.",
    )
    members = [_article("신작 MMORPG 정식 출시일 발표")]

    assert is_core_summary_candidate(issue, members) is True


def test_merchandise_sellout_is_not_an_industry_core_summary():
    issue = _issue(
        "신작 아트북과 굿즈 완판",
        "일본 코믹마켓 전시를 성료하고 티저 아트북을 완판했습니다.",
    )
    members = [_article("코믹마켓서 신작 굿즈 완판")]

    assert is_core_summary_candidate(issue, members) is False


def test_single_company_ai_adoption_is_not_core_summary_candidate():
    issue = _issue(
        "한미약품 AI 품질관리 시스템 구축",
        "한미약품이 AI를 도입하여 의약품 품질 관리 시스템을 개선하고, 품질보고서를 자동으로 생성하는 체계를 구축하고 있다.",
        category="AI",
    )
    members = [_article("메가존클라우드가 한미약품의 품질보증 업무를 자동화하기 위해 AI 에이전트를 구축했다")]

    assert is_core_summary_candidate(issue, members) is False
    assert editorial_score(issue, members) == 20.0


def test_single_venue_ai_adoption_with_formal_ending_is_filtered():
    # "하였다→했다" 축약형이 "습니다" 존칭형과 결합하면 "도입하"라는
    # 어간 자체가 문자열에 안 남는다 — "도입했습니다"에서도 걸려야 한다.
    issue = _issue(
        "KT위즈파크 AI 안면인식 입장",
        "수원 KT위즈파크가 AI 기술을 활용하여 안면인식 입장과 맞춤 응원 서비스를 도입했습니다.",
        category="AI",
    )
    members = [_article("KT위즈파크, AI 안면인식 입장 서비스 도입")]

    assert is_core_summary_candidate(issue, members) is False


def test_ai_model_launch_remains_core_even_if_a_company_adopts_something():
    issue = _issue(
        "오픈AI GPT-6 아스트라 공개",
        "오픈AI가 새로운 AI 모델 'GPT-6 아스트라'의 발표로 AGI 시대의 도래를 알렸습니다.",
        category="AI",
    )
    members = [_article("오픈AI, GPT-6 아스트라 공개")]

    assert is_core_summary_candidate(issue, members) is True


def test_company_exhibition_pr_without_structural_signal_is_not_core_candidate():
    # 실서비스 사례: 삼성전자 뉴스룸(공식 출처)이 낸 전시회 하이라이트 기사가
    # synthesis_eligible(공식 확인)만으로 진짜 기술 뉴스를 제치고 헤드라인을
    # 차지했다 — 신제품/신기술 발표 같은 구조적 내용이 없으면 걸러야 한다.
    issue = _issue(
        "삼성전자, 디자인 마이애미 서울 2026 전시 하이라이트",
        "삼성전자가 디자인 마이애미 서울 2026 전시에서 AI와 예술의 융합을 통해 인간 중심 디자인 비전을 소개했다.",
        category="AI",
    )
    members = [_article("삼성전자 제품이 아티스트의 상상력과 만났을 때… 전시 하이라이트")]

    assert is_core_summary_candidate(issue, members) is False
    assert editorial_score(issue, members) == 20.0


def test_exhibition_that_also_unveils_new_tech_remains_core():
    issue = _issue(
        "삼성전자, CES 부스에서 신형 온디바이스 AI 모델 공개",
        "삼성전자가 이번 전시 부스에서 새로운 온디바이스 AI 모델을 공개했다.",
        category="AI",
    )
    members = [_article("삼성전자, CES 전시에서 신형 AI 모델 공개")]

    assert is_core_summary_candidate(issue, members) is True


def test_established_media_technical_scoop_has_strong_signal():
    issue = _issue(
        "젠슨 황, GPU 10만개로 오픈AI 최신 모델 학습",
        "젠슨 황이 엔비디아 GPU 10만개가 오픈AI의 최신 모델 학습에 쓰였다고 밝혔다.",
        category="AI",
    )
    members = [_article("Jensen Huang says 100,000 Nvidia GPUs were used to train OpenAI's latest model")]

    assert has_strong_ai_technical_signal(issue, members, established_media_count=1) is True


def test_single_source_technical_scoop_without_established_media_has_no_strong_signal():
    issue = _issue(
        "젠슨 황, GPU 10만개로 오픈AI 최신 모델 학습",
        "젠슨 황이 엔비디아 GPU 10만개가 오픈AI의 최신 모델 학습에 쓰였다고 밝혔다.",
        category="AI",
    )
    members = [_article("Jensen Huang says 100,000 Nvidia GPUs were used to train OpenAI's latest model")]

    assert has_strong_ai_technical_signal(issue, members, established_media_count=0) is False


def test_established_media_non_technical_story_has_no_strong_signal():
    issue = _issue(
        "AI 업계 관계자 인터뷰",
        "한 AI 스타트업 대표가 회사 문화에 대해 이야기했다.",
        category="AI",
    )
    members = [_article("AI 스타트업 대표 인터뷰")]

    assert has_strong_ai_technical_signal(issue, members, established_media_count=1) is False


def test_has_strong_ai_technical_signal_is_game_scoped_to_ai_only():
    issue = _issue(
        "신작 MMORPG 8월 26일 정식 출시",
        "새로운 게임 엔진과 서버 인프라를 공개했다.",
        category="GAME",
    )
    members = [_article("신작 MMORPG 정식 출시")]

    assert has_strong_ai_technical_signal(issue, members, established_media_count=1) is False
