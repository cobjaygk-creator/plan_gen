"""Source list (design doc section 20/21) — kept small and manually
verified rather than exhaustive, per "관리 가능한 수준으로 제한". Each
entry's feed_url was checked by hand (real HTTP 200 + rss/xml content-type)
before being added here; don't add a source without doing the same.

Sources that return slightly malformed metadata are allowed only when the
production parser still receives a successful response with real entries.
디스이즈게임 remains excluded because all verified candidates returned 404."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    name: str
    feed_url: str
    category: str  # "GAME" | "AI"
    source_type: str  # "media" | "official"


SOURCES: list[Source] = [
    # GAME
    Source("GamesIndustry.biz", "https://www.gamesindustry.biz/feed", "GAME", "media"),
    Source("PC Gamer", "https://www.pcgamer.com/rss/", "GAME", "media"),
    Source("인벤", "https://webzine.inven.co.kr/news/rss.php", "GAME", "media"),
    Source("게임메카", "https://www.gamemeca.com/rss.php", "GAME", "media"),
    # AI
    Source("삼성전자 뉴스룸", "https://news.samsung.com/kr/feed/rss", "AI", "official"),
    Source("OpenAI", "https://openai.com/news/rss.xml", "AI", "official"),
    Source("Microsoft", "https://blogs.microsoft.com/feed/", "AI", "official"),
    Source("NVIDIA", "https://blogs.nvidia.com/feed/", "AI", "official"),
    Source("TechCrunch", "https://techcrunch.com/feed/", "AI", "media"),
    Source("The Verge", "https://www.theverge.com/rss/index.xml", "AI", "media"),
    Source("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "AI", "media"),
    Source("AI타임스", "https://www.aitimes.com/rss/allArticle.xml", "AI", "media"),
    Source("전자신문 AI", "http://rss.etnews.com/04046.xml", "AI", "media"),
]


# Pending articles from these outlets are classified first so a small manual
# batch still produces a Korea-focused brief. This affects Industry Brief only.
KOREAN_SOURCE_NAMES: tuple[str, ...] = (
    "인벤",
    "게임메카",
    "크래프톤",
    "넥슨게임즈",
    "넷마블",
    "삼성전자 뉴스룸",
    "AI타임스",
    "전자신문 AI",
    "한국콘텐츠진흥원",
    "문화체육관광부",
    "대한민국 정책브리핑",
    "게임물관리위원회",
)

NAVER_SOURCE_PREFIX = "NAVER · "


def is_korean_source(source_name: str) -> bool:
    """NAVER News is a Korean discovery source even though its publisher varies."""
    return source_name in KOREAN_SOURCE_NAMES or source_name.startswith(NAVER_SOURCE_PREFIX)


# 게임 전업 퍼블리셔/개발사 — 카카오·네이버·삼성전자처럼 게임 사업부가
# 있을 뿐인 대기업은 일부러 뺐다(그런 곳의 AI 뉴스까지 걸러내면 과도함).
# "AI로 게임 만든다" 류 기사처럼, AI 카테고리로 분류돼 있어도 실제로는
# 게임회사가 주인공인 기사를 판별하는 데 쓴다 — routes.py의 차트 라벨
# 후보 제외, tech_radar.py의 기술 레이더 노출 제외 두 곳에서 공유한다.
GAME_COMPANY_NAMES: tuple[str, ...] = (
    "넥슨", "넷마블", "크래프톤", "엔씨소프트", "엔씨", "카카오게임즈", "위메이드",
    "펄어비스", "스마일게이트", "컴투스", "데브시스터즈", "시프트업", "그라비티",
    "네오위즈",
)
